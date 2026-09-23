from rest_framework import serializers


class VerificationRequestSerializer(serializers.Serializer):
    portfolio = serializers.DictField(
        help_text="The 'portfolio' object exactly as it appeared in the export.")
    signature = serializers.CharField(
        help_text="The base64 signature value from the export's 'signature' block.")
    public_key = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Optional. Defaults to this platform's current public key; supply "
                  "one to check an export signed with a retired key.",
    )
