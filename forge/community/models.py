"""
Discussion, questions and study groups.

A deliberately small forum. The concept proposal notes that messaging groups
have no memory, no structure and no evidence, and that is the whole gap this
module fills -- a threaded, searchable, attributable record per discipline.
It is not trying to be a general-purpose forum, and if the pilot finds that
students want one, the right answer is to run Discourse alongside FORGE
rather than to grow this into it.

The one feature worth having that a chat group cannot offer is the accepted
answer: a question with a marked answer is a question the next student does
not have to ask.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from forge.common.fields import validate_no_html
from forge.common.models import BaseModel, SoftDeleteModel


class Space(BaseModel):
    """A place to talk, usually mapped to a discipline area."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.CharField(max_length=300, blank=True)
    discipline_area = models.ForeignKey("accounts.DisciplineArea", null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name="spaces")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name


class Thread(BaseModel, SoftDeleteModel):
    class Kind(models.TextChoices):
        DISCUSSION = "discussion", "Discussion"
        QUESTION = "question", "Question"
        STUDY_GROUP = "study_group", "Study group"
        EVENT = "event", "Event"
        SHOW_AND_TELL = "show_and_tell", "Show and tell"

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="threads")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                               on_delete=models.SET_NULL, related_name="threads")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.DISCUSSION)
    title = models.CharField(max_length=180, validators=[validate_no_html])
    body = models.TextField(max_length=8000, validators=[validate_no_html])
    project = models.ForeignKey("projects.Project", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="threads")

    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    accepted_answer = models.OneToOneField("Post", null=True, blank=True,
                                            on_delete=models.SET_NULL,
                                            related_name="accepted_for")
    reply_count = models.PositiveIntegerField(default=0, editable=False)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-is_pinned", "-last_activity_at"]
        indexes = [models.Index(fields=["space", "-last_activity_at"]),
                   models.Index(fields=["kind", "is_resolved"])]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        super().clean()
        if self.accepted_answer and self.kind != self.Kind.QUESTION:
            raise ValidationError({"accepted_answer": "Only a question has an accepted answer."})

    def touch(self) -> None:
        now = timezone.now()
        type(self).all_objects.filter(pk=self.pk).update(last_activity_at=now)
        self.last_activity_at = now


class Post(BaseModel, SoftDeleteModel):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                               on_delete=models.SET_NULL, related_name="posts")
    author_name = models.CharField(
        max_length=160, blank=True,
        help_text="The author's name at the time. Preserved so that a thread stays "
                  "readable after someone exercises their right to erasure.",
    )
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE,
                               related_name="replies")
    body = models.TextField(max_length=8000, validators=[validate_no_html])
    edited_at = models.DateTimeField(null=True, blank=True)
    vote_score = models.IntegerField(default=0, editable=False, db_index=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["thread", "created_at"])]

    def __str__(self) -> str:
        return f"{self.author_name or 'Former member'}: {self.body[:50]}"

    def clean(self):
        super().clean()
        if self.parent and self.parent.thread_id != self.thread_id:
            raise ValidationError({"parent": "That reply belongs to another thread."})
        if self.parent and self.parent.parent_id:
            # One level of nesting. Deeper trees are unreadable on a phone,
            # which is where most of this platform will be read.
            raise ValidationError({"parent": "Replies nest one level deep only."})


class Vote(BaseModel):
    """
    An up or down vote on a post.

    Votes affect the ordering of answers within a question and nothing else.
    They deliberately do not feed recognition: section 10 is explicit that
    the platform rewards demonstrated contribution rather than popularity,
    and the fastest way to break that promise would be to let a popular post
    earn points.
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="votes")
    value = models.SmallIntegerField(choices=[(1, "Up"), (-1, "Down")])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="uniq_vote")]

    def __str__(self) -> str:
        return f"{self.user.display_name} {self.value:+d}"


class Subscription(BaseModel):
    """Follow a thread to be notified of replies. Authors are subscribed on creation."""

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="subscriptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="thread_subscriptions")
    is_muted = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["thread", "user"],
                                               name="uniq_thread_subscription")]
