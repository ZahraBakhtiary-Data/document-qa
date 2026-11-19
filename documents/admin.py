
from django.core.exceptions import ValidationError
from django.contrib import admin

from .models import Document, QuestionAnswer
from .services.document_processor import process_document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at", "updated_at")
    search_fields = ("title", "full_text")
    list_filter = ("created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Re-index only when the file or title changes.
        if change and not (
            "file" in form.changed_data
            or "title" in form.changed_data
        ):
            return

        try:
            if not change or "file" in form.changed_data:
                process_document(obj)
            else:
                from .services.rag_service import index_document
                index_document(obj)
        except (ValidationError, ValueError):
            raise

    def delete_model(self, request, obj):
        from .services.rag_service import delete_document_index

        delete_document_index(obj.pk)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        from .services.rag_service import delete_document_index

        document_ids = list(queryset.values_list("pk", flat=True))

        for document_id in document_ids:
            delete_document_index(document_id)

        super().delete_queryset(request, queryset)


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ("short_question", "created_at")
    search_fields = ("question", "answer", "retrieved_context")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)
    filter_horizontal = ("source_documents",)
    ordering = ("-created_at",)

    @admin.display(description="Question")
    def short_question(self, obj):
        return obj.question[:80]
