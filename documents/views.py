import logging

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Document, QuestionAnswer
from .serializers import (
    AskQuestionSerializer,
    DocumentSerializer,
    QuestionAnswerSerializer,
)
from .services.rag_service import generate_answer, delete_document_index

logger = logging.getLogger(__name__)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def perform_destroy(self, instance):
        delete_document_index(instance.pk)
        instance.delete()


class QuestionAnswerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = QuestionAnswer.objects.all()
    serializer_class = QuestionAnswerSerializer


@extend_schema(
    request=AskQuestionSerializer,
    responses={201: dict},
)
@api_view(["POST"])
def ask_question(request):
    input_serializer = AskQuestionSerializer(data=request.data)
    input_serializer.is_valid(raise_exception=True)

    question = input_serializer.validated_data["question"]
    document_id = input_serializer.validated_data.get("document_id")

    try:
        result = generate_answer(
            question=question,
            k=3,
            document_id=document_id,
        )
    except ValueError as exc:
        logger.warning("Unable to generate an answer: %s", exc)
        return Response(
            {
                "detail": (
                    "The question could not be answered. "
                    "Please try again."
                )
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:
        logger.exception("The RAG question-answering request failed.")
        return Response(
            {
                "detail": (
                    "The question-answering service is temporarily "
                    "unavailable."
                )
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    qa_record = QuestionAnswer.objects.create(
        question=question,
        answer=result["answer"],
        retrieved_context=result["context"],
    )

    source_documents = Document.objects.filter(
        pk__in=result["source_document_ids"]
    )
    qa_record.source_documents.set(source_documents)

    return Response(
        {
            "question_id": qa_record.pk,
            "question": qa_record.question,
            "answer": qa_record.answer,
            "source_documents": [
                {
                    "id": document.pk,
                    "title": document.title,
                }
                for document in source_documents
            ],
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def api_root(request):
    return Response(
        {
            "message": "Document Q&A API",
            "documents": "/api/documents/",
            "questions": "/api/questions/",
            "ask": "/api/ask/",
            "schema": "/api/schema/",
            "swagger": "/api/docs/",
        },
        status=status.HTTP_200_OK,
    )