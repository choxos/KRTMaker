from django.urls import path
from . import views
from .views_statistics import StatisticsView
from . import views_ai_enhancement

app_name = 'web'

urlpatterns = [
    # Main pages
    path('', views.HomeView.as_view(), name='home'),
    path('maker/', views.KRTMakerView.as_view(), name='krt_maker'),
    path('results/<str:session_id>/', views.ResultsView.as_view(), name='results'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('api/', views.APIDocsView.as_view(), name='api_docs'),
    path('statistics/', StatisticsView.as_view(), name='statistics'),
    
    # Article management
    path('articles/', views.ArticleDashboardView.as_view(), name='article_dashboard'),
    path('articles/<path:identifier>/', views.ArticleProfileView.as_view(), name='article_profile'),
    
    # Database management (removed for VPS deployment - use terminal commands instead)
    # path('database/', views.DatabaseManagementView.as_view(), name='database_management'),
    # path('admin-krts/', views.AdminKRTManagementView.as_view(), name='admin_krt_management'),
    
    # path('analytics/', views.AnalyticsView.as_view(), name='analytics'),  # TODO: Implement AnalyticsView
    
    # Export functionality
    path('export/<str:session_id>/<str:format_type>/', views.export_krt, name='export_krt'),
    
    # AJAX endpoints
    path('check-doi/', views.check_doi_availability, name='check_doi_availability'),
    path('check-doi-local/', views.check_doi_local_availability, name='check_doi_local_availability'),
    path('doi-suggestions/', views.get_doi_suggestions, name='get_doi_suggestions'),
    
    # API endpoints for KRT data
    path('api/krt/<str:session_id>/', views.get_krt_data_api, name='get_krt_data_api'),
    path('api/krt/doi/<path:doi>/', views.get_krt_data_by_doi_api, name='get_krt_data_by_doi_api'),
    
    # Feedback
    # path('feedback/', views.FeedbackView.as_view(), name='feedback'),  # TODO: Implement FeedbackView
    # path('feedback/<str:session_id>/', views.FeedbackView.as_view(), name='feedback_session'),  # TODO: Implement FeedbackView
    
    # API endpoints
    # path('api/status/<str:session_id>/', views.api_status, name='api_status'),  # TODO: Implement api_status
    
    # AI Enhancement Features
    path('ai/', views_ai_enhancement.AIFeaturesView.as_view(), name='ai_features'),
    path('ai/dashboard/', views_ai_enhancement.AIEnhancementDashboardView.as_view(), name='ai_dashboard'),
    path('ai/chat/', views_ai_enhancement.ConversationalKRTView.as_view(), name='conversational_krt'),
    
    # AI API Endpoints
    path('api/ai/suggest-rrid/', views_ai_enhancement.suggest_rrid, name='api_suggest_rrid'),
    path('api/ai/validate-rrid/', views_ai_enhancement.validate_rrid, name='api_validate_rrid'),
    path('api/ai/recommend/', views_ai_enhancement.get_resource_recommendations, name='api_recommend_resources'),
    path('api/ai/chat/', views_ai_enhancement.conversational_krt, name='api_conversational_krt'),
    
    # Browser Extension API
    path('api/browser/suggest-rrid/', views_ai_enhancement.browser_extension_suggest_rrid, name='api_browser_suggest_rrid'),
    path('api/browser/validate-rrid/', views_ai_enhancement.browser_extension_validate_rrid, name='api_browser_validate_rrid'),
]