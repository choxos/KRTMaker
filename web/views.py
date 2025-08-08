import os
import json
import uuid
import time
from datetime import datetime, timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.files.storage import default_storage
from django.utils.decorators import method_decorator
from django.views.generic import FormView, TemplateView
from django.db.models import Count, Avg, Sum
from django.utils import timezone

from .forms import KRTMakerForm, FeedbackForm
from .models import KRTSession, ProcessedFile, KRTExport, SystemMetrics

# Import the KRT maker functionality
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from builder import build_from_xml_path, BuildOptions
from validation import validate_xml_file, validate_api_config, ValidationError as KRTValidationError


class HomeView(TemplateView):
    """Beautiful homepage with features and getting started info"""
    template_name = 'web/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get some basic stats for the homepage
        total_sessions = KRTSession.objects.count()
        successful_sessions = KRTSession.objects.filter(status='completed').count()
        total_resources = KRTSession.objects.aggregate(Sum('resources_found'))['resources_found__sum'] or 0
        
        context.update({
            'total_sessions': total_sessions,
            'successful_sessions': successful_sessions,
            'total_resources': total_resources,
            'success_rate': round((successful_sessions / total_sessions * 100) if total_sessions > 0 else 0, 1),
        })
        
        return context


class KRTMakerView(FormView):
    """Main KRT maker form and processing view"""
    template_name = 'web/krt_maker.html'
    form_class = KRTMakerForm
    
    def form_valid(self, form):
        """Process the form and extract KRT"""
        # Generate unique session ID
        session_id = uuid.uuid4().hex[:16]
        
        # Get form data
        xml_file = form.cleaned_data['xml_file']
        mode = form.cleaned_data['mode']
        provider = form.cleaned_data.get('provider')
        model = form.cleaned_data.get('model')
        base_url = form.cleaned_data.get('base_url')
        api_key = form.cleaned_data.get('api_key')
        extra_instructions = form.cleaned_data.get('extra_instructions')
        
        # Create session record
        session = KRTSession.objects.create(
            session_id=session_id,
            original_filename=xml_file.name,
            file_size=xml_file.size,
            mode=mode,
            provider=provider,
            model_name=model,
            base_url=base_url,
            extra_instructions=extra_instructions,
            status='processing'
        )
        
        try:
            # Save uploaded file temporarily
            temp_path = default_storage.save(f"temp/{session_id}_{xml_file.name}", xml_file)
            abs_path = default_storage.path(temp_path)
            
            # Create ProcessedFile record
            ProcessedFile.objects.create(
                session=session,
                file=temp_path
            )
            
            # Validate file
            validate_xml_file(abs_path)
            
            # Build options for KRT extraction
            options = BuildOptions(
                mode='llm' if mode == 'llm' else 'regex',
                provider=provider,
                model=model,
                base_url=base_url,
                api_key=api_key,
                extra_instructions=extra_instructions,
            )
            
            # Validate LLM configuration if needed
            if mode == 'llm':
                validate_api_config(provider or "openai", api_key, model)
            
            # Record start time
            start_time = time.time()
            
            # Extract KRT
            result = build_from_xml_path(abs_path, options)
            
            # Record processing time
            processing_time = time.time() - start_time
            
            # Update session with results
            session.status = 'completed'
            session.title = result.get('title', '')
            session.abstract = result.get('abstract', '')
            session.krt_data = result.get('rows', [])
            session.processing_time = processing_time
            session.save()
            
            # Update analytics
            session.update_analytics()
            
            # Clean up temporary file
            default_storage.delete(temp_path)
            
            messages.success(
                self.request, 
                f'KRT extraction completed successfully! Found {len(result.get("rows", []))} resources in {processing_time:.1f} seconds.'
            )
            
            return redirect('web:results', session_id=session_id)
            
        except KRTValidationError as e:
            session.status = 'failed'
            session.error_message = str(e)
            session.save()
            
            messages.error(self.request, f'Validation error: {e}')
            return self.form_invalid(form)
            
        except Exception as e:
            session.status = 'failed'
            session.error_message = str(e)
            session.save()
            
            messages.error(self.request, f'Processing error: {e}')
            return self.form_invalid(form)


class ResultsView(TemplateView):
    """Display KRT extraction results"""
    template_name = 'web/results.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = kwargs.get('session_id')
        
        try:
            session = get_object_or_404(KRTSession, session_id=session_id)
            context['session'] = session
            
            if session.status == 'completed':
                # Process KRT data for display
                krt_data = session.krt_data or []
                
                # Group by resource type for better visualization
                resource_types = {}
                for row in krt_data:
                    resource_type = row.get('RESOURCE TYPE', 'Other')
                    if resource_type not in resource_types:
                        resource_types[resource_type] = []
                    resource_types[resource_type].append(row)
                
                context.update({
                    'krt_data': krt_data,
                    'resource_types': resource_types,
                    'resource_count': len(krt_data),
                    'new_count': len([r for r in krt_data if r.get('NEW/REUSE', '').lower() == 'new']),
                    'reuse_count': len([r for r in krt_data if r.get('NEW/REUSE', '').lower() == 'reuse']),
                })
            
        except KRTSession.DoesNotExist:
            messages.error(self.request, 'Session not found or expired.')
            return redirect('web:home')
        
        return context