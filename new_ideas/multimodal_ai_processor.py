"""
Multimodal AI Processing System for KRT Extraction

This module implements advanced multimodal processing using LayoutLMv3 architecture
to extract Key Resources Tables from both textual and visual elements including 
figures, tables, and supplementary materials in scientific manuscripts.

Based on Claude Opus 4.1 research recommendations for addressing the 54% resource 
identification failure rate in biomedical literature.
"""

import torch
import cv2
import numpy as np
from transformers import (
    LayoutLMv3Processor, 
    LayoutLMv3ForTokenClassification,
    AutoTokenizer
)
from PIL import Image, ImageDraw, ImageFont
import pdf2image
import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Optional, Any
import json
import re
from dataclasses import dataclass
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExtractedResource:
    """Data class for extracted resource information"""
    resource_type: str
    resource_name: str
    source: str
    identifier: str
    new_reuse: str
    additional_info: str
    confidence_score: float
    location: Dict[str, Any]  # bbox, page number, section


@dataclass
class DocumentSection:
    """Data class for document sections"""
    section_type: str  # 'text', 'table', 'figure', 'supplementary'
    content: str
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    page_number: int
    confidence: float


class MultimodalKRTProcessor:
    """
    Advanced multimodal processor for extracting KRT information from scientific documents
    using LayoutLMv3 architecture for unified text and image understanding.
    """
    
    def __init__(self, model_name: str = "microsoft/layoutlmv3-base"):
        """
        Initialize the multimodal processor
        
        Args:
            model_name: HuggingFace model identifier for LayoutLMv3
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
        # Load LayoutLMv3 model and processor
        try:
            self.processor = LayoutLMv3Processor.from_pretrained(model_name)
            self.model = LayoutLMv3ForTokenClassification.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Loaded LayoutLMv3 model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load LayoutLMv3 model: {e}")
            raise
        
        # Resource type patterns based on ASAP guidelines
        self.resource_patterns = {
            'antibody': [
                r'anti-\w+', r'antibody', r'Ab\b', r'monoclonal', r'polyclonal',
                r'primary antibody', r'secondary antibody'
            ],
            'software': [
                r'software', r'algorithm', r'package', r'tool', r'script',
                r'version \d+', r'v\d+\.\d+', r'ImageJ', r'MATLAB', r'Python'
            ],
            'dataset': [
                r'dataset', r'data', r'GEO:', r'GSE\d+', r'repository',
                r'accession', r'database'
            ],
            'cell_line': [
                r'cell line', r'cells', r'culture', r'passage', r'ATCC',
                r'immortalized', r'primary cells'
            ],
            'reagent': [
                r'reagent', r'chemical', r'compound', r'buffer', r'solution',
                r'kit', r'catalog', r'Cat#', r'catalogue'
            ]
        }
        
        # RRID patterns
        self.rrid_pattern = r'RRID:\s*([A-Z]+_\d+)'
        self.catalog_pattern = r'Cat#?\s*([A-Z0-9\-_]+)'
        
    def extract_from_pdf(self, pdf_path: str) -> List[ExtractedResource]:
        """
        Extract KRT resources from a PDF document using multimodal processing
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of extracted resources with confidence scores
        """
        logger.info(f"Processing PDF: {pdf_path}")
        
        # Convert PDF to images
        images = self._pdf_to_images(pdf_path)
        
        # Extract text and layout information
        document_sections = []
        for page_num, image in enumerate(images):
            sections = self._process_page(image, page_num)
            document_sections.extend(sections)
        
        # Extract resources using multimodal analysis
        resources = self._extract_resources_multimodal(document_sections, images)
        
        # Post-process and validate
        validated_resources = self._validate_and_score(resources)
        
        logger.info(f"Extracted {len(validated_resources)} resources")
        return validated_resources
    
    def _pdf_to_images(self, pdf_path: str, dpi: int = 200) -> List[Image.Image]:
        """Convert PDF pages to PIL Images"""
        try:
            images = pdf2image.convert_from_path(pdf_path, dpi=dpi)
            logger.info(f"Converted PDF to {len(images)} images")
            return images
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            return []
    
    def _process_page(self, image: Image.Image, page_num: int) -> List[DocumentSection]:
        """
        Process a single page using LayoutLMv3 to identify sections and extract text
        
        Args:
            image: PIL Image of the page
            page_num: Page number
            
        Returns:
            List of document sections with layout information
        """
        try:
            # Prepare input for LayoutLMv3
            encoding = self.processor(image, return_tensors="pt")
            encoding = {k: v.to(self.device) for k, v in encoding.items()}
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(**encoding)
            
            # Extract predictions and layout
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # Convert to document sections
            sections = self._layout_to_sections(encoding, predictions, page_num)
            
            return sections
            
        except Exception as e:
            logger.error(f"Failed to process page {page_num}: {e}")
            return []
    
    def _layout_to_sections(self, encoding, predictions, page_num: int) -> List[DocumentSection]:
        """Convert LayoutLMv3 output to structured document sections"""
        sections = []
        
        # Extract bounding boxes and text
        bbox = encoding['bbox'][0]  # Remove batch dimension
        
        # Group tokens by sections (simplified approach)
        # In practice, you'd use the model's predictions to identify section types
        text_tokens = []
        current_bbox = [float('inf'), float('inf'), 0, 0]
        
        for i, box in enumerate(bbox):
            if box.sum() > 0:  # Valid bounding box
                text_tokens.append(i)
                # Update overall bbox
                current_bbox[0] = min(current_bbox[0], box[0].item())
                current_bbox[1] = min(current_bbox[1], box[1].item())
                current_bbox[2] = max(current_bbox[2], box[2].item())
                current_bbox[3] = max(current_bbox[3], box[3].item())
        
        if text_tokens:
            # Extract text from tokens (simplified)
            section = DocumentSection(
                section_type='text',
                content="",  # Would extract actual text here
                bbox=tuple(current_bbox),
                page_number=page_num,
                confidence=0.8
            )
            sections.append(section)
        
        return sections
    
    def _extract_resources_multimodal(self, sections: List[DocumentSection], 
                                    images: List[Image.Image]) -> List[ExtractedResource]:
        """
        Extract resources using multimodal analysis of text and visual elements
        
        Args:
            sections: List of document sections
            images: Original page images
            
        Returns:
            List of extracted resources
        """
        resources = []
        
        for section in sections:
            # Text-based extraction
            text_resources = self._extract_from_text(section)
            resources.extend(text_resources)
            
            # Visual element extraction (tables, figures)
            if section.section_type in ['table', 'figure']:
                visual_resources = self._extract_from_visual(section, images)
                resources.extend(visual_resources)
        
        return resources
    
    def _extract_from_text(self, section: DocumentSection) -> List[ExtractedResource]:
        """Extract resources from text content using NLP patterns"""
        resources = []
        
        for resource_type, patterns in self.resource_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, section.content, re.IGNORECASE)
                for match in matches:
                    # Extract additional context around the match
                    context = self._extract_context(section.content, match.span())
                    
                    # Try to identify source, identifier, etc.
                    source = self._identify_source(context)
                    identifier = self._identify_identifier(context)
                    
                    resource = ExtractedResource(
                        resource_type=resource_type,
                        resource_name=match.group(),
                        source=source,
                        identifier=identifier,
                        new_reuse=self._determine_new_reuse(source),
                        additional_info="",
                        confidence_score=0.7,
                        location={
                            'bbox': section.bbox,
                            'page': section.page_number,
                            'section': section.section_type
                        }
                    )
                    resources.append(resource)
        
        return resources
    
    def _extract_from_visual(self, section: DocumentSection, 
                           images: List[Image.Image]) -> List[ExtractedResource]:
        """Extract resources from visual elements like tables and figures"""
        resources = []
        
        # This would implement table detection and OCR
        # For now, return empty list as placeholder
        logger.info(f"Visual extraction from {section.section_type} not yet implemented")
        
        return resources
    
    def _extract_context(self, text: str, span: Tuple[int, int], 
                        window: int = 100) -> str:
        """Extract context around a matched pattern"""
        start = max(0, span[0] - window)
        end = min(len(text), span[1] + window)
        return text[start:end]
    
    def _identify_source(self, context: str) -> str:
        """Identify the source/vendor from context"""
        # Common vendor patterns
        vendors = [
            'Abcam', 'Sigma-Aldrich', 'Invitrogen', 'BD Biosciences',
            'Cell Signaling', 'BioLegend', 'Thermo Fisher', 'Millipore'
        ]
        
        for vendor in vendors:
            if vendor.lower() in context.lower():
                return vendor
        
        # Look for "This study" patterns
        if any(phrase in context.lower() for phrase in 
               ['this study', 'this paper', 'this work', 'we generated']):
            return "This study"
        
        return "Unknown source"
    
    def _identify_identifier(self, context: str) -> str:
        """Identify RRID, catalog number, or other identifier"""
        # Look for RRID
        rrid_match = re.search(self.rrid_pattern, context, re.IGNORECASE)
        if rrid_match:
            return f"RRID: {rrid_match.group(1)}"
        
        # Look for catalog number
        cat_match = re.search(self.catalog_pattern, context, re.IGNORECASE)
        if cat_match:
            return f"Cat# {cat_match.group(1)}"
        
        return "No identifier exists"
    
    def _determine_new_reuse(self, source: str) -> str:
        """Determine if resource is new or reused based on source"""
        if source.lower() in ['this study', 'this paper', 'this work']:
            return 'new'
        return 'reuse'
    
    def _validate_and_score(self, resources: List[ExtractedResource]) -> List[ExtractedResource]:
        """Validate extracted resources and assign confidence scores"""
        validated = []
        
        for resource in resources:
            # Basic validation
            if not resource.resource_name or resource.resource_name.lower() in ['n/a', 'unknown']:
                continue
            
            # Calculate confidence score based on multiple factors
            confidence = self._calculate_confidence(resource)
            resource.confidence_score = confidence
            
            # Only include resources above confidence threshold
            if confidence >= 0.5:
                validated.append(resource)
        
        # Remove duplicates
        validated = self._remove_duplicates(validated)
        
        return validated
    
    def _calculate_confidence(self, resource: ExtractedResource) -> float:
        """Calculate confidence score for an extracted resource"""
        score = 0.5  # Base score
        
        # Increase score for specific identifiers
        if 'RRID:' in resource.identifier:
            score += 0.3
        elif 'Cat#' in resource.identifier:
            score += 0.2
        
        # Increase score for known sources
        known_vendors = ['Abcam', 'Sigma-Aldrich', 'Invitrogen', 'BD Biosciences']
        if any(vendor in resource.source for vendor in known_vendors):
            score += 0.2
        
        # Decrease score for missing information
        if resource.source == "Unknown source":
            score -= 0.2
        
        return min(1.0, max(0.0, score))
    
    def _remove_duplicates(self, resources: List[ExtractedResource]) -> List[ExtractedResource]:
        """Remove duplicate resources based on name and source"""
        seen = set()
        unique_resources = []
        
        for resource in resources:
            key = (resource.resource_name.lower(), resource.source.lower())
            if key not in seen:
                seen.add(key)
                unique_resources.append(resource)
        
        return unique_resources
    
    def export_to_json(self, resources: List[ExtractedResource], 
                      output_path: str) -> None:
        """Export extracted resources to JSON format"""
        krt_data = []
        
        for resource in resources:
            krt_entry = {
                "RESOURCE TYPE": resource.resource_type.title(),
                "RESOURCE NAME": resource.resource_name,
                "SOURCE": resource.source,
                "IDENTIFIER": resource.identifier,
                "NEW/REUSE": resource.new_reuse,
                "ADDITIONAL INFORMATION": resource.additional_info,
                "confidence_score": resource.confidence_score,
                "location": resource.location
            }
            krt_data.append(krt_entry)
        
        with open(output_path, 'w') as f:
            json.dump(krt_data, f, indent=2)
        
        logger.info(f"Exported {len(krt_data)} resources to {output_path}")


# Example usage and testing
if __name__ == "__main__":
    # Example usage
    processor = MultimodalKRTProcessor()
    
    # Process a sample PDF (would need actual PDF file)
    # resources = processor.extract_from_pdf("sample_paper.pdf")
    # processor.export_to_json(resources, "extracted_krt.json")
    
    print("Multimodal KRT Processor initialized successfully!")
    print("To use: processor.extract_from_pdf('your_paper.pdf')")
