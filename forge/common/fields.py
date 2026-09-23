"""Small reusable field types."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class AutoSlugField(models.SlugField):
    """
    A slug derived from another field, made unique by appending a counter.

    Slugs appear in URLs that students share, so once assigned a slug is not
    recomputed when the source field changes. A link that a student put on a
    CV should not break because they fixed a typo in a project title.
    """

    def __init__(self, *args, populate_from: str = "title", **kwargs):
        self.populate_from = populate_from
        kwargs.setdefault("max_length", 80)
        kwargs.setdefault("unique", True)
        kwargs.setdefault("editable", False)
        kwargs.setdefault("blank", True)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["populate_from"] = self.populate_from
        return name, path, args, kwargs

    def pre_save(self, model_instance, add):
        value = getattr(model_instance, self.attname, "")
        if value:
            return value
        source = getattr(model_instance, self.populate_from, "") or ""
        base = slugify(source)[: self.max_length - 6] or "item"
        candidate, counter = base, 1
        manager = type(model_instance)._default_manager
        while manager.filter(**{self.attname: candidate}).exclude(
            pk=model_instance.pk
        ).exists():
            counter += 1
            candidate = f"{base}-{counter}"
        setattr(model_instance, self.attname, candidate)
        return candidate


def validate_no_html(value: str) -> None:
    """
    Reject raw HTML in free-text fields.

    FORGE stores user text as plain text or Markdown and renders it safely at
    the edge. Allowing HTML through would hand a stored-XSS vector to anyone
    who can post, on a platform whose whole purpose is inviting students to
    post. The cost of disallowing it is close to zero.
    """
    if "<" in value and ">" in value:
        lowered = value.lower()
        for tag in ("<script", "<iframe", "<object", "<embed", "<style", "<link",
                    "<form", "<svg", "on="):
            if tag in lowered:
                raise ValidationError(
                    "HTML is not accepted here. Use Markdown for formatting."
                )
