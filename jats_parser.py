from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from lxml import etree


JATS_NS = {
    "j": "http://jats.nlm.nih.gov",
}


def parse_xml_string(xml_content: bytes) -> etree._ElementTree:
    parser = etree.XMLParser(recover=True, remove_blank_text=True)
    return etree.fromstring(xml_content, parser=parser).getroottree()


def read_xml(path: str) -> etree._ElementTree:
    with open(path, "rb") as f:
        content = f.read()
    return parse_xml_string(content)


def extract_plain_text(tree: etree._ElementTree) -> str:
    text_parts: List[str] = []
    for elem in tree.iter():
        if elem.text and elem.text.strip():
            text_parts.append(elem.text.strip())
    return " \n".join(text_parts)


def extract_sections(tree: etree._ElementTree) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    for sec in tree.findall(".//sec"):
        title_elem = sec.find("title")
        title = (
            title_elem.text.strip()
            if title_elem is not None and title_elem.text
            else ""
        )
        para_texts: List[str] = []
        for p in sec.findall("p"):
            if p.text and p.text.strip():
                para_texts.append(p.text.strip())
        if title or para_texts:
            sections.setdefault(title or "Untitled", []).append(" ".join(para_texts))
    return {k: "\n".join(vs) for k, vs in sections.items()}


def extract_external_links(tree: etree._ElementTree) -> List[str]:
    links: List[str] = []
    for ext in tree.findall(".//ext-link"):
        href = ext.get("{http://www.w3.org/1999/xlink}href") or ext.get("href")
        if href:
            links.append(href)
    return links


def extract_title_and_abstract(
    tree: etree._ElementTree,
) -> Tuple[Optional[str], Optional[str]]:
    title = None
    abstract = None
    title_elem = tree.find(".//article-title")
    if title_elem is not None and title_elem.text:
        title = title_elem.text.strip()
    abstract_elem = tree.find(".//abstract")
    if abstract_elem is not None:
        # concatenate text content
        abstract_parts: List[str] = []
        for t in abstract_elem.itertext():
            if t and t.strip():
                abstract_parts.append(t.strip())
        abstract = " ".join(abstract_parts)
    return title, abstract
