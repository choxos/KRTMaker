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


def validate_s3_access() -> Tuple[bool, str]:
    """Check if AWS credentials are configured for S3 access."""
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, ClientError

        # Try to create S3 client
        client = boto3.client("s3", region_name="us-east-1")

        # Test access with a simple operation
        client.list_objects_v2(
            Bucket="biorxiv-src-monthly", MaxKeys=1, RequestPayer="requester"
        )
        return True, "S3 access confirmed"

    except NoCredentialsError:
        return (
            False,
            "AWS credentials not found. Configure with 'aws configure' or environment variables",
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "AccessDenied":
            return False, "AWS credentials lack S3 access permissions"
        elif error_code == "NoSuchBucket":
            return False, "bioRxiv S3 bucket not accessible (may be region issue)"
        else:
            return False, f"S3 access error: {e}"
    except Exception as e:
        return False, f"Unexpected error testing S3 access: {e}"
