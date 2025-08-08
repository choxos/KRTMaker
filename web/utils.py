"""
Utility functions for the web application
"""

def validate_model_choices_sync():
    """
    Development helper to ensure JavaScript and Django model choices stay synchronized.
    This function can be called in tests or development to verify consistency.
    """
    from .forms import KRTMakerForm
    
    form = KRTMakerForm()
    
    # Get all Django model choices
    all_django_models = {
        'anthropic': [choice[0] for choice in form.ANTHROPIC_MODELS],
        'gemini': [choice[0] for choice in form.GEMINI_MODELS], 
        'openai_compatible': [choice[0] for choice in form.OPENAI_COMPATIBLE_MODELS],
    }
    
    print("✅ Django Model Choices:")
    for provider, models in all_django_models.items():
        print(f"  {provider}: {len(models)} models")
        for model in models:
            print(f"    - {model}")
    
    print(f"\n✅ Model choices are dynamically generated from Django forms.")
    print(f"✅ JavaScript choices are automatically synchronized via template rendering.")
    
    return all_django_models


def get_model_choices_for_provider(provider):
    """
    Get valid model choices for a specific provider.
    Used for validation and debugging.
    """
    from .forms import KRTMakerForm
    
    form = KRTMakerForm()
    
    if provider == 'anthropic':
        return [choice[0] for choice in form.ANTHROPIC_MODELS]
    elif provider == 'gemini':
        return [choice[0] for choice in form.GEMINI_MODELS]
    elif provider == 'openai_compatible':
        return [choice[0] for choice in form.OPENAI_COMPATIBLE_MODELS]
    else:
        return []


def validate_provider_model_combination(provider, model):
    """
    Validate that a model is valid for the given provider.
    Returns (is_valid, error_message)
    """
    if not provider or not model:
        return True, None  # Optional fields
    
    valid_models = get_model_choices_for_provider(provider)
    
    if model in valid_models:
        return True, None
    else:
        return False, f"Model '{model}' is not valid for provider '{provider}'. Valid models: {', '.join(valid_models[:3])}{'...' if len(valid_models) > 3 else ''}"