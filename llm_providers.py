from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


LLM_SYSTEM_PROMPT = """You are an expert research assistant that extracts Key Resources Tables (KRT) from scientific articles following ASAP Open Science guidelines. Your task is to create a comprehensive, accurate KRT that meets strict scientific standards.

CRITICAL REQUIREMENTS:
1. Return STRICT JSON only - no code fences, no commentary, no markdown
2. JSON must be an array of objects with EXACTLY these 6 keys: ['RESOURCE TYPE','RESOURCE NAME','SOURCE','IDENTIFIER','NEW/REUSE','ADDITIONAL INFORMATION']
3. NEVER leave required fields empty or use "N/A", "Unknown", or similar placeholders
4. When information is not in the full text, search the web for the most accurate information available

EXACT RESOURCE TYPES (use these exact values, case-insensitive):
- Dataset
- Software/code  
- Protocol
- Antibody
- Bacterial strain
- Viral vector
- Biological sample
- Chemical, peptide, or recombinant protein
- Critical commercial assay
- Experimental model: Cell line
- Experimental model: Organism/strain
- Oligonucleotide
- Recombinant DNA
- Other

REQUIRED FIELDS (cannot be empty):
- RESOURCE TYPE: Use exact values from list above
- RESOURCE NAME: Specific, descriptive name matching manuscript text. For software, include version numbers.
- IDENTIFIER: Persistent identifier (RRID, DOI, GEO accession, catalog #, URL). If none exists, use "No identifier exists"
- NEW/REUSE: "new" if generated for this study, "reuse" if pre-existing

IDENTIFIER EXAMPLES:
- Antibodies: "Cat# AB152; RRID: AB_390204" 
- Software: "https://imagej.net/software/fiji/; RRID: SCR_002285"
- Datasets: "GEO Accession #: GSE12345; https://www.ncbi.nlm.nih.gov/geo/..."
- Chemicals: "Cat# D9628" (Sigma-Aldrich)
- If no identifier exists: "No identifier exists"

NEW/REUSE GUIDELINES:
- "new": Data collected, protocols developed, code written, organisms generated FOR THIS STUDY
- "reuse": Pre-existing resources, published protocols, commercial reagents, established cell lines

WEB SEARCH INSTRUCTIONS:
When the article text lacks specific information (vendor, catalog #, RRID, version), search the web to find:
- Exact vendor/supplier names
- Catalog/part numbers
- RRIDs from antibodyregistry.org, cellosaurus.org, etc.
- Software version numbers and official URLs
- Proper database accession numbers
- DOIs for protocols and datasets

QUALITY STANDARDS:
- Each resource mentioned in Methods MUST have a KRT row
- Resource names must match how they appear in the manuscript
- Sources must be specific vendors/repositories, not generic terms
- Multiple identifiers per resource are encouraged (e.g., catalog # + RRID)
- Dilution factors, concentrations in ADDITIONAL INFORMATION
- Specify figure panels/tables produced by new datasets/code

EXAMPLES OF GOOD ENTRIES:
{
  "RESOURCE TYPE": "Antibody",
  "RESOURCE NAME": "Rabbit Anti-TH", 
  "SOURCE": "Millipore",
  "IDENTIFIER": "Cat# AB152; RRID: AB_390204",
  "NEW/REUSE": "reuse",
  "ADDITIONAL INFORMATION": "Dilution: 1:500"
}

{
  "RESOURCE TYPE": "Software/code",
  "RESOURCE NAME": "FIJI Version 2.10.0",
  "SOURCE": "National Institute of Health (NIH)", 
  "IDENTIFIER": "https://imagej.net/software/fiji/; RRID: SCR_002285",
  "NEW/REUSE": "reuse",
  "ADDITIONAL INFORMATION": ""
}

{
  "RESOURCE TYPE": "Dataset",
  "RESOURCE NAME": "RNA-Seq expression data",
  "SOURCE": "Gene Expression Omnibus (GEO)",
  "IDENTIFIER": "GEO Accession #: GSE123456; https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE123456", 
  "NEW/REUSE": "new",
  "ADDITIONAL INFORMATION": "Raw data used to produce Figure panels 2A-2C"
}

Remember: A reader must be able to unambiguously identify and obtain every resource listed. Completeness and accuracy are critical for scientific reproducibility."""


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    return value if value is not None else default


@dataclass
class LLMConfig:
    provider: str = "openai_compatible"  # 'openai' or 'openai_compatible'
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # for OpenAI-compatible endpoints (e.g., DeepSeek)

    @staticmethod
    def from_env() -> "LLMConfig":
        return LLMConfig(
            provider=get_env("KRT_MAKER_LLM", "openai_compatible"),
            model=get_env("KRT_MAKER_LLM_MODEL", get_env("OPENAI_MODEL", "gpt-4o-mini"))
            or "gpt-4o-mini",
            api_key=get_env("KRT_MAKER_LLM_API_KEY", get_env("OPENAI_API_KEY")),
            base_url=get_env("KRT_MAKER_LLM_BASE_URL", get_env("OPENAI_BASE_URL")),
        )


class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig.from_env()

    def extract_krt(
        self, article_text: str, extra_instructions: Optional[str] = None
    ) -> List[Dict[str, str]]:
        prompt = (
            "Extract a comprehensive Key Resources Table (KRT) in JSON format from this scientific article.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "- Analyze the ENTIRE article text thoroughly, especially Methods, Materials, and Results sections\n"
            "- For EVERY resource mentioned (antibodies, software, reagents, datasets, etc.), create a KRT entry\n" 
            "- When specific information is missing (vendor, catalog #, RRID), use your knowledge to search for the most likely correct information\n"
            "- NEVER use 'N/A', 'Unknown', or leave required fields empty\n"
            "- Ensure resource names match exactly how they appear in the manuscript text\n"
            "- Include version numbers for all software\n"
            "- Use specific vendor/supplier names, not generic descriptions\n"
            "- For new datasets/code, specify which figures/tables they produced\n\n"
            "Return only valid JSON array with no additional text or formatting.\n\n"
        )
        if extra_instructions:
            prompt += f"Additional requirements: {extra_instructions.strip()}\n\n"
        prompt += (
            "Article full text:\n" + article_text[:150000]
        )  # Reduced slightly to allow for longer system prompt

        provider = (self.config.provider or "openai_compatible").lower()
        if provider == "openai":
            return self._extract_with_openai(prompt)
        if provider in {"openai_compatible", "ollama", "grok", "deepseek"}:
            return self._extract_with_openai_compatible(prompt)
        if provider == "anthropic":
            return self._extract_with_anthropic(prompt)
        if provider in {"gemini", "google"}:
            return self._extract_with_gemini(prompt)
        # default fallback
        return self._extract_with_openai_compatible(prompt)

    def _extract_with_openai(self, prompt: str) -> List[Dict[str, str]]:
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "openai package is required for 'openai' provider"
            ) from exc

        client = OpenAI()
        response = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "[]"
        return self._parse_json_strict(content)

    def _extract_with_openai_compatible(self, prompt: str) -> List[Dict[str, str]]:
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "openai package is required for OpenAI-compatible providers"
            ) from exc

        api_key = self.config.api_key or "dummy"
        # Common base URLs examples:
        # - Ollama: http://localhost:11434/v1
        # - DeepSeek: https://api.deepseek.com/v1
        # - xAI Grok: https://api.x.ai/v1
        base_url = self.config.base_url or "https://api.openai.com/v1"
        client = OpenAI(api_key=api_key, base_url=base_url)

        response = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "[]"
        return self._parse_json_strict(content)

    def _extract_with_anthropic(self, prompt: str) -> List[Dict[str, str]]:
        try:
            import anthropic  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "anthropic package is required for 'anthropic' provider"
            ) from exc

        api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=self.config.model or "claude-3-5-sonnet-latest",
            system=LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.1,
        )
        # Extract text segments
        text_parts: List[str] = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        content = "\n".join(tp for tp in text_parts if tp)
        return self._parse_json_strict(content)

    def _extract_with_gemini(self, prompt: str) -> List[Dict[str, str]]:
        try:
            import google.generativeai as genai  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "google-generativeai package is required for 'gemini' provider"
            ) from exc

        api_key = (
            self.config.api_key
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY (Gemini) not set")
        genai.configure(api_key=api_key)
        model_name = self.config.model or "gemini-1.5-pro"
        model = genai.GenerativeModel(model_name)
        full_prompt = LLM_SYSTEM_PROMPT + "\n\n" + prompt
        response = model.generate_content(full_prompt)
        content = getattr(response, "text", None) or "[]"
        return self._parse_json_strict(content)

    @staticmethod
    def _parse_json_strict(text: str) -> List[Dict[str, str]]:
        # Strip code fences if any slipped through
        text = text.strip()
        if text.startswith("```") and text.endswith("```"):
            # Try to extract inner JSON
            inner = text.strip("`")
            if inner.startswith("json\n"):
                inner = inner[5:]
            text = inner
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data  # type: ignore[return-value]
            if (
                isinstance(data, dict)
                and "rows" in data
                and isinstance(data["rows"], list)
            ):
                return data["rows"]  # type: ignore[return-value]
        except Exception:
            pass
        # Fallback to empty list if parsing failed
        return []
