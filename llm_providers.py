from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


LLM_SYSTEM_PROMPT = (
    "You are an expert research assistant that extracts Key Resources Tables (KRT) "
    "from a full-text scientific article. Return STRICT JSON only, no code fences, "
    "no commentary. The JSON must be an array of objects with EXACT keys: \n"
    "['RESOURCE TYPE','RESOURCE NAME','SOURCE','IDENTIFIER','NEW/REUSE','ADDITIONAL INFORMATION']. "
    "Values for 'RESOURCE TYPE' must be one of: Dataset; Software/code; Protocol; Antibody; "
    "Bacterial strain; Viral vector; Biological sample; Chemical, peptide, or recombinant protein; "
    "Critical commercial assay; Experimental model: Cell line; Experimental model: Organism/strain; "
    "Oligonucleotide; Recombinant DNA; Other. \n"
    "Every row MUST have values for 'RESOURCE TYPE','RESOURCE NAME','IDENTIFIER','NEW/REUSE'. "
    "If no identifier exists, set 'IDENTIFIER' to 'No identifier exists'. "
    "Use concise names; deduplicate near-duplicates; prefer canonical identifiers (RRID, DOI, GEO, SRA, Addgene, catalog #)."
)


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
            "Extract a Key Resources Table in JSON from the following article text.\n"
            "Return only JSON.\n"
        )
        if extra_instructions:
            prompt += extra_instructions.strip() + "\n"
        prompt += (
            "Article full text begins:\n" + article_text[:200000]
        )  # safety: limit prompt size

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
