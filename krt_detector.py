"""
KRT Detection Utility - Detect existing Key Resources Tables in scientific articles
"""

import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class KRTDetector:
    """Detect existing KRT tables in scientific articles"""
    
    # Enhanced patterns for different journal formats (ASAP, STAR Methods, Cell Press, etc.)
    KRT_TABLE_PATTERNS = [
        # ASAP formats
        r'key\s+resources?\s+table',
        r'key\s+reagents?\s+table',
        
        # STAR Methods (Cell Press) formats
        r'star\s*\u2605?\s+methods\s+table',
        r'star\s+methods',
        r'resource\s+table',
        r'materials?\s+and\s+methods?\s+table',
        
        # General resource tables
        r'reagents?\s+and\s+resources?\s+table',
        r'resources?\s+table',
        r'materials\s+table',
        r'supplies\s+table',
        
        # Specific resource type tables  
        r'antibodies?\s+table',
        r'primers?\s+table',
        r'reagents?\s+table',
        r'software\s+table',
        r'equipment\s+table',
        r'plasmids?\s+table',
        r'cell\s+lines?\s+table',
        r'strains?\s+table',
        
        # Nature/Science formats
        r'extended\s+data\s+table',
        r'supplementary\s+table',
        
        # Generic patterns
        r'table\s+\d+.*(?:resource|reagent|material)',
        r'(?:resource|reagent|material).*table\s+\d+',
    ]
    
    # Enhanced patterns for column headers (different journal formats)
    KRT_HEADER_PATTERNS = [
        # Standard ASAP format
        r'resource\s+type',
        r'resource\s+name',
        r'source',
        r'identifier',
        r'new\s*/\s*reuse',
        r'additional\s+information',
        
        # Alternative formats
        r'reagent\s+type',
        r'reagent\s+name',
        r'material\s+name?',
        r'item',
        r'description',
        
        # Source/vendor patterns
        r'vendor',
        r'supplier',
        r'company',
        r'manufacturer',
        
        # Identifier patterns
        r'cat\s*#?',
        r'cat\s*no\.?',
        r'catalog\s+number',
        r'catalogue\s+number',
        r'product\s+code',
        r'order\s+number',
        r'item\s+number',
        r'rrid',
        r'accession',
        r'doi',
        
        # Usage patterns
        r'application',
        r'purpose',
        r'use',
        r'dilution',
        r'concentration',
        r'lot\s+number',
        r'comments?',
        r'notes?',
        r'details',
        
        # Cell Press STAR Methods specific
        r'final\s+concentration',
        r'working\s+concentration',
        r'storage',
        r'conditions',
    ]
    
    # Common resource types in KRT tables
    RESOURCE_TYPES = [
        'antibody', 'antibodies',
        'primer', 'primers',
        'software',
        'reagent', 'reagents',
        'cell line', 'cell lines',
        'strain', 'strains',
        'plasmid', 'plasmids',
        'equipment',
        'chemical', 'chemicals',
        'drug', 'drugs',
        'compound', 'compounds',
        'oligonucleotide', 'oligonucleotides',
        'kit', 'kits',
        'medium', 'media',
        'buffer', 'buffers',
    ]
    
    def __init__(self):
        self.compiled_patterns = {
            'table': [re.compile(pattern, re.IGNORECASE) for pattern in self.KRT_TABLE_PATTERNS],
            'header': [re.compile(pattern, re.IGNORECASE) for pattern in self.KRT_HEADER_PATTERNS],
        }
    
    def detect_krt_in_xml(self, xml_content: str) -> Dict:
        """
        Detect existing KRT tables in XML content.
        
        Args:
            xml_content: The XML content to analyze
            
        Returns:
            Dictionary with detection results
        """
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Find all tables
            tables = self._find_tables(root)
            krt_tables = []
            
            for table in tables:
                krt_info = self._analyze_table_for_krt(table)
                if krt_info['is_krt']:
                    krt_tables.append(krt_info)
            
            # Also check for structured KRT data in specific sections
            structured_krt = self._find_structured_krt(root)
            krt_tables.extend(structured_krt)
            
            return {
                'has_krt': len(krt_tables) > 0,
                'krt_count': len(krt_tables),
                'krt_tables': krt_tables,
                'confidence_score': self._calculate_confidence(krt_tables),
            }
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            return {'has_krt': False, 'krt_count': 0, 'krt_tables': [], 'confidence_score': 0}
        except Exception as e:
            logger.error(f"Error detecting KRT: {e}")
            return {'has_krt': False, 'krt_count': 0, 'krt_tables': [], 'confidence_score': 0}
    
    def detect_krt_in_file(self, file_path: str) -> Dict:
        """
        Detect existing KRT tables in an XML file.
        
        Args:
            file_path: Path to the XML file
            
        Returns:
            Dictionary with detection results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            return self.detect_krt_in_xml(xml_content)
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return {'has_krt': False, 'krt_count': 0, 'krt_tables': [], 'confidence_score': 0}
    
    def _find_tables(self, root: ET.Element) -> List[ET.Element]:
        """Find all table elements in the XML"""
        tables = []
        
        # Common table tags in scientific XML formats
        table_tags = ['table', 'table-wrap', 'tbody', 'thead']
        
        for tag in table_tags:
            tables.extend(root.findall(f'.//{tag}'))
        
        return tables
    
    def _analyze_table_for_krt(self, table: ET.Element) -> Dict:
        """Analyze a table element to determine if it's a KRT table"""
        result = {
            'is_krt': False,
            'confidence': 0,
            'table_data': [],
            'headers': [],
            'title': '',
            'caption': '',
        }
        
        # Get table text content
        table_text = self._get_element_text(table).lower()
        
        # Check table title/caption for KRT indicators
        title_elements = table.findall('.//title') + table.findall('.//caption')
        for title_elem in title_elements:
            title_text = self._get_element_text(title_elem).lower()
            result['title'] = title_text
            result['caption'] = title_text
            
            # Check if title matches KRT patterns
            for pattern in self.compiled_patterns['table']:
                if pattern.search(title_text):
                    result['confidence'] += 30
                    break
        
        # Extract table headers
        headers = self._extract_table_headers(table)
        result['headers'] = headers
        
        # Check headers for KRT indicators
        header_text = ' '.join(headers).lower()
        header_matches = 0
        for pattern in self.compiled_patterns['header']:
            if pattern.search(header_text):
                header_matches += 1
                result['confidence'] += 20
        
        # Check for resource types in table content
        resource_type_matches = 0
        for resource_type in self.RESOURCE_TYPES:
            if re.search(r'\b' + re.escape(resource_type) + r'\b', table_text):
                resource_type_matches += 1
                result['confidence'] += 10
        
        # Extract table data if it looks like KRT
        if result['confidence'] > 30:
            result['table_data'] = self._extract_table_data(table)
        
        # Determine if this is likely a KRT table
        result['is_krt'] = result['confidence'] >= 50
        
        return result
    
    def _find_structured_krt(self, root: ET.Element) -> List[Dict]:
        """Find KRT data in structured sections (like methods sections)"""
        structured_krt = []
        
        # Look for methods/materials sections
        methods_sections = root.findall('.//sec[@sec-type="methods"]') + \
                          root.findall('.//sec[@sec-type="materials"]') + \
                          root.findall('.//sec[title]')
        
        for section in methods_sections:
            section_text = self._get_element_text(section).lower()
            
            # Check if section mentions KRT
            for pattern in self.compiled_patterns['table']:
                if pattern.search(section_text):
                    structured_krt.append({
                        'is_krt': True,
                        'confidence': 40,
                        'section_type': 'methods',
                        'content': section_text[:500] + '...' if len(section_text) > 500 else section_text
                    })
                    break
        
        return structured_krt
    
    def _extract_table_headers(self, table: ET.Element) -> List[str]:
        """Extract headers from a table element"""
        headers = []
        
        # Look for header rows
        header_rows = table.findall('.//thead//tr') + table.findall('.//tr[1]')
        
        for row in header_rows:
            cells = row.findall('.//th') + row.findall('.//td')
            for cell in cells:
                header_text = self._get_element_text(cell).strip()
                if header_text:
                    headers.append(header_text)
            break  # Only process first header row
        
        return headers
    
    def _extract_table_data(self, table: ET.Element) -> List[Dict]:
        """Extract data from a table that appears to be a KRT table, preserving original formatting"""
        data = []
        
        # Get all rows (handle both with and without namespaces)
        rows = table.findall('.//tr') + table.findall('.//{http://jats.nlm.nih.gov}tr')
        headers = self._extract_table_headers(table)
        
        # Skip header row(s) and extract data
        header_row_count = 1
        # Check if first few rows are all headers
        for i, row in enumerate(rows[:3]):
            cells = row.findall('.//td') + row.findall('.//th') + \
                   row.findall('.//{http://jats.nlm.nih.gov}td') + \
                   row.findall('.//{http://jats.nlm.nih.gov}th')
            if all(cell.tag.endswith('th') for cell in cells):
                header_row_count = i + 1
            else:
                break
        
        data_rows = rows[header_row_count:] if len(rows) > header_row_count else rows
        
        for row in data_rows[:20]:  # Increased limit to capture more data
            cells = row.findall('.//td') + row.findall('.//th') + \
                   row.findall('.//{http://jats.nlm.nih.gov}td') + \
                   row.findall('.//{http://jats.nlm.nih.gov}th')
            row_data = {}
            
            for i, cell in enumerate(cells):
                cell_text = self._get_element_text(cell).strip()
                header = headers[i] if i < len(headers) else f'Column_{i+1}'
                row_data[header] = cell_text
            
            # Only include rows with substantial content
            if row_data and any(len(str(v).strip()) > 1 for v in row_data.values()):
                data.append(row_data)
        
        return data
    
    def _get_element_text(self, element: ET.Element) -> str:
        """Get all text content from an element and its children"""
        text_parts = [element.text or '']
        for child in element:
            text_parts.append(self._get_element_text(child))
            text_parts.append(child.tail or '')
        return ' '.join(text_parts).strip()
    
    def _calculate_confidence(self, krt_tables: List[Dict]) -> float:
        """Calculate overall confidence score for KRT detection"""
        if not krt_tables:
            return 0.0
        
        total_confidence = sum(table.get('confidence', 0) for table in krt_tables)
        max_possible = len(krt_tables) * 100
        
        return min(100.0, (total_confidence / max_possible) * 100) if max_possible > 0 else 0.0


def detect_existing_krt(xml_file_path: str) -> Dict:
    """
    Convenience function to detect existing KRT in an XML file.
    
    Args:
        xml_file_path: Path to the XML file to analyze
        
    Returns:
        Dictionary with KRT detection results
    """
    detector = KRTDetector()
    return detector.detect_krt_in_file(xml_file_path)


def format_krt_data_for_display(krt_tables: List[Dict]) -> List[Dict]:
    """
    Format detected KRT data for display in templates, preserving original formatting.
    
    Args:
        krt_tables: List of detected KRT tables
        
    Returns:
        Formatted data suitable for template rendering
    """
    formatted_data = []
    
    for table in krt_tables:
        if table.get('table_data'):
            # Add table metadata
            table_info = {
                'table_title': table.get('title', ''),
                'table_caption': table.get('caption', ''),
                'confidence': table.get('confidence', 0),
                'headers': table.get('headers', []),
                'raw_data': table.get('table_data', []),
            }
            
            for row in table['table_data']:
                # Preserve original structure but try to map to standard fields
                formatted_row = dict(row)  # Start with original data
                
                # Add standardized fields for compatibility
                standardized = {
                    'RESOURCE_TYPE': '',
                    'RESOURCE_NAME': '',
                    'SOURCE': '',
                    'IDENTIFIER': '',
                    'NEW_REUSE': '',
                    'ADDITIONAL_INFO': ''
                }
                
                # Smart mapping based on content analysis
                for key, value in row.items():
                    if not value or str(value).strip() in ['', '-', 'N/A', 'NA', 'n/a']:
                        continue
                        
                    key_lower = key.lower()
                    value_clean = str(value).strip()
                    
                    # Resource type mapping
                    if any(pattern in key_lower for pattern in ['resource type', 'reagent type', 'type', 'category']):
                        standardized['RESOURCE_TYPE'] = value_clean
                    
                    # Resource name mapping (most important)
                    elif any(pattern in key_lower for pattern in ['resource name', 'reagent name', 'name', 'item', 'material', 'description']):
                        if len(value_clean) > 2:  # Avoid empty or very short values
                            standardized['RESOURCE_NAME'] = value_clean
                    
                    # Source/vendor mapping
                    elif any(pattern in key_lower for pattern in ['source', 'vendor', 'supplier', 'company', 'manufacturer']):
                        standardized['SOURCE'] = value_clean
                    
                    # Identifier mapping
                    elif any(pattern in key_lower for pattern in ['identifier', 'cat', 'catalog', 'rrid', 'product code', 'item number', 'accession']):
                        standardized['IDENTIFIER'] = value_clean
                    
                    # New/Reuse mapping
                    elif any(pattern in key_lower for pattern in ['new', 'reuse', 'use']):
                        standardized['NEW_REUSE'] = value_clean
                    
                    # Everything else goes to additional info
                    else:
                        if standardized['ADDITIONAL_INFO']:
                            standardized['ADDITIONAL_INFO'] += f"; {key}: {value_clean}"
                        else:
                            standardized['ADDITIONAL_INFO'] = f"{key}: {value_clean}"
                
                # Merge original and standardized data
                formatted_row.update(standardized)
                formatted_row['_table_info'] = table_info
                
                # Only include rows with meaningful content
                if standardized['RESOURCE_NAME'] or any(len(str(v).strip()) > 3 for v in row.values()):
                    formatted_data.append(formatted_row)
    
    return formatted_data