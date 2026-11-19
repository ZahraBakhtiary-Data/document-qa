from django.db import models


class Document(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/%Y/%m/")
    full_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class QuestionAnswer(models.Model):
    question = models.TextField()
    answer = models.TextField(blank=True)
    source_documents = models.ManyToManyField(
        Document,
        blank=True,
        related_name="question_answers",
    )
    retrieved_context = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.question[:80]
