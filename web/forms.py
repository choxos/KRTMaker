from django import forms
from django.core.exceptions import ValidationError
import os


class KRTMakerForm(forms.Form):
    """Form for uploading XML and configuring KRT extraction"""
    
    MODE_CHOICES = [
        ('regex', 'Regex/Heuristics (Fast, Offline)'),
        ('llm', 'AI-Powered (More Accurate, Requires API)'),
    ]
    
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI (GPT-4, GPT-3.5)'),
        ('anthropic', 'Anthropic (Claude)'),
        ('gemini', 'Google (Gemini Pro)'),
        ('openai_compatible', 'OpenAI-Compatible (Ollama, DeepSeek, Grok)'),
    ]
    
    # File upload
    xml_file = forms.FileField(
        label="Upload bioRxiv XML File",
        help_text="Select a JATS XML file from bioRxiv (usually ending in .xml)",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xml,.jats',
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
    
    model = forms.CharField(
        required=False,
        label="Model Name",
        help_text="Specify the model (e.g., gpt-4o-mini, claude-3-5-sonnet, gemini-1.5-pro)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., gpt-4o-mini'
        })
    )
    
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
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
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
            if provider in ['openai', 'anthropic', 'gemini'] and not api_key:
                # Check if API key is available in environment
                env_key_map = {
                    'openai': 'OPENAI_API_KEY',
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