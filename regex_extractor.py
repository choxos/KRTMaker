from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from krt_types import (
    ALLOWED_RESOURCE_TYPES,
    KRTEntry,
)


# Core identifier patterns
PATTERN_RRID = re.compile(r"RRID:([A-Z]{2}_[A-Z0-9-]+)")
PATTERN_DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
PATTERN_GEO = re.compile(r"\bGSE\d{3,8}\b", re.IGNORECASE)
PATTERN_SRA = re.compile(r"\bSR[APX]R?\d{3,9}\b", re.IGNORECASE)
PATTERN_ADDGENE = re.compile(r"Addgene(?:\s+plasmid)?\s*#?\s*(\d{3,6})", re.IGNORECASE)
PATTERN_CATALOG = re.compile(
    r"(?:catalog|cat\.?\s*no\.?|cat\.?\s*#)\s*[:#]?\s*([A-Z0-9-]+)", re.IGNORECASE
)
PATTERN_PROTOCOLS = re.compile(r"protocols\.io/[\w/-]+", re.IGNORECASE)
PATTERN_GITHUB = re.compile(r"github\.com/[\w.-]+/[\w.-]+", re.IGNORECASE)

# Enhanced patterns based on real KRT data analysis
# Antibody patterns (1790 entries in real data)
PATTERN_ANTIBODY = re.compile(
    r"\b(?:(?:chicken|mouse|rabbit|goat|rat|human|donkey|sheep)\s+)?(?:monoclonal|polyclonal)?\s*anti-([A-Z0-9-]+)\b",
    re.IGNORECASE
)
PATTERN_ANTIBODY_CONJUGATED = re.compile(
    r"\b(?:PE|FITC|APC|Alexa\s+Fluor\s+\d+|PE-Cy\d+|DAPI)\s+(?:Mouse|Rabbit|Chicken|Goat|Rat)\s+Anti-([A-Z0-9-]+)",
    re.IGNORECASE
)

# Software patterns with versions (1690 entries in real data)  
PATTERN_SOFTWARE_VERSION = re.compile(
    r"\b(CellRanger|HTSeq|FastQC|STAR|Seurat|DESeq2|ImageJ|FIJI|R|Python|MATLAB|Prism|scVelo|pheatmap|EnhancedVolcano|SingleCellExperiment)\s*(?:\(version\s+([\d.]+[a-z]?)\)|\s+version\s+([\d.]+[a-z]?)|\s+v([\d.]+[a-z]?))?",
    re.IGNORECASE
)

# Chemical/reagent patterns (2385 entries - most common in real data)
PATTERN_CHEMICALS = re.compile(
    r"\b(?:Human|Mouse|Rat)?\s*(?:TNF\s*alpha|NURR1|FBS|Fetal\s+Bovine\s+Serum|DAPI|Trypsin|Matrigel|Accutase|L-DOPA|DMSO|BSA|Triton|Tween|PBS|HEPES|EDTA|DTT|PMSF)\b",
    re.IGNORECASE
)

# Oligonucleotide patterns (334 entries - usually NEW)
PATTERN_OLIGONUCLEOTIDES = re.compile(
    r"\b(?:Human|Mouse|Rat)\s+([A-Z0-9]+)\s+(?:PCR|qPCR)\s+primer\s+(?:forward|reverse):\s*([ATCG]{10,})",
    re.IGNORECASE
)

# Cell line patterns (387 entries)
PATTERN_CELL_LINES = re.compile(
    r"\b(?:Human|Mouse):\s*([A-Z0-9/-]+\s*(?:hESC|ESC|cell\s+line))",
    re.IGNORECASE
)

# Commercial assay patterns (297 entries)
PATTERN_COMMERCIAL_ASSAYS = re.compile(
    r"\b(RNAscope.*?kit|.*Supermix|.*Transcription.*kit|.*Imaging\s+Assay|.*protein\s+assay\s+kit|BCA.*kit|TUNEL.*kit)\b",
    re.IGNORECASE
)

# Vendor detection patterns (based on real data analysis)
VENDOR_PATTERNS = {
    'Abcam': re.compile(r'\babcam\b', re.IGNORECASE),
    'BD Biosciences': re.compile(r'\bBD\s+Biosciences?\b', re.IGNORECASE),
    'Invitrogen': re.compile(r'\binvitrogen\b', re.IGNORECASE),
    'Cell Signaling Technology': re.compile(r'\bCell\s+Signaling\b', re.IGNORECASE),
    'Bio-Rad': re.compile(r'\bBio-?Rad\b', re.IGNORECASE),
    'Sigma-Aldrich': re.compile(r'\bSigma-?Aldrich\b', re.IGNORECASE),
    'ACD Biosciences': re.compile(r'\bACD\s+Biosciences?\b', re.IGNORECASE),
    'BioLegend': re.compile(r'\bBioLegend\b', re.IGNORECASE),
    'Pierce': re.compile(r'\bPierce\b', re.IGNORECASE),
    '10x Genomics': re.compile(r'\b10x\s+Genomics\b', re.IGNORECASE),
    'Corning': re.compile(r'\bCorning\b', re.IGNORECASE),
}


def _unique(iterable: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in iterable:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _detect_vendor(text: str, context: str = "") -> Optional[str]:
    """Detect vendor/source from text context"""
    search_text = f"{text} {context}".lower()
    for vendor, pattern in VENDOR_PATTERNS.items():
        if pattern.search(search_text):
            return vendor
    return None


def extract_krt_regex(article_text: str) -> List[KRTEntry]:
    text = article_text or ""
    entries: List[KRTEntry] = []

    # Enhanced antibody extraction (1790 entries in real data)
    for match in PATTERN_ANTIBODY.finditer(text):
        target = match.group(1)
        full_match = match.group(0)
        context = text[max(0, match.start()-100):match.end()+100]
        
        vendor = _detect_vendor(context)
        resource_name = full_match.strip()
        
        entries.append(
            KRTEntry(
                resource_type="Antibody",
                resource_name=resource_name,
                source=vendor or "Unknown vendor",
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Conjugated antibodies (common in flow cytometry)
    for match in PATTERN_ANTIBODY_CONJUGATED.finditer(text):
        target = match.group(1)
        full_match = match.group(0)
        context = text[max(0, match.start()-100):match.end()+100]
        
        vendor = _detect_vendor(context)
        
        entries.append(
            KRTEntry(
                resource_type="Antibody",
                resource_name=full_match.strip(),
                source=vendor or "Unknown vendor",
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Enhanced software extraction with versions (1690 entries in real data)
    for match in PATTERN_SOFTWARE_VERSION.finditer(text):
        software = match.group(1)
        version = match.group(2) or match.group(3) or match.group(4)
        
        if version:
            resource_name = f"{software} (version {version})"
        else:
            resource_name = software
        
        entries.append(
            KRTEntry(
                resource_type="Software/code",
                resource_name=resource_name,
                source="Software developer",
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Chemical/reagent extraction (2385 entries - most common)
    for match in PATTERN_CHEMICALS.finditer(text):
        chemical = match.group(0).strip()
        context = text[max(0, match.start()-100):match.end()+100]
        
        vendor = _detect_vendor(context)
        
        entries.append(
            KRTEntry(
                resource_type="Chemical, peptide, or recombinant protein",
                resource_name=chemical,
                source=vendor or "Unknown vendor",
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Oligonucleotides (334 entries - usually NEW)
    for match in PATTERN_OLIGONUCLEOTIDES.finditer(text):
        species = match.group(0).split()[0]  # Human, Mouse, etc.
        gene = match.group(1)
        sequence = match.group(2) if len(match.groups()) > 1 else ""
        
        primer_type = "forward" if "forward" in match.group(0).lower() else "reverse"
        resource_name = f"{species} {gene} PCR primer {primer_type}"
        if sequence:
            resource_name += f": {sequence}"
        
        entries.append(
            KRTEntry(
                resource_type="Oligonucleotide",
                resource_name=resource_name,
                source="This study",  # Oligonucleotides are usually custom designed
                identifier="No identifier exists",
                new_or_reuse="New",
                additional_information="Custom designed primer",
            )
        )

    # Cell lines (387 entries)
    for match in PATTERN_CELL_LINES.finditer(text):
        cell_line = match.group(0).strip()
        context = text[max(0, match.start()-100):match.end()+100]
        
        # Check if it's from "this study"
        if any(phrase in context.lower() for phrase in ["this study", "this paper", "generated", "created"]):
            source = "This study"
            new_or_reuse = "New"
        else:
            source = "Established cell line"
            new_or_reuse = "Reuse"
        
        entries.append(
            KRTEntry(
                resource_type="Experimental model: Cell line",
                resource_name=cell_line,
                source=source,
                identifier="No identifier exists",
                new_or_reuse=new_or_reuse,
                additional_information=None,
            )
        )

    # Commercial assays (297 entries)
    for match in PATTERN_COMMERCIAL_ASSAYS.finditer(text):
        assay = match.group(0).strip()
        context = text[max(0, match.start()-100):match.end()+100]
        
        vendor = _detect_vendor(context)
        
        entries.append(
            KRTEntry(
                resource_type="Critical commercial assay",
                resource_name=assay,
                source=vendor or "Unknown vendor",
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Original patterns (enhanced)
    # Datasets
    for geo in _unique(PATTERN_GEO.findall(text)):
        entries.append(
            KRTEntry(
                resource_type="Dataset",
                resource_name=f"GEO dataset {geo.upper()}",
                source="Gene Expression Omnibus (GEO)",
                identifier=geo.upper(),
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )
    for sra in _unique(PATTERN_SRA.findall(text)):
        entries.append(
            KRTEntry(
                resource_type="Dataset",
                resource_name=f"SRA dataset {sra.upper()}",
                source="Sequence Read Archive (SRA)",
                identifier=sra.upper(),
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Protocols (enhanced based on real data - 961 entries)
    for pr in _unique(PATTERN_PROTOCOLS.findall(text)):
        context = text[text.find(pr)-100:text.find(pr)+100]
        
        # Check if it's a new protocol from this study
        if any(phrase in context.lower() for phrase in ["this study", "this paper", "we developed", "new protocol"]):
            source = "This study"
            new_or_reuse = "New"
            resource_name = "Custom protocol"
        else:
            source = "protocols.io"
            new_or_reuse = "Reuse"
            resource_name = "Published protocol"
            
        entries.append(
            KRTEntry(
                resource_type="Protocol",
                resource_name=resource_name,
                source=source,
                identifier=f"https://{pr}",
                new_or_reuse=new_or_reuse,
                additional_information=None,
            )
        )

    # Software/code (GitHub repositories)
    for repo in _unique(PATTERN_GITHUB.findall(text)):
        repo_name = repo.split("/")[-1]
        entries.append(
            KRTEntry(
                resource_type="Software/code",
                resource_name=repo_name,
                source="GitHub",
                identifier=f"https://{repo}",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Enhanced RRID extraction for antibodies
    for rrid in _unique(PATTERN_RRID.findall(text)):
        rrid_full = f"RRID:{rrid}"
        context = text[text.find(rrid_full)-100:text.find(rrid_full)+100]
        
        # Try to extract antibody name from context
        vendor = _detect_vendor(context)
        
        # Look for antibody patterns near RRID
        resource_name = rrid_full
        for match in PATTERN_ANTIBODY.finditer(context):
            resource_name = match.group(0).strip()
            break
        
        entries.append(
            KRTEntry(
                resource_type="Antibody",
                resource_name=resource_name,
                source=vendor or "RRID database",
                identifier=rrid_full,
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Plasmids / Recombinant DNA (723 entries in real data)
    for ag in _unique(PATTERN_ADDGENE.findall(text)):
        context = text[text.find(ag)-100:text.find(ag)+100]
        
        # Try to extract plasmid name from context
        resource_name = f"Addgene plasmid #{ag}"
        
        # Look for actual plasmid names in context
        if "pSp" in context or "pCas" in context or "SGL" in context:
            for word in context.split():
                if any(prefix in word for prefix in ["pSp", "pCas", "SGL", "p"]) and len(word) > 3:
                    resource_name = word.strip("().,")
                    break
        
        entries.append(
            KRTEntry(
                resource_type="Recombinant DNA",
                resource_name=resource_name,
                source="Addgene",
                identifier=f"Cat#{ag}",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Enhanced catalog number extraction
    for cat in _unique(PATTERN_CATALOG.findall(text)):
        context = text[text.find(cat)-150:text.find(cat)+150]
        vendor = _detect_vendor(context)
        
        # Determine resource type based on context
        resource_type = "Chemical, peptide, or recombinant protein"
        if any(word in context.lower() for word in ["kit", "assay", "supermix"]):
            resource_type = "Critical commercial assay"
        elif any(word in context.lower() for word in ["antibody", "anti-"]):
            resource_type = "Antibody"
        
        # Try to extract product name from context
        resource_name = f"Product {cat}"
        for chemical_match in PATTERN_CHEMICALS.finditer(context):
            resource_name = chemical_match.group(0).strip()
            break
        for assay_match in PATTERN_COMMERCIAL_ASSAYS.finditer(context):
            resource_name = assay_match.group(0).strip()
            break
        
        entries.append(
            KRTEntry(
                resource_type=resource_type,  # type: ignore[arg-type]
                resource_name=resource_name,
                source=vendor or "Unknown vendor",
                identifier=f"Cat#{cat}",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # DOIs appear in many contexts; map under Dataset if surrounded by data repository cues else Other
    for doi in _unique(PATTERN_DOI.findall(text)):
        res_type = "Other"
        lowered = text.lower()
        if any(
            repo in lowered for repo in ["zenodo", "figshare", "dryad", "dataverse"]
        ):
            res_type = "Dataset"
        entries.append(
            KRTEntry(
                resource_type=res_type,  # type: ignore[arg-type]
                resource_name=f"DOI:{doi}",
                source="DOI",
                identifier=doi,
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Heuristic for models
    if re.search(r"\bHEK[ -]?293\b", text, re.IGNORECASE):
        entries.append(
            KRTEntry(
                resource_type="Experimental model: Cell line",
                resource_name="HEK293",
                source=None,
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )
    if re.search(r"\bMus\s+musculus\b|\bmice\b|\bmouse\b", text, re.IGNORECASE):
        entries.append(
            KRTEntry(
                resource_type="Experimental model: Organism/strain",
                resource_name="Mus musculus",
                source=None,
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Deduplicate by (type, identifier)
    dedup: Dict[str, KRTEntry] = {}
    for e in entries:
        key = f"{e.resource_type}|{e.identifier}"
        if key not in dedup:
            dedup[key] = e
    return list(dedup.values())
