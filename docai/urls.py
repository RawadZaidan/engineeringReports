from django.urls import path
from . import views

app_name = 'docai'

urlpatterns = [
    path('', views.docai_home, name='home'),
    path('summarize/', views.summarize_document, name='summarize'),
    path('summary/<int:summary_id>/', views.summary_detail, name='detail'),
    path('summary/<int:summary_id>/progress/', views.analysis_progress_api, name='progress_api'),
    path('summary/<int:summary_id>/delete/', views.delete_summary, name='delete'),
    path('summary/<int:summary_id>/edit/', views.edit_summary, name='edit'),
]
