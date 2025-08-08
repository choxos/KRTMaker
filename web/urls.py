from django.urls import path
from . import views

app_name = 'web'

urlpatterns = [
    # Main pages
    path('', views.HomeView.as_view(), name='home'),
    path('maker/', views.KRTMakerView.as_view(), name='krt_maker'),
    path('results/<str:session_id>/', views.ResultsView.as_view(), name='results'),
    
    # Article management
    path('articles/', views.ArticleDashboardView.as_view(), name='article_dashboard'),
    path('articles/<path:identifier>/', views.ArticleProfileView.as_view(), name='article_profile'),
    
    # path('analytics/', views.AnalyticsView.as_view(), name='analytics'),  # TODO: Implement AnalyticsView
    
    # Export functionality
    path('export/<str:session_id>/<str:format_type>/', views.export_krt, name='export_krt'),
    
    # Feedback
    # path('feedback/', views.FeedbackView.as_view(), name='feedback'),  # TODO: Implement FeedbackView
    # path('feedback/<str:session_id>/', views.FeedbackView.as_view(), name='feedback_session'),  # TODO: Implement FeedbackView
    
    # API endpoints
    # path('api/status/<str:session_id>/', views.api_status, name='api_status'),  # TODO: Implement api_status
]