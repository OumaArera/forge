from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AcceptInvitationView,
    AdminMemberViewSet,
    AdminOverviewView,
    ChangePasswordView,
    EmailLogViewSet,
    ForgeTokenObtainPairView,
    InvitationViewSet,
    MemberViewSet,
    MeView,
    MyDataView,
    MySkillsViewSet,
    RecoveryEmailView,
    ReferenceDataView,
    RegistrationView,
    ResendRecoveryEmailView,
    ResendVerificationView,
    RoleGrantViewSet,
    SkillViewSet,
    SlugAvailabilityView,
    VerifyEmailView,
)

router = DefaultRouter()
router.register("members", MemberViewSet, basename="member")
router.register("my-skills", MySkillsViewSet, basename="my-skill")
router.register("skills", SkillViewSet, basename="skill")
router.register("role-grants", RoleGrantViewSet, basename="role-grant")
router.register("invitations", InvitationViewSet, basename="invitation")
router.register("admin/members", AdminMemberViewSet, basename="admin-member")
router.register("admin/email-log", EmailLogViewSet, basename="email-log")

urlpatterns = [
    # Joining
    path("register/", RegistrationView.as_view(), name="register"),
    path("accept-invitation/", AcceptInvitationView.as_view(), name="accept-invitation"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend-verification"),
    path("slug-availability/", SlugAvailabilityView.as_view(), name="slug-availability"),

    # Sessions
    path("token/", ForgeTokenObtainPairView.as_view(), name="token-obtain"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # The signed-in member
    path("me/", MeView.as_view(), name="me"),
    path("me/recovery-email/", RecoveryEmailView.as_view(), name="recovery-email"),
    path("me/recovery-email/resend/", ResendRecoveryEmailView.as_view(),
         name="recovery-email-resend"),
    path("me/password/", ChangePasswordView.as_view(), name="change-password"),
    path("me/data/", MyDataView.as_view(), name="my-data"),

    # Reference and administration
    path("reference/", ReferenceDataView.as_view(), name="reference-data"),
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),

    path("", include(router.urls)),
]
