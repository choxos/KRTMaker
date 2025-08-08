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
        # Extract all text content from the section, including nested sections
        para_texts: List[str] = []
        
        # Get all paragraphs within this section (including nested ones)
        for p in sec.findall(".//p"):
            if p.text and p.text.strip():
                para_texts.append(p.text.strip())
            # Also get any text from child elements within paragraphs
            for text in p.itertext():
                if text and text.strip() and text.strip() not in [pt.strip() for pt in para_texts]:
                    para_texts.append(text.strip())
        
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


def extract_relevant_sections_for_llm(tree: etree._ElementTree) -> str:
    """
    Extract only methods, results, and appendix sections for LLM processing.
    This reduces API usage by focusing on content most likely to contain resource information.
    """
    # Patterns for sections we want to include
    methods_patterns = [
        "methods", "materials and methods", "methodology", "experimental procedures",
        "materials & methods", "experimental methods", "materials", "procedures",
        "experimental design", "study design", "data collection"
    ]
    
    results_patterns = [
        "results", "findings", "observations", "outcomes"
    ]
    
    appendix_patterns = [
        "appendix", "supplementary methods", "supporting information", 
        "supplemental methods", "additional methods", "supplementary materials",
        "supporting methods", "appendices"
    ]
    
    # Get all sections
    all_sections = extract_sections(tree)
    relevant_text_parts = []
    
    for section_title, section_content in all_sections.items():
        title_lower = section_title.lower().strip()
        
        # Check if this is a methods section
        if any(pattern in title_lower for pattern in methods_patterns):
            relevant_text_parts.append(f"METHODS SECTION - {section_title}:\n{section_content}\n")
            continue
            
        # Check if this is a results section (but exclude discussion)
        if any(pattern in title_lower for pattern in results_patterns):
            # If it's "Results and Discussion", try to extract only results part
            if "discussion" in title_lower or "conclusions" in title_lower:
                # Split content and try to find where discussion starts
                lines = section_content.split('\n')
                results_lines = []
                for line in lines:
                    line_lower = line.lower()
                    # Stop at discussion indicators
                    if any(indicator in line_lower for indicator in 
                          ["discussion", "in conclusion", "to conclude", "these findings suggest",
                           "in summary", "our results demonstrate", "these results indicate"]):
                        break
                    results_lines.append(line)
                
                if results_lines:
                    relevant_text_parts.append(f"RESULTS SECTION - {section_title}:\n" + '\n'.join(results_lines) + "\n")
            else:
                relevant_text_parts.append(f"RESULTS SECTION - {section_title}:\n{section_content}\n")
            continue
            
        # Check if this is an appendix section
        if any(pattern in title_lower for pattern in appendix_patterns):
            relevant_text_parts.append(f"APPENDIX SECTION - {section_title}:\n{section_content}\n")
            continue
    
    # If no relevant sections found, fall back to extracting from the body
    if not relevant_text_parts:
        # Try to find methods and results in the main body text
        body_text = extract_plain_text(tree)
        
        # Look for method-like content patterns
        method_indicators = ["protocol", "procedure", "antibod", "reagent", "software", "analysis", "statistical"]
        if any(indicator in body_text.lower() for indicator in method_indicators):
            relevant_text_parts.append(f"EXTRACTED CONTENT (Methods/Results):\n{body_text[:50000]}\n")
    
    # Join all relevant sections
    result = "\n".join(relevant_text_parts).strip()
    
    # If still no content, return first 50k characters as fallback
    if not result:
        result = extract_plain_text(tree)[:50000]
    
    return result


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
