"""
FORGE Showcase: completed projects, presented properly.

A showcase entry is the artefact the whole lifecycle produces. It is the
thing a student sends an employer, so the required fields are the ones an
employer actually reads: what problem it solved, what was built, what the
team learned, and a link to see it working.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.utils import timezone

from forge.common.fields import validate_no_html
from forge.common.models import BaseModel

from .validators import validate_video_url


class ShowcaseEntry(BaseModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE,
                                   related_name="showcase")
    headline = models.CharField(max_length=180, validators=[validate_no_html])
    what_we_built = models.TextField(max_length=4000, validators=[validate_no_html])
    what_we_learned = models.TextField(
        max_length=4000, validators=[validate_no_html],
        help_text="Including what went wrong. A showcase where every project went "
                  "smoothly is a showcase nobody believes, and the difficulties are "
                  "the most useful part for the next team.",
    )
    outcome = models.TextField(
        blank=True, max_length=2000, validators=[validate_no_html],
        help_text="Who used it, what changed, what happened next.",
    )

    demonstration_url = models.URLField(
        blank=True, validators=[validate_video_url],
        help_text="A link to a short demonstration video hosted elsewhere. FORGE "
                  "does not host video.",
    )
    documentation_url = models.URLField(blank=True,
                                        validators=[URLValidator(schemes=["https"])])
    live_url = models.URLField(blank=True, validators=[URLValidator(schemes=["https"])])
    repository_url = models.URLField(blank=True, validators=[URLValidator(schemes=["https"])])

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    featured_note = models.CharField(max_length=200, blank=True)
    view_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-is_featured", "-published_at"]
        verbose_name_plural = "showcase entries"

    def __str__(self) -> str:
        return self.headline

    def clean(self):
        super().clean()
        from forge.projects.models import Project

        if self.is_published and self.project.status not in {
            Project.Status.DOCUMENTING, Project.Status.COMPLETED, Project.Status.ARCHIVED
        }:
            raise ValidationError(
                "Publish a showcase entry only once the project has reached "
                "documentation. The showcase is a record of delivered work."
            )

    def publish(self) -> None:
        self.is_published = True
        self.published_at = self.published_at or timezone.now()
        self.full_clean()
        self.save(update_fields=["is_published", "published_at", "updated_at"])


class ShowcaseImage(BaseModel):
    """
    A screenshot. Small images only -- see MAX_UPLOAD_BYTES.

    Images are hosted because they are cheap and because a showcase without
    a picture does not get read. Video is a different matter entirely.
    """

    entry = models.ForeignKey(ShowcaseEntry, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="showcase/%Y/%m/")
    caption = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(
        max_length=200,
        help_text="Describe the image for someone who cannot see it. Required: the "
                  "University's inclusivity commitment applies to this platform as "
                  "much as to any other.",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]

    def clean(self):
        super().clean()
        if not self.alt_text.strip():
            raise ValidationError({"alt_text": "Alternative text is required."})
        if self.image and self.image.size > settings.MAX_UPLOAD_BYTES:
            limit_mb = settings.MAX_UPLOAD_BYTES / (1024 * 1024)
            raise ValidationError({
                "image": f"Keep screenshots under {limit_mb:.0f} MB. Many members "
                         f"browse on a metered connection."
            })
