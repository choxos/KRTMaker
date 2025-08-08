from __future__ import annotations

import os
from typing import List, Optional, Tuple

from krt_types import ALLOWED_RESOURCE_TYPES, KRTEntry


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


def validate_xml_file(xml_path: str) -> None:
    """Validate that XML file exists and is readable."""
    if not os.path.exists(xml_path):
        raise ValidationError(f"XML file not found: {xml_path}")

    if not os.path.isfile(xml_path):
        raise ValidationError(f"Path is not a file: {xml_path}")

    if not os.access(xml_path, os.R_OK):
        raise ValidationError(f"XML file is not readable: {xml_path}")

    # Check file extension
    if not xml_path.lower().endswith((".xml", ".jats")):
        print(f"Warning: File does not have .xml extension: {xml_path}")


def validate_krt_entry(entry: KRTEntry) -> List[str]:
    """Validate a single KRT entry and return list of warnings."""
    warnings = []

    # Check required fields
    if not entry.resource_name.strip():
        warnings.append("Empty resource name")

    if not entry.identifier.strip():
        warnings.append("Empty identifier")

    if entry.resource_type not in ALLOWED_RESOURCE_TYPES:
        warnings.append(f"Invalid resource type: {entry.resource_type}")

    # Check new/reuse field
    if entry.new_or_reuse.lower() not in ["new", "reuse"]:
        warnings.append(
            f"NEW/REUSE should be 'New' or 'Reuse', got: {entry.new_or_reuse}"
        )

    return warnings


def validate_api_config(
    provider: str, api_key: Optional[str], model: Optional[str]
) -> None:
    """Validate LLM API configuration."""
    if provider == "openai" and not api_key:
        env_key = os.getenv("OPENAI_API_KEY")
        if not env_key:
            raise ValidationError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable or use --api-key"
            )

    if provider == "anthropic" and not api_key:
        env_key = os.getenv("ANTHROPIC_API_KEY")
        if not env_key:
            raise ValidationError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable or use --api-key"
            )

    if provider == "gemini" and not api_key:
        env_key = os.getenv("GOOGLE_API_KEY")
        if not env_key:
            raise ValidationError(
                "Google API key required. Set GOOGLE_API_KEY environment variable or use --api-key"
            )

    # Warn about commonly forgotten models
    if provider == "openai" and not model:
        print("Warning: No model specified, defaulting to gpt-4o-mini")
    elif provider == "anthropic" and not model:
        print("Warning: No model specified, defaulting to claude-3-5-sonnet-latest")


# Note: S3 validation removed - now using Europe PMC for bioRxiv papers
# No AWS credentials or S3 access needed anymore!
