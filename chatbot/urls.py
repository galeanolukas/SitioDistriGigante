# urls.py
from django.urls import path, include
from . import views
import settings

app_name = "chatbot"

urlpatterns = [
    path('api/assistant/chat/', views.AssistantAPIView.as_view(), name='assistant_chat'),
]

# urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# urlpatterns += [
#     path("ckeditor5/", include('django_ckeditor_5.urls'), name="ck_editor_5_upload_file"),
# ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
#
# if settings.DEBUG:
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
