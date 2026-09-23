from __future__ import annotations

from django.db.models import F
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from forge.common.exceptions import NotEligible
from forge.common.permissions import IsVerifiedStudent

from .models import ShowcaseEntry, ShowcaseImage
from .serializers import ShowcaseEntrySerializer, ShowcaseImageSerializer


class ShowcaseViewSet(viewsets.ModelViewSet):
    """
    Completed work, presented for an outside reader.

    Published entries are readable without an account. That is the point: a
    showcase only an enrolled student can see does nothing for the employability
    argument the whole initiative rests on.
    """
    queryset = ShowcaseEntry.objects.none()  # real filtering happens in get_queryset

    serializer_class = ShowcaseEntrySerializer
    filterset_fields = ["is_featured", "project"]
    search_fields = ["headline", "what_we_built", "outcome"]
    ordering_fields = ["published_at", "view_count"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsVerifiedStudent()]

    def get_queryset(self):
        queryset = (ShowcaseEntry.objects
                    .select_related("project", "project__lead")
                    .prefetch_related("images", "project__discipline_areas",
                                      "project__memberships__user"))
        user = self.request.user
        if not user.is_authenticated:
            return queryset.filter(is_published=True)
        if user.is_superuser or user.can_moderate:
            return queryset
        return queryset.filter(is_published=True) | queryset.filter(
            project__memberships__user=user)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not project.may_manage(self.request.user):
            raise NotEligible("Only the project lead may write the showcase entry.")
        serializer.save()

    def perform_update(self, serializer):
        if not serializer.instance.project.may_manage(self.request.user):
            raise NotEligible("Only the project lead may edit the showcase entry.")
        serializer.save()

    @extend_schema(request=None, responses={200: ShowcaseEntrySerializer})
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        entry = self.get_object()
        if not entry.project.may_manage(request.user):
            raise NotEligible("Only the project lead may publish.")
        entry.publish()
        return Response(ShowcaseEntrySerializer(entry, context={"request": request}).data)

    @extend_schema(request=ShowcaseImageSerializer, responses={201: ShowcaseImageSerializer})
    @action(detail=True, methods=["post"], url_path="images")
    def add_image(self, request, pk=None):
        entry = self.get_object()
        if not entry.project.may_manage(request.user):
            raise NotEligible("Only the project lead may add screenshots.")
        serializer = ShowcaseImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = ShowcaseImage(entry=entry, **serializer.validated_data)
        image.full_clean()
        image.save()
        return Response(ShowcaseImageSerializer(image).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: ShowcaseEntrySerializer})
    @action(detail=True, methods=["post"], url_path="viewed",
            permission_classes=[AllowAny])
    def viewed(self, request, pk=None):
        """
        Count a view.

        A separate call rather than an increment inside retrieve, so that a
        crawler or a link preview does not inflate the number, and so the
        read path stays free of a write.
        """
        ShowcaseEntry.objects.filter(pk=pk, is_published=True).update(
            view_count=F("view_count") + 1)
        return Response(status=status.HTTP_204_NO_CONTENT)
