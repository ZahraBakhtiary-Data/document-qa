from pathlib import Path

from django.core.exceptions import ValidationError
from rest_framework import serializers

from .models import Document, QuestionAnswer
from .services.document_processor import extract_docx_text
from .services.rag_service import index_document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file",
            "full_text",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "full_text",
            "created_at",
            "updated_at",
        ]

    def validate_file(self, value):
        if Path(value.name).suffix.lower() != ".docx":
            raise serializers.ValidationError(
                "Only .docx files are supported."
            )
        return value

    def create(self, validated_data):
        uploaded_file = validated_data["file"]

        try:
            full_text = extract_docx_text(uploaded_file)
        except ValidationError as exc:
            raise serializers.ValidationError(
                {"file": exc.messages}
            ) from exc

        document = Document.objects.create(
            **validated_data,
            full_text=full_text,
        )

        try:
            index_document(document)
        except Exception:
            document.delete()
            raise

        return document

    def update(self, instance, validated_data):
        new_file = validated_data.get("file")

        if new_file is not None:
            try:
                full_text = extract_docx_text(new_file)
            except ValidationError as exc:
                raise serializers.ValidationError(
                    {"file": exc.messages}
                ) from exc

            instance.full_text = full_text

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        # Re-index the document after a title or file change.
        index_document(instance)

        return instance


class QuestionAnswerSerializer(serializers.ModelSerializer):
    source_documents = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
    )

    class Meta:
        model = QuestionAnswer
        fields = [
            "id",
            "question",
            "answer",
            "source_documents",
            "created_at",
        ]
        read_only_fields = fields


class AskQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )
    document_id = serializers.IntegerField(
        required=False,
        min_value=1,
    )

    def validate_question(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "The question cannot be empty."
            )
        return value

    def validate_document_id(self, value):
        if not Document.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                "The requested document does not exist."
            )
        return value