"""Serializers for identity, profiles and reference data."""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from forge.common.models_mail import EmailLog

from .models import (
    DisciplineArea,
    Invitation,
    Programme,
    RoleGrant,
    School,
    Skill,
    User,
    UserSkill,
)


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["id", "name", "code"]


class ProgrammeSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)

    class Meta:
        model = Programme
        fields = ["id", "name", "code", "level", "school"]


class DisciplineAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisciplineArea
        fields = ["id", "name", "slug", "description"]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "slug", "is_approved", "usage_count"]
        read_only_fields = ["slug", "is_approved", "usage_count"]


class UserSkillSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    skill_id = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), source="skill", write_only=True
    )

    class Meta:
        model = UserSkill
        fields = ["id", "skill", "skill_id", "self_rating", "wants_to_learn",
                  "evidence_count"]
        # evidence_count is derived from confirmed contributions and is not
        # something a member may assert about themselves.
        read_only_fields = ["evidence_count"]


class RoleGrantSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    granted_by_name = serializers.CharField(source="granted_by.display_name",
                                            read_only=True, default=None)
    discipline_area = DisciplineAreaSerializer(read_only=True)

    class Meta:
        model = RoleGrant
        fields = ["id", "role", "role_display", "discipline_area", "granted_at",
                  "expires_at", "revoked_at", "granted_by_name", "note", "is_active"]
        read_only_fields = fields


class PublicUserSerializer(serializers.ModelSerializer):
    """What anyone may see about a member. No email, ever."""

    display_name = serializers.CharField(read_only=True)
    school = serializers.CharField(source="school.name", read_only=True, default=None)
    programme = serializers.CharField(source="programme.name", read_only=True, default=None)
    level = serializers.CharField(source="standing.level.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = ["id", "display_name", "public_slug", "headline", "avatar",
                  "school", "programme", "level", "kind"]
        read_only_fields = fields


class MemberSerializer(serializers.ModelSerializer):
    """A fuller view, for signed-in members looking at each other."""

    display_name = serializers.CharField(read_only=True)
    school = SchoolSerializer(read_only=True)
    programme = ProgrammeSerializer(read_only=True)
    skills = UserSkillSerializer(many=True, read_only=True)
    interests = DisciplineAreaSerializer(many=True, read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "display_name", "full_name", "preferred_name", "public_slug",
                  "headline", "bio", "location", "links", "avatar", "kind", "status",
                  "school", "programme", "year_of_study", "skills", "interests",
                  "roles", "portfolio_is_public", "created_at"]
        read_only_fields = ["id", "status", "kind", "created_at"]

    def get_roles(self, obj) -> list[str]:
        return sorted(obj.role_names)


class MeSerializer(MemberSerializer):
    """The signed-in member's own record, including private fields."""

    class Meta(MemberSerializer.Meta):
        fields = [*MemberSerializer.Meta.fields,
            "email", "recovery_email", "pending_recovery_email", "email_verified_at",
            "show_email_on_portfolio", "last_seen_at", "accepted_conduct_at",
            "is_verified_member", "may_join_projects", "must_change_password",
        ]
        read_only_fields = ["id", "email", "email_verified_at", "status", "kind",
                            "created_at", "last_seen_at", "is_verified_member",
                            "may_join_projects", "pending_recovery_email",
                            "recovery_email", "must_change_password"]

    is_verified_member = serializers.BooleanField(read_only=True)
    may_join_projects = serializers.BooleanField(read_only=True)

    def validate_public_slug(self, value: str) -> str:
        # Changing a slug breaks links a member may already have shared, so it
        # is allowed but the client is expected to warn first.
        from .models import RESERVED_SLUGS

        if value in RESERVED_SLUGS:
            raise serializers.ValidationError("That address is reserved.")
        return value


class RegistrationSerializer(serializers.Serializer):
    """
    Joining FORGE.

    There is deliberately no password field. Credentials are generated and
    emailed to the University address, so opening an account requires being
    able to read that mailbox. Letting people choose their own password would
    mean anyone who can guess the shape of a University address can create a
    working account without ever proving they hold it.
    """

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=160)
    recovery_email = serializers.EmailField(
        required=False, allow_blank=True,
        help_text="Optional now, and you can add it later. Your University address "
                  "stops working when you graduate; your portfolio does not.",
    )
    programme_id = serializers.PrimaryKeyRelatedField(
        queryset=Programme.objects.filter(is_active=True), source="programme",
        required=False, allow_null=True,
    )
    year_of_study = serializers.IntegerField(required=False, allow_null=True,
                                             min_value=1, max_value=9)
    public_slug = serializers.SlugField(required=False, allow_blank=True, max_length=40)

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        if not User.is_university_email(value):
            raise serializers.ValidationError(
                "Register with your Open University of Kenya email address. If you "
                "are staff, an alumnus or an external partner, ask a FORGE steward "
                "to invite you instead."
            )
        # Deliberately the same wording as success would produce, because
        # whether an address is registered is not something an anonymous caller
        # gets to enumerate. The view returns an identical response either way.
        return value


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    full_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    programme_id = serializers.PrimaryKeyRelatedField(
        queryset=Programme.objects.filter(is_active=True), source="programme",
        required=False, allow_null=True,
    )
    year_of_study = serializers.IntegerField(required=False, allow_null=True,
                                             min_value=1, max_value=9)
    public_slug = serializers.SlugField(required=False, allow_blank=True, max_length=40)


class InvitationSerializer(serializers.ModelSerializer):
    invited_by_display = serializers.CharField(source="invited_by_name", read_only=True)
    role_label = serializers.CharField(read_only=True)
    is_usable = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Invitation
        fields = ["id", "email", "full_name", "kind", "role", "role_label",
                  "discipline_area", "message", "invited_by_display", "status",
                  "status_display", "is_usable", "expires_at", "accepted_at",
                  "sent_count", "last_sent_at", "created_at"]
        read_only_fields = ["status", "expires_at", "accepted_at", "sent_count",
                            "last_sent_at", "invited_by_display"]


class CreateInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=User.Kind.choices, default=User.Kind.STUDENT)
    role = serializers.ChoiceField(choices=RoleGrant.Role.choices, required=False,
                                   allow_blank=True, default="")
    discipline_area_id = serializers.PrimaryKeyRelatedField(
        queryset=DisciplineArea.objects.all(), source="discipline_area",
        required=False, allow_null=True,
    )
    message = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class InvitationPreviewSerializer(serializers.Serializer):
    """What the accept screen shows before anybody fills anything in."""

    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    kind = serializers.CharField(read_only=True)
    role_label = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    invited_by_name = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class SetRecoveryEmailSerializer(serializers.Serializer):
    recovery_email = serializers.EmailField()

    def validate_recovery_email(self, value: str) -> str:
        user = self.context["request"].user
        if value.lower() == user.email.lower():
            raise serializers.ValidationError(
                "Use a personal address that will outlast your University account."
            )
        return value.lower()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=10)

    def validate_current_password(self, value: str) -> str:
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("That is not your current password.")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value, self.context["request"].user)
        return value


class GrantRoleSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="user")
    role = serializers.ChoiceField(choices=RoleGrant.Role.choices)
    discipline_area_id = serializers.PrimaryKeyRelatedField(
        queryset=DisciplineArea.objects.all(), source="discipline_area",
        required=False, allow_null=True,
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class ForgeTokenObtainPairSerializer(TokenObtainPairSerializer):
    # SimpleJWT's default reads "No active account found with the given
    # credentials", which is both unfriendly and misleading: it suggests the
    # account does not exist when usually the password is simply wrong. It is
    # deliberately the same sentence for a wrong password and an unknown
    # address, because telling them apart is how somebody enumerates accounts.
    default_error_messages = {
        "no_active_account": (
            "That email address and password do not match. Check both and try "
            "again — after a few failed attempts the account locks for a while."
        )
    }

    """
    Sign-in, with the verification gate applied at the door.

    The default serializer only checks `is_active`, which means an account
    that has registered but never confirmed its email address would still be
    issued a token. That matters: anyone can guess the shape of a University
    address, and an unconfirmed account holding a valid token could read the
    member directory without ever proving it controls the address it claimed.

    An alumnus signs in with their recovery address, which is resolved here so
    that losing a University account does not lock somebody out of the record
    the platform exists to give them.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Claims a client can read without another round trip. Nothing
        # sensitive and nothing authoritative -- the server re-checks.
        token["name"] = user.display_name
        token["slug"] = user.public_slug
        token["kind"] = user.kind
        return token

    def validate(self, attrs):
        from .lockout import clear, is_locked, lock_message, record_failure

        address = (attrs.get(self.username_field) or "").lower().strip()
        if address and not User.objects.filter(email=address).exists():
            alumnus = User.objects.filter(
                recovery_email=address, status=User.Status.ALUMNUS
            ).first()
            if alumnus:
                attrs[self.username_field] = alumnus.email
                address = alumnus.email.lower()

        # Checked before the password is even compared, so that a locked
        # account costs an attacker a request and tells them nothing.
        if is_locked(address):
            raise serializers.ValidationError({
                "detail": lock_message(address), "code": "account_locked",
            })

        request = self.context.get("request")
        ip = ""
        if request is not None:
            from forge.common.throttling import client_address

            ip = client_address(request)

        try:
            data = super().validate(attrs)
        except Exception:
            # Any authentication failure counts, including an unknown address:
            # not counting those would let somebody enumerate accounts by
            # watching which addresses can be retried indefinitely.
            record_failure(address, ip=ip)
            raise

        clear(address)

        if self.user.status == User.Status.PENDING or self.user.email_verified_at is None:
            raise serializers.ValidationError({
                "detail": "Confirm your University email address before signing in. "
                          "We sent you a link when you registered; request another "
                          "at /api/v1/accounts/resend-verification/.",
                "code": "email_not_verified",
            })
        if self.user.status == User.Status.SUSPENDED:
            raise serializers.ValidationError({
                "detail": "This account is suspended. Contact the faculty advisor.",
                "code": "suspended",
            })
        if self.user.status == User.Status.CLOSED:
            raise serializers.ValidationError({
                "detail": "This account has been closed.", "code": "closed",
            })

        data["member"] = MeSerializer(self.user).data
        return data


class EmailLogSerializer(serializers.ModelSerializer):
    """
    A record of one attempted send.

    No message body, deliberately: verification links and generated passwords
    pass through this path, and a table holding them would be a better target
    than the password hashes it sits beside.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    member = serializers.CharField(source="user.display_name", read_only=True,
                                   default=None)

    class Meta:
        model = EmailLog
        fields = ["id", "to_address", "subject", "template", "category", "status",
                  "status_display", "member", "sent_at", "error", "created_at"]
        read_only_fields = fields
