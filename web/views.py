import os
import json
import uuid
import time
import tempfile
from datetime import datetime, timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.files.storage import default_storage
from django.utils.decorators import method_decorator
from django.views.generic import FormView, TemplateView
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone

from .forms import KRTMakerForm, FeedbackForm
from .models import KRTSession, ProcessedFile, KRTExport, SystemMetrics, Article

# Import the KRT maker functionality (using project root path)
from django.conf import settings
import sys
import os

# Add project root to path only once during module import
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from builder import build_from_xml_path, BuildOptions
from validation import validate_xml_file, validate_api_config, ValidationError as KRTValidationError
from biorxiv_fetcher import BioRxivFetcher


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
    
    def get_context_data(self, **kwargs):
        """Add model choices to context for JavaScript synchronization"""
        context = super().get_context_data(**kwargs)
        
        # Add model choices for JavaScript - ensures Django and JS stay synchronized
        from .forms import KRTMakerForm
        form = KRTMakerForm()
        context['model_choices'] = {
            'anthropic': form.ANTHROPIC_MODELS,
            'gemini': form.GEMINI_MODELS,
            'openai_compatible': form.OPENAI_COMPATIBLE_MODELS,
        }
        
        return context
    
    def form_valid(self, form):
        """Process the form and extract KRT"""
        # Generate unique session ID
        session_id = uuid.uuid4().hex[:16]
        
        # Get form data
        input_method = form.cleaned_data['input_method']
        xml_file = form.cleaned_data.get('xml_file')
        biorxiv_url = form.cleaned_data.get('biorxiv_url')
        mode = form.cleaned_data['mode']
        provider = form.cleaned_data.get('provider')
        model = form.cleaned_data.get('model')
        base_url = form.cleaned_data.get('base_url')
        api_key = form.cleaned_data.get('api_key')
        extra_instructions = form.cleaned_data.get('extra_instructions')
        
        # Handle input method - get XML file path and metadata
        xml_path = None
        original_filename = "unknown.xml"
        file_size = 0
        temp_xml_path = None  # For cleanup if downloaded
        temp_path = None  # For Django file storage cleanup (uploads only)
        
        try:
            if input_method == 'upload' and xml_file:
                # File upload method
                original_filename = xml_file.name
                file_size = xml_file.size
                
                # Save uploaded file to system temp directory (NOT in project media directory)
                # This prevents Django auto-reloader from detecting the file and restarting
                temp_file = tempfile.NamedTemporaryFile(
                    mode='wb',
                    suffix=f"_{original_filename}",
                    delete=False,
                    dir=tempfile.gettempdir()  # Use system temp directory
                )
                
                # Copy uploaded file content to temp file
                for chunk in xml_file.chunks():
                    temp_file.write(chunk)
                temp_file.close()
                
                xml_path = temp_file.name
                temp_xml_path = xml_path  # For cleanup via finally block
                # Note: For uploads, we don't use Django's default_storage since 
                # we're saving to system temp directory to avoid auto-reload issues
                
            elif input_method == 'url' and biorxiv_url:
                # bioRxiv URL method
                fetcher = BioRxivFetcher()
                
                # Parse DOI from URL
                doi = fetcher.parse_biorxiv_identifier(biorxiv_url)
                if not doi:
                    raise ValueError("Invalid bioRxiv URL or DOI")
                
                # Get metadata and download XML
                metadata, xml_path = fetcher.fetch_paper_info(biorxiv_url)
                if not xml_path:
                    raise ValueError(f"Could not download XML for {doi}")
                
                temp_xml_path = xml_path  # For cleanup
                original_filename = f"{doi.replace('10.1101/', '')}.xml"
                file_size = os.path.getsize(xml_path) if os.path.exists(xml_path) else 0
                
            else:
                raise ValueError("No valid input method provided")
            
            # Get bioRxiv metadata if available
            biorxiv_metadata = {}
            session_doi = None
            if input_method == 'url' and biorxiv_url:
                fetcher = BioRxivFetcher()
                session_doi = fetcher.parse_biorxiv_identifier(biorxiv_url)
                if session_doi:
                    biorxiv_metadata = fetcher.get_paper_metadata(session_doi) or {}
            
            # Create session record
            session = KRTSession.objects.create(
                session_id=session_id,
                original_filename=original_filename,
                file_size=file_size,
                input_method=input_method,
                doi=biorxiv_metadata.get('doi') or session_doi,
                biorxiv_id=biorxiv_metadata.get('biorxiv_id'),
                epmc_id=biorxiv_metadata.get('epmc_id'),
                authors=json.dumps(biorxiv_metadata.get('authors', [])) if biorxiv_metadata.get('authors') else None,
                publication_date=biorxiv_metadata.get('publication_date'),
                journal=biorxiv_metadata.get('journal'),
                keywords=json.dumps(biorxiv_metadata.get('keywords', [])) if biorxiv_metadata.get('keywords') else None,
                categories=json.dumps(biorxiv_metadata.get('categories', [])) if biorxiv_metadata.get('categories') else None,
                mode=mode,
                provider=provider,
                model_name=model,
                base_url=base_url,
                extra_instructions=extra_instructions,
                status='processing'
            )
            
            # Note: No ProcessedFile record needed since we use system temp files
            # This avoids Django auto-reload issues from file monitoring
            
            # Validate XML file
            validate_xml_file(xml_path)
            
            # Detect existing KRT in the article (import only when needed to avoid auto-reload)
            try:
                from krt_detector import detect_existing_krt, format_krt_data_for_display
                existing_krt_info = detect_existing_krt(xml_path)
                existing_krt_data = format_krt_data_for_display(existing_krt_info.get('krt_tables', []))
                
                # Update session with existing KRT info
                session.existing_krt_detected = existing_krt_info.get('has_krt', False)
                session.existing_krt_count = existing_krt_info.get('krt_count', 0)
                session.existing_krt_data = existing_krt_data
            except Exception as e:
                print(f"KRT detection failed: {e}")
                # Set default values if KRT detection fails
                session.existing_krt_detected = False
                session.existing_krt_count = 0
                session.existing_krt_data = []
            
            session.save()
            
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
            result = build_from_xml_path(xml_path, options)
            
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
            
            # Note: Temp files cleaned up in finally block below
            
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
            
        finally:
            # Clean up temporary bioRxiv XML file
            if temp_xml_path and os.path.exists(temp_xml_path):
                try:
                    os.unlink(temp_xml_path)
                except Exception:
                    pass  # Ignore cleanup errors


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


class ArticleDashboardView(TemplateView):
    """Dashboard showing all processed articles with their metadata and LLM comparison"""
    template_name = 'web/article_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get unique articles using the class method
        unique_articles = KRTSession.get_unique_articles()
        
        # Statistics
        total_articles = len(unique_articles)
        total_sessions = KRTSession.objects.filter(status='completed').count()
        biorxiv_articles = len([a for a in unique_articles if a['primary_session'].is_biorxiv_paper])
        
        # LLM usage statistics
        llm_stats = {}
        for article in unique_articles:
            for llm_result in article['llm_results']:
                provider_model = f"{llm_result['provider']}_{llm_result['model']}"
                if provider_model not in llm_stats:
                    llm_stats[provider_model] = {
                        'count': 0, 
                        'avg_resources': 0, 
                        'avg_time': 0,
                        'provider': llm_result['provider'],
                        'model': llm_result['model']
                    }
                llm_stats[provider_model]['count'] += 1
                llm_stats[provider_model]['avg_resources'] += llm_result['resources_found']
                llm_stats[provider_model]['avg_time'] += llm_result['processing_time'] or 0
        
        # Calculate averages
        for stats in llm_stats.values():
            if stats['count'] > 0:
                stats['avg_resources'] = round(stats['avg_resources'] / stats['count'], 1)
                stats['avg_time'] = round(stats['avg_time'] / stats['count'], 2)
        
        context.update({
            'articles': unique_articles,
            'total_articles': total_articles,
            'total_sessions': total_sessions,
            'biorxiv_articles': biorxiv_articles,
            'upload_articles': total_articles - biorxiv_articles,
            'llm_stats': list(llm_stats.values()),
        })
        
        return context


class ArticleProfileView(TemplateView):
    """Detailed profile page for a specific article showing all LLM results and metadata"""
    template_name = 'web/article_profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get article identifier from URL
        identifier = kwargs.get('identifier')
        
        # Find sessions for this article (by DOI or session_id)
        if identifier.startswith('10.1101/'):
            # DOI identifier
            sessions = KRTSession.objects.filter(doi=identifier, status='completed').order_by('-created_at')
            article_key = identifier
        else:
            # Session ID identifier - find by session and then group by DOI/filename
            try:
                primary_session = KRTSession.objects.get(session_id=identifier, status='completed')
                article_key = primary_session.doi or primary_session.original_filename
                sessions = KRTSession.objects.filter(
                    Q(doi=article_key) | Q(original_filename=article_key),
                    status='completed'
                ).order_by('-created_at')
            except KRTSession.DoesNotExist:
                messages.error(self.request, 'Article not found.')
                return redirect('web:article_dashboard')
        
        if not sessions.exists():
            messages.error(self.request, 'Article not found.')
            return redirect('web:article_dashboard')
        
        # Primary session (most recent or best)
        primary_session = sessions.first()
        
        # Group sessions by LLM model
        llm_results = {}
        regex_results = []
        
        for session in sessions:
            if session.mode == 'llm':
                key = f"{session.provider}_{session.model_name}"
                if key not in llm_results:
                    llm_results[key] = {
                        'provider': session.provider,
                        'model': session.model_name,
                        'sessions': [],
                        'best_session': session,
                        'avg_resources': 0,
                        'avg_time': 0
                    }
                
                llm_results[key]['sessions'].append(session)
                
                # Update best session
                if session.resources_found > llm_results[key]['best_session'].resources_found:
                    llm_results[key]['best_session'] = session
            else:
                regex_results.append(session)
        
        # Calculate averages for each LLM
        for result in llm_results.values():
            sessions_list = result['sessions']
            result['avg_resources'] = sum(s.resources_found for s in sessions_list) / len(sessions_list)
            result['avg_time'] = sum(s.processing_time or 0 for s in sessions_list) / len(sessions_list)
        
        # Check for existing KRT in the article
        existing_krt_info = self._detect_existing_krt(primary_session)
        
        context.update({
            'primary_session': primary_session,
            'all_sessions': sessions,
            'llm_results': list(llm_results.values()),
            'regex_results': regex_results,
            'total_sessions': sessions.count(),
            'article_key': article_key,
            'existing_krt_info': existing_krt_info,
        })
        
        return context
    
    def _detect_existing_krt(self, session):
        """Detect if the article already contains KRT tables"""
        return {
            'has_krt': session.existing_krt_detected,
            'krt_count': session.existing_krt_count,
            'krt_data': session.existing_krt_data
        }