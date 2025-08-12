from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
import json

from .models import Article, KRTSession, ProcessedFile, KRTExport, SystemMetrics, XMLFile, AdminKRT


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title_short', 'doi_link', 'journal', 'publication_date', 'total_sessions', 'has_existing_krt', 'last_processed']
    list_filter = ['journal', 'publication_date', 'has_existing_krt', 'last_processed']
    search_fields = ['title', 'doi', 'authors', 'abstract']
    readonly_fields = ['doi', 'first_processed', 'last_processed', 'total_sessions', 'session_links']
    ordering = ['-last_processed']
    
    fieldsets = (
        ('Article Information', {
            'fields': ('title', 'doi_link', 'journal', 'publication_date')
        }),
        ('Content', {
            'fields': ('abstract', 'authors_display', 'keywords_display'),
            'classes': ('collapse',)
        }),
        ('KRT Analysis', {
            'fields': ('has_existing_krt', 'existing_krt_count', 'existing_krt_display')
        }),
        ('Database Info', {
            'fields': ('total_sessions', 'session_links', 'first_processed', 'last_processed'),
            'classes': ('collapse',)
        })
    )
    
    def title_short(self, obj):
        return obj.title[:80] + '...' if len(obj.title) > 80 else obj.title
    title_short.short_description = 'Title'
    
    def doi_link(self, obj):
        if obj.doi:
            return format_html('<a href="https://doi.org/{}" target="_blank">{}</a>', obj.doi, obj.doi)
        return 'No DOI'
    doi_link.short_description = 'DOI'
    
    def authors_display(self, obj):
        try:
            authors = json.loads(obj.authors) if obj.authors else []
            if len(authors) > 5:
                return ', '.join(authors[:5]) + f' ... ({len(authors)} total)'
            return ', '.join(authors)
        except:
            return obj.authors
    authors_display.short_description = 'Authors'
    
    def keywords_display(self, obj):
        try:
            keywords = json.loads(obj.keywords) if obj.keywords else []
            return ', '.join(keywords[:10])
        except:
            return obj.keywords
    keywords_display.short_description = 'Keywords'
    
    def existing_krt_display(self, obj):
        if obj.existing_krt_data:
            try:
                krt_data = obj.existing_krt_data if isinstance(obj.existing_krt_data, list) else json.loads(obj.existing_krt_data)
                return f'{len(krt_data)} KRT entries found'
            except:
                return 'KRT data present'
        return 'No existing KRT'
    existing_krt_display.short_description = 'Existing KRT'
    
    def session_links(self, obj):
        sessions = obj.sessions.all()[:5]
        links = []
        for session in sessions:
            url = reverse('admin:web_krtsession_change', args=[session.pk])
            links.append(format_html('<a href="{}">{}</a>', url, session.session_id[:8]))
        
        if obj.total_sessions > 5:
            links.append(f'... ({obj.total_sessions - 5} more)')
        
        return format_html(' | '.join(links)) if links else 'No sessions'
    session_links.short_description = 'Recent Sessions'


@admin.register(KRTSession)
class KRTSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id_short', 'article_link', 'mode', 'provider_model', 'status', 'resources_found', 'created_at']
    list_filter = ['status', 'mode', 'provider', 'input_method', 'created_at']
    search_fields = ['session_id', 'doi', 'biorxiv_id', 'article__title']
    readonly_fields = ['session_id', 'created_at', 'processing_time', 'article_link']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Session Info', {
            'fields': ('session_id', 'article_link', 'status', 'created_at', 'processing_time')
        }),
        ('Input', {
            'fields': ('input_method', 'uploaded_file', 'doi', 'biorxiv_id', 'epmc_id')
        }),
        ('Processing', {
            'fields': ('mode', 'provider', 'model_name', 'temperature', 'max_tokens')
        }),
        ('Results', {
            'fields': ('resources_found', 'krt_data_display', 'validation_display'),
            'classes': ('collapse',)
        }),
        ('Article Metadata', {
            'fields': ('authors', 'publication_date', 'journal', 'keywords'),
            'classes': ('collapse',)
        })
    )
    
    def session_id_short(self, obj):
        return obj.session_id[:12] + '...' if len(obj.session_id) > 12 else obj.session_id
    session_id_short.short_description = 'Session ID'
    
    def article_link(self, obj):
        if obj.article:
            url = reverse('admin:web_article_change', args=[obj.article.pk])
            return format_html('<a href="{}">{}</a>', url, obj.article.title[:50] + '...' if len(obj.article.title) > 50 else obj.article.title)
        return 'No article linked'
    article_link.short_description = 'Article'
    
    def provider_model(self, obj):
        if obj.provider and obj.model_name:
            return f'{obj.provider}/{obj.model_name}'
        return obj.mode
    provider_model.short_description = 'Provider/Model'
    
    def krt_data_display(self, obj):
        if obj.krt_data:
            return f'{len(obj.krt_data)} KRT entries'
        return 'No KRT data'
    krt_data_display.short_description = 'KRT Data'
    
    def validation_display(self, obj):
        if hasattr(obj, 'validation_results') and obj.validation_results:
            warnings = obj.validation_results.get('warnings', 0)
            score = obj.validation_results.get('quality_score', 0)
            return f'Score: {score}, Warnings: {warnings}'
        return 'Not validated'
    validation_display.short_description = 'Validation'


@admin.register(ProcessedFile)
class ProcessedFileAdmin(admin.ModelAdmin):
    list_display = ['file_display', 'session_link', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['file', 'session__session_id']
    readonly_fields = ['uploaded_at']
    
    def file_display(self, obj):
        if obj.file:
            return obj.file.name.split('/')[-1]  # Get filename from path
        return 'No file'
    file_display.short_description = 'File'
    
    def session_link(self, obj):
        if obj.session:
            url = reverse('admin:web_krtsession_change', args=[obj.session.pk])
            return format_html('<a href="{}">{}</a>', url, obj.session.session_id[:12])
        return 'No session'
    session_link.short_description = 'Session'


@admin.register(KRTExport)
class KRTExportAdmin(admin.ModelAdmin):
    list_display = ['session_link', 'format', 'exported_at', 'ip_address']
    list_filter = ['format', 'exported_at']
    search_fields = ['session__session_id', 'ip_address']
    readonly_fields = ['exported_at']
    
    def session_link(self, obj):
        if obj.session:
            url = reverse('admin:web_krtsession_change', args=[obj.session.pk])
            return format_html('<a href="{}">{}</a>', url, obj.session.session_id[:12])
        return 'No session'
    session_link.short_description = 'Session'


@admin.register(SystemMetrics)
class SystemMetricsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_sessions', 'total_resources_extracted', 'average_processing_time', 'llm_sessions']
    list_filter = ['date']
    readonly_fields = ['date']
    ordering = ['-date']


# Add some custom admin actions
@admin.action(description='Recalculate article session counts')
def recalculate_session_counts(modeladmin, request, queryset):
    for article in queryset:
        article.total_sessions = article.sessions.count()
        article.save()

ArticleAdmin.actions = [recalculate_session_counts]


@admin.register(XMLFile)
class XMLFileAdmin(admin.ModelAdmin):
    list_display = ['doi', 'title_short', 'file_size_display', 'publication_date', 'is_available', 'downloaded_at']
    list_filter = ['is_available', 'journal', 'publication_date', 'downloaded_at']
    search_fields = ['doi', 'title', 'authors', 'epmc_id']
    readonly_fields = ['doi', 'file_hash', 'downloaded_at', 'last_checked', 'file_path_display']
    ordering = ['-downloaded_at']
    
    fieldsets = (
        ('Paper Information', {
            'fields': ('doi', 'epmc_id', 'title', 'authors_display', 'publication_date', 'journal')
        }),
        ('File Information', {
            'fields': ('file_path_display', 'file_size_display', 'file_hash', 'download_source')
        }),
        ('Status', {
            'fields': ('is_available', 'error_message', 'downloaded_at', 'last_checked')
        })
    )
    
    def title_short(self, obj):
        return obj.title[:60] + '...' if obj.title and len(obj.title) > 60 else obj.title or 'No Title'
    title_short.short_description = 'Title'
    
    def file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size > 1024 * 1024:
                return f'{obj.file_size / (1024 * 1024):.1f} MB'
            elif obj.file_size > 1024:
                return f'{obj.file_size / 1024:.1f} KB'
            else:
                return f'{obj.file_size} bytes'
        return 'Unknown'
    file_size_display.short_description = 'File Size'
    
    def file_path_display(self, obj):
        import os
        if obj.file_path and os.path.exists(obj.full_file_path):
            return format_html('<code>{}</code> ✅', obj.file_path)
        else:
            return format_html('<code>{}</code> ❌ Missing', obj.file_path)
    file_path_display.short_description = 'File Path'
    
    def authors_display(self, obj):
        try:
            authors = json.loads(obj.authors) if obj.authors else []
            if len(authors) > 3:
                return ', '.join(authors[:3]) + f' ... ({len(authors)} total)'
            return ', '.join(authors)
        except:
            return obj.authors[:50] + '...' if obj.authors and len(obj.authors) > 50 else obj.authors
    authors_display.short_description = 'Authors'


@admin.register(AdminKRT)
class AdminKRTAdmin(admin.ModelAdmin):
    list_display = ['doi_short', 'formatted_provider_model', 'status', 'quality_rating', 'resources_found', 'processing_time_display', 'is_public', 'created_at']
    list_filter = ['status', 'quality_rating', 'provider', 'is_public', 'is_featured', 'created_at']
    search_fields = ['doi', 'xml_file__title', 'model_name', 'admin_notes']
    readonly_fields = ['doi', 'epmc_id', 'created_at', 'updated_at', 'resources_found', 'new_resources', 'reused_resources', 'xml_file_link', 'article_link', 'krt_preview']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Paper Information', {
            'fields': ('xml_file_link', 'article_link', 'doi', 'epmc_id')
        }),
        ('LLM Configuration', {
            'fields': ('provider', 'model_name', 'base_url')
        }),
        ('Generation Results', {
            'fields': ('status', 'processing_time_display', 'resources_found', 'new_resources', 'reused_resources', 'token_usage_display', 'cost_estimate')
        }),
        ('Quality Assessment', {
            'fields': ('quality_rating', 'admin_notes', 'is_public', 'is_featured')
        }),
        ('Approval Workflow', {
            'fields': ('created_by', 'approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
        ('KRT Data Preview', {
            'fields': ('krt_preview',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'error_message', 'retry_count'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['approve_krts', 'mark_as_public', 'mark_as_private', 'mark_as_featured']
    
    def doi_short(self, obj):
        return obj.doi[:30] + '...' if len(obj.doi) > 30 else obj.doi
    doi_short.short_description = 'DOI'
    
    def processing_time_display(self, obj):
        if obj.processing_time:
            return f'{obj.processing_time:.1f}s'
        return 'N/A'
    processing_time_display.short_description = 'Time'
    
    def xml_file_link(self, obj):
        if obj.xml_file:
            return format_html('<a href="/admin/web/xmlfile/{}/change/">{}</a>', obj.xml_file.id, obj.xml_file.doi)
        return 'No XML file'
    xml_file_link.short_description = 'XML File'
    
    def article_link(self, obj):
        if obj.article:
            return format_html('<a href="/admin/web/article/{}/change/">{}</a>', obj.article.id, obj.article.title[:50])
        return 'No Article'
    article_link.short_description = 'Article'
    
    def token_usage_display(self, obj):
        if obj.token_usage:
            try:
                usage = obj.token_usage
                if isinstance(usage, str):
                    usage = json.loads(usage)
                
                # Handle different token usage formats
                if 'total_tokens' in usage:
                    return f"Total: {usage['total_tokens']}"
                elif 'prompt_tokens' in usage and 'completion_tokens' in usage:
                    return f"In: {usage['prompt_tokens']}, Out: {usage['completion_tokens']}"
                else:
                    return str(usage)
            except:
                return str(obj.token_usage)[:100]
        return 'N/A'
    token_usage_display.short_description = 'Token Usage'
    
    def krt_preview(self, obj):
        if obj.krt_data:
            try:
                krt_data = obj.krt_data if isinstance(obj.krt_data, list) else json.loads(obj.krt_data)
                
                if len(krt_data) == 0:
                    return "No KRT data"
                
                # Create a simple table preview
                html = '<table style="width: 100%; border-collapse: collapse; font-size: 12px;">'
                html += '<tr style="background-color: #f0f0f0; font-weight: bold;">'
                
                # Get headers from first row
                if len(krt_data) > 0:
                    headers = list(krt_data[0].keys())
                    for header in headers:
                        html += f'<th style="border: 1px solid #ddd; padding: 4px; text-align: left;">{header}</th>'
                    html += '</tr>'
                    
                    # Show first 5 rows
                    for i, row in enumerate(krt_data[:5]):
                        html += '<tr>'
                        for header in headers:
                            value = str(row.get(header, '')).strip()
                            # Truncate long values
                            if len(value) > 50:
                                value = value[:47] + '...'
                            html += f'<td style="border: 1px solid #ddd; padding: 4px;">{value}</td>'
                        html += '</tr>'
                    
                    if len(krt_data) > 5:
                        html += f'<tr><td colspan="{len(headers)}" style="text-align: center; font-style: italic; padding: 8px;">... and {len(krt_data) - 5} more rows</td></tr>'
                
                html += '</table>'
                return format_html(html)
            except Exception as e:
                return f"Error displaying KRT data: {e}"
        return "No KRT data"
    krt_preview.short_description = 'KRT Data Preview'
    
    # Custom admin actions
    def approve_krts(self, request, queryset):
        count = 0
        for admin_krt in queryset:
            if admin_krt.status == 'completed':
                admin_krt.status = 'approved'
                admin_krt.approved_by = request.user
                admin_krt.approved_at = admin_krt.updated_at
                if admin_krt.quality_rating == 'unrated':
                    admin_krt.quality_rating = 'good'
                admin_krt.save()
                count += 1
        
        self.message_user(request, f'Successfully approved {count} AdminKRT(s).')
    approve_krts.short_description = 'Approve selected AdminKRTs'
    
    def mark_as_public(self, request, queryset):
        count = queryset.update(is_public=True)
        self.message_user(request, f'Successfully made {count} AdminKRT(s) public.')
    mark_as_public.short_description = 'Mark as public'
    
    def mark_as_private(self, request, queryset):
        count = queryset.update(is_public=False)
        self.message_user(request, f'Successfully made {count} AdminKRT(s) private.')
    mark_as_private.short_description = 'Mark as private'
    
    def mark_as_featured(self, request, queryset):
        count = queryset.filter(quality_rating__in=['excellent', 'good']).update(is_featured=True)
        self.message_user(request, f'Successfully featured {count} high-quality AdminKRT(s).')
    mark_as_featured.short_description = 'Mark as featured (high-quality only)'
