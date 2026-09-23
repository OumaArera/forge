from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from forge.common.exceptions import DomainRuleViolation, NotEligible
from forge.common.permissions import IsVerifiedStudent

from .models import MentorProfile, MentorshipRequest, OfficeHour, OfficeHourBooking
from .serializers import (
    MentorProfileSerializer,
    MentorshipRequestSerializer,
    OfficeHourBookingSerializer,
    OfficeHourSerializer,
    RespondToRequestSerializer,
)


class MentorViewSet(viewsets.ModelViewSet):
    serializer_class = MentorProfileSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["availability", "is_alumnus", "discipline_areas"]
    search_fields = ["headline", "about", "user__full_name", "organisation"]

    def get_queryset(self):
        return (MentorProfile.objects.select_related("user")
                .prefetch_related("expertise", "discipline_areas"))

    def perform_create(self, serializer):
        if MentorProfile.objects.filter(user=self.request.user).exists():
            raise DomainRuleViolation("You already have a mentor profile.")
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user_id != self.request.user.id:
            raise NotEligible("That is not your profile.")
        serializer.save()

    @extend_schema(responses={200: MentorProfileSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        """
        Mentors who can actually take somebody on right now.

        Capacity is checked rather than advertised. A directory that lists
        mentors who are already full produces a queue of unanswered requests,
        and an unanswered request is how a student concludes the platform is
        dead.
        """
        profiles = [p for p in self.get_queryset() if p.has_capacity]
        return Response(MentorProfileSerializer(profiles, many=True).data)


class MentorshipRequestViewSet(viewsets.ModelViewSet):
    queryset = MentorshipRequest.objects.none()  # real filtering happens in get_queryset
    serializer_class = MentorshipRequestSerializer
    permission_classes = [IsVerifiedStudent]
    filterset_fields = ["status"]

    def get_queryset(self):
        user = self.request.user
        return (MentorshipRequest.objects
                .filter(Q(requester=user) | Q(mentor=user))
                .select_related("requester", "mentor", "project"))

    def perform_create(self, serializer):
        from forge.accounts.models import User
        from forge.notifications.services import notify

        mentor = User.objects.filter(pk=serializer.validated_data["mentor_id"]).first()
        if mentor is None:
            raise DomainRuleViolation("No such mentor.")
        profile = getattr(mentor, "mentor_profile", None)
        if profile is None or not profile.has_capacity:
            raise DomainRuleViolation(
                "That mentor is not taking on new work at the moment. The "
                "'available' list shows who is."
            )
        request_obj = serializer.save(
            requester=self.request.user, mentor=mentor,
            expires_at=timezone.now() + timezone.timedelta(days=14),
        )
        notify(mentor, verb="mentorship.requested", target=request_obj,
               actor=self.request.user,
               summary=f"{self.request.user.display_name} has asked for your help.")

    @extend_schema(request=RespondToRequestSerializer,
                   responses={200: MentorshipRequestSerializer})
    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        from forge.notifications.services import notify

        serializer = RespondToRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mentorship_request = self.get_object()

        if mentorship_request.mentor_id != request.user.id:
            raise NotEligible("That request was not addressed to you.")
        if mentorship_request.status != MentorshipRequest.Status.PENDING:
            raise DomainRuleViolation("That request has already been answered.")

        accept = serializer.validated_data["accept"]
        mentorship_request.status = (MentorshipRequest.Status.ACCEPTED if accept
                                     else MentorshipRequest.Status.DECLINED)
        mentorship_request.response = serializer.validated_data.get("response", "")
        mentorship_request.responded_at = timezone.now()
        mentorship_request.save(update_fields=["status", "response", "responded_at",
                                               "updated_at"])

        if accept and mentorship_request.project and not mentorship_request.project.mentor_id:
            mentorship_request.project.mentor = request.user
            mentorship_request.project.save(update_fields=["mentor", "updated_at"])

        notify(mentorship_request.requester,
               verb="mentorship.accepted" if accept else "mentorship.requested",
               target=mentorship_request, actor=request.user,
               summary=(f"{request.user.display_name} accepted your mentorship request."
                        if accept else
                        f"{request.user.display_name} could not take this on."))
        return Response(MentorshipRequestSerializer(mentorship_request).data)


class OfficeHourViewSet(viewsets.ModelViewSet):
    serializer_class = OfficeHourSerializer
    permission_classes = [IsVerifiedStudent]

    def get_queryset(self):
        return (OfficeHour.objects.filter(is_cancelled=False,
                                          starts_at__gte=timezone.now())
                .select_related("mentor").prefetch_related("bookings"))

    def perform_create(self, serializer):
        if not self.request.user.can_attest_as_mentor:
            raise NotEligible("Only a mentor may publish office hours.")
        serializer.save(mentor=self.request.user)

    @extend_schema(request=OfficeHourBookingSerializer,
                   responses={201: OfficeHourBookingSerializer})
    @action(detail=True, methods=["post"])
    def book(self, request, pk=None):
        office_hour = self.get_object()
        if office_hour.is_full:
            raise DomainRuleViolation("That slot is full.")
        booking, created = OfficeHourBooking.objects.get_or_create(
            office_hour=office_hour, attendee=request.user, cancelled_at=None,
            defaults={"question": request.data.get("question", "")},
        )
        if not created:
            raise DomainRuleViolation("You have already booked that slot.")
        return Response(
            OfficeHourBookingSerializer(booking, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
