from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
import json

from .models import Article, KRTSession, ProcessedFile, KRTExport, SystemMetrics


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
