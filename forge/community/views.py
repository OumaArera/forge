from __future__ import annotations

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from forge.common.exceptions import DomainRuleViolation, NotEligible
from forge.common.permissions import IsVerifiedStudent

from .models import Post, Space, Subscription, Thread, Vote
from .serializers import (
    PostSerializer,
    SpaceSerializer,
    ThreadDetailSerializer,
    ThreadListSerializer,
    ThreadWriteSerializer,
    VoteSerializer,
)


class SpaceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                   viewsets.GenericViewSet):
    queryset = Space.objects.filter(is_active=True)
    serializer_class = SpaceSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


class ThreadViewSet(viewsets.ModelViewSet):
    queryset = Thread.objects.none()  # real filtering happens in get_queryset
    filterset_fields = ["space", "kind", "is_resolved", "project"]
    search_fields = ["title", "body"]
    ordering_fields = ["last_activity_at", "created_at", "reply_count"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsVerifiedStudent()]

    def get_queryset(self):
        return Thread.objects.select_related("author", "space").prefetch_related("posts")

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ThreadWriteSerializer
        if self.action == "retrieve":
            return ThreadDetailSerializer
        return ThreadListSerializer

    def perform_create(self, serializer):
        thread = serializer.save(author=self.request.user)
        Subscription.objects.get_or_create(thread=thread, user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.id:
            if not self.request.user.can_moderate:
                raise NotEligible("That is not your thread.")
        serializer.save()

    @extend_schema(request=PostSerializer, responses={201: PostSerializer})
    @action(detail=True, methods=["post"], url_path="reply",
            permission_classes=[IsVerifiedStudent])
    def reply(self, request, pk=None):
        thread = self.get_object()
        if thread.is_locked:
            raise DomainRuleViolation("This thread is locked.")

        serializer = PostSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        post = serializer.save(thread=thread, author=request.user,
                               author_name=request.user.display_name[:160])

        Thread.objects.filter(pk=thread.pk).update(reply_count=thread.posts.count())
        thread.touch()
        Subscription.objects.get_or_create(thread=thread, user=request.user)

        from forge.notifications.services import notify

        subscribers = (Subscription.objects.filter(thread=thread, is_muted=False)
                       .exclude(user=request.user).select_related("user"))
        for subscription in subscribers:
            notify(subscription.user, verb="community.reply", target=thread,
                   actor=request.user,
                   summary=f"{request.user.display_name} replied to '{thread.title}'.")
        return Response(PostSerializer(post, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        responses={200: ThreadDetailSerializer},
        parameters=[OpenApiParameter("post_id", OpenApiTypes.UUID, OpenApiParameter.PATH,
                                     description="The reply being accepted.")],
    )
    @action(detail=True, methods=["post"], url_path="accept-answer/(?P<post_id>[^/.]+)",
            permission_classes=[IsVerifiedStudent])
    def accept_answer(self, request, pk=None, post_id=None):
        """
        Mark the answer that solved it.

        The one thing a threaded forum gives a distance cohort that a chat
        group cannot: a question with a marked answer is a question the next
        student does not have to ask.
        """
        thread = self.get_object()
        if thread.author_id != request.user.id and not request.user.can_moderate:
            raise NotEligible("Only the person who asked may accept an answer.")
        if thread.kind != Thread.Kind.QUESTION:
            raise DomainRuleViolation("Only a question has an accepted answer.")

        post = thread.posts.filter(pk=post_id).first()
        if post is None:
            raise DomainRuleViolation("That reply is not on this thread.")

        thread.accepted_answer = post
        thread.is_resolved = True
        thread.save(update_fields=["accepted_answer", "is_resolved", "updated_at"])

        from forge.notifications.services import notify

        notify(post.author, verb="community.answer_accepted", target=thread,
               actor=request.user,
               summary=f"Your answer was accepted on '{thread.title}'.")
        return Response(ThreadDetailSerializer(thread, context={"request": request}).data)

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"], permission_classes=[IsVerifiedStudent])
    def subscribe(self, request, pk=None):
        subscription, _ = Subscription.objects.get_or_create(thread=self.get_object(),
                                                             user=request.user)
        subscription.is_muted = not subscription.is_muted
        subscription.save(update_fields=["is_muted", "updated_at"])
        return Response({"following": not subscription.is_muted})

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"], permission_classes=[IsVerifiedStudent])
    def lock(self, request, pk=None):
        if not request.user.can_moderate:
            raise NotEligible("Only a moderator may lock a thread.")
        thread = self.get_object()
        thread.is_locked = not thread.is_locked
        thread.save(update_fields=["is_locked", "updated_at"])
        return Response({"is_locked": thread.is_locked})


class PostViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    queryset = Post.objects.none()  # real filtering happens in get_queryset
    serializer_class = PostSerializer
    permission_classes = [IsVerifiedStudent]

    def get_queryset(self):
        return Post.objects.select_related("author", "thread").prefetch_related("votes")

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.id:
            raise NotEligible("That is not your post.")
        serializer.save(edited_at=timezone.now())

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.id and not self.request.user.can_moderate:
            raise NotEligible("That is not your post.")
        # Soft delete: removing the row would orphan replies and leave the
        # thread unreadable for everyone else.
        instance.delete(reason="removed by author" if
                        instance.author_id == self.request.user.id else "moderated")

    @extend_schema(request=VoteSerializer, responses={200: None})
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def vote(self, request, pk=None):
        """
        Vote on a post.

        Votes order answers within a question and do nothing else. They
        deliberately do not feed recognition: the platform's stated position
        is that it rewards demonstrated contribution rather than popularity,
        and letting a well-liked post earn points would quietly abandon that.
        """
        serializer = VoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = self.get_object()
        value = serializer.validated_data["value"]

        if post.author_id == request.user.id:
            raise DomainRuleViolation("You cannot vote on your own post.")

        if value == 0:
            Vote.objects.filter(post=post, user=request.user).delete()
        else:
            Vote.objects.update_or_create(post=post, user=request.user,
                                          defaults={"value": value})

        score = Vote.objects.filter(post=post).aggregate(s=Sum("value"))["s"] or 0
        Post.objects.filter(pk=post.pk).update(vote_score=score)
        return Response({"vote_score": score, "my_vote": value})
