from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MecaContents:
    root_dir: str
    xml_paths: List[str]
    pdf_paths: List[str]


def is_meca_file(path: str) -> bool:
    return path.endswith(".meca") or path.endswith(".zip")


def unpack_meca(meca_path: str, out_dir: str) -> MecaContents:
    if not zipfile.is_zipfile(meca_path):
        raise ValueError(f"Not a valid MECA (zip) file: {meca_path}")

    with zipfile.ZipFile(meca_path, "r") as zf:
        zf.extractall(out_dir)

    # MECA layout contains a 'content' directory at the root of the archive.
    # We will scan recursively for .xml and .pdf files underneath.
    xml_paths: List[str] = []
    pdf_paths: List[str] = []
    for root, _dirs, files in os.walk(out_dir):
        for name in files:
            lower = name.lower()
            abs_path = os.path.join(root, name)
            if lower.endswith(".xml"):
                xml_paths.append(abs_path)
            elif lower.endswith(".pdf"):
                pdf_paths.append(abs_path)

    return MecaContents(root_dir=out_dir, xml_paths=xml_paths, pdf_paths=pdf_paths)
