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
    
    # Find sections with and without namespace
    sec_elements = tree.findall(".//sec") + tree.findall(".//{http://jats.nlm.nih.gov}sec")
    
    for sec in sec_elements:
        title_elem = sec.find("title") or sec.find("{http://jats.nlm.nih.gov}title")
        title = (
            title_elem.text.strip()
            if title_elem is not None and title_elem.text
            else ""
        )
        
        # Extract all text content from the section, including nested sections
        para_texts: List[str] = []
        
        # Get all paragraphs within this section (including nested ones) - with and without namespace
        paragraphs = sec.findall(".//p") + sec.findall(".//{http://jats.nlm.nih.gov}p")
        
        for p in paragraphs:
            # Get all text content from this paragraph
            for text in p.itertext():
                if text and text.strip():
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
    Extract comprehensive content for LLM processing, including methods, results, appendices,
    and sections that commonly contain KRT tables (after discussion, references, etc.).
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
        "supporting methods", "appendices", "supplementary data"
    ]
    
    # NEW: Patterns for sections that often contain KRT tables
    krt_table_patterns = [
        "key resources", "resource table", "resources", "reagents", "materials table",
        "software table", "antibodies table", "data availability", "availability",
        "reagent table", "key resource table", "table", "supplementary table"
    ]
    
    # Get all sections
    all_sections = extract_sections(tree)
    relevant_text_parts = []
    found_sections = set()
    
    for section_title, section_content in all_sections.items():
        title_lower = section_title.lower().strip()
        
        # Check if this is a methods section
        if any(pattern in title_lower for pattern in methods_patterns):
            relevant_text_parts.append(f"METHODS SECTION - {section_title}:\n{section_content}\n")
            found_sections.add('methods')
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
            found_sections.add('results')
            continue
            
        # Check if this is an appendix section
        if any(pattern in title_lower for pattern in appendix_patterns):
            relevant_text_parts.append(f"APPENDIX SECTION - {section_title}:\n{section_content}\n")
            found_sections.add('appendix')
            continue
            
        # NEW: Check if this section likely contains KRT tables
        if any(pattern in title_lower for pattern in krt_table_patterns):
            relevant_text_parts.append(f"KRT/TABLE SECTION - {section_title}:\n{section_content}\n")
            found_sections.add('krt_tables')
            continue
    
    # NEW: Extract tables from anywhere in the document, especially after discussion/references
    table_content = extract_tables_and_end_content(tree)
    if table_content:
        relevant_text_parts.append(f"TABLES AND END CONTENT:\n{table_content}\n")
        found_sections.add('tables')
    
    # If no relevant sections found, fall back to extracting from the body
    if not relevant_text_parts:
        # Try to find methods and results in the main body text
        body_text = extract_plain_text(tree)
        
        # Look for method-like content patterns
        method_indicators = ["protocol", "procedure", "antibod", "reagent", "software", "analysis", "statistical"]
        if any(indicator in body_text.lower() for indicator in method_indicators):
            relevant_text_parts.append(f"EXTRACTED CONTENT (Methods/Results):\n{body_text[:75000]}\n")
    
    # Join all relevant sections
    result = "\n".join(relevant_text_parts).strip()
    
    # If still no content, return first 75k characters as fallback (increased from 50k)
    if not result:
        result = extract_plain_text(tree)[:75000]
    
    return result


def extract_tables_and_end_content(tree: etree._ElementTree) -> str:
    """
    Extract table content and content from the end of the document where KRT tables are often placed.
    This includes content after discussion, references, and any standalone tables.
    """
    content_parts = []
    
    # 1. Extract all table elements with their captions (with and without namespace)
    table_wraps = tree.findall(".//table-wrap") + tree.findall(".//{http://jats.nlm.nih.gov}table-wrap")
    
    for table in table_wraps:
        table_id = table.get("id", "")
        
        # Get table caption (with and without namespace)
        caption_elem = (table.find(".//caption") or 
                       table.find(".//{http://jats.nlm.nih.gov}caption"))
        caption_text = ""
        if caption_elem is not None:
            caption_text = " ".join(caption_elem.itertext()).strip()
        
        # Get table content (with and without namespace)
        table_elem = (table.find(".//table") or 
                     table.find(".//{http://jats.nlm.nih.gov}table"))
        table_text = ""
        if table_elem is not None:
            table_text = " ".join(table_elem.itertext()).strip()
        
        if caption_text or table_text:
            content_parts.append(f"TABLE {table_id}:\nCaption: {caption_text}\nContent: {table_text}\n")
    
    # 2. Extract content from sections that commonly appear after main text
    all_sections = extract_sections(tree)
    end_section_patterns = [
        "acknowledgment", "acknowledgments", "funding", "author contribution", 
        "data availability", "conflicts of interest", "supplementary", "additional files",
        "tables", "figures", "legends", "competing interests", "ethics", "consent"
    ]
    
    for section_title, section_content in all_sections.items():
        title_lower = section_title.lower().strip()
        if any(pattern in title_lower for pattern in end_section_patterns):
            # Check if this section contains table-like content
            content_lower = section_content.lower()
            if any(indicator in content_lower for indicator in 
                  ["table", "resource", "antibod", "software", "reagent", "protocol", "dataset"]):
                content_parts.append(f"END SECTION - {section_title}:\n{section_content}\n")
    
    # 3. Look for any standalone table content in the back matter (with and without namespace)
    back_matter = tree.find(".//back") or tree.find(".//{http://jats.nlm.nih.gov}back")
    if back_matter is not None:
        back_text = " ".join(back_matter.itertext()).strip()
        if back_text and len(back_text) > 100:  # Only include if substantial content
            # Check if it contains resource-related keywords
            back_lower = back_text.lower()
            if any(keyword in back_lower for keyword in 
                  ["table", "resource", "antibod", "software", "reagent", "material", "protocol"]):
                content_parts.append(f"BACK MATTER:\n{back_text}\n")
    
    return "\n".join(content_parts).strip()


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
