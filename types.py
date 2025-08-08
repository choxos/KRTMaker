from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Literal, Optional


KRT_COLUMN_RESOURCE_TYPE = "RESOURCE TYPE"
KRT_COLUMN_RESOURCE_NAME = "RESOURCE NAME"
KRT_COLUMN_SOURCE = "SOURCE"
KRT_COLUMN_IDENTIFIER = "IDENTIFIER"
KRT_COLUMN_NEW_OR_REUSE = "NEW/REUSE"
KRT_COLUMN_ADDITIONAL_INFO = "ADDITIONAL INFORMATION"


AllowedResourceType = Literal[
    "Dataset",
    "Software/code",
    "Protocol",
    "Antibody",
    "Bacterial strain",
    "Viral vector",
    "Biological sample",
    "Chemical, peptide, or recombinant protein",
    "Critical commercial assay",
    "Experimental model: Cell line",
    "Experimental model: Organism/strain",
    "Oligonucleotide",
    "Recombinant DNA",
    "Other",
]


ALLOWED_RESOURCE_TYPES: List[str] = [
    "Dataset",
    "Software/code",
    "Protocol",
    "Antibody",
    "Bacterial strain",
    "Viral vector",
    "Biological sample",
    "Chemical, peptide, or recombinant protein",
    "Critical commercial assay",
    "Experimental model: Cell line",
    "Experimental model: Organism/strain",
    "Oligonucleotide",
    "Recombinant DNA",
    "Other",
]


@dataclass
class KRTEntry:
    resource_type: AllowedResourceType
    resource_name: str
    source: Optional[str]
    identifier: str
    new_or_reuse: str
    additional_information: Optional[str]

    def to_row(self) -> Dict[str, str]:
        # Enforce mandatory fields
        resource_name = self.resource_name.strip() or "Unknown resource"
        identifier = self.identifier.strip() or "No identifier exists"
        new_or_reuse = self.new_or_reuse.strip() or "Reuse"

        row: Dict[str, str] = {
            KRT_COLUMN_RESOURCE_TYPE: str(self.resource_type),
            KRT_COLUMN_RESOURCE_NAME: resource_name,
            KRT_COLUMN_SOURCE: (self.source or "").strip(),
            KRT_COLUMN_IDENTIFIER: identifier,
            KRT_COLUMN_NEW_OR_REUSE: new_or_reuse,
            KRT_COLUMN_ADDITIONAL_INFO: (self.additional_information or "").strip(),
        }
        return row


def krt_entries_to_json_rows(entries: List[KRTEntry]) -> List[Dict[str, str]]:
    return [entry.to_row() for entry in entries]
