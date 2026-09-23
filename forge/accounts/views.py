"""Account and reference-data endpoints."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from forge.common.exceptions import DomainRuleViolation
from forge.common.permissions import HasPlatformRole, IsVerifiedStudent
from forge.common.throttling import LoginEmailThrottle, LoginRateThrottle
from forge.projects.serializers import RoleSuggestionSerializer
from forge.projects.services import suggest_roles_for

from .models import (
    DisciplineArea,
    EmailVerification,
    Invitation,
    Programme,
    RoleGrant,
    School,
    Skill,
    User,
    UserSkill,
)
from .serializers import (
    AcceptInvitationSerializer,
    ChangePasswordSerializer,
    CreateInvitationSerializer,
    DisciplineAreaSerializer,
    EmailLogSerializer,
    ForgeTokenObtainPairSerializer,
    GrantRoleSerializer,
    InvitationPreviewSerializer,
    InvitationSerializer,
    MemberSerializer,
    MeSerializer,
    ProgrammeSerializer,
    PublicUserSerializer,
    RegistrationSerializer,
    ResendVerificationSerializer,
    RoleGrantSerializer,
    SchoolSerializer,
    SetRecoveryEmailSerializer,
    SkillSerializer,
    UserSkillSerializer,
    VerifyEmailSerializer,
)
from .services import (
    accept_invitation,
    cancel_recovery_email,
    erase_user,
    export_personal_data,
    grant_role,
    invite,
    peek_invitation,
    register_student,
    request_recovery_email,
    resend_invitation,
    revoke_invitation,
    revoke_role,
    send_verification_email,
    suggest_public_slug,
    verify_email,
)


class ForgeTokenObtainPairView(TokenObtainPairView):
    """
    Sign-in.

    Two throttles and a lockout, for three different attacks. The address
    throttle stops one host working through a list of accounts; the email
    throttle stops a botnet working on one account; the lockout stops a slow
    grind that stays under both. See forge/common/throttling.py.
    """

    serializer_class = ForgeTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle, LoginEmailThrottle]


class RegistrationView(APIView):
    """
    Join FORGE with a University email address.

    The response is identical whether or not the address already has an
    account. That is not politeness: a different answer turns this endpoint
    into a way of discovering which students are registered, which is exactly
    the enumeration the credential-by-email design is meant to prevent.
    """

    permission_classes = [AllowAny]
    throttle_scope = "registration"

    SENT = {
        "detail": (
            "If that is a valid University address, your sign-in details are on "
            "their way to it. Check your inbox, and your spam folder."
        ),
    }

    @extend_schema(request=RegistrationSerializer, responses={202: None})
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        programme = data.get("programme")

        try:
            register_student(
                email=data["email"],
                full_name=data["full_name"],
                programme=programme,
                school=programme.school if programme else None,
                year_of_study=data.get("year_of_study"),
                recovery_email=data.get("recovery_email", ""),
                public_slug=data.get("public_slug") or "",
            )
        except DomainRuleViolation as error:
            # An address that is already taken gets the same answer as a new
            # one. Anything else is an honest failure the caller should see.
            if error.code != "email_taken":
                raise

        return Response(self.SENT, status=status.HTTP_202_ACCEPTED)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "email-verification"

    @extend_schema(request=VerifyEmailSerializer, responses={200: None})
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, already = verify_email(serializer.validated_data["token"])

        # `purpose` lets the client offer the right remedy when something goes
        # wrong later: a recovery-address link and a registration link have
        # completely different next steps.
        purpose = (
            "recovery_email"
            if user.recovery_email and not user.pending_recovery_email
            else "registration"
        )
        return Response({
            "already_confirmed": already,
            "purpose": purpose,
            "confirmed_address": user.recovery_email or user.email,
            "member": MeSerializer(user).data,
        })


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "email-verification"

    @extend_schema(request=ResendVerificationSerializer, responses={202: None})
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email=serializer.validated_data["email"].lower()).first()
        if user and user.email_verified_at is None:
            verification, token = EmailVerification.issue(user, user.email)
            send_verification_email(user, token, verification.purpose)
        # The same response either way: whether an address is registered is not
        # something an unauthenticated caller gets to find out.
        return Response(
            {"detail": "If that address has an unverified FORGE account, a new "
                       "confirmation link is on its way."},
            status=status.HTTP_202_ACCEPTED,
        )


class SlugAvailabilityView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[OpenApiParameter("slug", str, required=True),
                    OpenApiParameter("name", str, required=False)],
        responses={200: None},
    )
    def get(self, request):
        from .models import RESERVED_SLUGS

        slug = (request.query_params.get("slug") or "").lower().strip()
        if not slug:
            return Response({"suggestion": suggest_public_slug(
                request.query_params.get("name", "") or "member")})
        taken = slug in RESERVED_SLUGS or User.objects.filter(public_slug=slug).exists()
        return Response({
            "slug": slug,
            "available": not taken,
            "suggestion": None if not taken else suggest_public_slug(slug),
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer})
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=MeSerializer, responses={200: MeSerializer})
    def patch(self, request):
        serializer = MeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RecoveryEmailView(APIView):
    """
    Add, replace or withdraw the personal address on an account.

    POST starts confirmation of a new address; DELETE abandons a pending one.
    The address is not promoted to `recovery_email` until the link is followed,
    and `pending_recovery_email` is what the interface shows in the meantime --
    without it, submitting the form appeared to do nothing at all.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "email-verification"

    @extend_schema(request=SetRecoveryEmailSerializer, responses={202: MeSerializer})
    def post(self, request):
        serializer = SetRecoveryEmailSerializer(data=request.data,
                                                context={"request": request})
        serializer.is_valid(raise_exception=True)
        address = serializer.validated_data["recovery_email"]
        delivered = request_recovery_email(request.user, address)
        request.user.refresh_from_db()

        return Response(
            {
                "member": MeSerializer(request.user).data,
                "delivered": delivered,
                "detail": (
                    f"Confirm the address by following the link we sent to {address}."
                    if delivered else
                    f"We could not send to {address} just now. The address is saved "
                    f"as pending -- try sending the link again in a moment."
                ),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(responses={200: MeSerializer})
    def delete(self, request):
        cancel_recovery_email(request.user)
        request.user.refresh_from_db()
        return Response(MeSerializer(request.user).data)


class ResendRecoveryEmailView(APIView):
    """Send the confirmation link again for an address already pending."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "email-verification"

    @extend_schema(request=None, responses={202: None})
    def post(self, request):
        address = request.user.pending_recovery_email
        if not address:
            raise DomainRuleViolation("There is no address waiting to be confirmed.")
        delivered = request_recovery_email(request.user, address)
        return Response(
            {"delivered": delivered,
             "detail": f"Sent again to {address}." if delivered
                       else "We could not send it just now. Try again shortly."},
            status=status.HTTP_202_ACCEPTED,
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    @extend_schema(request=ChangePasswordSerializer, responses={200: None})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data,
                                              context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        # Choosing a password retires the generated one, so the member is no
        # longer held at the change-password screen.
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password",
                                         "updated_at"])

        from forge.audit.models import AuditEvent
        from forge.audit.services import record as audit

        audit(AuditEvent.Action.PASSWORD_CHANGED, actor=request.user,
              target=request.user)
        return Response({"detail": "Password changed.",
                         "member": MeSerializer(request.user).data})


class MyDataView(APIView):
    """
    Data subject rights, Data Protection Act 2019.

    GET returns everything the platform holds about the caller. DELETE erases
    their personal data while leaving other members' confirmed records intact
    -- see accounts.services.erase_user for why that boundary is where it is.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "export"

    @extend_schema(responses={200: None})
    def get(self, request):
        return Response(export_personal_data(request.user))

    @extend_schema(responses={200: None})
    def delete(self, request):
        confirmation = request.data.get("confirm_slug") if hasattr(request, "data") else None
        if confirmation != request.user.public_slug:
            return Response(
                {"error": {
                    "code": "confirmation_required",
                    "detail": "Send {\"confirm_slug\": \"<your public slug>\"} to "
                              "confirm. Erasure cannot be undone.",
                }},
                status=status.HTTP_400_BAD_REQUEST,
            )
        erase_user(request.user, requested_by=request.user)
        return Response({"detail": "Your personal data has been erased and your "
                                   "account closed."})


class MySkillsViewSet(viewsets.ModelViewSet):
    queryset = UserSkill.objects.none()  # real filtering happens in get_queryset
    serializer_class = UserSkillSerializer
    permission_classes = [IsVerifiedStudent]

    def get_queryset(self):
        return UserSkill.objects.filter(user=self.request.user).select_related("skill")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MemberViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    """Browsing members. Read-only, and email addresses never appear."""
    queryset = User.objects.none()  # real filtering happens in get_queryset

    permission_classes = [IsAuthenticated]
    lookup_field = "public_slug"
    search_fields = ["full_name", "preferred_name", "headline", "public_slug"]
    filterset_fields = ["school", "programme", "kind"]

    def get_queryset(self):
        return (
            User.objects.filter(is_active=True)
            .exclude(status__in=[User.Status.CLOSED, User.Status.PENDING])
            .select_related("school", "programme")
            .prefetch_related("skills__skill", "interests")
        )

    def get_serializer_class(self):
        return MemberSerializer if self.action == "retrieve" else PublicUserSerializer

    @extend_schema(responses={200: RoleSuggestionSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="suggested-roles")
    def suggested_roles(self, request):
        """
        Open roles that fit the caller.

        The most common way a voluntary platform dies is that a willing
        student cannot find the thing they would gladly have done.
        """
        roles = suggest_roles_for(request.user, limit=12)
        return Response(RoleSuggestionSerializer(roles, many=True,
                                                 context={"request": request}).data)


class RoleGrantViewSet(viewsets.ModelViewSet):
    """Granting and revoking standing roles. Stewards only."""
    queryset = RoleGrant.objects.none()  # real filtering happens in get_queryset

    serializer_class = RoleGrantSerializer
    permission_classes = [HasPlatformRole]
    required_roles = [RoleGrant.Role.FACULTY_ADVISOR, RoleGrant.Role.PLATFORM_MAINTAINER]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return (RoleGrant.objects.select_related("user", "granted_by", "discipline_area")
                .order_by("-granted_at"))

    @extend_schema(request=GrantRoleSerializer, responses={201: RoleGrantSerializer})
    def create(self, request, *args, **kwargs):
        serializer = GrantRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grant = grant_role(granted_by=request.user, **serializer.validated_data)
        return Response(RoleGrantSerializer(grant).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        grant = self.get_object()
        revoke_role(grant=grant, revoked_by=request.user,
                    note=request.query_params.get("note", ""))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReferenceDataView(APIView):
    """
    Everything a client needs to render its forms, in one call.

    Deliberately one request rather than five. Most members are on a phone and
    on a constrained connection, and five round trips before a registration
    form can be drawn is four too many.
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request):
        from django.conf import settings

        return Response({
            # How to sign in, so the client can offer University single
            # sign-on when it exists and say nothing about it when it does
            # not. A button that only pretends to work is worse than no
            # button -- somebody will press it and conclude the site is broken.
            "identity": {
                "oidc_enabled": settings.OIDC_ENABLED,
                "university_email_domains": settings.UNIVERSITY_EMAIL_DOMAINS,
                "credentials_by_email": settings.FORGE_POLICY["CREDENTIALS_BY_EMAIL"],
            },
            "schools": SchoolSerializer(
                School.objects.filter(is_active=True), many=True).data,
            "programmes": ProgrammeSerializer(
                Programme.objects.filter(is_active=True).select_related("school"),
                many=True).data,
            "discipline_areas": DisciplineAreaSerializer(
                DisciplineArea.objects.filter(is_active=True), many=True).data,
            "skills": SkillSerializer(
                Skill.objects.filter(is_approved=True)[:300], many=True).data,
        })


class SkillViewSet(mixins.ListModelMixin, mixins.CreateModelMixin,
                   viewsets.GenericViewSet):
    """
    The shared skill vocabulary.

    Members may propose a skill; it becomes visible in the shared list only
    once a moderator approves it. Otherwise the tag cloud is unusable for
    role matching within a trimester.
    """
    queryset = Skill.objects.none()  # real filtering happens in get_queryset

    serializer_class = SkillSerializer
    permission_classes = [IsVerifiedStudent]
    search_fields = ["name"]

    def get_queryset(self):
        queryset = Skill.objects.all()
        if self.request.query_params.get("include_proposed") != "true":
            queryset = queryset.filter(is_approved=True)
        return queryset

    def perform_create(self, serializer):
        from django.utils.text import slugify

        name = serializer.validated_data["name"].strip()
        existing = Skill.objects.filter(name__iexact=name).first()
        if existing:
            serializer.instance = existing
            return
        serializer.save(slug=slugify(name)[:80], is_approved=False)


class AcceptInvitationView(APIView):
    """
    Look at an invitation, then accept it.

    GET shows who invited you and in what capacity, without consuming the
    token — nobody should have to commit to an account before seeing what they
    are being asked to join. POST creates the account and emails its
    credentials, exactly as open registration does.
    """

    permission_classes = [AllowAny]
    throttle_scope = "registration"

    @extend_schema(responses={200: InvitationPreviewSerializer})
    def get(self, request):
        token = request.query_params.get("token", "")
        invitation = peek_invitation(token)
        return Response(InvitationPreviewSerializer(invitation).data)

    @extend_schema(request=AcceptInvitationSerializer, responses={202: None})
    def post(self, request):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        accept_invitation(
            token=data["token"],
            full_name=data.get("full_name", ""),
            programme=data.get("programme"),
            year_of_study=data.get("year_of_study"),
            public_slug=data.get("public_slug", ""),
        )
        return Response(
            {"detail": "Your account is ready. Your sign-in details are on their "
                       "way to your email address."},
            status=status.HTTP_202_ACCEPTED,
        )


class InvitationViewSet(viewsets.ModelViewSet):
    """
    Inviting people who cannot use the open route.

    Restricted to stewards. Students with a University address register
    directly and are never invited; this is for staff, alumni returning to
    mentor, and external partners, whose accounts skip the domain check.
    """

    serializer_class = InvitationSerializer
    permission_classes = [HasPlatformRole]
    required_roles = [RoleGrant.Role.FACULTY_ADVISOR, RoleGrant.Role.PLATFORM_MAINTAINER]
    throttle_scope = "invite"
    http_method_names = ["get", "post", "delete", "head", "options"]
    filterset_fields = ["status", "kind"]
    search_fields = ["email", "full_name"]
    queryset = Invitation.objects.none()

    def get_queryset(self):
        return Invitation.objects.select_related(
            "invited_by", "discipline_area", "accepted_user"
        ).order_by("-created_at")

    @extend_schema(request=CreateInvitationSerializer, responses={201: InvitationSerializer})
    def create(self, request, *args, **kwargs):
        serializer = CreateInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = invite(invited_by=request.user, **serializer.validated_data)
        return Response(InvitationSerializer(invitation).data,
                        status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        revoke_invitation(self.get_object(), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        delivered = resend_invitation(self.get_object(), actor=request.user)
        return Response({
            "delivered": delivered,
            "detail": "Sent again." if delivered
                      else "Could not send just now — check the email log.",
        })


class AdminMemberViewSet(viewsets.ReadOnlyModelViewSet):
    """
    The member directory as a steward sees it.

    Carries the fields the ordinary directory withholds — email address,
    status, last seen, roles held — because managing access without them is
    guesswork. Restricted accordingly, and every action it offers writes to
    the audit log.
    """

    permission_classes = [HasPlatformRole]
    required_roles = [RoleGrant.Role.FACULTY_ADVISOR, RoleGrant.Role.PLATFORM_MAINTAINER]
    serializer_class = MeSerializer
    lookup_field = "public_slug"
    search_fields = ["full_name", "preferred_name", "email", "public_slug"]
    filterset_fields = ["status", "kind", "school", "programme"]
    queryset = User.objects.none()

    def get_queryset(self):
        return (User.objects.select_related("school", "programme")
                .prefetch_related("role_grants", "skills__skill")
                .order_by("full_name"))

    @extend_schema(request=None, responses={200: MeSerializer})
    @action(detail=True, methods=["post"])
    def suspend(self, request, public_slug=None):
        """
        Suspend an account.

        Separate from moderation's suspension, which attaches to a report and
        a rationale. This is the administrative lever for an account that has
        to be stopped now — it still records who did it and why.
        """
        member = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 10:
            raise DomainRuleViolation(
                "Give a reason. An account suspended without one cannot be "
                "explained to the person it happened to, or appealed.",
                code="reason_required",
            )
        if member.is_superuser and member != request.user:
            raise DomainRuleViolation("Superuser accounts cannot be suspended here.")

        member.status = User.Status.SUSPENDED
        member.save(update_fields=["status", "updated_at"])

        from forge.audit.models import AuditEvent
        from forge.audit.services import record as audit

        audit(AuditEvent.Action.MODERATION_ACTION, actor=request.user, target=member,
              metadata={"action": "suspend", "reason": reason})
        return Response(MeSerializer(member).data)

    @extend_schema(request=None, responses={200: MeSerializer})
    @action(detail=True, methods=["post"])
    def reinstate(self, request, public_slug=None):
        member = self.get_object()
        member.status = (User.Status.ALUMNUS if member.deprovisioned_at
                         else User.Status.ACTIVE)
        member.save(update_fields=["status", "updated_at"])

        from forge.accounts.lockout import clear
        from forge.audit.models import AuditEvent
        from forge.audit.services import record as audit

        clear(member.email)
        audit(AuditEvent.Action.MODERATION_ACTION, actor=request.user, target=member,
              metadata={"action": "reinstate"})
        return Response(MeSerializer(member).data)

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, public_slug=None):
        """
        Issue a fresh generated password and email it.

        The platform has no self-service password reset, on purpose: a reset
        link is a second credential travelling by email, and the account can
        already be recovered through the same mailbox. A steward doing it
        leaves an audit row naming who asked and who acted.
        """
        from .services import generated_password, send_credentials

        member = self.get_object()
        password = generated_password()
        member.set_password(password)
        member.must_change_password = True
        member.save(update_fields=["password", "must_change_password", "updated_at"])

        from forge.accounts.lockout import clear
        from forge.audit.models import AuditEvent
        from forge.audit.services import record as audit

        clear(member.email)
        delivered = send_credentials(member, password)
        audit(AuditEvent.Action.PASSWORD_CHANGED, actor=request.user, target=member,
              metadata={"by": "steward reset", "delivered": delivered})
        return Response({
            "delivered": delivered,
            "detail": (f"New credentials sent to {member.email}." if delivered
                       else "Could not send the email — check the email log."),
        })

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"], url_path="unlock")
    def unlock(self, request, public_slug=None):
        """Clear a sign-in lockout without changing the password."""
        from forge.accounts.lockout import clear, locked_until

        member = self.get_object()
        was_locked = locked_until(member.email) is not None
        clear(member.email)
        return Response({"was_locked": was_locked,
                         "detail": "Sign-in attempts reset."})


class AdminOverviewView(APIView):
    """One call for the administration console's summary row."""

    permission_classes = [HasPlatformRole]
    required_roles = [RoleGrant.Role.FACULTY_ADVISOR, RoleGrant.Role.PLATFORM_MAINTAINER]

    @extend_schema(responses={200: None})
    def get(self, request):
        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        from forge.common.models_mail import EmailLog
        from forge.contributions.models import Contribution, LedgerEntry
        from forge.projects.models import Project

        week_ago = timezone.now() - timedelta(days=7)
        return Response({
            "members": {
                "total": User.objects.count(),
                "active": User.objects.filter(status=User.Status.ACTIVE).count(),
                "pending": User.objects.filter(status=User.Status.PENDING).count(),
                "suspended": User.objects.filter(status=User.Status.SUSPENDED).count(),
                "alumni": User.objects.filter(status=User.Status.ALUMNUS).count(),
                "joined_this_week": User.objects.filter(created_at__gte=week_ago).count(),
                "never_signed_in": User.objects.filter(last_seen_at__isnull=True).count(),
            },
            "invitations": {
                row["status"]: row["n"]
                for row in Invitation.objects.values("status").annotate(n=Count("id"))
            },
            "roles": {
                row["role"]: row["n"]
                for row in RoleGrant.objects.filter(revoked_at__isnull=True)
                .values("role").annotate(n=Count("id"))
            },
            "projects": {
                row["status"]: row["n"]
                for row in Project.objects.values("status").annotate(n=Count("id"))
            },
            "evidence": {
                "ledger_entries": LedgerEntry.objects.count(),
                "awaiting_confirmation": Contribution.objects.filter(
                    status=Contribution.Status.SUBMITTED).count(),
            },
            # Mail is the thing most likely to be quietly broken, so its health
            # belongs on the first screen a steward sees rather than three
            # clicks away.
            "email": {
                "sent_this_week": EmailLog.objects.filter(
                    status=EmailLog.Status.SENT, created_at__gte=week_ago).count(),
                "failed_this_week": EmailLog.objects.filter(
                    status=EmailLog.Status.FAILED, created_at__gte=week_ago).count(),
            },
        })


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    What the platform has tried to send.

    Exists so that "the email never arrived" has an answer. Stewards only, and
    no message body is stored — verification links and generated passwords
    pass through this path.
    """

    permission_classes = [HasPlatformRole]
    required_roles = [RoleGrant.Role.FACULTY_ADVISOR, RoleGrant.Role.PLATFORM_MAINTAINER]
    filterset_fields = ["status", "category", "template"]
    search_fields = ["to_address", "subject"]

    serializer_class = EmailLogSerializer

    def get_queryset(self):
        from forge.common.models_mail import EmailLog

        return EmailLog.objects.select_related("user").order_by("-created_at")
