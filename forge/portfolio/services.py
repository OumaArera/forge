"""
Assembling a portfolio and issuing a signed export.

The public portfolio and the export are built from the same function so that
what an employer sees on the web and what they can verify from a file cannot
drift apart.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.utils import timezone

from forge.audit.models import AuditEvent
from forge.audit.services import record as audit
from forge.common.exceptions import NotEligible

from .models import PortfolioExport
from .signing import SigningUnavailable, canonical_json, public_key_b64, sign


def build_portfolio(user, *, for_public: bool = True) -> dict:
    """
    The portfolio document.

    Only confirmed, ledger-settled work appears. A draft or disputed
    contribution is not part of anybody's portfolio, which is the whole point
    of having a settlement step.
    """
    from forge.contributions.models import LedgerEntry
    from forge.projects.models import Membership, Project
    from forge.recognition.models import BadgeAward, Certificate, Standing

    entries = (
        LedgerEntry.objects.filter(contributor=user)
        .select_related("project")
        .order_by("sequence")
    )
    standing = Standing.objects.filter(user=user).select_related("level").first()

    memberships = (
        Membership.objects.filter(user=user)
        .select_related("project", "role", "project__lead")
        .order_by("-joined_at")
    )

    projects = []
    for membership in memberships:
        project = membership.project
        if for_public and project.status not in Project.PUBLIC_STATUSES:
            continue
        project_entries = [e for e in entries if e.project_id == project.id]
        projects.append({
            "title": project.title,
            "slug": project.slug,
            "summary": project.summary,
            "status": project.get_status_display(),
            "discipline_areas": [a.name for a in project.discipline_areas.all()],
            "role": membership.role.title if membership.role else None,
            "was_lead": membership.is_lead or project.lead_id == user.id,
            "joined_at": membership.joined_at.date().isoformat(),
            "left_at": membership.left_at.date().isoformat() if membership.left_at else None,
            "days_served": membership.days_served,
            "is_open_source": project.is_open_source,
            "repository_url": project.repository_url if project.is_open_source else "",
            "confirmed_contributions": len(project_entries),
            "points": sum(e.points for e in project_entries),
        })

    contributions = [
        {
            "sequence": entry.sequence,
            "project": entry.payload.get("project_title"),
            "dimension": entry.get_dimension_display(),
            "description": entry.payload.get("description"),
            "occurred_on": entry.payload.get("occurred_on"),
            "evidence_url": entry.payload.get("evidence_url"),
            "ai_assistance": entry.payload.get("ai_assistance"),
            "skills": entry.payload.get("skills", []),
            "confirmed_by": [
                {"name": a["attestor_name"], "capacity": a["capacity"]}
                for a in entry.payload.get("attestations", [])
                if a.get("decision") == "confirm"
            ],
            "points": entry.points,
            "entry_hash": entry.entry_hash,
        }
        for entry in entries
    ]

    skills = [
        {"skill": us.skill.name, "self_rating": us.get_self_rating_display(),
         "evidence_count": us.evidence_count}
        for us in user.skills.select_related("skill").order_by("-evidence_count")
    ]

    head = entries.last()
    return {
        "format": "forge.portfolio/v1",
        "generated_at": timezone.now().isoformat(),
        "platform": {
            "name": "FORGE",
            "institution": "The Open University of Kenya",
            "url": settings.FRONTEND_BASE_URL,
            "note": (
                "FORGE is a voluntary student initiative. Nothing in this document "
                "is an academic credit or a qualification of the University. Each "
                "contribution listed was confirmed independently by the project "
                "lead and by the project's assigned mentor."
            ),
        },
        "member": {
            "display_name": user.display_name,
            "public_slug": user.public_slug,
            # The address a member puts on a CV, so it points at the site a
            # reader can actually open, not at the API that serves it.
            "portfolio_url": f"{settings.FRONTEND_BASE_URL}/p/{user.public_slug}",
            "school": user.school.name if user.school else None,
            "programme": user.programme.name if user.programme else None,
            "status": user.get_status_display(),
            "headline": user.headline,
            "bio": user.bio,
            "links": user.links,
            "member_since": user.created_at.date().isoformat(),
        },
        "standing": {
            "level": standing.level.name if standing and standing.level else None,
            "total_points": standing.total_points if standing else 0,
            "confirmed_contributions": standing.confirmed_contributions if standing else 0,
            "completed_projects": standing.completed_projects if standing else 0,
            "projects_led": standing.projects_led if standing else 0,
            "points_by_dimension": standing.points_by_dimension if standing else {},
        } if standing else {},
        "projects": projects,
        "contributions": contributions,
        "skills": skills,
        "badges": [
            {"name": b.badge.name, "criteria": b.badge.criteria,
             "awarded_at": b.awarded_at.date().isoformat()}
            for b in BadgeAward.objects.filter(user=user).select_related("badge")
        ],
        "certificates": [
            {"kind": c.get_kind_display(), "code": c.verification_code,
             "issued_at": c.issued_at.date().isoformat(),
             "verify_at": f"{settings.PUBLIC_BASE_URL}/api/v1/recognition/certificates/"
                          f"verify/{c.verification_code}/"}
            for c in Certificate.objects.filter(user=user, revoked_at__isnull=True)
        ],
        "ledger": {
            "entry_count": len(contributions),
            "head_hash": head.entry_hash if head else None,
            "chain_note": (
                "Each contribution is an entry in an append-only, hash-chained "
                "ledger. Altering any historical entry invalidates every entry "
                "recorded after it."
            ),
        },
    }


def issue_signed_export(user, *, requested_by=None) -> dict:
    """
    Produce a signed, verifiable portfolio document.

    The signature covers the portfolio body only, not the envelope around it,
    so that a verifier knows exactly which bytes were attested to.
    """
    if requested_by is not None and requested_by.id != user.id and not requested_by.is_superuser:
        raise NotEligible("You may only export your own portfolio.")

    body = build_portfolio(user, for_public=True)
    try:
        signature, key_id, digest = sign(body)
        signed = True
    except SigningUnavailable:
        # An unsigned export is still useful, and refusing to give a student
        # their own record because of a server misconfiguration would be the
        # wrong trade. It is marked clearly as unverifiable.
        signature, key_id = "", ""
        digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
        signed = False

    record = PortfolioExport.objects.create(
        user=user,
        export_format=PortfolioExport.Format.JSON,
        document_digest=digest,
        signature=signature,
        key_id=key_id,
        ledger_head=(body["ledger"]["head_hash"] or ""),
        entry_count=body["ledger"]["entry_count"],
        requested_by=requested_by or user,
    )
    audit(AuditEvent.Action.DATA_EXPORTED, actor=requested_by or user, target=user,
          metadata={"kind": "portfolio", "digest": digest, "signed": signed})

    return {
        "portfolio": body,
        "signature": {
            "signed": signed,
            "algorithm": "Ed25519",
            "value": signature,
            "key_id": key_id,
            "public_key": public_key_b64() if signed else "",
            "document_sha256": digest,
            "issued_at": record.issued_at.isoformat(),
            "how_to_verify": (
                f"{settings.PUBLIC_BASE_URL}/api/v1/portfolio/verify/ -- POST the "
                f"'portfolio' object and the signature value. Or verify offline: "
                f"see {settings.PUBLIC_BASE_URL}/docs/verifying-a-portfolio."
            ) if signed else (
                "This export is NOT signed and cannot be verified. The platform "
                "has no signing key configured."
            ),
        },
    }
