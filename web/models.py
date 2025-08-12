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
    
    # Link to article (for grouping multiple sessions of the same article)
    article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='sessions', null=True, blank=True)
    
    # File info
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    
    # Article metadata (enhanced for bioRxiv and other sources)
    input_method = models.CharField(max_length=20, choices=[('upload', 'File Upload'), ('url', 'bioRxiv URL/DOI')], default='upload')
    doi = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    biorxiv_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    epmc_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    authors = models.TextField(blank=True, null=True)  # JSON list of authors
    publication_date = models.DateField(blank=True, null=True)
    journal = models.CharField(max_length=255, blank=True, null=True)
    keywords = models.TextField(blank=True, null=True)  # JSON list of keywords
    categories = models.TextField(blank=True, null=True)  # JSON list of categories
    
    # KRT analysis
    existing_krt_detected = models.BooleanField(default=False)
    existing_krt_count = models.PositiveIntegerField(default=0)
    existing_krt_data = models.JSONField(default=list, blank=True)  # Store detected KRT from original paper
    
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
    
    @property
    def formatted_authors(self):
        """Get formatted authors list"""
        if self.authors:
            try:
                # Handle JSON parsing
                if isinstance(self.authors, str):
                    authors_data = json.loads(self.authors)
                else:
                    authors_data = self.authors
                
                # Handle different data types
                if isinstance(authors_data, list):
                    # Proper list format
                    authors_list = authors_data
                elif isinstance(authors_data, str):
                    # String format (could be old comma-separated format)
                    authors_list = [author.strip() for author in authors_data.split(',')]
                else:
                    # Fallback for unexpected format
                    return str(authors_data)
                
                # Format the authors
                if len(authors_list) > 3:
                    return f"{', '.join(authors_list[:3])} et al."
                return ', '.join(authors_list)
                
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                # Fallback to raw string if JSON parsing fails
                return str(self.authors)
        return "Unknown Authors"
    
    @property
    def formatted_keywords(self):
        """Get formatted keywords list"""
        if self.keywords:
            try:
                keywords_list = json.loads(self.keywords) if isinstance(self.keywords, str) else self.keywords
                return keywords_list
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @property
    def is_biorxiv_paper(self):
        """Check if this is a bioRxiv paper"""
        return self.input_method == 'url' and (self.doi or self.biorxiv_id)
    
    @property
    def display_title(self):
        """Get title for display, with fallback"""
        return self.title or f"Document: {self.original_filename}"
    
    @classmethod
    def get_by_doi(cls, doi):
        """Get all sessions for a specific DOI"""
        return cls.objects.filter(doi=doi).order_by('-created_at')
    
    @classmethod
    def get_unique_articles(cls):
        """Get unique articles (by DOI or filename)"""
        # Get all completed sessions
        sessions = cls.objects.filter(status='completed').order_by('-created_at')
        
        # Group by DOI or filename
        unique_articles = {}
        for session in sessions:
            key = session.doi or session.original_filename
            if key not in unique_articles:
                unique_articles[key] = {
                    'primary_session': session,
                    'all_sessions': [session],
                    'llm_results': []
                }
            else:
                unique_articles[key]['all_sessions'].append(session)
            
            # Track LLM results
            if session.mode == 'llm':
                unique_articles[key]['llm_results'].append({
                    'session': session,
                    'provider': session.provider,
                    'model': session.model_name,
                    'resources_found': session.resources_found,
                    'processing_time': session.processing_time
                })
        
        return list(unique_articles.values())


class XMLFile(models.Model):
    """Model to track downloaded XML files for bioRxiv papers"""
    
    # Paper identifiers
    doi = models.CharField(max_length=255, unique=True, db_index=True)
    epmc_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    
    # File storage
    file_path = models.CharField(max_length=500)  # Relative path from XML storage directory
    file_size = models.PositiveIntegerField()
    file_hash = models.CharField(max_length=64, db_index=True)  # SHA256 hash for integrity
    
    # Download metadata
    downloaded_at = models.DateTimeField(auto_now_add=True)
    last_checked = models.DateTimeField(auto_now=True)
    download_source = models.CharField(max_length=50, default='europe_pmc')
    
    # Paper metadata
    title = models.CharField(max_length=500, blank=True, null=True)
    authors = models.TextField(blank=True, null=True)  # JSON list
    publication_date = models.DateField(blank=True, null=True)
    journal = models.CharField(max_length=255, default='bioRxiv')
    
    # Status tracking
    is_available = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['doi']),
            models.Index(fields=['epmc_id']),
            models.Index(fields=['publication_date']),
            models.Index(fields=['is_available']),
        ]
    
    def __str__(self):
        return f"XML: {self.doi}"
    
    @property
    def full_file_path(self):
        """Get the complete file path including XML storage directory"""
        from django.conf import settings
        import os
        xml_storage_dir = getattr(settings, 'XML_STORAGE_DIR', os.path.join(settings.BASE_DIR, 'xml_files'))
        return os.path.join(xml_storage_dir, self.file_path)
    
    def verify_file_exists(self):
        """Check if the XML file still exists on disk"""
        import os
        exists = os.path.exists(self.full_file_path)
        if not exists:
            self.is_available = False
            self.error_message = "File not found on disk"
            self.save()
        return exists
    
    def calculate_file_hash(self):
        """Calculate SHA256 hash of the XML file"""
        import hashlib
        import os
        
        if not os.path.exists(self.full_file_path):
            return None
            
        hash_sha256 = hashlib.sha256()
        with open(self.full_file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()


class Article(models.Model):
    """Model to group multiple KRT sessions for the same article"""
    
    # Unique identifier for the article
    doi = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    filename_hash = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)  # For uploaded files
    
    # Link to XML file if available
    xml_file = models.ForeignKey(XMLFile, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    
    # Article metadata
    title = models.CharField(max_length=500, blank=True, null=True)
    authors = models.TextField(blank=True, null=True)  # JSON list
    abstract = models.TextField(blank=True, null=True)
    publication_date = models.DateField(blank=True, null=True)
    journal = models.CharField(max_length=255, blank=True, null=True)
    keywords = models.TextField(blank=True, null=True)  # JSON list
    
    # Analysis metadata
    first_processed = models.DateTimeField(auto_now_add=True)
    last_processed = models.DateTimeField(auto_now=True)
    total_sessions = models.PositiveIntegerField(default=0)
    
    # Existing KRT detection
    has_existing_krt = models.BooleanField(default=False)
    existing_krt_count = models.PositiveIntegerField(default=0)
    existing_krt_data = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-last_processed']
        indexes = [
            models.Index(fields=['doi']),
            models.Index(fields=['filename_hash']),
            models.Index(fields=['last_processed']),
        ]
    
    def __str__(self):
        return self.title or f"Article ({self.doi or 'Uploaded file'})"
    
    @property
    def best_session(self):
        """Get the session with the most resources found"""
        return self.sessions.filter(status='completed').order_by('-resources_found', '-created_at').first()
    
    @property
    def llm_comparison_data(self):
        """Get comparison data across different LLM models"""
        llm_sessions = self.sessions.filter(mode='llm', status='completed').order_by('-created_at')
        
        comparison = {}
        for session in llm_sessions:
            key = f"{session.provider}_{session.model_name}"
            if key not in comparison:
                comparison[key] = {
                    'provider': session.provider,
                    'model': session.model_name,
                    'sessions': [],
                    'avg_resources': 0,
                    'avg_time': 0,
                    'best_session': None
                }
            
            comparison[key]['sessions'].append(session)
            
            # Calculate averages
            sessions_for_model = comparison[key]['sessions']
            comparison[key]['avg_resources'] = sum(s.resources_found for s in sessions_for_model) / len(sessions_for_model)
            comparison[key]['avg_time'] = sum(s.processing_time or 0 for s in sessions_for_model) / len(sessions_for_model)
            comparison[key]['best_session'] = max(sessions_for_model, key=lambda s: s.resources_found)
        
        return list(comparison.values())


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


class AdminKRT(models.Model):
    """Model to store LLM-generated KRTs created by admin for bioRxiv preprints"""
    
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI (GPT)'),
        ('anthropic', 'Anthropic (Claude)'),
        ('gemini', 'Google (Gemini)'),
        ('openai_compatible', 'OpenAI-compatible (Ollama, DeepSeek, Grok)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Generation'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reviewing', 'Under Review'),
        ('approved', 'Approved'),
    ]
    
    QUALITY_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('unrated', 'Unrated'),
    ]
    
    # Unique identifier
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Link to XML file and/or article
    xml_file = models.ForeignKey(XMLFile, on_delete=models.CASCADE, related_name='admin_krts')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='admin_krts', null=True, blank=True)
    
    # Paper identifiers (for quick access)
    doi = models.CharField(max_length=255, db_index=True)
    epmc_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    
    # LLM generation settings
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    model_name = models.CharField(max_length=100)
    base_url = models.URLField(blank=True, null=True)  # For OpenAI-compatible APIs
    
    # Generation metadata
    processing_time = models.FloatField(null=True, blank=True)  # in seconds
    token_usage = models.JSONField(default=dict, blank=True)  # Store token usage info
    cost_estimate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)  # USD cost
    
    # Results
    krt_data = models.JSONField(default=list)  # Store the generated KRT rows
    resources_found = models.PositiveIntegerField(default=0)
    new_resources = models.PositiveIntegerField(default=0)
    reused_resources = models.PositiveIntegerField(default=0)
    
    # Quality assessment
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    quality_rating = models.CharField(max_length=20, choices=QUALITY_CHOICES, default='unrated')
    admin_notes = models.TextField(blank=True, null=True)
    
    # Error handling
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    # Public availability
    is_public = models.BooleanField(default=True)  # Whether to show to users
    is_featured = models.BooleanField(default=False)  # Featured high-quality KRTs
    
    # Admin who created this
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_krts')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_krts')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['doi']),
            models.Index(fields=['epmc_id']),
            models.Index(fields=['status']),
            models.Index(fields=['provider', 'model_name']),
            models.Index(fields=['quality_rating']),
            models.Index(fields=['is_public']),
            models.Index(fields=['created_at']),
        ]
        
        # Ensure one AdminKRT per DOI+provider+model combination
        unique_together = ['doi', 'provider', 'model_name']
    
    def __str__(self):
        return f"Admin KRT: {self.doi} ({self.provider}/{self.model_name})"
    
    def save(self, *args, **kwargs):
        # Auto-populate DOI and EPMC ID from xml_file
        if self.xml_file:
            self.doi = self.xml_file.doi
            self.epmc_id = self.xml_file.epmc_id
        super().save(*args, **kwargs)
    
    def update_analytics(self):
        """Update analytics based on KRT data"""
        if self.krt_data:
            self.resources_found = len(self.krt_data)
            self.new_resources = len([r for r in self.krt_data if r.get('NEW/REUSE', '').lower() == 'new'])
            self.reused_resources = len([r for r in self.krt_data if r.get('NEW/REUSE', '').lower() == 'reuse'])
            self.save(update_fields=['resources_found', 'new_resources', 'reused_resources'])
    
    @property
    def formatted_provider_model(self):
        """Get formatted provider and model name"""
        return f"{self.get_provider_display()} - {self.model_name}"
    
    @property
    def success_rate(self):
        """Calculate success rate based on resources found"""
        if self.resources_found > 0:
            return min((self.resources_found / 20) * 100, 100)  # Assume 20 is a good number
        return 0
    
    @property
    def is_high_quality(self):
        """Check if this is considered high quality"""
        return self.quality_rating in ['excellent', 'good'] and self.status == 'approved'
    
    @classmethod
    def get_for_doi(cls, doi):
        """Get all admin KRTs for a specific DOI"""
        return cls.objects.filter(doi=doi, is_public=True).order_by('-quality_rating', '-resources_found')
    
    @classmethod
    def get_best_for_doi(cls, doi):
        """Get the best admin KRT for a specific DOI"""
        return cls.objects.filter(
            doi=doi, 
            is_public=True, 
            status='approved'
        ).order_by('-quality_rating', '-resources_found').first()
    
    @classmethod
    def get_pending_generation(cls, limit=10):
        """Get pending KRTs that need to be generated"""
        return cls.objects.filter(status='pending').order_by('created_at')[:limit]
    
    @classmethod
    def get_statistics(cls):
        """Get statistics about admin KRT generation"""
        total = cls.objects.count()
        completed = cls.objects.filter(status='completed').count()
        approved = cls.objects.filter(status='approved').count()
        
        return {
            'total': total,
            'completed': completed,
            'approved': approved,
            'pending': cls.objects.filter(status='pending').count(),
            'failed': cls.objects.filter(status='failed').count(),
            'completion_rate': (completed / total * 100) if total > 0 else 0,
            'approval_rate': (approved / completed * 100) if completed > 0 else 0,
        }