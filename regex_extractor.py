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

# ULTIMATE ANTIBODY PATTERNS - Based on actual AI KRT data analysis
# Covers all formats found in real data: "Anti-X antibody [clone]", "X Antibody (clone)", "Cleaved X Antibody", etc.
PATTERN_ANTIBODY_ULTIMATE = re.compile(
    r"""
    (?:
        # Format: "Anti-PROTEIN antibody [CLONE]" or "Anti-PROTEIN antibody (CLONE)"
        (?:Anti-|anti-|α-)\s*([A-Z0-9/-]+)\s+antibody\s*(?:\[([A-Z0-9()]+)\]|\(([A-Z0-9]+)\))?
    |
        # Format: "PROTEIN Antibody (CLONE)" or "PROTEIN antibody [CLONE]"  
        ([A-Z0-9/-]+)\s+(?:Antibody|antibody)\s*(?:\[([A-Z0-9()]+)\]|\(([A-Z0-9]+)\))?
    |
        # Format: "Cleaved PROTEIN (details) Antibody (CLONE)"
        (?:Cleaved\s+)?([A-Z0-9/-]+)\s+(?:\([A-Za-z0-9]+\))?\s*(?:Antibody|antibody)\s*(?:\[([A-Z0-9()]+)\]|\(([A-Z0-9]+)\))?
    |
        # Format: "FLUOROPHORE anti-mouse PROTEIN Antibody, Clone XXX"
        (?:PE|FITC|APC|BV\d+|PerCP/Cy\d+\.?\d*|Alexa\s+Fluor\s+\d+)\s+anti-(?:mouse|human|rat)\s+([A-Z0-9/-]+)\s+Antibody,?\s*(?:Clone\s+([A-Z0-9./]+))?
    |
        # Format: "CD## (FLUOROPHORE, clone XXXX)"
        (CD\d+)\s*\(([A-Z]+),?\s*clone\s+([A-Z0-9]+)\)
    |
        # Format: "Purified anti-mouse PROTEIN Antibody, Clone XX"
        Purified\s+anti-(?:mouse|human|rat)\s+([A-Z0-9/-]+)\s+(?:\([^)]*\))?\s*Antibody,?\s*(?:Clone\s+([A-Z0-9]+))?
    |
        # Format: "Total OXPHOS [details] Antibody Cocktail"
        (Total\s+[A-Z]+\s+[^A]*Antibody\s+Cocktail)
    )
    """, 
    re.IGNORECASE | re.VERBOSE
)

# Additional antibody patterns for complex cases
PATTERN_ANTIBODY_COMPLEX = re.compile(
    r"\b((?:Total\s+)?OXPHOS\s+[^A]*Antibody\s+Cocktail|(?:PE|FITC|APC|BV\d+)/Cy\d+\s+anti-mouse\s+[A-Z0-9/-]+\s+Antibody)",
    re.IGNORECASE
)

# ULTIMATE SOFTWARE PATTERNS - Based on actual AI KRT data (66 unique tools found)
PATTERN_SOFTWARE_ULTIMATE = re.compile(
    r"\b(GraphPad\s+Prism|FreeSurfer|FSL|Brain\s+Connectivity\s+Toolbox|BrainNet\s+Viewer|FIJI|Relion|Motioncorr2|CTFFIND|EPU\s+software|ChimeraX|MODELLER|Coot|Phenix|DeepEMhancer|LocScale|CheckM2|CheckV|BLAST\+|Bandage|Clustal\s+Omega|CortexModel|DNA\s+melting\s+temperature\s+calculator|Elements\s+Data\s+Reader\s+software|FastQC|Geneious\s+Prime|HostPhinder|Igor\s+Pro|Kleborate|LMFIT|MATLAB|MLSpike|MODELLER|Motioncorr2|OMERO|Phenix|PsychoPy|Suite2p|R\s+package|R\s+software|ImageJ|STAR|Seurat|DESeq2|scVelo|pheatmap|EnhancedVolcano|SingleCellExperiment|CellRanger|HTSeq|Python|SPSS|PyMOL|Gaussian|VMD|FlowJo|Imaris|Prism|Adobe\s+Illustrator|Adobe\s+Photoshop|Inkscape|OriginPro|Mathematica|Stata|SAS|JMP|Spotfire|Tableau|CytoSeer|CytExpert|BD\s+FACSDiva|Columbus|Opera\s+Phenix|ZEN|NIS-Elements|MetaMorph|MicroManager|CellProfiler|QuPath|Icy|ITK-SNAP)\s*(?:\(version\s+([\d.v]+[a-z]?)\)|\s+version\s+([\d.v]+[a-z]?)|\s+v([\d.v]+[a-z]?)|\s+([\d.v]+[a-z]?))?",
    re.IGNORECASE
)

# Simple software names (for cases without version info)
PATTERN_SOFTWARE_SIMPLE = re.compile(
    r"\b(ChatGPT|MATLAB\s+\d{4}[a-z]?|Igor\s+Pro\s+\d+|FIJI|Prism|ImageJ|R|Python|SPSS|FreeSurfer|FSL|ChimeraX|Suite2p|MLSpike|LMFIT|PsychoPy)\b",
    re.IGNORECASE
)

# Chemical/reagent patterns (significantly expanded based on missed resources)
PATTERN_CHEMICALS = re.compile(
    r"\b(?:Human|Mouse|Rat)?\s*(?:TNF\s*alpha|NURR1|FBS|Fetal\s+Bovine\s+Serum|DAPI|Trypsin|Matrigel|Accutase|L-DOPA|DMSO|BSA|Triton|Tween|PBS|HEPES|EDTA|DTT|PMSF|isopropyl\s+β-d-1-thiogalactopyranoside|IPTG|glucose|sucrose|mannitol|sorbitol|glycerol|ethanol|methanol|acetone|chloroform|formaldehyde|paraformaldehyde|glutaraldehyde|osmium\s+tetroxide|uranyl\s+acetate|lead\s+citrate)\b",
    re.IGNORECASE
)

# Viral vector patterns (based on missed AAV resources)
PATTERN_VIRAL_VECTORS = re.compile(
    r"\b(AAV[0-9]+\.(?:CAG|CMV|Syn|CaMKII|hSyn|EF1a|GFAP)\.(?:GCaMP|jGCaMP|FLEX|Cre|ChR2|eYFP|mCherry|tdTomato|ArchT|eNpHR|GFP)\.[\w.]+|rAAV[0-9]+-[\w.-]+|lentivirus|adenovirus|HSV|VSV)\b",
    re.IGNORECASE
)

# Protocol patterns (for missed protocols)
PATTERN_PROTOCOLS_SPECIFIC = re.compile(
    r"\b(animal\s+procedures\s+for\s+in\s+vivo\s+experiments|surgery\s+to\s+inject\s+viral\s+vectors|calcium\s+imaging\s+data\s+acquisition|immunoperoxidase\s+staining|peripheral\s+blood\s+mononuclear\s+cell\s+isolation|two-photon\s+calcium\s+imaging|miniscope\s+calcium\s+imaging)\b",
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

# Vendor detection patterns (significantly expanded)
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
    'Thermo Fisher Scientific': re.compile(r'\bThermo\s+Fisher\b', re.IGNORECASE),
    'Millipore': re.compile(r'\bMillipore\b', re.IGNORECASE),
    'Santa Cruz Biotechnology': re.compile(r'\bSanta\s+Cruz\b', re.IGNORECASE),
    'R&D Systems': re.compile(r'\bR&D\s+Systems\b', re.IGNORECASE),
    'Jackson ImmunoResearch': re.compile(r'\bJackson\s+ImmunoResearch\b', re.IGNORECASE),
    'eBioscience': re.compile(r'\beBioscience\b', re.IGNORECASE),
    'Molecular Probes': re.compile(r'\bMolecular\s+Probes\b', re.IGNORECASE),
    'Life Technologies': re.compile(r'\bLife\s+Technologies\b', re.IGNORECASE),
    'Promega': re.compile(r'\bPromega\b', re.IGNORECASE),
    'New England Biolabs': re.compile(r'\bNEB\b|New\s+England\s+Biolabs', re.IGNORECASE),
    'Roche': re.compile(r'\bRoche\b', re.IGNORECASE),
    'Qiagen': re.compile(r'\bQiagen\b', re.IGNORECASE),
    'Agilent': re.compile(r'\bAgilent\b', re.IGNORECASE),
    'Applied Biosystems': re.compile(r'\bApplied\s+Biosystems\b', re.IGNORECASE),
    'Illumina': re.compile(r'\bIllumina\b', re.IGNORECASE),
    'Addgene': re.compile(r'\bAddgene\b', re.IGNORECASE),
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

    # ULTIMATE ANTIBODY EXTRACTION - matches actual AI patterns
    for match in PATTERN_ANTIBODY_ULTIMATE.finditer(text):
        full_match = match.group(0).strip()
        context = text[max(0, match.start()-100):match.end()+100]
        
        vendor = _detect_vendor(context)
        
        # Extract catalog/RRID info from context
        identifier = "No identifier exists"
        cat_match = PATTERN_CATALOG.search(context)
        rrid_match = PATTERN_RRID.search(context)
        if cat_match and rrid_match:
            identifier = f"Cat# {cat_match.group(1)}; RRID: {rrid_match.group(1)}"
        elif cat_match:
            identifier = f"Cat# {cat_match.group(1)}"
        elif rrid_match:
            identifier = f"RRID: {rrid_match.group(1)}"
        
        entries.append(
            KRTEntry(
                resource_type="Antibody",
                resource_name=full_match,
                source=vendor or "Antibody vendor",
                identifier=identifier,
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Complex antibody patterns (cocktails, etc.)
    for match in PATTERN_ANTIBODY_COMPLEX.finditer(text):
        full_match = match.group(0).strip()
        context = text[max(0, match.start()-100):match.end()+100]
        vendor = _detect_vendor(context)
        
        entries.append(
            KRTEntry(
                resource_type="Antibody",
                resource_name=full_match,
                source=vendor or "Antibody vendor",
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Note: Conjugated antibodies are now handled by PATTERN_ANTIBODY_ULTIMATE

    # ULTIMATE SOFTWARE EXTRACTION - matches actual AI patterns  
    for match in PATTERN_SOFTWARE_ULTIMATE.finditer(text):
        software = match.group(1)
        version = match.group(2) or match.group(3) or match.group(4) or match.group(5)
        
        if version:
            resource_name = f"{software} (version {version})"
        else:
            resource_name = software
        
        # Determine source based on context and software name
        context = text[max(0, match.start()-100):match.end()+100]
        source = "Software developer"
        if "10x genomics" in context.lower() or "10x" in software.lower():
            source = "10x Genomics"
        elif "graphpad" in software.lower():
            source = "GraphPad Software"
        elif "mathworks" in context.lower() or "matlab" in software.lower():
            source = "MathWorks"
        elif "adobe" in software.lower():
            source = "Adobe"
        elif "fsl" in software.lower():
            source = "FMRIB Software Library"
        elif "freesurfer" in software.lower():
            source = "FreeSurfer"
        elif "fiji" in software.lower() or "imagej" in software.lower():
            source = "ImageJ/FIJI"
        
        entries.append(
            KRTEntry(
                resource_type="Software/code",
                resource_name=resource_name,
                source=source,
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Simple software patterns (no version info)
    for match in PATTERN_SOFTWARE_SIMPLE.finditer(text):
        software = match.group(0).strip()
        
        # Determine source
        source = "Software developer"
        if "matlab" in software.lower():
            source = "MathWorks"
        elif "prism" in software.lower():
            source = "GraphPad Software"
        elif "spss" in software.lower():
            source = "IBM"
        elif "fiji" in software.lower() or "imagej" in software.lower():
            source = "ImageJ/FIJI"
        
        entries.append(
            KRTEntry(
                resource_type="Software/code",
                resource_name=software,
                source=source,
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

    # Viral vectors (new extraction based on missed resources)
    for match in PATTERN_VIRAL_VECTORS.finditer(text):
        vector = match.group(0).strip()
        context = text[max(0, match.start()-100):match.end()+100]
        
        vendor = _detect_vendor(context)
        
        entries.append(
            KRTEntry(
                resource_type="Viral vector",
                resource_name=vector,
                source=vendor or "Vector source",
                identifier="No identifier exists",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Protocol-specific extraction (new)
    for match in PATTERN_PROTOCOLS_SPECIFIC.finditer(text):
        protocol = match.group(0).strip()
        context = text[max(0, match.start()-100):match.end()+100]
        
        # Check if it's from "this study"
        if any(phrase in context.lower() for phrase in ["this study", "this paper", "we developed", "we performed"]):
            source = "This study"
            new_or_reuse = "New"
        else:
            source = "Published protocol"
            new_or_reuse = "Reuse"
        
        entries.append(
            KRTEntry(
                resource_type="Protocol",
                resource_name=protocol,
                source=source,
                identifier="No identifier exists",
                new_or_reuse=new_or_reuse,
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

    # DOIs - only include those that are clearly datasets/resources (reduce false positives)
    for doi in _unique(PATTERN_DOI.findall(text)):
        # Check context around the DOI
        doi_pos = text.find(doi)
        context = text[max(0, doi_pos-200):doi_pos+200].lower()
        
        # Only include DOIs that are clearly resources/datasets, not citations
        if any(keyword in context for keyword in [
            "zenodo", "figshare", "dryad", "dataverse", "dataset", "data repository", 
            "supplementary data", "data availability", "accession", "available at"
        ]):
            res_type = "Dataset"
            entries.append(
                KRTEntry(
                    resource_type=res_type,
                    resource_name=f"Dataset DOI:{doi}",
                    source="Data repository",
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
