from rest_framework import serializers


class ChatAskSerializer(serializers.Serializer):
    """
    Serializer for guest chatbot questions.
    Validates non-empty prompt strings and enforces character limits.
    """

    question = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=1000,
        help_text="Customer prompt or question (max 1000 characters).",
    )

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({"non_field_errors": "Invalid data type."})
        if "question" in data and not isinstance(data["question"], str):
            raise serializers.ValidationError({"question": "Question must be a string."})
        return super().to_internal_value(data)

    def validate_question(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Question cannot be empty or blank.")

        if len(cleaned) > 1000:
            raise serializers.ValidationError("Question cannot exceed 1000 characters.")

        return cleaned
