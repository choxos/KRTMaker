from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from .types import (
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


def _unique(iterable: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in iterable:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_krt_regex(article_text: str) -> List[KRTEntry]:
    text = article_text or ""

    entries: List[KRTEntry] = []

    # Datasets
    for geo in _unique(PATTERN_GEO.findall(text)):
        entries.append(
            KRTEntry(
                resource_type="Dataset",
                resource_name=geo.upper(),
                source="GEO",
                identifier=geo.upper(),
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )
    for sra in _unique(PATTERN_SRA.findall(text)):
        entries.append(
            KRTEntry(
                resource_type="Dataset",
                resource_name=sra.upper(),
                source="SRA",
                identifier=sra.upper(),
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Protocols
    for pr in _unique(PATTERN_PROTOCOLS.findall(text)):
        entries.append(
            KRTEntry(
                resource_type="Protocol",
                resource_name="protocols.io protocol",
                source="protocols.io",
                identifier=pr,
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Software/code
    for repo in _unique(PATTERN_GITHUB.findall(text)):
        entries.append(
            KRTEntry(
                resource_type="Software/code",
                resource_name=repo.split("/")[-1],
                source="GitHub",
                identifier=f"https://{repo}",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Antibodies via RRID
    for rrid in _unique(PATTERN_RRID.findall(text)):
        ab = f"RRID:{rrid}"
        entries.append(
            KRTEntry(
                resource_type="Antibody",
                resource_name=ab,
                source="RRID",
                identifier=ab,
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Plasmids / Recombinant DNA
    for ag in _unique(PATTERN_ADDGENE.findall(text)):
        entries.append(
            KRTEntry(
                resource_type="Recombinant DNA",
                resource_name=f"Addgene plasmid {ag}",
                source="Addgene",
                identifier=f"Addgene:{ag}",
                new_or_reuse="Reuse",
                additional_information=None,
            )
        )

    # Chemicals / assays via catalog numbers and vendor mentions
    for cat in _unique(PATTERN_CATALOG.findall(text)):
        entries.append(
            KRTEntry(
                resource_type="Chemical, peptide, or recombinant protein",
                resource_name=f"Reagent {cat}",
                source=None,
                identifier=f"Catalog:{cat}",
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
