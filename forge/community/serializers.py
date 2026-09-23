from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from forge.accounts.serializers import PublicUserSerializer

from .models import Post, Space, Thread


class SpaceSerializer(serializers.ModelSerializer):
    thread_count = serializers.SerializerMethodField()

    class Meta:
        model = Space
        fields = ["id", "name", "slug", "description", "discipline_area", "thread_count"]

    def get_thread_count(self, obj) -> int:
        return obj.threads.count()


class PostSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True)
    my_vote = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    is_accepted = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "thread", "parent", "author", "author_name", "body",
                  "vote_score", "my_vote", "reply_count", "is_accepted",
                  "edited_at", "created_at"]
        read_only_fields = ["author", "author_name", "vote_score", "edited_at"]

    def get_my_vote(self, obj) -> int:
        user = self.context["request"].user
        if not user.is_authenticated:
            return 0
        vote = next((v for v in obj.votes.all() if v.user_id == user.id), None)
        return vote.value if vote else 0

    def get_reply_count(self, obj) -> int:
        return obj.replies.count()

    def get_is_accepted(self, obj) -> bool:
        return obj.thread.accepted_answer_id == obj.id


class ThreadListSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)

    class Meta:
        model = Thread
        fields = ["id", "space", "space_name", "kind", "title", "author",
                  "is_pinned", "is_locked", "is_resolved", "reply_count",
                  "last_activity_at", "created_at"]


class ThreadDetailSerializer(ThreadListSerializer):
    posts = serializers.SerializerMethodField()

    class Meta(ThreadListSerializer.Meta):
        fields = [*ThreadListSerializer.Meta.fields, "body", "project",
                  "accepted_answer", "posts"]

    @extend_schema_field(PostSerializer(many=True))
    def get_posts(self, obj):
        queryset = (obj.posts.filter(parent__isnull=True)
                    .select_related("author").prefetch_related("votes", "replies__author")
                    .order_by("-vote_score" if obj.kind == Thread.Kind.QUESTION
                              else "created_at"))
        return PostSerializer(queryset, many=True, context=self.context).data


class ThreadWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Thread
        fields = ["space", "kind", "title", "body", "project"]


class VoteSerializer(serializers.Serializer):
    value = serializers.ChoiceField(choices=[1, -1, 0],
                                    help_text="0 clears your vote.")
