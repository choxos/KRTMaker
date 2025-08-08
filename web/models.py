from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class KRTSession(models.Model):
    """Model to store KRT processing sessions and results"""
    
    MODE_CHOICES = [
        ('regex', 'Regex/Heuristics'),
        ('llm', 'Large Language Model'),
    ]
    
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI (GPT)'),
        ('anthropic', 'Anthropic (Claude)'),
        ('gemini', 'Google (Gemini)'),
        ('openai_compatible', 'OpenAI-compatible (Ollama, DeepSeek, Grok)'),
    ]
    
    # Session info
    session_id = models.CharField(max_length=32, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # File info
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    
    # Processing options
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, blank=True, null=True)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    base_url = models.URLField(blank=True, null=True)
    extra_instructions = models.TextField(blank=True, null=True)
    
    # Results
    title = models.CharField(max_length=500, blank=True, null=True)
    abstract = models.TextField(blank=True, null=True)
    krt_data = models.JSONField(default=list)  # Store the KRT rows
    processing_time = models.FloatField(null=True, blank=True)  # in seconds
    
    # Status
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    error_message = models.TextField(blank=True, null=True)
    
    # Analytics
    resources_found = models.PositiveIntegerField(default=0)
    new_resources = models.PositiveIntegerField(default=0)
    reused_resources = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"KRT Session {self.session_id} - {self.original_filename}"
    
    @property
    def success_rate(self):
        """Calculate success rate based on resources found"""
        if self.resources_found > 0:
            return (self.resources_found / (self.resources_found + 1)) * 100
        return 0
    
    def update_analytics(self):
        """Update analytics based on KRT data"""
        if self.krt_data:
            self.resources_found = len(self.krt_data)
            self.new_resources = len([r for r in self.krt_data if r.get('NEW/REUSE', '').lower() == 'new'])
            self.reused_resources = len([r for r in self.krt_data if r.get('NEW/REUSE', '').lower() == 'reuse'])
            self.save(update_fields=['resources_found', 'new_resources', 'reused_resources'])


class ProcessedFile(models.Model):
    """Model to store uploaded files temporarily"""
    
    session = models.ForeignKey(KRTSession, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='temp_uploads/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"File for {self.session.session_id}"


class KRTExport(models.Model):
    """Model to track KRT exports and downloads"""
    
    EXPORT_FORMATS = [
        ('json', 'JSON'),
        ('csv', 'CSV'),
        ('excel', 'Excel (XLSX)'),
    ]
    
    session = models.ForeignKey(KRTSession, on_delete=models.CASCADE, related_name='exports')
    format = models.CharField(max_length=10, choices=EXPORT_FORMATS)
    exported_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-exported_at']
    
    def __str__(self):
        return f"{self.format.upper()} export for {self.session.session_id}"


class SystemMetrics(models.Model):
    """Model to store system usage metrics"""
    
    date = models.DateField(unique=True)
    total_sessions = models.PositiveIntegerField(default=0)
    successful_sessions = models.PositiveIntegerField(default=0)
    failed_sessions = models.PositiveIntegerField(default=0)
    
    regex_sessions = models.PositiveIntegerField(default=0)
    llm_sessions = models.PositiveIntegerField(default=0)
    
    total_resources_extracted = models.PositiveIntegerField(default=0)
    total_files_processed = models.PositiveIntegerField(default=0)
    total_file_size_mb = models.FloatField(default=0.0)
    
    average_processing_time = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"Metrics for {self.date}"
    
    @classmethod
    def update_daily_metrics(cls):
        """Update metrics for today"""
        today = timezone.now().date()
        
        sessions_today = KRTSession.objects.filter(created_at__date=today)
        
        metrics, created = cls.objects.get_or_create(
            date=today,
            defaults={
                'total_sessions': sessions_today.count(),
                'successful_sessions': sessions_today.filter(status='completed').count(),
                'failed_sessions': sessions_today.filter(status='failed').count(),
                'regex_sessions': sessions_today.filter(mode='regex').count(),
                'llm_sessions': sessions_today.filter(mode='llm').count(),
                'total_resources_extracted': sum(s.resources_found for s in sessions_today),
                'total_files_processed': sessions_today.exclude(file_size__isnull=True).count(),
                'total_file_size_mb': sum(s.file_size for s in sessions_today if s.file_size) / (1024 * 1024),
                'average_processing_time': sessions_today.exclude(processing_time__isnull=True).aggregate(
                    models.Avg('processing_time')
                )['processing_time__avg'] or 0.0,
            }
        )
        
        if not created:
            # Update existing metrics
            metrics.total_sessions = sessions_today.count()
            metrics.successful_sessions = sessions_today.filter(status='completed').count()
            metrics.failed_sessions = sessions_today.filter(status='failed').count()
            metrics.regex_sessions = sessions_today.filter(mode='regex').count()
            metrics.llm_sessions = sessions_today.filter(mode='llm').count()
            metrics.total_resources_extracted = sum(s.resources_found for s in sessions_today)
            metrics.total_files_processed = sessions_today.exclude(file_size__isnull=True).count()
            metrics.total_file_size_mb = sum(s.file_size for s in sessions_today if s.file_size) / (1024 * 1024)
            metrics.average_processing_time = sessions_today.exclude(processing_time__isnull=True).aggregate(
                models.Avg('processing_time')
            )['processing_time__avg'] or 0.0
            metrics.save()
        
        return metrics