"""
Simplified Natural Language Interface (No External Dependencies)

Provides working conversational KRT creation functionality using
pattern matching and keyword extraction without external NLP libraries.
"""

import re
import time
import random
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass


@dataclass
class ExtractedEntity:
    """Data class for extracted entities"""
    entity_type: str  # 'resource_name', 'vendor', 'catalog', 'concentration', etc.
    value: str
    confidence: float
    start_pos: int = 0
    end_pos: int = 0


class ConversationalKRTInterface:
    """Simplified conversational interface with pattern-based NLP"""
    
    def __init__(self):
        # Intent patterns
        self.intent_patterns = {
            'add_resource': [
                r'(i|we) (used|applied|utilized|employed)',
                r'(add|include|put in) (.+)',
                r'(treated|incubated) (with|using)',
                r'(stained|labeled) (with|using)',
                r'(diluted|dissolved) (.+) (in|with)',
                r'(.+) (antibody|reagent|chemical|software|equipment)',
                r'(from|by) (company|vendor)',
            ],
            'modify_resource': [
                r'(change|modify|update|edit|correct)',
                r'(replace|substitute) (.+) (with|for)',
                r'(wrong|incorrect|mistake)',
            ],
            'delete_resource': [
                r'(remove|delete|take out)',
                r'(don\'t|do not) (need|want|include)',
                r'(mistake|error)',
            ],
            'validate_resource': [
                r'(check|validate|verify)',
                r'(is|are) (.+) (correct|right|valid)',
                r'(rrid|identifier) (for|of)',
            ],
            'export_krt': [
                r'(export|download|save|finish)',
                r'(done|finished|complete)',
                r'(generate|create) (table|krt)',
            ],
            'help': [
                r'(help|how|what|explain)',
                r'(don\'t know|confused|stuck)',
                r'(guide|tutorial|example)',
            ]
        }
        
        # Resource type patterns
        self.resource_type_patterns = {
            'antibody': [r'anti-\w+', r'\w+\s+antibody', r'ab\d+', r'antibodies'],
            'chemical': [r'dapi', r'fitc', r'hoechst', r'dmso', r'pbs', r'tris', r'nacl'],
            'software': [r'imagej', r'fiji', r'prism', r'matlab', r'photoshop', r'software'],
            'equipment': [r'microscope', r'centrifuge', r'incubator', r'camera', r'laser'],
            'cell_line': [r'hela', r'hek293', r'cos-?\d+', r'nih3t3', r'cells?'],
            'reagent': [r'buffer', r'medium', r'serum', r'trypsin', r'collagenase'],
        }
        
        # Vendor patterns
        self.vendor_patterns = {
            'abcam': r'abcam',
            'thermo_fisher': r'thermo\s*fisher|invitrogen|life\s*technologies',
            'sigma': r'sigma(-?aldrich)?|merck',
            'cell_signaling': r'cell\s*signaling|cst',
            'santa_cruz': r'santa\s*cruz',
            'bio_rad': r'bio-?rad',
            'bd_biosciences': r'bd\s*biosciences?',
            'miltenyi': r'miltenyi',
            'r_and_d': r'r\s*&\s*d\s*systems?',
        }
        
        # Catalog number patterns
        self.catalog_patterns = [
            r'cat[\.\#\s]*([a-z0-9\-]+)',
            r'catalog[\.\#\s]*([a-z0-9\-]+)',
            r'item[\.\#\s]*([a-z0-9\-]+)', 
            r'product[\.\#\s]*([a-z0-9\-]+)',
            r'#([a-z0-9\-]+)',
            r'([a-z]{1,3}\d{3,6}[a-z]?)',  # Common catalog patterns like ab1234, D1306, etc.
        ]
        
        # Common concentration/dilution patterns
        self.concentration_patterns = [
            r'1:\d+',  # 1:1000
            r'\d+:\d+',  # 2:1000
            r'\d+\s*(µg|ug|mg|ng|g)/ml',
            r'\d+\s*(µM|uM|mM|nM|M)',
            r'\d+\s*%',
        ]
    
    async def process_message(self, message: str, session_id: str = None) -> Dict[str, Any]:
        """Process a natural language message and extract KRT information"""
        # Simulate processing time
        await self._simulate_async_delay()
        
        # Clean and normalize the message
        message = message.lower().strip()
        
        # Classify intent
        intent = self._classify_intent(message)
        
        # Extract entities
        entities = self._extract_entities(message)
        
        # Generate response based on intent and entities
        response_data = await self._generate_response(intent, entities, message)
        
        return response_data
    
    def _classify_intent(self, message: str) -> str:
        """Classify the intent of the message"""
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    return intent
        
        # Default intent based on content
        if any(word in message for word in ['antibody', 'chemical', 'software', 'used', 'treated']):
            return 'add_resource'
        else:
            return 'clarification'
    
    def _extract_entities(self, message: str) -> List[ExtractedEntity]:
        """Extract entities from the message using pattern matching"""
        entities = []
        
        # Extract resource names and types
        resource_info = self._extract_resource_info(message)
        entities.extend(resource_info)
        
        # Extract vendor information
        vendor = self._extract_vendor(message)
        if vendor:
            entities.append(ExtractedEntity('vendor', vendor, 0.8))
        
        # Extract catalog numbers
        catalog = self._extract_catalog_number(message)
        if catalog:
            entities.append(ExtractedEntity('catalog_number', catalog, 0.9))
        
        # Extract concentrations/dilutions
        concentration = self._extract_concentration(message)
        if concentration:
            entities.append(ExtractedEntity('concentration', concentration, 0.85))
        
        return entities
    
    def _extract_resource_info(self, message: str) -> List[ExtractedEntity]:
        """Extract resource names and types"""
        entities = []
        
        # Check for resource type patterns
        for resource_type, patterns in self.resource_type_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, message, re.IGNORECASE)
                for match in matches:
                    resource_name = match.group(0)
                    entities.append(ExtractedEntity('resource_type', resource_type, 0.85))
                    entities.append(ExtractedEntity('resource_name', resource_name, 0.80))
        
        # Extract quoted resource names
        quoted_matches = re.findall(r'"([^"]+)"', message)
        for quoted in quoted_matches:
            entities.append(ExtractedEntity('resource_name', quoted, 0.90))
        
        # Extract potential resource names from context
        # Look for patterns like "anti-" followed by word
        anti_pattern = r'anti-(\w+)'
        for match in re.finditer(anti_pattern, message, re.IGNORECASE):
            entities.append(ExtractedEntity('resource_name', match.group(0), 0.85))
            entities.append(ExtractedEntity('resource_type', 'antibody', 0.90))
        
        return entities
    
    def _extract_vendor(self, message: str) -> str:
        """Extract vendor information"""
        for vendor, pattern in self.vendor_patterns.items():
            if re.search(pattern, message, re.IGNORECASE):
                # Return the formatted vendor name
                vendor_names = {
                    'abcam': 'Abcam',
                    'thermo_fisher': 'Thermo Fisher',
                    'sigma': 'Sigma-Aldrich',
                    'cell_signaling': 'Cell Signaling Technology',
                    'santa_cruz': 'Santa Cruz Biotechnology',
                    'bio_rad': 'Bio-Rad',
                    'bd_biosciences': 'BD Biosciences',
                    'miltenyi': 'Miltenyi Biotec',
                    'r_and_d': 'R&D Systems',
                }
                return vendor_names.get(vendor, vendor.replace('_', ' ').title())
        
        # Look for "from COMPANY" patterns
        from_pattern = r'from\s+([a-z\s&]+?)(?:\s|,|$)'
        match = re.search(from_pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
        
        return None
    
    def _extract_catalog_number(self, message: str) -> str:
        """Extract catalog numbers"""
        for pattern in self.catalog_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # Return the captured group if it exists, otherwise the full match
                return match.group(1) if match.groups() else match.group(0)
        return None
    
    def _extract_concentration(self, message: str) -> str:
        """Extract concentration or dilution information"""
        for pattern in self.concentration_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(0)
        return None
    
    async def _generate_response(self, intent: str, entities: List[ExtractedEntity], 
                               original_message: str) -> Dict[str, Any]:
        """Generate appropriate response based on intent and entities"""
        
        if intent == 'add_resource':
            return await self._handle_add_resource(entities, original_message)
        elif intent == 'modify_resource':
            return await self._handle_modify_resource(entities, original_message)
        elif intent == 'delete_resource':
            return await self._handle_delete_resource(entities, original_message)
        elif intent == 'validate_resource':
            return await self._handle_validate_resource(entities, original_message)
        elif intent == 'export_krt':
            return await self._handle_export_krt(entities, original_message)
        elif intent == 'help':
            return await self._handle_help_request(entities, original_message)
        else:
            return await self._handle_clarification(entities, original_message)
    
    async def _handle_add_resource(self, entities: List[ExtractedEntity], 
                                 message: str) -> Dict[str, Any]:
        """Handle adding a resource to the KRT"""
        # Extract information from entities
        resource_name = self._get_entity_value(entities, 'resource_name')
        resource_type = self._get_entity_value(entities, 'resource_type')
        vendor = self._get_entity_value(entities, 'vendor')
        catalog = self._get_entity_value(entities, 'catalog_number')
        concentration = self._get_entity_value(entities, 'concentration')
        
        # Build KRT entry
        krt_entry = {
            'RESOURCE TYPE': (resource_type or 'Unknown').title(),
            'RESOURCE NAME': resource_name or 'Unknown Resource',
            'SOURCE': vendor or 'Unknown',
            'IDENTIFIER': f"Cat# {catalog}" if catalog else 'Unknown',
            'NEW/REUSE': 'new',  # Assume new for simplicity
            'ADDITIONAL INFORMATION': concentration or ''
        }
        
        # Generate response
        response = f"I've added {resource_name or 'the resource'} to your KRT table."
        if vendor:
            response += f" From {vendor}."
        if catalog:
            response += f" Catalog number: {catalog}."
        
        response += " Would you like to add any more resources?"
        
        # Check for missing information
        clarifications = []
        if not resource_name or resource_name == 'Unknown Resource':
            clarifications.append("What is the specific name of this resource?")
        if not vendor:
            clarifications.append("Which vendor or company provided this resource?")
        if not catalog:
            clarifications.append("What is the catalog or product number?")
        
        return {
            'response': response,
            'intent': 'add_resource',
            'krt_entries': [krt_entry],
            'needs_clarification': len(clarifications) > 0,
            'clarifications': clarifications,
            'extracted_entities': [{'type': e.entity_type, 'value': e.value, 'confidence': e.confidence} for e in entities]
        }
    
    async def _handle_modify_resource(self, entities: List[ExtractedEntity], 
                                    message: str) -> Dict[str, Any]:
        """Handle modifying an existing resource"""
        return {
            'response': "I can help you modify a resource. Which resource would you like to change, and what needs to be updated?",
            'intent': 'modify_resource',
            'krt_entries': [],
            'needs_clarification': True,
            'clarifications': ["Which resource needs modification?", "What information should be changed?"],
            'extracted_entities': [{'type': e.entity_type, 'value': e.value, 'confidence': e.confidence} for e in entities]
        }
    
    async def _handle_delete_resource(self, entities: List[ExtractedEntity], 
                                    message: str) -> Dict[str, Any]:
        """Handle deleting a resource"""
        return {
            'response': "I can help you remove a resource from the table. Which specific resource should I delete?",
            'intent': 'delete_resource',
            'krt_entries': [],
            'needs_clarification': True,
            'clarifications': ["Which resource should be removed from the KRT table?"],
            'extracted_entities': [{'type': e.entity_type, 'value': e.value, 'confidence': e.confidence} for e in entities]
        }
    
    async def _handle_validate_resource(self, entities: List[ExtractedEntity], 
                                      message: str) -> Dict[str, Any]:
        """Handle resource validation request"""
        return {
            'response': "I can help validate your resources. Please provide the resource name or RRID you'd like me to check.",
            'intent': 'validate_resource', 
            'krt_entries': [],
            'needs_clarification': True,
            'clarifications': ["Which resource or RRID should I validate?"],
            'extracted_entities': [{'type': e.entity_type, 'value': e.value, 'confidence': e.confidence} for e in entities]
        }
    
    async def _handle_export_krt(self, entities: List[ExtractedEntity], 
                               message: str) -> Dict[str, Any]:
        """Handle KRT export request"""
        return {
            'response': "Your KRT table is ready for export! You can download it as JSON, CSV, or Excel format. Use the export button to save your work.",
            'intent': 'export_krt',
            'krt_entries': [],
            'needs_clarification': False,
            'clarifications': [],
            'extracted_entities': [{'type': e.entity_type, 'value': e.value, 'confidence': e.confidence} for e in entities]
        }
    
    async def _handle_help_request(self, entities: List[ExtractedEntity], 
                                 message: str) -> Dict[str, Any]:
        """Handle help requests"""
        help_text = """I can help you create a Key Resources Table! Here's what you can do:

• Tell me about resources you used: "I used anti-beta-tubulin antibody from Abcam, catalog ab6046"
• Add chemicals: "We treated cells with DAPI at 1:1000 dilution"
• Include software: "Images were analyzed using ImageJ"
• Modify entries: "Change the vendor for DAPI to Sigma"
• Validate RRIDs: "Check if RRID:AB_2138153 is correct"

Just describe your resources in natural language and I'll build the table for you!"""
        
        return {
            'response': help_text,
            'intent': 'help',
            'krt_entries': [],
            'needs_clarification': False,
            'clarifications': [],
            'extracted_entities': [{'type': e.entity_type, 'value': e.value, 'confidence': e.confidence} for e in entities]
        }
    
    async def _handle_clarification(self, entities: List[ExtractedEntity], 
                                  message: str) -> Dict[str, Any]:
        """Handle unclear messages requiring clarification"""
        clarifications = [
            "Could you provide more details about the resource?",
            "What type of resource is this (antibody, chemical, software, etc.)?",
            "Which vendor or company provided this resource?"
        ]
        
        return {
            'response': "I'd like to help you add that resource! Could you provide a bit more detail about what you used in your research?",
            'intent': 'clarification',
            'krt_entries': [],
            'needs_clarification': True,
            'clarifications': clarifications,
            'extracted_entities': [{'type': e.entity_type, 'value': e.value, 'confidence': e.confidence} for e in entities]
        }
    
    def _get_entity_value(self, entities: List[ExtractedEntity], entity_type: str) -> str:
        """Get the value of a specific entity type"""
        for entity in entities:
            if entity.entity_type == entity_type:
                return entity.value
        return None
    
    async def _simulate_async_delay(self, min_delay: float = 0.2, max_delay: float = 0.6):
        """Simulate realistic processing time"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
