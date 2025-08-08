from django.urls import path
from . import views

app_name = 'web'

urlpatterns = [
    # Main pages
    path('', views.HomeView.as_view(), name='home'),
    path('maker/', views.KRTMakerView.as_view(), name='krt_maker'),
    path('results/<str:session_id>/', views.ResultsView.as_view(), name='results'),
    path('analytics/', views.AnalyticsView.as_view(), name='analytics'),
    
    # Export functionality
    path('export/<str:session_id>/<str:format_type>/', views.export_krt, name='export_krt'),
    
    # Feedback
    path('feedback/', views.FeedbackView.as_view(), name='feedback'),
    path('feedback/<str:session_id>/', views.FeedbackView.as_view(), name='feedback_session'),
    
    # API endpoints
    path('api/status/<str:session_id>/', views.api_status, name='api_status'),
]