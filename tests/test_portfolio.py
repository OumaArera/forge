"""
Portfolio assembly, signing and verification.

The signature is what turns "this student says the platform confirmed their
work" into something an employer can check without trusting whoever handed
them the file. These tests hold that property.
"""

from __future__ import annotations

import copy

import pytest
from django.utils import timezone

from forge.contributions.models import Dimension
from forge.contributions.services import attest, submit
from forge.portfolio.services import build_portfolio, issue_signed_export
from forge.portfolio.signing import canonical_json, generate_key_pair, sign, verify
from forge.projects.services import add_member

pytestmark = pytest.mark.django_db


def settle_one(project, contributor, mentor, description="Built the thing."):
    contribution = project.contributions.create(
        contributor=contributor, dimension=Dimension.DELIVERY,
        description=description, occurred_on=timezone.localdate(), effort_hours=10,
    )
    submit(contribution, actor=contributor)
    attest(contribution, attestor=project.lead, confirm=True)
    attest(contribution, attestor=mentor, confirm=True)
    return contribution


class TestPortfolioContents:
    def test_only_confirmed_work_appears(self, approved_project, peer, mentor):
        add_member(approved_project, peer, actor=approved_project.lead)

        settle_one(approved_project, peer, mentor, "Confirmed work.")
        unconfirmed = approved_project.contributions.create(
            contributor=peer, dimension=Dimension.DELIVERY,
            description="Unconfirmed work.", occurred_on=timezone.localdate(),
        )
        submit(unconfirmed, actor=peer)

        portfolio = build_portfolio(peer)
        descriptions = [c["description"] for c in portfolio["contributions"]]
        assert "Confirmed work." in descriptions
        assert "Unconfirmed work." not in descriptions

    def test_each_contribution_names_who_confirmed_it(
        self, approved_project, peer, mentor
    ):
        add_member(approved_project, peer, actor=approved_project.lead)
        settle_one(approved_project, peer, mentor)

        entry = build_portfolio(peer)["contributions"][0]
        capacities = {c["capacity"] for c in entry["confirmed_by"]}
        assert capacities == {"lead", "mentor"}

    def test_the_document_says_it_is_not_a_qualification(
        self, approved_project, peer, mentor
    ):
        """
        The platform awards no academic credit and issues nothing that could
        be mistaken for a University qualification. Every document has to keep
        that true on its face.
        """
        add_member(approved_project, peer, actor=approved_project.lead)
        settle_one(approved_project, peer, mentor)

        note = build_portfolio(peer)["platform"]["note"].lower()
        assert "not" in note and "qualification" in note


class TestSigning:
    def test_a_signature_verifies(self, student):
        document = build_portfolio(student)
        signature, key_id, digest = sign(document)
        assert verify(document, signature) is True
        assert len(digest) == 64
        assert key_id

    def test_altering_one_character_invalidates_the_signature(
        self, approved_project, peer, mentor
    ):
        add_member(approved_project, peer, actor=approved_project.lead)
        settle_one(approved_project, peer, mentor, "Wrote three tests.")

        export = issue_signed_export(peer)
        document = export["portfolio"]
        assert verify(document, export["signature"]["value"]) is True

        tampered = copy.deepcopy(document)
        tampered["contributions"][0]["description"] = "Wrote three hundred tests."
        assert verify(tampered, export["signature"]["value"]) is False

    def test_adding_a_contribution_invalidates_the_signature(self, student):
        export = issue_signed_export(student)
        tampered = copy.deepcopy(export["portfolio"])
        tampered["contributions"].append({
            "sequence": 999, "project": "Something impressive",
            "description": "Invented a new kind of database.",
        })
        assert verify(tampered, export["signature"]["value"]) is False

    def test_a_signature_from_another_key_does_not_verify(self, student):
        document = build_portfolio(student)
        signature, _, _ = sign(document)
        _, someone_elses_public_key = generate_key_pair()
        assert verify(document, signature, someone_elses_public_key) is False

    def test_canonical_json_is_order_independent(self):
        """
        A verifier reproduces these bytes from the document it received. If the
        serialisation were not deterministic, valid documents would fail
        verification for cosmetic reasons.
        """
        assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})

    def test_an_export_is_recorded(self, student):
        from forge.portfolio.models import PortfolioExport

        export = issue_signed_export(student)
        record = PortfolioExport.objects.get(user=student)
        assert record.document_digest == export["signature"]["document_sha256"]
        assert record.signature == export["signature"]["value"]

    def test_export_still_issues_when_no_key_is_configured(self, student, settings):
        """
        Refusing to give a student their own record because of a server
        misconfiguration would be the wrong trade. It is marked unverifiable
        instead.
        """
        settings.PORTFOLIO_SIGNING_KEY = ""
        export = issue_signed_export(student)
        assert export["signature"]["signed"] is False
        assert "NOT signed" in export["signature"]["how_to_verify"]


class TestVerificationEndpoint:
    def test_anyone_may_verify_an_export(self, api, approved_project, peer, mentor):
        add_member(approved_project, peer, actor=approved_project.lead)
        settle_one(approved_project, peer, mentor)
        export = issue_signed_export(peer)

        response = api.post("/api/v1/portfolio/verify/", {
            "portfolio": export["portfolio"],
            "signature": export["signature"]["value"],
        }, format="json")

        assert response.status_code == 200
        assert response.data["signature_valid"] is True
        assert response.data["ledger_head_recognised"] is True

    def test_a_tampered_export_is_rejected(self, api, student):
        export = issue_signed_export(student)
        tampered = copy.deepcopy(export["portfolio"])
        tampered["member"]["display_name"] = "Somebody Else"

        response = api.post("/api/v1/portfolio/verify/", {
            "portfolio": tampered, "signature": export["signature"]["value"],
        }, format="json")

        assert response.status_code == 200
        assert response.data["signature_valid"] is False
        assert "Do not rely on it" in response.data["verdict"]

    def test_the_public_key_is_published(self, api):
        response = api.get("/api/v1/portfolio/verification-key/")
        assert response.status_code == 200
        assert response.data["algorithm"] == "Ed25519"
        assert response.data["public_key"]

    def test_a_public_portfolio_needs_no_account(self, api, student):
        response = api.get(f"/api/v1/portfolio/{student.public_slug}/")
        assert response.status_code == 200
        assert response.data["member"]["display_name"] == student.display_name

    def test_a_private_portfolio_is_not_served(self, api, student):
        student.portfolio_is_public = False
        student.save(update_fields=["portfolio_is_public"])
        response = api.get(f"/api/v1/portfolio/{student.public_slug}/")
        assert response.status_code == 404


class TestCertificates:
    def test_a_certificate_needs_evidence_behind_it(self, student, project):
        from forge.common.exceptions import DomainRuleViolation
        from forge.recognition.models import Certificate
        from forge.recognition.services import issue_certificate

        with pytest.raises(DomainRuleViolation) as exc:
            issue_certificate(user=student, kind=Certificate.Kind.PARTICIPATION,
                              project=project)
        assert exc.value.code == "no_evidence"

    def test_a_certificate_can_be_verified_without_an_account(
        self, api, approved_project, peer, mentor
    ):
        from forge.recognition.models import Certificate
        from forge.recognition.services import issue_certificate

        add_member(approved_project, peer, actor=approved_project.lead)
        settle_one(approved_project, peer, mentor)
        certificate = issue_certificate(user=peer,
                                        kind=Certificate.Kind.PARTICIPATION,
                                        project=approved_project)

        response = api.get(
            f"/api/v1/recognition/certificates/verify/{certificate.verification_code}/")
        assert response.status_code == 200
        assert response.data["valid"] is True
        assert response.data["recipient_name"] == peer.display_name
        assert "not a qualification" in response.data["note"]

    def test_a_revoked_certificate_reports_as_invalid(
        self, api, approved_project, peer, mentor, advisor
    ):
        from forge.recognition.models import Certificate
        from forge.recognition.services import issue_certificate, revoke_certificate

        add_member(approved_project, peer, actor=approved_project.lead)
        settle_one(approved_project, peer, mentor)
        certificate = issue_certificate(user=peer,
                                        kind=Certificate.Kind.PARTICIPATION,
                                        project=approved_project)
        revoke_certificate(certificate, actor=advisor,
                           reason="Issued against a disputed contribution.")

        response = api.get(
            f"/api/v1/recognition/certificates/verify/{certificate.verification_code}/")
        assert response.data["valid"] is False
        assert response.data["revoked_reason"]

    def test_an_unknown_code_is_not_found(self, api):
        response = api.get("/api/v1/recognition/certificates/verify/XXXX-XXXX-XXXX/")
        assert response.status_code == 404
        assert response.data["valid"] is False


class TestCertificatePDF:
    """
    The PDF a member actually hands to an employer.

    Three properties matter: it renders at all, it is fetchable by whoever
    holds the code rather than only by its owner, and it never claims to be an
    academic award.
    """

    def _issue(self, approved_project, peer, mentor):
        from forge.recognition.models import Certificate
        from forge.recognition.services import issue_certificate

        add_member(approved_project, peer, actor=approved_project.lead)
        settle_one(approved_project, peer, mentor)
        return issue_certificate(user=peer, kind=Certificate.Kind.PARTICIPATION,
                                 project=approved_project)

    def test_it_renders(self, approved_project, peer, mentor):
        from forge.recognition.pdf import render_certificate

        certificate = self._issue(approved_project, peer, mentor)
        pdf = render_certificate(certificate)

        assert pdf.startswith(b"%PDF-")
        assert pdf.rstrip().endswith(b"%%EOF")
        assert len(pdf) > 1500

    def test_the_name_and_code_are_drawn_as_outlines(
        self, approved_project, peer, mentor
    ):
        """
        They appear on the page but not in the text layer.

        Checked by drawing two certificates that differ only in the holder's
        name: if the name were absent from the page the files would be
        identical, and if it were text it would show up in `pdf_text`.
        """
        certificate = self._issue(approved_project, peer, mentor)
        text = pdf_text(certificate)
        assert peer.display_name not in text

        from forge.recognition.pdf import render_certificate

        before = render_certificate(certificate)
        certificate.recipient_name = "Somebody Else Entirely"
        after = render_certificate(certificate)
        assert before != after, "the name is not being drawn at all"

    def test_only_the_holder_can_download_it(
        self, api, approved_project, peer, mentor, nurse
    ):
        """
        The code travels on the document, so anybody ever shown a certificate
        could otherwise pull a clean copy and pass it off as their own. An
        employer does not need the file — they verify the code.
        """
        certificate = self._issue(approved_project, peer, mentor)
        url = f"/api/v1/recognition/certificates/{certificate.verification_code}/pdf/"

        assert api.get(url).status_code in (401, 403)

        api.force_authenticate(user=nurse)
        response = api.get(url)
        assert response.status_code == 403
        assert "not_the_holder" in str(response.data)

        api.force_authenticate(user=peer)
        response = api.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_a_steward_can_download_on_their_behalf(
        self, api, approved_project, peer, mentor, advisor
    ):
        certificate = self._issue(approved_project, peer, mentor)
        api.force_authenticate(user=advisor)
        response = api.get(
            f"/api/v1/recognition/certificates/{certificate.verification_code}/pdf/")
        assert response.status_code == 200

    def test_every_download_is_recorded(
        self, api, approved_project, peer, mentor, advisor
    ):
        from forge.recognition.models import CertificateDownload

        certificate = self._issue(approved_project, peer, mentor)
        url = f"/api/v1/recognition/certificates/{certificate.verification_code}/pdf/"

        api.force_authenticate(user=peer)
        api.get(url)
        api.get(url)
        api.force_authenticate(user=advisor)
        api.get(url)

        downloads = CertificateDownload.objects.filter(certificate=certificate)
        assert downloads.count() == 3
        assert downloads.filter(was_holder=True).count() == 2
        assert downloads.filter(was_holder=False).count() == 1
        # The name is denormalised so the trail survives an erasure.
        assert downloads.filter(downloaded_by_name=peer.display_name).exists()

    def test_the_download_record_cannot_be_rewritten(
        self, api, approved_project, peer, mentor
    ):
        from forge.common.models import ImmutableRecordError
        from forge.recognition.models import CertificateDownload

        certificate = self._issue(approved_project, peer, mentor)
        api.force_authenticate(user=peer)
        api.get(f"/api/v1/recognition/certificates/{certificate.verification_code}/pdf/")

        record = CertificateDownload.objects.get()
        record.was_holder = False
        with pytest.raises(ImmutableRecordError):
            record.save()

    def test_each_copy_is_stamped_with_when_it_was_taken(
        self, approved_project, peer, mentor
    ):
        """A leaked copy traces back to one download, not to 'somebody'."""
        from datetime import datetime

        from forge.recognition.pdf import render_certificate

        certificate = self._issue(approved_project, peer, mentor)
        unstamped = render_certificate(certificate)
        stamped = render_certificate(certificate, issued_to="Grace Njeri",
                                     issued_at=datetime(2026, 9, 23, 10, 6))
        assert stamped != unstamped

    def test_verification_reports_the_download_history_but_not_who(
        self, api, approved_project, peer, mentor
    ):
        certificate = self._issue(approved_project, peer, mentor)
        api.force_authenticate(user=peer)
        api.get(f"/api/v1/recognition/certificates/{certificate.verification_code}/pdf/")

        api.force_authenticate(user=None)
        response = api.get(
            f"/api/v1/recognition/certificates/verify/{certificate.verification_code}/")

        assert response.status_code == 200
        assert response.data["download_count"] == 1
        assert response.data["last_downloaded_at"] is not None
        # Whose downloads they were is the holder's business. (The recipient's
        # name is in the statement, which is the certificate speaking — the
        # trail itself must not appear.)
        assert "downloads" not in response.data
        assert "downloaded_by" not in str(response.data)
        assert "pdf_url" not in response.data

    def test_an_unknown_code_is_not_found(self, api, student):
        api.force_authenticate(user=student)
        response = api.get("/api/v1/recognition/certificates/ZZZZ-ZZZZ-ZZZZ/pdf/")
        assert response.status_code == 404

    def test_a_revoked_certificate_still_renders_and_says_so(
        self, approved_project, peer, mentor, advisor
    ):
        from forge.recognition.services import revoke_certificate

        certificate = self._issue(approved_project, peer, mentor)
        revoke_certificate(certificate, actor=advisor,
                           reason="Issued against a disputed contribution.")
        certificate.refresh_from_db()

        text = pdf_text(certificate)
        # Somebody holding a stale copy should see it has been withdrawn
        # rather than wonder why the code no longer resolves.
        assert "REVOKED" in text

    def test_the_holders_name_is_woven_through_the_background(
        self, approved_project, peer, mentor
    ):
        """
        The anti-forgery property.

        The holder's name is repeated as microtext across the page and in a
        band beneath their printed name. None of this proves authenticity --
        the verification code and the ledger hash do that -- but it means a
        stolen certificate cannot have its name swapped without redrawing the
        whole background, and a retyped imitation looks obviously wrong beside
        a real one.
        """
        certificate = self._issue(approved_project, peer, mentor)

        # The row of microtext is a form XObject placed once per line. Counting
        # the placements asserts the weave is there without relying on the text
        # layer, which no longer carries it.
        assert _microtext_rows(certificate) > 20, (
            "expected the holder's name woven across the page many times"
        )
        # And it must not be liftable, which was the whole point of outlining it.
        assert peer.display_name not in pdf_text(certificate)

    def test_the_watermark_does_not_bloat_the_file(
        self, approved_project, peer, mentor
    ):
        """
        The logo is 1254px square. Embedded verbatim it took a 3 KB document
        to nearly a megabyte, on a file students email from a phone.
        """
        from forge.recognition.pdf import render_certificate

        certificate = self._issue(approved_project, peer, mentor)
        assert len(render_certificate(certificate)) < 200_000

    def test_a_missing_logo_does_not_break_the_download(
        self, approved_project, peer, mentor, monkeypatch
    ):
        """A decorative watermark must never be the reason a member cannot
        fetch their own certificate."""
        from pathlib import Path

        from forge.recognition import pdf as pdf_module

        pdf_module._watermark.cache_clear()
        monkeypatch.setattr(pdf_module, "LOGO_PATH", Path("/nonexistent/logo.png"))
        try:
            certificate = self._issue(approved_project, peer, mentor)
            assert pdf_module.render_certificate(certificate).startswith(b"%PDF-")
        finally:
            pdf_module._watermark.cache_clear()

    def test_nothing_identifying_can_be_copied_out_of_the_pdf(
        self, approved_project, peer, mentor
    ):
        """
        The complaint this exists to answer: select-all and copy lifted the
        whole certificate out of the PDF, which is most of the work of
        building a forgery.

        The permission flags stop a compliant viewer. They do not stop
        `pdftotext`, which is what this test uses — so the fields a forger
        would need are drawn as vector outlines with no character codes
        behind them.
        """
        certificate = self._issue(approved_project, peer, mentor)
        text = pdf_text(certificate)

        assert peer.display_name not in text
        assert certificate.verification_code not in text
        assert mentor.display_name not in text

    def test_the_disclaimer_stays_readable_to_assistive_technology(
        self, approved_project, peer, mentor
    ):
        """
        The deliberate limit on the above. Outlined text cannot be read aloud,
        so only the fields a forger needs are outlined — a reader using a
        screen reader must still hear that this carries no academic credit.
        """
        certificate = self._issue(approved_project, peer, mentor)
        text = pdf_text(certificate)

        assert "no academic credit" in text
        assert "Anyone can check this code" in text

    def test_the_pdf_forbids_copying(self, approved_project, peer, mentor):
        import io

        from pypdf import PdfReader

        from forge.recognition.pdf import render_certificate

        certificate = self._issue(approved_project, peer, mentor)
        reader = PdfReader(io.BytesIO(render_certificate(certificate)))
        assert reader.is_encrypted


def pdf_text(certificate) -> str:
    """
    The visible text of a rendered certificate.

    Read back through a PDF parser rather than grepped out of the raw bytes,
    because reportlab compresses its content streams -- a substring search on
    the file would silently pass for the wrong reason.
    """
    import io

    from pypdf import PdfReader

    from forge.recognition.pdf import render_certificate

    reader = PdfReader(io.BytesIO(render_certificate(certificate)))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _microtext_rows(certificate) -> int:
    """
    How many times the microtext row is placed on the page.

    Read from the content stream rather than the text layer, because the row
    is drawn as vector outlines inside a form XObject and referenced by name.
    """
    import io
    import re

    from pypdf import PdfReader

    from forge.recognition.pdf import render_certificate

    reader = PdfReader(io.BytesIO(render_certificate(certificate)))
    stream = reader.pages[0].get_contents().get_data().decode("latin-1")
    return len(re.findall(r"/FormXob\.\S*\s+Do|/forge-microtext-row\s+Do", stream))
