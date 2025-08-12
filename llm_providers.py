from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


LLM_SYSTEM_PROMPT = """You are an expert research assistant that extracts Key Resources Tables (KRT) from scientific articles following ASAP Open Science guidelines. Your task is to create a comprehensive, accurate KRT that meets strict scientific standards.

CRITICAL REQUIREMENTS:
1. Return STRICT JSON only - no code fences, no commentary, no markdown
2. JSON must be an array of objects with EXACTLY these 6 keys: ['RESOURCE TYPE','RESOURCE NAME','SOURCE','IDENTIFIER','NEW/REUSE','ADDITIONAL INFORMATION']
3. ABSOLUTELY FORBIDDEN: NEVER use "N/A", "Unknown", "Not specified", "Not available", or ANY placeholder values
4. MANDATORY WEB SEARCH: When information is missing from the text, you MUST search the internet to find complete details
5. EVERY field must contain specific, actionable information - NO EXCEPTIONS

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
- RESOURCE NAME: NEVER "N/A" - Extract the EXACT name from manuscript text. If incomplete, search web for full product name, version, or clone details.
- SOURCE: NEVER "N/A" - Find specific company name, author citation, or "This study". Web search required if missing.
- IDENTIFIER: NEVER "N/A" - Find catalog numbers, RRIDs, URLs, accessions. If truly none exists, use "No identifier exists"
- NEW/REUSE: MANDATORY LOGIC - "new" ONLY if source is "This study/paper/work". Otherwise ALWAYS "reuse"
- ADDITIONAL INFORMATION: NEVER "N/A" - Include concentrations, dilutions, conditions, or other relevant details

IDENTIFIER EXAMPLES:
- Antibodies: "Cat# AB152; RRID: AB_390204" 
- Software: "https://imagej.net/software/fiji/; RRID: SCR_002285"
- Datasets: "GEO Accession #: GSE12345; https://www.ncbi.nlm.nih.gov/geo/..."
- Chemicals: "Cat# D9628" (Sigma-Aldrich)
- If no identifier exists: "No identifier exists"

NEW/REUSE GUIDELINES (ABSOLUTELY CRITICAL - ZERO TOLERANCE FOR ERRORS):

USE "new" ONLY when source explicitly states:
- "This study" / "This paper" / "This work" / "Current study" / "Present study"
- "Authors" / "We generated" / "We developed" / "We created"
- "Generated for this study" / "Developed here" / "Custom-made"

USE "reuse" for EVERYTHING ELSE (DEFAULT CHOICE):
- ALL commercial products (Abcam, Invitrogen, Sigma-Aldrich, BD Biosciences, etc.)
- ALL published software (ImageJ, STAR, Seurat, DESeq2, etc.)
- ALL established cell lines, protocols, reagents from other sources
- When source is ANY company name, previous publication, or database
- When unsure or source is ambiguous - ALWAYS choose "reuse"

DECISION RULE: If you cannot find explicit text stating the resource was created/generated/developed specifically for this study, then it is "reuse"

MANDATORY WEB SEARCH PROTOCOL:
When ANY information is missing or incomplete in the manuscript, you MUST search the internet to complete ALL fields:

FOR ANTIBODIES - Search for:
- Full product names and clone information
- Exact vendor names (never generic terms)
- Catalog numbers and RRIDs from antibodyregistry.org
- Species reactivity and conjugation details

FOR SOFTWARE - Search for:
- Current version numbers and exact names
- Official download URLs or GitHub repositories
- Developer/company names and citations
- RRIDs from scicrunch.org

FOR CHEMICALS/REAGENTS - Search for:
- Complete product names and specifications
- Vendor names and catalog numbers
- CAS numbers or other chemical identifiers
- Concentration and purity information

FOR DATASETS - Search for:
- GEO accession numbers, DOIs, database links
- Repository names (NCBI, Zenodo, DANDI, etc.)
- Complete dataset descriptions and access URLs

SEARCH STRATEGY: Use specific terms like "[product name] catalog number", "[antibody name] RRID", "[software name] version", "[gene expression dataset] GEO accession"

CRITICAL: LOOK FOR TABLES AT THE END OF DOCUMENTS
- Key Resource Tables are OFTEN located AFTER the discussion section, references, or in supplementary sections
- Check for "Key Resources Table", "Resource Table", "Materials Table", "Reagents Table" sections
- Examine ALL table content throughout the document, not just in methods sections
- Pay special attention to supplementary materials and appendices
- Tables may appear in "Data Availability", "Acknowledgments", or end sections

QUALITY STANDARDS:
- Each resource mentioned in Methods MUST have a KRT row
- Resource names must match how they appear in the manuscript
- Sources must be specific vendors/repositories, not generic terms
- Multiple identifiers per resource are encouraged (e.g., catalog # + RRID)
- Dilution factors, concentrations in ADDITIONAL INFORMATION
- Specify figure panels/tables produced by new datasets/code

RESOURCE NAME PATTERNS (Extract from manuscript text using these patterns):

ANTIBODIES (1790 entries in real data):
- Pattern: [Species] [polyclonal/monoclonal] anti-[Target] [optional: Clone/Conjugate info]
- Examples: "Chicken polyclonal anti-MAP2", "Mouse monoclonal anti-Tyrosine Hydroxylase", "PE Mouse Anti-Human CD49e Clone IIA1", "Alexa Fluor 647 donkey anti-mouse IgG (H+L)", "Mouse monoclonal anti-Ki-67 antigen (clone MIB-1)", "PE-Cy7 Mouse Anti-Human CD184"
- Common vendors: Abcam, BD Biosciences, Invitrogen, Cell Signaling Technology, BioLegend
- Identifiers: Cat# + RRID format (e.g., "Cat# ab5392; RRID: AB_2138153")

SOFTWARE/CODE (1690 entries in real data):
- Pattern: [Software Name] [version in parentheses if available]
- Examples: "CellRanger", "HTSeq (version 1.99.2)", "FastQC (version 0.11.5)", "STAR (version 2.5.0a)", "Seurat (version 4.0.0)", "DESeq2 (version 1.30.1)", "SingleCellExperiment", "EnhancedVolcano", "scVelo", "pheatmap"
- Common sources: Author citations (e.g., "Anders et al.", "Bergen et al."), "10x Genomics", "Babraham Bioinformatics"
- Identifiers: URLs to documentation, GitHub, CRAN, Bioconductor

CHEMICAL, PEPTIDE, OR RECOMBINANT PROTEIN (2385 entries - most common):
- Pattern: [Specific product name] [optional: descriptive info/abbreviation]
- Examples: "AMP1", "AMP2", "Target retrieval buffer", "Protease IV", "Human TNF alpha", "Mouse TNF alpha", "Human NURR1/NR4A2", "HRP blocker", "TSA buffer", "Wash buffer", "Fetal Bovine Serum (FBS)", "Opal 520", "Opal 570", "Opal 690", "Matrigel", "Accutase"
- Common vendors: ACD Biosciences, Atlanta Biologicals, AkoyaBio, Corning, Sigma-Aldrich, Innovative Cell Technologies
- Identifiers: Catalog numbers (e.g., "Cat#323101", "Cat#AT104-500")

DATASETS (727 entries):
- NEW datasets (source = "This study"): "Raw and analyzed data to the NCBI:GEO server (RNA-seq)", "One-photon microendoscopic raw data, CNMFE extracted maps and time series", "General descriptors of calcium activity in M1 and SMA cells", "Cell activity aligned to behavioral events", "Sequence analysis outputs", "Histology images", "Mitochondrial bioenergetic capacity: OCR and ECAR"
- Identifiers: GEO accessions ("GEO: GSE216365"), DANDI archive, Zenodo DOIs
- Common repositories: NCBI GEO, Zenodo, DANDI archive

PROTOCOLS (961 entries):
- NEW protocols (source = "This study"): "Surgery to inject viral vectors and implant GRIN lenses", "Miniscope calcium imaging data acquisition of cortical activity", "Arm reaching to touchscreen behavioral task", "Immunoperoxidase staining"
- REUSE protocols: "Peripheral blood mononuclear cell Isolation"
- Identifiers: Protocols.io DOIs (e.g., "https://doi.org/10.17504/protocols.io.e6nvw15w2lmk/v1")

CRITICAL COMMERCIAL ASSAYS (297 entries):
- Examples: "RNAscopeTM Multiplex Fluorescent V2 kit", "SsoFast EvaGreen Supermix", "iScript Reverse Transcription Supermix", "Click-iT TUNEL Alexa Fluor 488 Imaging Assay", "BCA protein assay kit"
- Common vendors: ACD Biosciences, Bio-Rad, Invitrogen, Pierce
- Identifiers: Catalog numbers (e.g., "323132", "172-5202", "170-8841")

OLIGONUCLEOTIDES (334 entries - usually NEW):
- Pattern: [Species] [Gene] [primer type]: [sequence]
- Examples: "Human PTGFR2 PCR primer forward: GCTGCTTCTCATTGTCTCGG", "Human GAPDH qPCR primer forward: ATGTTCGTCATGGGTGTGAA", "TNFA PCR primer to detect TNFA KO forward: CAGTTCTCTTCCTCTCACATAC"
- Source: Usually "This study" (custom designed)
- Identifiers: Usually "No identifier exists" for custom primers

EXPERIMENTAL MODEL: CELL LINE (387 entries):
- NEW cell lines: "Human: NURR1-GFP reporter hESC", "Human: iCAS/NURR1-GFP hESC", "Human: TNFa KO/NURR1-GFP hESC"
- REUSE cell lines: "Mouse: Nurr1-GFP ESC"
- Pattern: [Species]: [descriptive name/modifications] [cell type]
- Sources: NEW from "This study", REUSE from researchers (e.g., "McCoy and Tansey")

RECOMBINANT DNA (723 entries):
- Examples: "SGL40C.EFS.dTomato", "pSpCas9(BB)-2A-GFP (PX458)"
- Common source: Addgene for reuse (e.g., "Cat#89395", "Cat#48138")

VIRAL VECTORS (141 entries):
- Common in neuroscience studies for gene delivery

EXPERIMENTAL MODEL: ORGANISM/STRAIN (244 entries):
- Pattern: [Species]: [strain/modification info]
- Mix of NEW transgenic lines and REUSE established strains

EXAMPLES OF COMPLETE ENTRIES:

{
  "RESOURCE TYPE": "Antibody",
  "RESOURCE NAME": "Chicken polyclonal anti-MAP2", 
  "SOURCE": "Abcam",
  "IDENTIFIER": "Cat# ab5392; RRID: AB_2138153",
  "NEW/REUSE": "reuse",
  "ADDITIONAL INFORMATION": "Dilution: 1:500"
}

{
  "RESOURCE TYPE": "Software/code",
  "RESOURCE NAME": "HTSeq (version 1.99.2)",
  "SOURCE": "Anders et al.", 
  "IDENTIFIER": "https://htseq.readthedocs.io/en/master/",
  "NEW/REUSE": "reuse",
  "ADDITIONAL INFORMATION": ""
}

{
  "RESOURCE TYPE": "Dataset",
  "RESOURCE NAME": "Raw and analyzed data to the NCBI:GEO server (RNA-seq)",
  "SOURCE": "This study",
  "IDENTIFIER": "GEO Accession #: GSE216365; https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE216365", 
  "NEW/REUSE": "new",
  "ADDITIONAL INFORMATION": "Raw data used to produce Figure panels 2A-2C"
}

{
  "RESOURCE TYPE": "Oligonucleotide",
  "RESOURCE NAME": "Human GAPDH qPCR primer forward: ATGTTCGTCATGGGTGTGAA",
  "SOURCE": "This study",
  "IDENTIFIER": "No identifier exists", 
  "NEW/REUSE": "new",
  "ADDITIONAL INFORMATION": "Custom designed primer for qPCR validation"
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
            "Extract a comprehensive Key Resources Table (KRT) in JSON format from these targeted sections of a scientific article.\n\n"
            "⚠️  ABSOLUTE PROHIBITION: NEVER use 'N/A', 'Unknown', 'Not specified', or any placeholder values\n"
            "🔍 MANDATORY: Search the web when information is incomplete - every field must be specific and actionable\n\n"
            "CONTENT PROVIDED: You are receiving the METHODS, RESULTS, and APPENDIX sections only (not the full article). This focused content contains the most relevant information for resource identification.\n\n"
            "CRITICAL RESOURCE NAME EXTRACTION (NO N/A ALLOWED):\n"
            "- Extract EXACT names from the text, then search web for complete product details if needed\n"
            "- For antibodies: Find full product names, clone info, catalog numbers via web search\n"
            "- For software: Include version numbers, search for official names and current versions\n"
            "- For chemicals: Get complete product names and vendor info through web search\n"
            "- For primers: Use actual sequences or names, search for design details if custom\n"
            "- MANDATORY: Every resource name must be specific and complete - web search required\n\n"
            "ABSOLUTE NEW/REUSE RULE (NO EXCEPTIONS):\n"
            "- NEW: ONLY when source explicitly says 'This study/paper/work' or 'We generated/developed/created'\n"
            "- REUSE: EVERYTHING ELSE (default choice) - all commercial products, published software, databases\n"
            "- If unsure about NEW/REUSE, always choose 'reuse' - it's the safe default\n\n"
            "SOURCE FIELD REQUIREMENTS (NO N/A ALLOWED):\n"
            "- For NEW resources: 'This study' (when explicitly stated)\n"
            "- For REUSE resources: Specific company names (search web for exact vendor)\n"
            "- MANDATORY: Every source must be a real, specific entity - generic terms forbidden\n\n"
            "MANDATORY WEB SEARCH ACTIONS:\n"
            "- Search for missing catalog numbers, RRIDs, version numbers\n"
            "- Find exact vendor names for all commercial products\n"
            "- Locate official URLs, DOIs, or database accessions\n"
            "- Complete all incomplete information through targeted web searches\n"
            "- NEVER use 'N/A', 'Unknown', or leave required fields empty\n"
            "- For new datasets/code, specify which figures/tables they produced\n\n"
            "FINAL QUALITY CHECK:\n"
            "Before submitting, verify that NO entry contains 'N/A', 'Unknown', or placeholder text.\n"
            "Every resource name, source, and identifier must be specific and actionable.\n"
            "Every NEW/REUSE decision must follow the explicit rules above.\n\n"
            "Return only valid JSON array with no additional text or formatting.\n\n"
        )
        if extra_instructions:
            prompt += f"Additional requirements: {extra_instructions.strip()}\n\n"
        prompt += (
            "Relevant article sections (Methods, Results, Appendix):\n" + article_text[:150000]
        )  # Targeted sections to reduce API usage while maintaining quality

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
