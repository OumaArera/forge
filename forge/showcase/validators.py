"""
Validation for showcase material.

The rule that matters here is that FORGE does not host video.

A demonstration video is the single largest storage and bandwidth item a
platform like this can acquire, and on a pilot funded by sponsored cloud
credits it is the item most likely to exhaust them. Hosting video also brings
transcoding, adaptive bitrate for students on poor connections, and a
moderation surface that a volunteer team is not equipped to police.

So teams link to a video hosted elsewhere -- unlisted is fine and is what we
recommend. This costs the platform nothing, gives students adaptive quality
for free, and keeps the moderation problem with a provider that has solved it.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.core.exceptions import ValidationError

ALLOWED_VIDEO_HOSTS = {
    "youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com",
    "vimeo.com", "player.vimeo.com", "www.vimeo.com",
    "drive.google.com",  # many students already have University Drive access
    "loom.com", "www.loom.com",
}


def validate_video_url(value: str) -> None:
    if not value:
        return
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise ValidationError("Use an https link.")
    host = (parsed.netloc or "").lower().split(":")[0]
    if host not in ALLOWED_VIDEO_HOSTS:
        allowed = ", ".join(sorted({"youtube.com", "vimeo.com", "drive.google.com",
                                    "loom.com"}))
        raise ValidationError(
            f"Host your demonstration video on one of: {allowed}, and link to it "
            f"here. FORGE does not host video -- an unlisted upload elsewhere is "
            f"free, plays well on a slow connection, and costs the platform nothing."
        )
