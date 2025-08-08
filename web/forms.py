from django import forms
from django.core.exceptions import ValidationError
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from biorxiv_fetcher import BioRxivFetcher


class KRTMakerForm(forms.Form):
    """Form for uploading XML and configuring KRT extraction"""
    
    MODE_CHOICES = [
        ('regex', 'Regex/Heuristics (Fast, Offline)'),
        ('llm', 'AI-Powered (More Accurate, Requires API)'),
    ]
    
    PROVIDER_CHOICES = [
        ('anthropic', 'Anthropic (Claude)'),
        ('gemini', 'Google (Gemini)'),
        ('openai_compatible', 'OpenAI-Compatible (Ollama, DeepSeek, Grok)'),
    ]
    
    # Model choices for each provider
    ANTHROPIC_MODELS = [
        ('claude-opus-4-1-20250805', 'Claude Opus 4.1 (Latest)'),
        ('claude-opus-4-20250514', 'Claude Opus 4'),
        ('claude-sonnet-4-20250514', 'Claude Sonnet 4'),
        ('claude-3-7-sonnet-20250219', 'Claude Sonnet 3.7'),
        ('claude-3-5-sonnet-20241022', 'Claude Sonnet 3.5 v2'),
        ('claude-3-5-sonnet-20240620', 'Claude Sonnet 3.5'),
        ('claude-3-5-haiku-20241022', 'Claude Haiku 3.5'),
        ('claude-3-haiku-20240307', 'Claude Haiku 3'),
    ]
    
    GEMINI_MODELS = [
        ('gemini-2.5-pro', 'Gemini 2.5 Pro (Enhanced reasoning, multimodal)'),
        ('gemini-2.5-flash', 'Gemini 2.5 Flash (Adaptive thinking, cost efficient)'),
        ('gemini-2.5-flash-lite', 'Gemini 2.5 Flash-Lite (Most cost-efficient)'),
        ('gemini-2.0-flash', 'Gemini 2.0 Flash (Next generation features)'),
        ('gemini-2.0-flash-lite', 'Gemini 2.0 Flash-Lite (Cost efficient, low latency)'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash (Fast and versatile)'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro (Complex reasoning) [Deprecated]'),
    ]
    
    OPENAI_COMPATIBLE_MODELS = [
        ('gpt-4o', 'GPT-4o (OpenAI-compatible)'),
        ('gpt-4-turbo', 'GPT-4 Turbo (OpenAI-compatible)'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo (OpenAI-compatible)'),
        ('llama-3.1-70b', 'Llama 3.1 70B (Ollama/Local)'),
        ('llama-3.1-8b', 'Llama 3.1 8B (Ollama/Local)'),
        ('deepseek-v3', 'DeepSeek V3 (DeepSeek API)'),
        ('grok-2', 'Grok 2 (xAI API)'),
    ]
    
    # Input method choice
    INPUT_METHOD_CHOICES = [
        ('upload', 'Upload XML File'),
        ('url', 'bioRxiv URL or DOI'),
    ]
    
    input_method = forms.ChoiceField(
        choices=INPUT_METHOD_CHOICES,
        initial='url',
        label="Input Method",
        help_text="Choose how to provide the manuscript",
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    # File upload
    xml_file = forms.FileField(
        required=False,
        label="Upload bioRxiv XML File",
        help_text="Select a JATS XML file from bioRxiv (usually ending in .xml)",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xml,.jats',
        })
    )
    
    # bioRxiv URL/DOI
    biorxiv_url = forms.CharField(
        required=False,
        max_length=500,
        label="bioRxiv URL or DOI",
        help_text="Enter a bioRxiv URL (e.g., https://biorxiv.org/content/10.1101/2023.01.01.123456) or DOI (e.g., 10.1101/2023.01.01.123456)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://biorxiv.org/content/10.1101/2023.01.01.123456 or 2023.01.01.123456'
        })
    )
    
    # Extraction mode
    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial='regex',
        label="Extraction Method",
        help_text="Choose between fast regex-based extraction or AI-powered analysis",
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    # LLM Configuration (only shown when mode=llm)
    provider = forms.ChoiceField(
        choices=PROVIDER_CHOICES,
        required=False,
        label="AI Provider",
        help_text="Select your preferred AI service provider",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # LLM model (dynamic choices based on provider)
    model = forms.ChoiceField(
        required=False,
        choices=[],  # Will be populated dynamically
        label="Model",
        help_text="Select the specific model to use",
        widget=forms.Select(attrs={
            'class': 'form-control',
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default model choices (Anthropic as default)
        self.fields['model'].choices = [('', 'Select a model')] + self.ANTHROPIC_MODELS
    
    base_url = forms.URLField(
        required=False,
        label="Base URL (for OpenAI-Compatible)",
        help_text="Required for Ollama, DeepSeek, or Grok (e.g., http://localhost:11434/v1)",
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'http://localhost:11434/v1'
        })
    )
    
    api_key = forms.CharField(
        required=False,
        label="API Key",
        help_text="Your API key for the selected provider (not needed for local Ollama)",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'sk-...'
        })
    )
    
    extra_instructions = forms.CharField(
        required=False,
        label="Additional Instructions",
        help_text="Optional custom instructions for the AI (e.g., 'Focus on novel datasets')",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional: Add specific instructions for the AI...'
        })
    )
    
    def clean_xml_file(self):
        """Validate the uploaded XML file"""
        xml_file = self.cleaned_data.get('xml_file')
        
        if xml_file:
            # Check file size (max 50MB)
            if xml_file.size > 50 * 1024 * 1024:
                raise ValidationError("File too large. Maximum size is 50MB.")
            
            # Check file extension
            filename = xml_file.name.lower()
            if not (filename.endswith('.xml') or filename.endswith('.jats')):
                raise ValidationError("Please upload a valid XML file (.xml or .jats extension).")
            
            # Basic content check
            try:
                content = xml_file.read(1024).decode('utf-8', errors='ignore')
                xml_file.seek(0)  # Reset file pointer
                
                if '<article' not in content and '<?xml' not in content:
                    raise ValidationError("This doesn't appear to be a valid XML file.")
                    
            except Exception:
                raise ValidationError("Unable to read the uploaded file. Please ensure it's a valid XML file.")
        
        return xml_file
    
    def clean_biorxiv_url(self):
        """Validate bioRxiv URL or DOI"""
        biorxiv_url = self.cleaned_data.get('biorxiv_url')
        
        if biorxiv_url:
            biorxiv_url = biorxiv_url.strip()
            
            # Validate the URL/DOI format
            fetcher = BioRxivFetcher()
            doi = fetcher.parse_biorxiv_identifier(biorxiv_url)
            
            if not doi:
                raise ValidationError(
                    "Invalid bioRxiv URL or DOI format. Please provide a valid bioRxiv URL or DOI "
                    "(e.g., https://biorxiv.org/content/10.1101/2023.01.01.123456 or 2023.01.01.123456)"
                )
            
            # Test if the paper exists
            try:
                metadata = fetcher.get_paper_metadata(doi)
                if not metadata:
                    raise ValidationError(f"Paper not found: {doi}. Please check the URL or DOI and make sure the paper exists on bioRxiv.")
                
                # With S3 method, most papers should work, so just validate existence
                # XML availability will be checked during actual processing
                    
            except ValidationError:
                raise  # Re-raise validation errors as-is
            except Exception as e:
                raise ValidationError(f"Error accessing bioRxiv: {str(e)}")
        
        return biorxiv_url

    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        
        # Input method validation
        input_method = cleaned_data.get('input_method')
        xml_file = cleaned_data.get('xml_file')
        biorxiv_url = cleaned_data.get('biorxiv_url')
        
        if input_method == 'upload':
            if not xml_file:
                self.add_error('xml_file', 'Please upload an XML file when using file upload method.')
            if biorxiv_url:
                self.add_error('biorxiv_url', 'Please clear the URL field when using file upload method.')
        elif input_method == 'url':
            if not biorxiv_url:
                self.add_error('biorxiv_url', 'Please provide a bioRxiv URL or DOI when using URL method.')
            if xml_file:
                self.add_error('xml_file', 'Please clear the file upload when using URL method.')
        
        # LLM configuration validation
        mode = cleaned_data.get('mode')
        provider = cleaned_data.get('provider')
        base_url = cleaned_data.get('base_url')
        api_key = cleaned_data.get('api_key')
        
        if mode == 'llm':
            # Validate LLM configuration
            if not provider:
                self.add_error('provider', 'Please select an AI provider when using LLM mode.')
            
            if provider == 'openai_compatible' and not base_url:
                self.add_error('base_url', 'Base URL is required for OpenAI-compatible providers.')
            
            # Check for API key (except for local Ollama)
            if provider in ['anthropic', 'gemini'] and not api_key:
                # Check if API key is available in environment
                env_key_map = {
                    'anthropic': 'ANTHROPIC_API_KEY',
                    'gemini': 'GOOGLE_API_KEY'
                }
                
                env_key = env_key_map.get(provider)
                if not (env_key and os.getenv(env_key)):
                    self.add_error('api_key', f'API key is required for {provider}. Either provide it here or set the {env_key} environment variable.')
        
        return cleaned_data


class FeedbackForm(forms.Form):
    """Form for user feedback"""
    
    RATING_CHOICES = [
        (5, '⭐⭐⭐⭐⭐ Excellent'),
        (4, '⭐⭐⭐⭐ Good'),
        (3, '⭐⭐⭐ Average'),
        (2, '⭐⭐ Poor'),
        (1, '⭐ Very Poor'),
    ]
    
    session_id = forms.CharField(widget=forms.HiddenInput())
    
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        label="How would you rate the KRT extraction quality?",
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    accuracy_feedback = forms.CharField(
        required=False,
        label="Accuracy Feedback",
        help_text="Tell us about any missing or incorrect resources",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Optional: Describe any issues with the extracted resources...'
        })
    )
    
    suggestions = forms.CharField(
        required=False,
        label="Suggestions for Improvement",
        help_text="How can we make this tool better?",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional: Share your ideas for improvement...'
        })
    )
    
    email = forms.EmailField(
        required=False,
        label="Email (Optional)",
        help_text="Leave your email if you'd like us to follow up",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com'
        })
    )