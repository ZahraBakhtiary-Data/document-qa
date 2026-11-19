
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from docx import Document as WordDocument
from langchain_chroma import Chroma
from langchain_core.embeddings import FakeEmbeddings

from .models import Document
from .services.document_processor import extract_docx_text
from .services.rag_service import index_document, delete_document_index


class DocumentProcessingTests(TestCase):
    def test_extract_text_from_docx(self):
        # Create a real DOCX file in memory.
        word_file = WordDocument()
        word_file.add_paragraph(
            "Employees must attend team meetings."
        )

        table = word_file.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Department"
        table.cell(0, 1).text = "IT"

        buffer = BytesIO()
        word_file.save(buffer)

        uploaded_file = SimpleUploadedFile(
            "policy.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

        extracted_text = extract_docx_text(uploaded_file)

        self.assertIn(
            "Employees must attend team meetings.",
            extracted_text,
        )
        self.assertIn("Department", extracted_text)
        self.assertIn("IT", extracted_text)


class DocumentIndexDeletionTests(TestCase):
    def test_deleting_document_removes_its_chroma_chunks(self):
        embeddings = FakeEmbeddings(size=8)

        vector_store = Chroma(
            collection_name="test_document_deletion",
            embedding_function=embeddings,
            persist_directory=None,
        )

        try:
            with patch(
                "documents.services.rag_service.get_vector_store",
                return_value=vector_store,
            ):
                uploaded_file = SimpleUploadedFile(
                    "deletion_test.docx",
                    b"test file",
                    content_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                )

                document = Document.objects.create(
                    title="Deletion Test",
                    file=uploaded_file,
                    full_text=(
                        "Employees must attach a blue label to laptops."
                    ),
                )

                try:
                    index_document(document)

                    before_delete = vector_store.get(
                        where={"document_id": document.pk}
                    )
                    self.assertTrue(before_delete["ids"])

                    delete_document_index(document.pk)

                    after_delete = vector_store.get(
                        where={"document_id": document.pk}
                    )
                    self.assertEqual(after_delete["ids"], [])
                finally:
                    document.file.delete(save=False)
                    document.delete()
        finally:
            vector_store.delete_collection()


class AskQuestionAPITests(TestCase):
    def test_ask_endpoint_saves_question_and_answer(self):
        uploaded_file = SimpleUploadedFile(
            "api_test.docx",
            b"test file",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

        document = Document.objects.create(
            title="API Test Document",
            file=uploaded_file,
            full_text="Employees must attend team meetings.",
        )

        try:
            mock_result = {
                "answer": "Employees must attend team meetings.",
                "context": "Source text from the test document.",
                "source_document_ids": [document.pk],
            }

            with patch(
                "documents.views.generate_answer",
                return_value=mock_result,
            ):
                client = APIClient()
                response = client.post(
                    "/api/ask/",
                    {
                        "question": "What must employees attend?",
                        "document_id": document.pk,
                    },
                    format="json",
                )

            self.assertEqual(response.status_code, 201)
            self.assertEqual(
                response.data["answer"],
                mock_result["answer"],
            )
            self.assertTrue(response.data["question_id"])
            self.assertEqual(
                response.data["source_documents"][0]["id"],
                document.pk,
            )

            from .models import QuestionAnswer

            self.assertTrue(
                QuestionAnswer.objects.filter(
                    pk=response.data["question_id"],
                    question="What must employees attend?",
                ).exists()
            )
        finally:
            document.file.delete(save=False)
