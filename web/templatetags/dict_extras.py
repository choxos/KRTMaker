from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Template filter to look up dictionary values by key.
    Usage: {{ my_dict|lookup:key_variable }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter
def get_item(dictionary, key):
    """
    Alternative name for lookup filter.
    Usage: {{ my_dict|get_item:key_variable }}
    """
    return lookup(dictionary, key)