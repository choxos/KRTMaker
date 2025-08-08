from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from jats_parser import read_xml, extract_plain_text, extract_title_and_abstract
from regex_extractor import extract_krt_regex
from krt_types import (
    KRTEntry,
    krt_entries_to_json_rows,
    ALLOWED_RESOURCE_TYPES,
    KRT_COLUMN_RESOURCE_TYPE,
    KRT_COLUMN_RESOURCE_NAME,
    KRT_COLUMN_SOURCE,
    KRT_COLUMN_IDENTIFIER,
    KRT_COLUMN_NEW_OR_REUSE,
    KRT_COLUMN_ADDITIONAL_INFO,
)
from llm_providers import LLMClient, LLMConfig
from validation import validate_xml_file, validate_api_config, ValidationError


@dataclass
class BuildOptions:
    mode: str = "regex"  # 'regex' or 'llm'
    provider: Optional[str] = None  # for llm
    model: Optional[str] = None  # for llm
    base_url: Optional[str] = None  # for llm (OpenAI-compatible)
    api_key: Optional[str] = None  # for llm
    extra_instructions: Optional[str] = None


def build_from_xml_path(
    xml_path: str, options: Optional[BuildOptions] = None
) -> Dict[str, object]:
    options = options or BuildOptions()

    # Validate input file
    try:
        validate_xml_file(xml_path)
    except ValidationError as e:
        raise ValueError(f"Invalid XML file: {e}") from e

    # Validate LLM configuration if using LLM mode
    if options.mode == "llm":
        try:
            validate_api_config(
                options.provider or "openai", options.api_key, options.model
            )
        except ValidationError as e:
            raise ValueError(f"LLM configuration error: {e}") from e

    tree = read_xml(xml_path)
    title, abstract = extract_title_and_abstract(tree)
    text = extract_plain_text(tree)

    if options.mode == "llm":
        config = LLMConfig(
            provider=(options.provider or "openai_compatible"),
            model=(options.model or "gpt-4o-mini"),
            api_key=options.api_key,
            base_url=options.base_url,
        )
        client = LLMClient(config)
        raw_rows = client.extract_krt(
            text, extra_instructions=options.extra_instructions
        )
        rows = _normalize_llm_rows(raw_rows)
        # Return as-is; enforce minimum keys if needed
        return {
            "title": title,
            "abstract": abstract,
            "rows": rows,
            "source": xml_path,
            "mode": "llm",
        }
    else:
        entries: List[KRTEntry] = extract_krt_regex(text)
        rows = krt_entries_to_json_rows(entries)
        return {
            "title": title,
            "abstract": abstract,
            "rows": rows,
            "source": xml_path,
            "mode": "regex",
        }


def _normalize_llm_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    allowed_lower = {t.lower(): t for t in ALLOWED_RESOURCE_TYPES}

    def get_ci(d: Dict[str, Any], key: str) -> Optional[str]:
        for k, v in d.items():
            if k.strip().lower() == key.strip().lower():
                return str(v) if v is not None else None
        return None

    for row in rows or []:
        rtype_raw = (get_ci(row, KRT_COLUMN_RESOURCE_TYPE) or "Other").strip()
        rtype_key = rtype_raw.lower()
        resource_type = allowed_lower.get(rtype_key, "Other")

        resource_name = (
            get_ci(row, KRT_COLUMN_RESOURCE_NAME) or ""
        ).strip()
        
        # Only use fallback if truly empty - let AI handle proper names
        if not resource_name or resource_name.lower() in ['n/a', 'na', 'unknown', 'none']:
            resource_name = "Resource name not extracted"
        identifier = (
            get_ci(row, KRT_COLUMN_IDENTIFIER) or ""
        ).strip() or "No identifier exists"
        new_or_reuse_raw = (get_ci(row, KRT_COLUMN_NEW_OR_REUSE) or "").strip()
        source_text = (get_ci(row, KRT_COLUMN_SOURCE) or "").strip().lower()
        
        # Apply correct NEW/REUSE logic based on source
        if new_or_reuse_raw.lower() in ['new', 'reuse']:
            new_or_reuse = new_or_reuse_raw.lower().capitalize()
        elif any(phrase in source_text for phrase in ['this study', 'this paper', 'current study', 'present study', 'authors']):
            new_or_reuse = "New"
        else:
            new_or_reuse = "Reuse"
        source = (get_ci(row, KRT_COLUMN_SOURCE) or "").strip()
        addl = (get_ci(row, KRT_COLUMN_ADDITIONAL_INFO) or "").strip()

        normalized.append(
            {
                KRT_COLUMN_RESOURCE_TYPE: resource_type,
                KRT_COLUMN_RESOURCE_NAME: resource_name,
                KRT_COLUMN_SOURCE: source,
                KRT_COLUMN_IDENTIFIER: identifier,
                KRT_COLUMN_NEW_OR_REUSE: new_or_reuse,
                KRT_COLUMN_ADDITIONAL_INFO: addl,
            }
        )

    # Deduplicate by (type, identifier)
    dedup: Dict[str, Dict[str, str]] = {}
    for r in normalized:
        key = f"{r[KRT_COLUMN_RESOURCE_TYPE]}|{r[KRT_COLUMN_IDENTIFIER]}"
        if key not in dedup:
            dedup[key] = r
    return list(dedup.values())
