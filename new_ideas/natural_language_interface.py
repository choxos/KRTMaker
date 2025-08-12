"""
Natural Language Interface for Conversational KRT Creation

This module implements conversational AI models for natural language KRT creation,
allowing researchers to input resources in natural language like 
"I used DAPI for nuclear staining and anti-tubulin antibodies" and automatically
generate structured KRT entries with proper formatting and identifiers.

Based on Claude Opus 4.1 research recommendations for revolutionizing user experience
through natural language interfaces and conversational KRT creation.
"""

import re
import json
import spacy
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import sqlite3
import logging
from transformers import (
    AutoTokenizer, AutoModelForTokenClassification,
    AutoModelForQuestionAnswering, pipeline
)
import openai
from anthropic import Anthropic
import asyncio
from enum import Enum

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of user intents in KRT conversations"""
    ADD_RESOURCE = "add_resource"
    MODIFY_RESOURCE = "modify_resource"
    DELETE_RESOURCE = "delete_resource"
    VALIDATE_RESOURCE = "validate_resource"
    EXPORT_KRT = "export_krt"
    HELP = "help"
    CLARIFICATION = "clarification"


@dataclass
class ExtractedEntity:
    """Extracted entity from natural language"""
    entity_type: str  # 'resource_name', 'vendor', 'catalog', 'concentration', etc.
    text: str
    confidence: float
    start_pos: int
    end_pos: int
    context: str


@dataclass
class ConversationContext:
    """Context for maintaining conversation state"""
    session_id: str
    current_krt_entries: List[Dict[str, Any]] = field(default_factory=list)
    pending_clarifications: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    last_intent: Optional[IntentType] = None
    extracted_entities: List[ExtractedEntity] = field(default_factory=list)


@dataclass
class KRTEntry:
    """Structured KRT entry"""
    resource_type: str
    resource_name: str
    source: str
    identifier: str
    new_reuse: str
    additional_information: str
    confidence_score: float = 1.0
    needs_validation: bool = False
    clarification_needed: List[str] = field(default_factory=list)


class EntityExtractor:
    """Named Entity Recognition for scientific resources"""
    
    def __init__(self):
        # Load scientific NER model (would need to be trained on scientific text)
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy model")
        except OSError:
            logger.warning("spaCy model not found, using basic extraction")
            self.nlp = None
        
        # Resource type patterns
        self.resource_patterns = {
            'antibody': [
                r'anti-?\w+', r'antibod(y|ies)', r'\bab\b', r'monoclonal', r'polyclonal',
                r'primary antibod(y|ies)', r'secondary antibod(y|ies)', r'immunoglobulin'
            ],
            'software': [
                r'software', r'program', r'tool', r'package', r'script', r'algorithm',
                r'ImageJ', r'MATLAB', r'Python', r'R\b', r'version\s+\d+',
                r'GraphPad', r'SPSS', r'SAS\b'
            ],
            'chemical': [
                r'chemical', r'compound', r'reagent', r'buffer', r'solution',
                r'DMSO', r'PBS', r'HEPES', r'Tris', r'EDTA', r'DTT'
            ],
            'cell_line': [
                r'cells?', r'cell\s+line', r'culture', r'HEK293', r'HeLa',
                r'NIH3T3', r'U2OS', r'MCF-?7'
            ],
            'plasmid': [
                r'plasmid', r'vector', r'construct', r'clone', r'pUC', r'pET',
                r'pcDNA', r'pLenti'
            ]
        }
        
        # Vendor patterns
        self.vendor_patterns = {
            'Abcam': [r'abcam', r'ab\d+'],
            'Sigma-Aldrich': [r'sigma', r'aldrich', r'sigma-?aldrich'],
            'Invitrogen': [r'invitrogen', r'thermo\s*fisher'],
            'BD Biosciences': [r'bd\s*biosciences?', r'becton\s*dickinson'],
            'Cell Signaling': [r'cell\s*signaling', r'cst\b'],
            'BioLegend': [r'biolegend'],
            'Addgene': [r'addgene']
        }
        
        # Identifier patterns
        self.identifier_patterns = {
            'catalog': r'cat(?:alog)?[\s#]*([A-Z0-9\-_]+)',
            'rrid': r'RRID:\s*([A-Z]+_\d+)',
            'lot': r'lot[\s#]*([A-Z0-9\-_]+)',
            'clone': r'clone[\s#]*([A-Z0-9\-_]+)'
        }
        
        # Concentration/dilution patterns
        self.quantity_patterns = [
            r'(\d+(?:\.\d+)?)\s*(μg|ug|mg|g|μl|ul|ml|l|μM|uM|mM|M|nM|pM)\b',
            r'1:(\d+)(?:\s*dilution)?',  # dilution ratios
            r'(\d+(?:\.\d+)?)\s*%',  # percentages
            r'(\d+(?:\.\d+)?)\s*x',  # fold concentrations
        ]
    
    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract entities from natural language text"""
        entities = []
        
        # Extract resource types
        for resource_type, patterns in self.resource_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity = ExtractedEntity(
                        entity_type='resource_type',
                        text=match.group(),
                        confidence=0.8,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        context=resource_type
                    )
                    entities.append(entity)
        
        # Extract vendors
        for vendor, patterns in self.vendor_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity = ExtractedEntity(
                        entity_type='vendor',
                        text=match.group(),
                        confidence=0.9,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        context=vendor
                    )
                    entities.append(entity)
        
        # Extract identifiers
        for id_type, pattern in self.identifier_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entity = ExtractedEntity(
                    entity_type='identifier',
                    text=match.group(),
                    confidence=0.95,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    context=id_type
                )
                entities.append(entity)
        
        # Extract quantities/concentrations
        for pattern in self.quantity_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entity = ExtractedEntity(
                    entity_type='quantity',
                    text=match.group(),
                    confidence=0.85,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    context='concentration_dilution'
                )
                entities.append(entity)
        
        # Use spaCy for additional entity extraction if available
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in ['ORG', 'PRODUCT', 'GPE']:  # Organizations, products, places
                    entity = ExtractedEntity(
                        entity_type='general',
                        text=ent.text,
                        confidence=0.7,
                        start_pos=ent.start_char,
                        end_pos=ent.end_char,
                        context=ent.label_
                    )
                    entities.append(entity)
        
        return sorted(entities, key=lambda x: x.start_pos)
    
    def extract_resource_names(self, text: str, entities: List[ExtractedEntity]) -> List[str]:
        """Extract potential resource names from text and entities"""
        resource_names = []
        
        # Look for quoted strings (often resource names)
        quoted_matches = re.finditer(r'"([^"]+)"', text)
        for match in quoted_matches:
            resource_names.append(match.group(1))
        
        # Look for capitalized terms that might be resource names
        cap_matches = re.finditer(r'\b[A-Z][A-Za-z0-9\-_]*\b', text)
        for match in cap_matches:
            if len(match.group()) > 2:  # Skip short acronyms
                resource_names.append(match.group())
        
        # Extract from known patterns
        antibody_targets = re.finditer(r'anti-?(\w+)', text, re.IGNORECASE)
        for match in antibody_targets:
            resource_names.append(f"anti-{match.group(1)}")
        
        return list(set(resource_names))  # Remove duplicates


class IntentClassifier:
    """Classify user intents in conversational KRT creation"""
    
    def __init__(self):
        # Intent classification patterns
        self.intent_patterns = {
            IntentType.ADD_RESOURCE: [
                r'\b(?:add|use|used|include|added|with)\b',
                r'\bi\s+(?:use|used|need|require)\b',
                r'\blet\'s\s+add\b',
                r'\binclude\s+the\b'
            ],
            IntentType.MODIFY_RESOURCE: [
                r'\b(?:change|modify|update|edit|correct)\b',
                r'\bthat\s+should\s+be\b',
                r'\bactually\b',
                r'\bi\s+meant\b'
            ],
            IntentType.DELETE_RESOURCE: [
                r'\b(?:remove|delete|drop|exclude)\b',
                r'\bdon\'t\s+(?:include|need|use)\b',
                r'\bskip\s+that\b'
            ],
            IntentType.VALIDATE_RESOURCE: [
                r'\b(?:check|validate|verify|confirm)\b',
                r'\bis\s+(?:this|that)\s+correct\b',
                r'\bcan\s+you\s+check\b'
            ],
            IntentType.EXPORT_KRT: [
                r'\b(?:export|download|save|generate)\b',
                r'\bfinish(?:ed)?\b',
                r'\bdone\b',
                r'\bgive\s+me\s+the\s+(?:table|krt)\b'
            ],
            IntentType.HELP: [
                r'\b(?:help|how|what|explain)\b',
                r'\bi\s+don\'t\s+(?:know|understand)\b',
                r'\bcan\s+you\s+help\b'
            ]
        }
    
    def classify_intent(self, text: str, context: ConversationContext) -> IntentType:
        """Classify user intent from text"""
        text_lower = text.lower()
        
        # Score each intent type
        intent_scores = {}
        for intent_type, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                score += len(matches)
            intent_scores[intent_type] = score
        
        # Get the highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            if best_intent[1] > 0:
                return best_intent[0]
        
        # Default to ADD_RESOURCE if entities suggest resource information
        if context.extracted_entities:
            return IntentType.ADD_RESOURCE
        
        return IntentType.CLARIFICATION


class KRTEntryBuilder:
    """Build structured KRT entries from extracted entities"""
    
    def __init__(self):
        self.resource_type_mapping = {
            'antibody': 'Antibody',
            'software': 'Software/code',
            'chemical': 'Chemical, peptide, or recombinant protein',
            'cell_line': 'Experimental model: Cell line',
            'plasmid': 'Recombinant DNA',
            'organism': 'Experimental model: Organism/strain',
            'protocol': 'Protocol',
            'dataset': 'Dataset'
        }
    
    def build_entry(self, entities: List[ExtractedEntity], 
                   resource_names: List[str],
                   context: ConversationContext) -> KRTEntry:
        """Build a KRT entry from extracted information"""
        
        # Determine resource type
        resource_type = self._determine_resource_type(entities)
        
        # Extract resource name
        resource_name = self._extract_resource_name(entities, resource_names)
        
        # Extract source/vendor
        source = self._extract_source(entities)
        
        # Extract identifier
        identifier = self._extract_identifier(entities)
        
        # Determine new/reuse
        new_reuse = self._determine_new_reuse(source, entities)
        
        # Extract additional information
        additional_info = self._extract_additional_info(entities)
        
        # Calculate confidence and identify missing information
        confidence, clarifications = self._assess_completeness(
            resource_type, resource_name, source, identifier
        )
        
        entry = KRTEntry(
            resource_type=resource_type,
            resource_name=resource_name,
            source=source,
            identifier=identifier,
            new_reuse=new_reuse,
            additional_information=additional_info,
            confidence_score=confidence,
            needs_validation=confidence < 0.8,
            clarification_needed=clarifications
        )
        
        return entry
    
    def _determine_resource_type(self, entities: List[ExtractedEntity]) -> str:
        """Determine resource type from entities"""
        type_entities = [e for e in entities if e.entity_type == 'resource_type']
        
        if type_entities:
            # Get the most confident resource type
            best_entity = max(type_entities, key=lambda x: x.confidence)
            resource_type = best_entity.context
            return self.resource_type_mapping.get(resource_type, 'Other')
        
        return 'Other'
    
    def _extract_resource_name(self, entities: List[ExtractedEntity], 
                             resource_names: List[str]) -> str:
        """Extract resource name"""
        if resource_names:
            return resource_names[0]  # Take the first extracted name
        
        # Try to extract from entities
        name_candidates = []
        for entity in entities:
            if entity.entity_type in ['general', 'resource_type']:
                name_candidates.append(entity.text)
        
        if name_candidates:
            return name_candidates[0]
        
        return "Resource name not specified"
    
    def _extract_source(self, entities: List[ExtractedEntity]) -> str:
        """Extract source/vendor information"""
        vendor_entities = [e for e in entities if e.entity_type == 'vendor']
        
        if vendor_entities:
            best_vendor = max(vendor_entities, key=lambda x: x.confidence)
            return best_vendor.context
        
        # Look for "this study" indicators
        study_indicators = ['this study', 'our lab', 'we generated', 'custom']
        for entity in entities:
            if any(indicator in entity.text.lower() for indicator in study_indicators):
                return "This study"
        
        return "Source not specified"
    
    def _extract_identifier(self, entities: List[ExtractedEntity]) -> str:
        """Extract identifier information"""
        id_entities = [e for e in entities if e.entity_type == 'identifier']
        
        identifiers = []
        for entity in id_entities:
            identifiers.append(entity.text)
        
        if identifiers:
            return "; ".join(identifiers)
        
        return "No identifier exists"
    
    def _determine_new_reuse(self, source: str, entities: List[ExtractedEntity]) -> str:
        """Determine if resource is new or reused"""
        if source.lower() in ['this study', 'our lab', 'custom']:
            return 'new'
        
        # Look for indicators in entities
        for entity in entities:
            if any(indicator in entity.text.lower() for indicator in 
                   ['generated', 'developed', 'created', 'synthesized']):
                return 'new'
        
        return 'reuse'
    
    def _extract_additional_info(self, entities: List[ExtractedEntity]) -> str:
        """Extract additional information like concentrations, dilutions"""
        quantity_entities = [e for e in entities if e.entity_type == 'quantity']
        
        additional_info = []
        for entity in quantity_entities:
            additional_info.append(entity.text)
        
        return "; ".join(additional_info) if additional_info else ""
    
    def _assess_completeness(self, resource_type: str, resource_name: str,
                           source: str, identifier: str) -> Tuple[float, List[str]]:
        """Assess completeness and generate clarification questions"""
        score = 1.0
        clarifications = []
        
        if resource_name == "Resource name not specified":
            score -= 0.4
            clarifications.append("What is the specific name of this resource?")
        
        if source == "Source not specified":
            score -= 0.3
            clarifications.append("What is the vendor or source of this resource?")
        
        if identifier == "No identifier exists" and source != "This study":
            score -= 0.2
            clarifications.append("Do you have a catalog number or RRID for this resource?")
        
        if resource_type == "Other":
            score -= 0.1
            clarifications.append("What type of resource is this?")
        
        return max(0.0, score), clarifications


class ConversationalKRTInterface:
    """
    Main conversational interface for natural language KRT creation
    """
    
    def __init__(self, llm_provider: str = "openai"):
        self.entity_extractor = EntityExtractor()
        self.intent_classifier = IntentClassifier()
        self.entry_builder = KRTEntryBuilder()
        
        # Initialize LLM for conversation
        self.llm_provider = llm_provider
        if llm_provider == "openai":
            self.llm_client = openai.OpenAI()
        elif llm_provider == "anthropic":
            self.llm_client = Anthropic()
        
        # Conversation database
        self.db_path = "conversation_krt.db"
        self._init_database()
        
        logger.info(f"Conversational KRT Interface initialized with {llm_provider}")
    
    def _init_database(self):
        """Initialize conversation database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY,
                current_krt TEXT,  -- JSON
                conversation_history TEXT,  -- JSON
                user_preferences TEXT,  -- JSON
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS krt_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                entry_data TEXT,  -- JSON
                status TEXT,  -- 'draft', 'confirmed', 'deleted'
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES conversations (session_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def process_message(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        Process a conversational message and return response
        
        Args:
            message: User's natural language message
            session_id: Conversation session ID
            
        Returns:
            Dictionary with response and updated KRT state
        """
        logger.info(f"Processing message for session {session_id}: {message[:50]}...")
        
        # Load or create conversation context
        context = self._load_conversation_context(session_id)
        
        # Extract entities from the message
        entities = self.entity_extractor.extract_entities(message)
        resource_names = self.entity_extractor.extract_resource_names(message, entities)
        
        context.extracted_entities = entities
        
        # Classify intent
        intent = self.intent_classifier.classify_intent(message, context)
        context.last_intent = intent
        
        # Process based on intent
        response = await self._process_intent(intent, message, context, entities, resource_names)
        
        # Update conversation history
        context.conversation_history.append({
            'timestamp': datetime.now().isoformat(),
            'user_message': message,
            'extracted_entities': [e.__dict__ for e in entities],
            'intent': intent.value,
            'bot_response': response
        })
        
        # Save conversation state
        self._save_conversation_context(context)
        
        return {
            'response': response,
            'intent': intent.value,
            'krt_entries': [entry.__dict__ for entry in context.current_krt_entries],
            'needs_clarification': len(context.pending_clarifications) > 0,
            'clarifications': context.pending_clarifications
        }
    
    async def _process_intent(self, intent: IntentType, message: str, 
                            context: ConversationContext, entities: List[ExtractedEntity],
                            resource_names: List[str]) -> str:
        """Process message based on classified intent"""
        
        if intent == IntentType.ADD_RESOURCE:
            return await self._handle_add_resource(message, context, entities, resource_names)
        
        elif intent == IntentType.MODIFY_RESOURCE:
            return await self._handle_modify_resource(message, context, entities)
        
        elif intent == IntentType.DELETE_RESOURCE:
            return await self._handle_delete_resource(message, context, entities)
        
        elif intent == IntentType.VALIDATE_RESOURCE:
            return await self._handle_validate_resource(message, context)
        
        elif intent == IntentType.EXPORT_KRT:
            return await self._handle_export_krt(context)
        
        elif intent == IntentType.HELP:
            return self._handle_help_request(message, context)
        
        else:  # CLARIFICATION
            return await self._handle_clarification(message, context)
    
    async def _handle_add_resource(self, message: str, context: ConversationContext,
                                 entities: List[ExtractedEntity], 
                                 resource_names: List[str]) -> str:
        """Handle adding a new resource"""
        
        if not entities and not resource_names:
            return ("I'd be happy to help you add a resource! Could you tell me more about "
                   "the resource you used? For example: 'I used anti-beta-tubulin antibody "
                   "from Abcam, catalog number ab6046'")
        
        # Build KRT entry from extracted information
        entry = self.entry_builder.build_entry(entities, resource_names, context)
        
        # Check if clarification is needed
        if entry.clarification_needed:
            context.pending_clarifications.extend(entry.clarification_needed)
            
            clarification_text = "\n".join([f"• {q}" for q in entry.clarification_needed])
            
            return (f"I've extracted some information about your resource, but I need "
                   f"a few clarifications:\n\n{clarification_text}\n\n"
                   f"Could you provide these details?")
        
        # Add entry to current KRT
        context.current_krt_entries.append(entry)
        
        # Generate confirmation message
        return (f"Great! I've added **{entry.resource_name}** to your KRT table:\n\n"
               f"• **Resource Type:** {entry.resource_type}\n"
               f"• **Source:** {entry.source}\n"
               f"• **Identifier:** {entry.identifier}\n"
               f"• **Status:** {entry.new_reuse}\n"
               f"{f'• **Additional Info:** {entry.additional_information}' if entry.additional_information else ''}\n\n"
               f"Would you like to add another resource or make any changes?")
    
    async def _handle_modify_resource(self, message: str, context: ConversationContext,
                                    entities: List[ExtractedEntity]) -> str:
        """Handle modifying an existing resource"""
        
        if not context.current_krt_entries:
            return ("I don't see any resources in your current KRT table to modify. "
                   "Would you like to add a resource first?")
        
        # Try to identify which resource to modify
        # This would need more sophisticated logic to match resources
        last_entry = context.current_krt_entries[-1]
        
        return (f"I understand you want to modify **{last_entry.resource_name}**. "
               f"What specifically would you like to change? You can say something like "
               f"'Change the vendor to Sigma' or 'Update the catalog number to XYZ123'.")
    
    async def _handle_delete_resource(self, message: str, context: ConversationContext,
                                    entities: List[ExtractedEntity]) -> str:
        """Handle deleting a resource"""
        
        if not context.current_krt_entries:
            return "There are no resources in your KRT table to remove."
        
        # Simple implementation - remove last entry
        if context.current_krt_entries:
            removed_entry = context.current_krt_entries.pop()
            return f"I've removed **{removed_entry.resource_name}** from your KRT table."
        
        return "No resources to remove."
    
    async def _handle_validate_resource(self, message: str, 
                                      context: ConversationContext) -> str:
        """Handle resource validation requests"""
        
        if not context.current_krt_entries:
            return "There are no resources to validate yet. Please add some resources first."
        
        # Validate the most recent entry
        entry = context.current_krt_entries[-1]
        
        validation_issues = []
        if entry.resource_name == "Resource name not specified":
            validation_issues.append("Resource name is missing")
        if entry.source == "Source not specified":
            validation_issues.append("Source/vendor is missing")
        if entry.identifier == "No identifier exists" and entry.source != "This study":
            validation_issues.append("Identifier (catalog number/RRID) is missing")
        
        if validation_issues:
            issues_text = "\n".join([f"• {issue}" for issue in validation_issues])
            return (f"I found some issues with **{entry.resource_name}**:\n\n"
                   f"{issues_text}\n\n"
                   f"Would you like to provide the missing information?")
        else:
            return (f"**{entry.resource_name}** looks good! All required fields are present "
                   f"and the entry appears to be complete.")
    
    async def _handle_export_krt(self, context: ConversationContext) -> str:
        """Handle KRT export requests"""
        
        if not context.current_krt_entries:
            return ("Your KRT table is currently empty. Please add some resources first "
                   "before exporting.")
        
        # Generate JSON format
        krt_json = []
        for entry in context.current_krt_entries:
            krt_json.append({
                "RESOURCE TYPE": entry.resource_type,
                "RESOURCE NAME": entry.resource_name,
                "SOURCE": entry.source,
                "IDENTIFIER": entry.identifier,
                "NEW/REUSE": entry.new_reuse,
                "ADDITIONAL INFORMATION": entry.additional_information
            })
        
        return (f"Here's your completed KRT table with {len(krt_json)} resources:\n\n"
               f"```json\n{json.dumps(krt_json, indent=2)}\n```\n\n"
               f"You can copy this JSON format for your submission!")
    
    def _handle_help_request(self, message: str, context: ConversationContext) -> str:
        """Handle help requests"""
        
        return (
            "I'm here to help you create Key Resources Tables (KRT) through natural conversation! "
            "Here's what you can do:\n\n"
            "**Adding Resources:**\n"
            "• 'I used anti-beta-tubulin antibody from Abcam'\n"
            "• 'We included DAPI for nuclear staining'\n"
            "• 'The cells were cultured with ImageJ software'\n\n"
            "**Modifying Resources:**\n"
            "• 'Change the vendor to Sigma'\n"
            "• 'Update the catalog number to ab123'\n\n"
            "**Getting Your Table:**\n"
            "• 'Export my KRT table'\n"
            "• 'I'm done, show me the results'\n\n"
            "Just describe your resources naturally, and I'll extract the relevant information!"
        )
    
    async def _handle_clarification(self, message: str, context: ConversationContext) -> str:
        """Handle clarification responses"""
        
        if context.pending_clarifications:
            # Process the clarification response
            # This would need more sophisticated logic to map responses to specific clarifications
            context.pending_clarifications.clear()
            
            return ("Thank you for the clarification! I'll update the resource information. "
                   "Is there anything else you'd like to add or modify?")
        
        return ("I'm not sure I understand. Could you try rephrasing that? "
               "For example, you could say 'Add anti-tubulin antibody' or 'Export my table'.")
    
    def _load_conversation_context(self, session_id: str) -> ConversationContext:
        """Load conversation context from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT current_krt, conversation_history, user_preferences
            FROM conversations WHERE session_id = ?
        ''', (session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            current_krt_data = json.loads(result[0]) if result[0] else []
            conversation_history = json.loads(result[1]) if result[1] else []
            user_preferences = json.loads(result[2]) if result[2] else {}
            
            # Convert KRT data back to KRTEntry objects
            current_entries = []
            for entry_data in current_krt_data:
                entry = KRTEntry(**entry_data)
                current_entries.append(entry)
            
            return ConversationContext(
                session_id=session_id,
                current_krt_entries=current_entries,
                conversation_history=conversation_history,
                user_preferences=user_preferences
            )
        else:
            return ConversationContext(session_id=session_id)
    
    def _save_conversation_context(self, context: ConversationContext):
        """Save conversation context to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert KRT entries to serializable format
        krt_data = [entry.__dict__ for entry in context.current_krt_entries]
        
        cursor.execute('''
            INSERT OR REPLACE INTO conversations
            (session_id, current_krt, conversation_history, user_preferences, 
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            context.session_id,
            json.dumps(krt_data),
            json.dumps(context.conversation_history),
            json.dumps(context.user_preferences),
            datetime.now(),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()


# Example usage and testing
if __name__ == "__main__":
    async def test_conversational_interface():
        interface = ConversationalKRTInterface()
        
        # Test conversation
        session_id = "test_session_1"
        
        # Test adding a resource
        response1 = await interface.process_message(
            "I used anti-beta-tubulin antibody from Abcam, catalog number ab6046",
            session_id
        )
        print("Response 1:", response1['response'])
        print()
        
        # Test adding another resource
        response2 = await interface.process_message(
            "We also included DAPI for nuclear staining at 1:1000 dilution",
            session_id
        )
        print("Response 2:", response2['response'])
        print()
        
        # Test export
        response3 = await interface.process_message(
            "Export my KRT table",
            session_id
        )
        print("Response 3:", response3['response'])
    
    # Run the test
    asyncio.run(test_conversational_interface())
    print("Conversational KRT Interface tested successfully!")
