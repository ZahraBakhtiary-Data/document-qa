
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DocumentViewSet,
    QuestionAnswerViewSet,
    api_root,
    ask_question,
)

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")
router.register("questions", QuestionAnswerViewSet, basename="question")

urlpatterns = [
    path("", api_root, name="api-root"),
    path("ask/", ask_question, name="ask-question"),
    path("", include(router.urls)),
]
