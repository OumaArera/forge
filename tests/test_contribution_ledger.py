"""
The two-party confirmation rule and the ledger.

These are the tests that matter most. Everything else on the platform is a
convenience; this is the part that makes a FORGE portfolio worth believing,
so each rule gets a test that fails loudly if somebody relaxes it.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from forge.common.exceptions import DomainRuleViolation, NotEligible
from forge.common.models import ImmutableRecordError
from forge.contributions.models import Attestation, Contribution, Dimension, LedgerEntry
from forge.contributions.services import attest, submit, verify_chain
from forge.projects.services import add_member

pytestmark = pytest.mark.django_db


def make_contribution(project, contributor, **kwargs):
    defaults = {
        "project": project,
        "contributor": contributor,
        "dimension": Dimension.DELIVERY,
        "description": "Built the queue model and its tests.",
        "effort_hours": 12,
        "occurred_on": timezone.localdate(),
    }
    defaults.update(kwargs)
    return Contribution.objects.create(**defaults)


class TestSelfAttestation:
    def test_contributor_cannot_confirm_their_own_work(self, approved_project, peer):
        """Without this rule the platform is a self-service portfolio generator."""
        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = make_contribution(approved_project, peer)
        submit(contribution, actor=peer)

        with pytest.raises(NotEligible) as exc:
            attest(contribution, attestor=peer, confirm=True)
        assert exc.value.code == "self_attestation"

    def test_lead_cannot_confirm_their_own_claim(self, approved_project):
        lead = approved_project.lead
        contribution = make_contribution(approved_project, lead)
        submit(contribution, actor=lead)

        with pytest.raises(NotEligible):
            attest(contribution, attestor=lead, confirm=True)


class TestTwoPartyRule:
    def test_one_confirmation_does_not_settle(self, approved_project, peer):
        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = make_contribution(approved_project, peer)
        submit(contribution, actor=peer)

        attest(contribution, attestor=approved_project.lead, confirm=True)
        contribution.refresh_from_db()

        assert contribution.status == Contribution.Status.SUBMITTED
        assert not LedgerEntry.objects.filter(contribution=contribution).exists()

    def test_lead_and_mentor_together_settle_it(self, approved_project, peer, mentor):
        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = make_contribution(approved_project, peer)
        submit(contribution, actor=peer)

        attest(contribution, attestor=approved_project.lead, confirm=True)
        attest(contribution, attestor=mentor, confirm=True)
        contribution.refresh_from_db()

        assert contribution.status == Contribution.Status.CONFIRMED
        entry = LedgerEntry.objects.get(contribution=contribution)
        assert entry.points > 0
        assert entry.is_intact

    def test_same_person_cannot_supply_both_signatures(self, project, peer, mentor):
        """
        Someone who is both lead and mentor supplies one signature, not two.

        This is the loophole a determined member would look for first.
        """
        from forge.projects.models import ProjectReview, ProjectRole
        from forge.projects.services import review_proposal, submit_for_review

        ProjectRole.objects.create(project=project, title="Dev", description="x")
        submit_for_review(project, actor=project.lead)
        review_proposal(project, reviewer=mentor,
                        decision=ProjectReview.Decision.APPROVED,
                        reasons="Fine.")
        project.refresh_from_db()

        # Make the lead also the mentor.
        project.mentor = project.lead
        project.save(update_fields=["mentor"])

        add_member(project, peer, actor=project.lead)
        contribution = make_contribution(project, peer)
        submit(contribution, actor=peer)

        attest(contribution, attestor=project.lead, confirm=True)
        with pytest.raises(DomainRuleViolation) as exc:
            attest(contribution, attestor=project.lead, confirm=True)
        assert exc.value.code == "capacity_taken"

        contribution.refresh_from_db()
        assert contribution.status == Contribution.Status.SUBMITTED

    def test_a_peer_confirmation_does_not_count_towards_the_two(
        self, approved_project, peer, nurse, mentor
    ):
        add_member(approved_project, peer, actor=approved_project.lead)
        add_member(approved_project, nurse, actor=approved_project.lead)
        contribution = make_contribution(approved_project, peer)
        submit(contribution, actor=peer)

        attest(contribution, attestor=nurse, confirm=True)      # peer
        attest(contribution, attestor=approved_project.lead, confirm=True)
        contribution.refresh_from_db()
        assert contribution.status == Contribution.Status.SUBMITTED

        attest(contribution, attestor=mentor, confirm=True)
        contribution.refresh_from_db()
        assert contribution.status == Contribution.Status.CONFIRMED

    def test_dispute_blocks_settlement_and_requires_a_reason(
        self, approved_project, peer
    ):
        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = make_contribution(approved_project, peer)
        submit(contribution, actor=peer)

        with pytest.raises(DomainRuleViolation):
            attest(contribution, attestor=approved_project.lead, confirm=False)

        attest(contribution, attestor=approved_project.lead, confirm=False,
               note="This describes work that another member did.")
        contribution.refresh_from_db()
        assert contribution.status == Contribution.Status.DISPUTED


class TestImmutability:
    def test_an_attestation_cannot_be_rewritten(self, approved_project, peer):
        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = make_contribution(approved_project, peer)
        submit(contribution, actor=peer)
        attestation = attest(contribution, attestor=approved_project.lead, confirm=True)

        attestation.decision = Attestation.Decision.DISPUTE
        with pytest.raises(ImmutableRecordError):
            attestation.save()

    def test_a_ledger_entry_cannot_be_rewritten_or_deleted(
        self, approved_project, peer, mentor
    ):
        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = make_contribution(approved_project, peer)
        submit(contribution, actor=peer)
        attest(contribution, attestor=approved_project.lead, confirm=True)
        attest(contribution, attestor=mentor, confirm=True)

        entry = LedgerEntry.objects.get(contribution=contribution)
        entry.points = 9999
        with pytest.raises(ImmutableRecordError):
            entry.save()
        with pytest.raises(ImmutableRecordError):
            entry.delete()

    def test_a_confirmed_contribution_cannot_be_withdrawn(
        self, approved_project, peer, mentor
    ):
        from forge.contributions.services import withdraw

        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = make_contribution(approved_project, peer)
        submit(contribution, actor=peer)
        attest(contribution, attestor=approved_project.lead, confirm=True)
        attest(contribution, attestor=mentor, confirm=True)
        contribution.refresh_from_db()

        with pytest.raises(DomainRuleViolation) as exc:
            withdraw(contribution, actor=peer)
        assert exc.value.code == "already_settled"


class TestHashChain:
    def _settle(self, project, contributor, mentor, description):
        contribution = make_contribution(project, contributor, description=description)
        submit(contribution, actor=contributor)
        attest(contribution, attestor=project.lead, confirm=True)
        attest(contribution, attestor=mentor, confirm=True)
        return contribution

    def test_chain_links_and_verifies(self, approved_project, peer, nurse, mentor):
        add_member(approved_project, peer, actor=approved_project.lead)
        add_member(approved_project, nurse, actor=approved_project.lead)

        self._settle(approved_project, peer, mentor, "Wrote the ingest job.")
        self._settle(approved_project, nurse, mentor, "Ran the clinic interviews.")
        self._settle(approved_project, peer, mentor, "Wrote the deployment guide.")

        entries = list(LedgerEntry.objects.order_by("sequence"))
        assert [e.sequence for e in entries] == [1, 2, 3]
        assert entries[0].previous_hash == LedgerEntry.GENESIS_HASH
        assert entries[1].previous_hash == entries[0].entry_hash
        assert entries[2].previous_hash == entries[1].entry_hash

        report = verify_chain()
        assert report["intact"] is True
        assert report["checked"] == 3

    def test_tampering_with_a_settled_entry_is_detected(
        self, approved_project, peer, mentor
    ):
        """
        The whole point of chaining: altering history has to be visible.

        The update below goes around the ORM deliberately, because that is
        what an attacker with database access would do.
        """
        add_member(approved_project, peer, actor=approved_project.lead)
        self._settle(approved_project, peer, mentor, "First.")
        self._settle(approved_project, peer, mentor, "Second.")
        self._settle(approved_project, peer, mentor, "Third.")

        assert verify_chain()["intact"] is True

        LedgerEntry.objects.filter(sequence=1).update(points=500)

        report = verify_chain()
        assert report["intact"] is False
        assert any(p["issue"] == "hash_mismatch" and p["sequence"] == 1
                   for p in report["problems"])

    def test_payload_tampering_is_detected(self, approved_project, peer, mentor):
        add_member(approved_project, peer, actor=approved_project.lead)
        self._settle(approved_project, peer, mentor, "Modest contribution.")

        entry = LedgerEntry.objects.get(sequence=1)
        payload = dict(entry.payload)
        payload["description"] = "Single-handedly built the entire platform."
        LedgerEntry.objects.filter(sequence=1).update(payload=payload)

        assert verify_chain()["intact"] is False


class TestSkillEvidence:
    def test_confirmation_credits_the_skill_it_used(
        self, approved_project, peer, mentor, skill
    ):
        """
        'Evidence before claims' made mechanical.

        Anyone may say they know Django. The portfolio shows whether they
        have ever shipped anything in it.
        """
        from forge.accounts.models import UserSkill

        add_member(approved_project, peer, actor=approved_project.lead)
        declared = UserSkill.objects.create(user=peer, skill=skill)
        assert declared.evidence_count == 0

        contribution = make_contribution(approved_project, peer)
        contribution.skills_used.add(skill)
        submit(contribution, actor=peer)
        attest(contribution, attestor=approved_project.lead, confirm=True)
        attest(contribution, attestor=mentor, confirm=True)

        declared.refresh_from_db()
        assert declared.evidence_count == 1


class TestLeadsOwnContributions:
    """
    A project lead's own work has to be able to settle.

    The lead cannot attest to their own claim, so if the lead capacity stayed
    on the required list their contributions would sit unsettled forever --
    and the person usually doing the most work on a project would accumulate
    nothing. A community lead stands in for the lead's signature instead.
    """

    def test_a_lead_can_settle_their_own_work_via_a_community_lead(
        self, approved_project, mentor, advisor, db
    ):

        lead = approved_project.lead
        community_lead = make_community_lead(advisor)

        contribution = make_contribution(approved_project, lead,
                                         dimension=Dimension.LEADERSHIP)
        submit(contribution, actor=lead)

        attest(contribution, attestor=mentor, confirm=True)
        contribution.refresh_from_db()
        assert contribution.status == Contribution.Status.SUBMITTED

        attest(contribution, attestor=community_lead, confirm=True)
        contribution.refresh_from_db()
        assert contribution.status == Contribution.Status.CONFIRMED
        assert LedgerEntry.objects.filter(contribution=contribution).exists()

    def test_the_lead_still_cannot_sign_their_own(self, approved_project, mentor):
        lead = approved_project.lead
        contribution = make_contribution(approved_project, lead)
        submit(contribution, actor=lead)

        with pytest.raises(NotEligible) as exc:
            attest(contribution, attestor=lead, confirm=True)
        assert exc.value.code == "self_attestation"

    def test_a_mentor_alone_does_not_settle_a_leads_claim(
        self, approved_project, mentor
    ):
        """One signature is never enough, whoever it belongs to."""
        lead = approved_project.lead
        contribution = make_contribution(approved_project, lead)
        submit(contribution, actor=lead)
        attest(contribution, attestor=mentor, confirm=True)

        contribution.refresh_from_db()
        assert contribution.status == Contribution.Status.SUBMITTED
        assert not LedgerEntry.objects.filter(contribution=contribution).exists()


def make_community_lead(granted_by):
    from django.utils import timezone

    from forge.accounts.models import RoleGrant, User

    user = User(email="community.lead@ouk.ac.ke", full_name="Peter Mutua",
                public_slug="peter-mutua", kind=User.Kind.STAFF,
                status=User.Status.ACTIVE, email_verified_at=timezone.now())
    user.set_password("a-long-enough-password")
    user.save()
    RoleGrant.objects.create(user=user, role=RoleGrant.Role.COMMUNITY_LEAD,
                             granted_by=granted_by)
    return User.objects.get(pk=user.pk)
