"""
Views for AI Enhancement Features

This module contains views for the new AI enhancement features including
RRID suggestions, resource recommendations, conversational KRT creation,
cross-reference validation, and multimodal processing.
"""

import json
# import asyncio  # No longer needed with synchronous AI modules
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from django.db import models
from django.db.models import Count, Avg, Q
import logging

from .models import (
    RRIDSuggestion, ResourceRecommendation, ConversationalKRTSession,
    CrossReferenceValidation, MultimodalProcessingResult, AIEnhancementUsage,
    KRTSession
)

# Import the AI enhancement modules
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import our new AI enhancement systems
try:
    from new_ideas.rrid_enhancement_system_simple import RRIDEnhancementSystem, BrowserExtensionAPI
    from new_ideas.smart_recommendation_engine_simple import SmartRecommendationEngine
    from new_ideas.natural_language_interface_simple import ConversationalKRTInterface
    from new_ideas.cross_reference_validation_simple import CrossReferenceValidator
    from new_ideas.multimodal_ai_processor import MultimodalKRTProcessor
except ImportError as e:
    logging.warning(f"Could not import AI enhancement modules: {e}")
    # Create stub classes for development
    class RRIDEnhancementSystem:
        def __init__(self): pass
        def suggest_rrid(self, *args, **kwargs): return []
        def validate_rrid(self, *args, **kwargs): return type('ValidationResult', (), {'rrid': '', 'is_valid': False, 'status': 'error', 'resource_info': {}})()
    
    class SmartRecommendationEngine:
        def __init__(self): pass
        def recommend_alternatives(self, *args, **kwargs): return []
    
    class ConversationalKRTInterface:
        def __init__(self, *args, **kwargs): pass
        def process_message(self, *args, **kwargs): return {'response': 'AI not available', 'intent': 'error'}
    
    class CrossReferenceValidator:
        def __init__(self): pass
        def validate_resource(self, *args, **kwargs): return {'success': False, 'error': 'Not implemented'}
    
    class MultimodalKRTProcessor:
        def __init__(self, *args, **kwargs): pass
        def extract_from_pdf(self, *args, **kwargs): return []
    
    class BrowserExtensionAPI:
        def __init__(self, *args, **kwargs): pass
        def suggest_rrid_api(self, *args, **kwargs): return {'status': 'error', 'error': 'Not implemented'}
        def validate_rrid_api(self, *args, **kwargs): return {'status': 'error', 'error': 'Not implemented'}

logger = logging.getLogger(__name__)


# Initialize AI enhancement systems
logger.info("Initializing AI enhancement systems...")
try:
    rrid_system = RRIDEnhancementSystem()
    recommendation_engine = SmartRecommendationEngine()
    conversational_interface = ConversationalKRTInterface()
    cross_validator = CrossReferenceValidator()
    multimodal_processor = MultimodalKRTProcessor()
    browser_api = BrowserExtensionAPI(rrid_system)
    logger.info("AI enhancement systems initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AI enhancement systems: {e}")
    # Use stub systems
    rrid_system = RRIDEnhancementSystem()
    recommendation_engine = SmartRecommendationEngine()
    conversational_interface = ConversationalKRTInterface()
    cross_validator = CrossReferenceValidator()
    multimodal_processor = MultimodalKRTProcessor()
    browser_api = BrowserExtensionAPI(rrid_system)
    logger.warning("Using stub AI enhancement systems")


class AIEnhancementDashboardView(TemplateView):
    """Dashboard view for AI enhancement features"""
    template_name = 'web/ai_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get usage statistics
        today = timezone.now().date()
        usage_stats_raw = AIEnhancementUsage.objects.filter(
            created_at__date=today
        ).values('feature_type').annotate(
            total_requests=Count('id'),
            successful_requests=Count('id', filter=Q(success=True)),
            failed_requests=Count('id', filter=Q(success=False)),
            avg_response_time=Avg('response_time')
        )
        
        # Calculate success rates and format data
        usage_stats = []
        for usage in usage_stats_raw:
            total = usage['total_requests'] or 0
            successful = usage['successful_requests'] or 0
            success_rate_percent = (successful / total * 100) if total > 0 else 0
            
            # Determine badge color based on success rate
            if success_rate_percent >= 90:
                badge_color = 'success'
            elif success_rate_percent >= 70:
                badge_color = 'warning'
            else:
                badge_color = 'danger'
            
            usage_stats.append({
                'feature_type': usage['feature_type'],
                'total_requests': total,
                'successful_requests': successful,
                'failed_requests': usage['failed_requests'] or 0,
                'success_rate_percent': round(success_rate_percent, 1),
                'badge_color': badge_color,
                'avg_response_time': usage['avg_response_time'] or 0.0
            })
        
        context.update({
            'usage_stats': usage_stats,
            'total_rrid_suggestions': RRIDSuggestion.objects.count(),
            'total_recommendations': ResourceRecommendation.objects.count(),
            'active_conversations': ConversationalKRTSession.objects.filter(is_active=True).count(),
            'total_validations': CrossReferenceValidation.objects.count(),
        })
        
        return context


@csrf_exempt
@require_http_methods(["POST"])
def suggest_rrid(request):
    """API endpoint for RRID suggestions"""
    try:
        data = json.loads(request.body)
        resource_name = data.get('resource_name', '')
        resource_type = data.get('resource_type', '')
        vendor = data.get('vendor', '')
        catalog_number = data.get('catalog_number', '')
        
        if not resource_name:
            return JsonResponse({'error': 'resource_name is required'}, status=400)
        
        # Log the request
        start_time = datetime.now()
        
        # Get suggestions using our RRID enhancement system
        try:
            suggestions = rrid_system.suggest_rrid(
                resource_name=resource_name,
                resource_type=resource_type,
                vendor=vendor,
                catalog_number=catalog_number
            )
            
            # Store suggestions in database
            stored_suggestions = []
            for suggestion in suggestions:
                rrid_suggestion = RRIDSuggestion.objects.create(
                    resource_name=resource_name,
                    resource_type=resource_type,
                    vendor=vendor or suggestion.vendor,
                    catalog_number=catalog_number or suggestion.catalog_number,
                    suggested_rrid=suggestion.suggested_rrid,
                    suggestion_type='rrid_suggestion',
                    validation_status='valid',  # Assume valid for now
                    validation_source='rrid_enhancement_system',
                    confidence_score=suggestion.confidence_score,
                    reasoning=suggestion.reasoning if hasattr(suggestion, 'reasoning') else 'AI generated suggestion'
                )
                stored_suggestions.append({
                    'id': rrid_suggestion.id,
                    'suggested_rrid': rrid_suggestion.suggested_rrid,
                    'confidence_score': rrid_suggestion.confidence_score,
                    'reasoning': rrid_suggestion.reasoning,
                    'vendor': rrid_suggestion.vendor,
                    'catalog_number': rrid_suggestion.catalog_number,
                })
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            # Log usage
            AIEnhancementUsage.log_usage(
                feature_type='rrid_suggestion',
                request_data=data,
                response_data={'suggestions_count': len(stored_suggestions)},
                response_time=response_time,
                success=True,
                user_session=request.session.session_key,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({
                'success': True,
                'suggestions': stored_suggestions,
                'total_found': len(stored_suggestions),
                'response_time': response_time
            })
            
        except Exception as e:
            logger.error(f"RRID suggestion error: {e}")
            
            # Log failed usage
            AIEnhancementUsage.log_usage(
                feature_type='rrid_suggestion',
                request_data=data,
                response_data={},
                response_time=(datetime.now() - start_time).total_seconds(),
                success=False,
                error_message=str(e),
                user_session=request.session.session_key,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({
                'success': False,
                'error': f'RRID suggestion error: {str(e)}',
                'suggestions': []
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"RRID suggestion endpoint error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def validate_rrid(request):
    """API endpoint for RRID validation"""
    try:
        data = json.loads(request.body)
        rrid = data.get('rrid', '')
        
        if not rrid:
            return JsonResponse({'error': 'rrid is required'}, status=400)
        
        start_time = datetime.now()
        
        # Check cache first
        cached_validation = CrossReferenceValidation.objects.filter(
            resource_identifier=rrid,
            expires_at__gt=timezone.now()
        ).first()
        
        if cached_validation:
            return JsonResponse({
                'success': True,
                'validation': {
                    'rrid': rrid,
                    'is_valid': cached_validation.overall_status == 'valid',
                    'status': cached_validation.overall_status,
                    'confidence_score': cached_validation.confidence_score,
                    'recommendations': cached_validation.recommendations,
                    'last_checked': cached_validation.created_at.isoformat(),
                    'source': 'cache'
                }
            })
        
        # Perform fresh validation
        try:
            validation_result = rrid_system.validate_rrid(rrid)
            
            # Store validation result
            expires_at = timezone.now() + timedelta(hours=24)  # Cache for 24 hours
            cross_validation = CrossReferenceValidation.objects.create(
                resource_identifier=rrid,
                resource_type='rrid',
                overall_status='valid' if validation_result.is_valid else 'invalid',
                confidence_score=0.9 if validation_result.is_valid else 0.1,
                validation_results=[{
                    'source': 'rrid_system',
                    'status': validation_result.status,
                    'resource_info': validation_result.resource_info,
                }],
                discrepancies=[],
                recommendations=[],
                validation_sources=['rrid_system'],
                expires_at=expires_at
            )
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            # Log usage
            AIEnhancementUsage.log_usage(
                feature_type='cross_validation',
                request_data=data,
                response_data={'is_valid': validation_result.is_valid},
                response_time=response_time,
                success=True,
                user_session=request.session.session_key,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({
                'success': True,
                'validation': {
                    'rrid': rrid,
                    'is_valid': validation_result.is_valid,
                    'status': validation_result.status,
                    'confidence_score': cross_validation.confidence_score,
                    'recommendations': cross_validation.recommendations,
                    'last_checked': cross_validation.created_at.isoformat(),
                    'source': 'fresh'
                }
            })
            
        except Exception as e:
            logger.error(f"RRID validation error: {e}")
            
            # Log failed usage
            AIEnhancementUsage.log_usage(
                feature_type='cross_validation',
                request_data=data,
                response_data={},
                response_time=(datetime.now() - start_time).total_seconds(),
                success=False,
                error_message=str(e),
                user_session=request.session.session_key,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({
                'success': False,
                'error': 'RRID validation service temporarily unavailable'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"RRID validation endpoint error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_resource_recommendations(request):
    """API endpoint for resource recommendations"""
    try:
        data = json.loads(request.body)
        resource_name = data.get('resource_name', '')
        resource_type = data.get('resource_type', '')
        context = data.get('context', {})
        
        if not resource_name:
            return JsonResponse({'error': 'resource_name is required'}, status=400)
        
        start_time = datetime.now()
        
        try:
            recommendations = recommendation_engine.recommend_alternatives(
                resource_name=resource_name,
                resource_type=resource_type,
                context=context,
                max_recommendations=5
            )
            
            # Store recommendations in database
            stored_recommendations = []
            for rec in recommendations:
                resource_rec = ResourceRecommendation.objects.create(
                    original_resource=resource_name,
                    original_vendor=context.get('vendor', ''),
                    original_catalog=context.get('catalog_number', ''),
                    recommended_resource=rec.recommended_resource,
                    recommended_vendor=rec.vendor,
                    recommended_catalog=rec.catalog_number,
                    recommendation_type=rec.recommendation_type,
                    similarity_score=rec.similarity_score,
                    confidence_score=rec.confidence_score,
                    reasoning=rec.reasoning,
                    availability_status=rec.availability_status
                )
                stored_recommendations.append({
                    'id': resource_rec.id,
                    'recommended_resource': resource_rec.recommended_resource,
                    'recommended_vendor': resource_rec.recommended_vendor,
                    'recommended_catalog': resource_rec.recommended_catalog,
                    'recommendation_type': resource_rec.recommendation_type,
                    'confidence_score': resource_rec.confidence_score,
                    'reasoning': resource_rec.reasoning,
                    'availability_status': resource_rec.availability_status,
                })
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            # Log usage
            AIEnhancementUsage.log_usage(
                feature_type='resource_recommendation',
                request_data=data,
                response_data={'recommendations_count': len(stored_recommendations)},
                response_time=response_time,
                success=True,
                user_session=request.session.session_key,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({
                'success': True,
                'recommendations': stored_recommendations,
                'total_found': len(stored_recommendations),
                'response_time': response_time
            })
            
        except Exception as e:
            logger.error(f"Resource recommendation error: {e}")
            
            # Log failed usage
            AIEnhancementUsage.log_usage(
                feature_type='resource_recommendation',
                request_data=data,
                response_data={},
                response_time=(datetime.now() - start_time).total_seconds(),
                success=False,
                error_message=str(e),
                user_session=request.session.session_key,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({
                'success': False,
                'error': 'Resource recommendation service temporarily unavailable',
                'recommendations': []
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Resource recommendation endpoint error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def conversational_krt(request):
    """API endpoint for conversational KRT creation"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '')
        session_id = data.get('session_id', '')
        
        if not message:
            return JsonResponse({'error': 'message is required'}, status=400)
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        start_time = datetime.now()
        
        try:
            # Get or create conversational session
            conv_session, created = ConversationalKRTSession.objects.get_or_create(
                session_id=session_id,
                defaults={'is_active': True}
            )
            
            # Process the message
            response_data = conversational_interface.process_message(message, session_id)
            
            # Update the conversation session
            conv_session.add_message(
                user_message=message,
                bot_response=response_data['response'],
                intent=response_data.get('intent'),
                entities=response_data.get('extracted_entities', [])
            )
            
            # Update KRT entries if changed
            if response_data.get('krt_entries'):
                conv_session.current_krt_entries = response_data['krt_entries']
                conv_session.resources_added = len(response_data['krt_entries'])
                conv_session.save()
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            # Log usage
            AIEnhancementUsage.log_usage(
                feature_type='conversational_krt',
                request_data={'message_length': len(message)},
                response_data={'intent': response_data.get('intent'), 'krt_entries_count': len(response_data.get('krt_entries', []))},
                response_time=response_time,
                success=True,
                user_session=session_id,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({
                'success': True,
                'session_id': session_id,
                'response': response_data['response'],
                'intent': response_data.get('intent'),
                'krt_entries': response_data.get('krt_entries', []),
                'needs_clarification': response_data.get('needs_clarification', False),
                'clarifications': response_data.get('clarifications', []),
                'response_time': response_time
            })
            
        except Exception as e:
            logger.error(f"Conversational KRT error: {e}")
            
            # Log failed usage
            AIEnhancementUsage.log_usage(
                feature_type='conversational_krt',
                request_data={'message_length': len(message)},
                response_data={},
                response_time=(datetime.now() - start_time).total_seconds(),
                success=False,
                error_message=str(e),
                user_session=session_id,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({
                'success': False,
                'error': 'Conversational KRT service temporarily unavailable',
                'response': "I'm sorry, but I'm having trouble processing your request right now. Please try again later."
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Conversational KRT endpoint error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


# Browser Extension API Endpoints
@csrf_exempt
@require_http_methods(["POST"])
def browser_extension_suggest_rrid(request):
    """Browser extension API for RRID suggestions"""
    try:
        data = json.loads(request.body)
        
        # Use the browser extension API
        response_data = browser_api.suggest_rrid_api(data)
        
        # Log usage
        AIEnhancementUsage.log_usage(
            feature_type='browser_extension',
            request_data=data,
            response_data=response_data,
            success=response_data.get('status') == 'success',
            user_session=request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Browser extension RRID suggestion error: {e}")
        return JsonResponse({
            'status': 'error',
            'error': 'Service temporarily unavailable'
        })


@csrf_exempt
@require_http_methods(["POST"])
def browser_extension_validate_rrid(request):
    """Browser extension API for RRID validation"""
    try:
        data = json.loads(request.body)
        
        # Use the browser extension API
        response_data = browser_api.validate_rrid_api(data)
        
        # Log usage
        AIEnhancementUsage.log_usage(
            feature_type='browser_extension',
            request_data=data,
            response_data=response_data,
            success=response_data.get('status') == 'success',
            user_session=request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Browser extension RRID validation error: {e}")
        return JsonResponse({
            'status': 'error',
            'error': 'Service temporarily unavailable'
        })


class ConversationalKRTView(TemplateView):
    """View for the conversational KRT interface"""
    template_name = 'web/conversational_krt.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session_id'] = str(uuid.uuid4())
        return context


class AIFeaturesView(TemplateView):
    """View showcasing all AI enhancement features"""
    template_name = 'web/ai_features.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent usage statistics
        recent_usage_raw = AIEnhancementUsage.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).values('feature_type').annotate(
            total_requests=Count('id'),
            successful_requests=Count('id', filter=models.Q(success=True)),
            failed_requests=Count('id', filter=models.Q(success=False)),
            avg_response_time=Avg('response_time')
        )
        
        # Calculate success rates and format data
        recent_usage = []
        for usage in recent_usage_raw:
            total = usage['total_requests'] or 0
            successful = usage['successful_requests'] or 0
            success_rate_percent = (successful / total * 100) if total > 0 else 0
            
            # Determine badge color based on success rate
            if success_rate_percent >= 90:
                badge_color = 'success'
            elif success_rate_percent >= 70:
                badge_color = 'warning'
            else:
                badge_color = 'danger'
            
            recent_usage.append({
                'feature_type': usage['feature_type'],
                'total_requests': total,
                'successful_requests': successful,
                'failed_requests': usage['failed_requests'] or 0,
                'success_rate_percent': round(success_rate_percent, 1),
                'badge_color': badge_color,
                'avg_response_time': usage['avg_response_time'] or 0.0
            })
        
        context.update({
            'recent_usage': recent_usage,
            'features': [
                {
                    'name': 'RRID Suggestions',
                    'description': 'Get intelligent RRID suggestions for your resources',
                    'endpoint': '/ai/suggest-rrid/',
                    'icon': '🔍'
                },
                {
                    'name': 'Resource Recommendations',
                    'description': 'Find alternative resources based on functional similarity',
                    'endpoint': '/ai/recommend/',
                    'icon': '💡'
                },
                {
                    'name': 'Conversational KRT',
                    'description': 'Create KRT tables through natural language conversation',
                    'endpoint': '/ai/chat/',
                    'icon': '💬'
                },
                {
                    'name': 'Cross-Reference Validation',
                    'description': 'Validate resources across multiple databases',
                    'endpoint': '/ai/validate/',
                    'icon': '✅'
                },
                {
                    'name': 'Browser Extension',
                    'description': 'Real-time RRID suggestions while writing manuscripts',
                    'endpoint': '/ai/browser-extension/',
                    'icon': '🌐'
                }
            ]
        })
        
        return context
