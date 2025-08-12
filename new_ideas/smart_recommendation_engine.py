"""
Smart Resource Recommendation Engine for Alternative Reagents

This module implements intelligent resource recommendation systems using 
sentence transformers and vector similarity searches to suggest alternative 
reagents based on functional similarity, as identified in Claude Opus research.

Features:
- Semantic similarity search for alternative reagents
- Functional equivalence detection
- Availability tracking and alternative suggestions
- Predictive resource needs based on methodology
- Standardized naming convention recommendations
"""

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
import faiss
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import sqlite3
import logging
import re
from pathlib import Path
import asyncio
import aiohttp
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import pickle

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ResourceRecommendation:
    """Data class for resource recommendations"""
    original_resource: str
    recommended_resource: str
    similarity_score: float
    recommendation_type: str  # 'functional_equivalent', 'updated_version', 'alternative_vendor'
    confidence_score: float
    reasoning: str
    vendor: str
    catalog_number: str
    availability_status: str
    price_comparison: Optional[Dict[str, float]] = None
    scientific_evidence: List[str] = field(default_factory=list)


@dataclass
class ResourceFeatures:
    """Feature representation of a scientific resource"""
    resource_id: str
    resource_name: str
    resource_type: str
    vendor: str
    catalog_number: str
    description: str
    target_protein: Optional[str] = None
    species_reactivity: List[str] = field(default_factory=list)
    applications: List[str] = field(default_factory=list)
    embedding_vector: Optional[np.ndarray] = None
    functional_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MethodologyProfile:
    """Profile of experimental methodology for predictive recommendations"""
    methodology_type: str
    typical_resources: List[str]
    critical_features: List[str]
    alternative_strategies: List[str]
    expected_outcomes: List[str]


class ResourceDatabase:
    """Database for storing resource features and recommendations"""
    
    def __init__(self, db_path: str = "resource_recommendations.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the recommendation database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Resource features table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resource_features (
                resource_id TEXT PRIMARY KEY,
                resource_name TEXT,
                resource_type TEXT,
                vendor TEXT,
                catalog_number TEXT,
                description TEXT,
                target_protein TEXT,
                species_reactivity TEXT,  -- JSON array
                applications TEXT,  -- JSON array
                embedding_vector BLOB,  -- Pickled numpy array
                functional_properties TEXT,  -- JSON
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        
        # Recommendations cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recommendation_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_resource TEXT,
                recommended_resource TEXT,
                similarity_score REAL,
                recommendation_type TEXT,
                confidence_score REAL,
                reasoning TEXT,
                vendor TEXT,
                catalog_number TEXT,
                availability_status TEXT,
                created_at TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')
        
        # Methodology profiles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS methodology_profiles (
                methodology_type TEXT PRIMARY KEY,
                typical_resources TEXT,  -- JSON array
                critical_features TEXT,  -- JSON array
                alternative_strategies TEXT,  -- JSON array
                expected_outcomes TEXT,  -- JSON array
                created_at TIMESTAMP
            )
        ''')
        
        # Resource availability tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS availability_tracking (
                resource_id TEXT,
                vendor TEXT,
                catalog_number TEXT,
                availability_status TEXT,  -- 'in_stock', 'out_of_stock', 'discontinued', 'backordered'
                price REAL,
                currency TEXT,
                last_checked TIMESTAMP,
                PRIMARY KEY (resource_id, vendor)
            )
        ''')
        
        # User feedback on recommendations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recommendation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id INTEGER,
                user_id TEXT,
                feedback_type TEXT,  -- 'useful', 'not_useful', 'incorrect'
                feedback_text TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (recommendation_id) REFERENCES recommendation_cache (id)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_resource_type ON resource_features(resource_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_target_protein ON resource_features(target_protein)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vendor ON resource_features(vendor)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_availability_status ON availability_tracking(availability_status)')
        
        conn.commit()
        conn.close()
        logger.info("Resource recommendation database initialized")


class SemanticEmbeddingEngine:
    """Engine for creating and managing semantic embeddings of resources"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the semantic embedding engine
        
        Args:
            model_name: SentenceTransformer model to use for embeddings
        """
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        # Initialize FAISS index for similarity search
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
        self.resource_ids = []  # Track which resource corresponds to each index
        
        logger.info(f"Initialized semantic embedding engine with {model_name}")
    
    def create_resource_embedding(self, resource: ResourceFeatures) -> np.ndarray:
        """Create semantic embedding for a resource"""
        # Combine all textual information about the resource
        text_components = [
            resource.resource_name,
            resource.description,
            resource.resource_type
        ]
        
        if resource.target_protein:
            text_components.append(f"Target: {resource.target_protein}")
        
        if resource.species_reactivity:
            text_components.append(f"Species: {', '.join(resource.species_reactivity)}")
        
        if resource.applications:
            text_components.append(f"Applications: {', '.join(resource.applications)}")
        
        # Create combined text
        combined_text = ". ".join(filter(None, text_components))
        
        # Generate embedding
        embedding = self.model.encode(combined_text, normalize_embeddings=True)
        
        return embedding
    
    def add_resource_to_index(self, resource: ResourceFeatures):
        """Add a resource to the similarity search index"""
        if resource.embedding_vector is None:
            resource.embedding_vector = self.create_resource_embedding(resource)
        
        # Add to FAISS index
        embedding_array = resource.embedding_vector.reshape(1, -1).astype('float32')
        self.index.add(embedding_array)
        self.resource_ids.append(resource.resource_id)
    
    def find_similar_resources(self, query_resource: ResourceFeatures, 
                             k: int = 10, min_similarity: float = 0.5) -> List[Tuple[str, float]]:
        """Find similar resources using semantic search"""
        if query_resource.embedding_vector is None:
            query_resource.embedding_vector = self.create_resource_embedding(query_resource)
        
        # Search in FAISS index
        query_vector = query_resource.embedding_vector.reshape(1, -1).astype('float32')
        similarities, indices = self.index.search(query_vector, k + 1)  # +1 to exclude self
        
        results = []
        for i, (similarity, idx) in enumerate(zip(similarities[0], indices[0])):
            if idx < len(self.resource_ids):
                resource_id = self.resource_ids[idx]
                
                # Skip self-matches
                if resource_id == query_resource.resource_id:
                    continue
                
                # Filter by minimum similarity
                if similarity >= min_similarity:
                    results.append((resource_id, float(similarity)))
        
        return results
    
    def cluster_resources(self, resource_features: List[ResourceFeatures]) -> Dict[int, List[str]]:
        """Cluster resources by functional similarity"""
        if not resource_features:
            return {}
        
        # Create embeddings for all resources
        embeddings = []
        resource_ids = []
        
        for resource in resource_features:
            if resource.embedding_vector is None:
                resource.embedding_vector = self.create_resource_embedding(resource)
            embeddings.append(resource.embedding_vector)
            resource_ids.append(resource.resource_id)
        
        # Perform clustering
        embeddings_array = np.array(embeddings)
        clustering = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
        cluster_labels = clustering.fit_predict(embeddings_array)
        
        # Group resources by cluster
        clusters = {}
        for resource_id, cluster_label in zip(resource_ids, cluster_labels):
            if cluster_label not in clusters:
                clusters[cluster_label] = []
            clusters[cluster_label].append(resource_id)
        
        return clusters


class FunctionalEquivalenceAnalyzer:
    """Analyzer for determining functional equivalence between resources"""
    
    def __init__(self):
        # Define functional equivalence criteria for different resource types
        self.equivalence_criteria = {
            'antibody': {
                'target_protein': 1.0,  # Same target = high equivalence
                'species_reactivity': 0.8,  # Similar species = good equivalence
                'applications': 0.6,  # Similar applications = moderate equivalence
                'clone_type': 0.4  # Monoclonal vs polyclonal
            },
            'software': {
                'functionality': 1.0,  # Same core function
                'input_format': 0.7,  # Compatible inputs
                'output_format': 0.7,  # Compatible outputs
                'algorithm': 0.5  # Similar algorithms
            },
            'cell_line': {
                'cell_type': 1.0,  # Same cell type
                'organism': 0.9,  # Same organism
                'genetic_modification': 0.8,  # Similar modifications
                'culture_conditions': 0.4  # Similar culture needs
            }
        }
    
    def calculate_functional_similarity(self, resource1: ResourceFeatures, 
                                      resource2: ResourceFeatures) -> float:
        """Calculate functional similarity score between two resources"""
        if resource1.resource_type != resource2.resource_type:
            return 0.0  # Different types are not functionally equivalent
        
        resource_type = resource1.resource_type.lower()
        criteria = self.equivalence_criteria.get(resource_type, {})
        
        if not criteria:
            # For unknown resource types, use semantic similarity only
            return self._semantic_similarity(resource1, resource2)
        
        similarity_score = 0.0
        total_weight = 0.0
        
        # Calculate weighted similarity based on criteria
        for criterion, weight in criteria.items():
            criterion_similarity = self._calculate_criterion_similarity(
                resource1, resource2, criterion
            )
            similarity_score += criterion_similarity * weight
            total_weight += weight
        
        # Normalize by total weight
        if total_weight > 0:
            similarity_score /= total_weight
        
        return similarity_score
    
    def _calculate_criterion_similarity(self, resource1: ResourceFeatures, 
                                      resource2: ResourceFeatures, criterion: str) -> float:
        """Calculate similarity for a specific criterion"""
        if criterion == 'target_protein':
            target1 = resource1.target_protein or ''
            target2 = resource2.target_protein or ''
            return 1.0 if target1.lower() == target2.lower() else 0.0
        
        elif criterion == 'species_reactivity':
            species1 = set(s.lower() for s in resource1.species_reactivity)
            species2 = set(s.lower() for s in resource2.species_reactivity)
            if not species1 or not species2:
                return 0.0
            intersection = len(species1 & species2)
            union = len(species1 | species2)
            return intersection / union if union > 0 else 0.0
        
        elif criterion == 'applications':
            apps1 = set(a.lower() for a in resource1.applications)
            apps2 = set(a.lower() for a in resource2.applications)
            if not apps1 or not apps2:
                return 0.0
            intersection = len(apps1 & apps2)
            union = len(apps1 | apps2)
            return intersection / union if union > 0 else 0.0
        
        elif criterion == 'functionality':
            # For software, compare descriptions for functional similarity
            desc1 = resource1.description.lower()
            desc2 = resource2.description.lower()
            # Simple keyword-based similarity (could be improved with NLP)
            words1 = set(desc1.split())
            words2 = set(desc2.split())
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            return intersection / union if union > 0 else 0.0
        
        else:
            # Default to semantic similarity for unknown criteria
            return self._semantic_similarity(resource1, resource2)
    
    def _semantic_similarity(self, resource1: ResourceFeatures, 
                           resource2: ResourceFeatures) -> float:
        """Calculate semantic similarity using embeddings"""
        if resource1.embedding_vector is None or resource2.embedding_vector is None:
            return 0.0
        
        # Cosine similarity
        dot_product = np.dot(resource1.embedding_vector, resource2.embedding_vector)
        norm1 = np.linalg.norm(resource1.embedding_vector)
        norm2 = np.linalg.norm(resource2.embedding_vector)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


class AvailabilityTracker:
    """Tracks resource availability across vendors"""
    
    def __init__(self, db: ResourceDatabase):
        self.db = db
        self.vendor_apis = {
            'abcam': {'url': 'https://api.abcam.com/availability/{catalog}'},
            'sigma': {'url': 'https://api.sigmaaldrich.com/availability/{catalog}'},
            'invitrogen': {'url': 'https://api.thermofisher.com/availability/{catalog}'}
        }
    
    async def check_availability(self, resource_id: str, vendor: str, 
                               catalog_number: str) -> Dict[str, Any]:
        """Check availability of a resource from a specific vendor"""
        try:
            api_config = self.vendor_apis.get(vendor.lower())
            if not api_config:
                return {'status': 'unknown', 'message': 'Vendor API not configured'}
            
            url = api_config['url'].format(catalog=catalog_number)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Update database
                        self._update_availability_db(
                            resource_id, vendor, catalog_number, data
                        )
                        
                        return data
                    else:
                        return {'status': 'error', 'message': f'HTTP {response.status}'}
        
        except Exception as e:
            logger.error(f"Error checking availability for {resource_id}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _update_availability_db(self, resource_id: str, vendor: str, 
                              catalog_number: str, availability_data: Dict[str, Any]):
        """Update availability information in database"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO availability_tracking
            (resource_id, vendor, catalog_number, availability_status, price, currency, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            resource_id,
            vendor,
            catalog_number,
            availability_data.get('status', 'unknown'),
            availability_data.get('price'),
            availability_data.get('currency'),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
    
    def get_alternative_vendors(self, resource_name: str) -> List[Dict[str, Any]]:
        """Find alternative vendors for a resource"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT vendor, catalog_number, availability_status, price
            FROM resource_features rf
            JOIN availability_tracking at ON rf.resource_id = at.resource_id
            WHERE rf.resource_name LIKE ?
            AND at.availability_status = 'in_stock'
            ORDER BY price ASC
        ''', (f'%{resource_name}%',))
        
        results = cursor.fetchall()
        conn.close()
        
        alternatives = []
        for vendor, catalog, status, price in results:
            alternatives.append({
                'vendor': vendor,
                'catalog_number': catalog,
                'availability_status': status,
                'price': price
            })
        
        return alternatives


class SmartRecommendationEngine:
    """
    Main recommendation engine that coordinates all components to provide
    intelligent resource recommendations.
    """
    
    def __init__(self):
        self.db = ResourceDatabase()
        self.embedding_engine = SemanticEmbeddingEngine()
        self.equivalence_analyzer = FunctionalEquivalenceAnalyzer()
        self.availability_tracker = AvailabilityTracker(self.db)
        
        # Load existing resources into the search index
        self._build_search_index()
        
        logger.info("Smart Recommendation Engine initialized")
    
    def _build_search_index(self):
        """Build the semantic search index from existing resources"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT resource_id, resource_name, resource_type, vendor, catalog_number,
                   description, target_protein, species_reactivity, applications,
                   embedding_vector, functional_properties
            FROM resource_features
        ''')
        
        for row in cursor.fetchall():
            try:
                # Reconstruct ResourceFeatures object
                resource = ResourceFeatures(
                    resource_id=row[0],
                    resource_name=row[1],
                    resource_type=row[2],
                    vendor=row[3],
                    catalog_number=row[4],
                    description=row[5],
                    target_protein=row[6],
                    species_reactivity=json.loads(row[7]) if row[7] else [],
                    applications=json.loads(row[8]) if row[8] else [],
                    functional_properties=json.loads(row[10]) if row[10] else {}
                )
                
                # Load embedding vector if available
                if row[9]:
                    resource.embedding_vector = pickle.loads(row[9])
                
                # Add to search index
                self.embedding_engine.add_resource_to_index(resource)
                
            except Exception as e:
                logger.error(f"Error loading resource {row[0]}: {e}")
        
        conn.close()
        logger.info(f"Loaded {len(self.embedding_engine.resource_ids)} resources into search index")
    
    async def recommend_alternatives(self, resource_name: str, 
                                   resource_type: str,
                                   context: Optional[Dict[str, Any]] = None,
                                   max_recommendations: int = 5) -> List[ResourceRecommendation]:
        """
        Generate intelligent recommendations for alternative resources
        
        Args:
            resource_name: Name of the resource to find alternatives for
            resource_type: Type of resource (antibody, software, etc.)
            context: Additional context (methodology, target, etc.)
            max_recommendations: Maximum number of recommendations
            
        Returns:
            List of ResourceRecommendation objects
        """
        logger.info(f"Generating recommendations for {resource_name} ({resource_type})")
        
        # Create a query resource
        query_resource = ResourceFeatures(
            resource_id="query",
            resource_name=resource_name,
            resource_type=resource_type,
            vendor="",
            catalog_number="",
            description=context.get('description', '') if context else '',
            target_protein=context.get('target_protein') if context else None,
            species_reactivity=context.get('species_reactivity', []) if context else [],
            applications=context.get('applications', []) if context else []
        )
        
        # Find semantically similar resources
        similar_resources = self.embedding_engine.find_similar_resources(
            query_resource, k=max_recommendations * 3  # Get more candidates for filtering
        )
        
        recommendations = []
        
        for resource_id, similarity_score in similar_resources:
            # Get detailed resource information
            resource_details = self._get_resource_details(resource_id)
            if not resource_details:
                continue
            
            # Calculate functional equivalence
            functional_similarity = self.equivalence_analyzer.calculate_functional_similarity(
                query_resource, resource_details
            )
            
            # Check availability
            availability_info = await self.availability_tracker.check_availability(
                resource_id, resource_details.vendor, resource_details.catalog_number
            )
            
            # Determine recommendation type
            rec_type = self._determine_recommendation_type(
                query_resource, resource_details, functional_similarity
            )
            
            # Calculate overall confidence
            confidence = self._calculate_recommendation_confidence(
                similarity_score, functional_similarity, availability_info
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                query_resource, resource_details, similarity_score, functional_similarity
            )
            
            # Create recommendation
            recommendation = ResourceRecommendation(
                original_resource=resource_name,
                recommended_resource=resource_details.resource_name,
                similarity_score=similarity_score,
                recommendation_type=rec_type,
                confidence_score=confidence,
                reasoning=reasoning,
                vendor=resource_details.vendor,
                catalog_number=resource_details.catalog_number,
                availability_status=availability_info.get('status', 'unknown')
            )
            
            recommendations.append(recommendation)
            
            if len(recommendations) >= max_recommendations:
                break
        
        # Sort by confidence score
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        
        # Cache recommendations
        self._cache_recommendations(resource_name, recommendations)
        
        return recommendations
    
    def predict_resource_needs(self, methodology_description: str) -> List[ResourceRecommendation]:
        """
        Predict likely resource needs based on methodology description
        
        Args:
            methodology_description: Description of experimental methodology
            
        Returns:
            List of predicted resource recommendations
        """
        logger.info("Predicting resource needs from methodology")
        
        # Extract key methodological terms
        methodology_terms = self._extract_methodology_terms(methodology_description)
        
        # Find matching methodology profiles
        profiles = self._find_methodology_profiles(methodology_terms)
        
        recommendations = []
        
        for profile in profiles:
            for typical_resource in profile.typical_resources:
                # Get resource details and create recommendation
                rec = self._create_predictive_recommendation(typical_resource, profile)
                if rec:
                    recommendations.append(rec)
        
        return recommendations
    
    def _get_resource_details(self, resource_id: str) -> Optional[ResourceFeatures]:
        """Get detailed information about a resource"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT resource_name, resource_type, vendor, catalog_number,
                   description, target_protein, species_reactivity, applications,
                   embedding_vector, functional_properties
            FROM resource_features
            WHERE resource_id = ?
        ''', (resource_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            resource = ResourceFeatures(
                resource_id=resource_id,
                resource_name=row[0],
                resource_type=row[1],
                vendor=row[2],
                catalog_number=row[3],
                description=row[4],
                target_protein=row[5],
                species_reactivity=json.loads(row[6]) if row[6] else [],
                applications=json.loads(row[7]) if row[7] else [],
                functional_properties=json.loads(row[9]) if row[9] else {}
            )
            
            # Load embedding vector
            if row[8]:
                resource.embedding_vector = pickle.loads(row[8])
            
            return resource
        
        return None
    
    def _determine_recommendation_type(self, query: ResourceFeatures, 
                                     candidate: ResourceFeatures, 
                                     functional_similarity: float) -> str:
        """Determine the type of recommendation"""
        if functional_similarity > 0.9:
            return 'functional_equivalent'
        elif query.vendor != candidate.vendor:
            return 'alternative_vendor'
        elif 'version' in candidate.resource_name.lower():
            return 'updated_version'
        else:
            return 'similar_resource'
    
    def _calculate_recommendation_confidence(self, semantic_similarity: float,
                                           functional_similarity: float,
                                           availability_info: Dict[str, Any]) -> float:
        """Calculate overall confidence score for a recommendation"""
        # Base confidence from similarities
        base_confidence = (semantic_similarity * 0.4) + (functional_similarity * 0.6)
        
        # Adjust for availability
        availability_status = availability_info.get('status', 'unknown')
        if availability_status == 'in_stock':
            availability_bonus = 0.1
        elif availability_status == 'out_of_stock':
            availability_bonus = -0.2
        elif availability_status == 'discontinued':
            availability_bonus = -0.4
        else:
            availability_bonus = 0.0
        
        final_confidence = base_confidence + availability_bonus
        return max(0.0, min(1.0, final_confidence))
    
    def _generate_reasoning(self, query: ResourceFeatures, candidate: ResourceFeatures,
                          semantic_similarity: float, functional_similarity: float) -> str:
        """Generate human-readable reasoning for the recommendation"""
        reasons = []
        
        if functional_similarity > 0.8:
            reasons.append("High functional similarity")
        
        if query.target_protein and candidate.target_protein:
            if query.target_protein.lower() == candidate.target_protein.lower():
                reasons.append("Same target protein")
        
        if query.species_reactivity and candidate.species_reactivity:
            overlap = set(s.lower() for s in query.species_reactivity) & \
                     set(s.lower() for s in candidate.species_reactivity)
            if overlap:
                reasons.append(f"Compatible with {', '.join(overlap)} species")
        
        if semantic_similarity > 0.7:
            reasons.append("Semantically similar description")
        
        if not reasons:
            reasons.append("Alternative option")
        
        return "; ".join(reasons)
    
    def _cache_recommendations(self, original_resource: str, 
                             recommendations: List[ResourceRecommendation]):
        """Cache recommendations for future use"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        for rec in recommendations:
            cursor.execute('''
                INSERT INTO recommendation_cache
                (original_resource, recommended_resource, similarity_score, 
                 recommendation_type, confidence_score, reasoning, vendor, 
                 catalog_number, availability_status, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                original_resource,
                rec.recommended_resource,
                rec.similarity_score,
                rec.recommendation_type,
                rec.confidence_score,
                rec.reasoning,
                rec.vendor,
                rec.catalog_number,
                rec.availability_status,
                datetime.now(),
                datetime.now() + timedelta(days=7)  # Cache for 1 week
            ))
        
        conn.commit()
        conn.close()
    
    def _extract_methodology_terms(self, description: str) -> List[str]:
        """Extract key methodological terms from description"""
        # Common methodology keywords
        methodology_keywords = [
            'pcr', 'qpcr', 'western blot', 'immunofluorescence', 'flow cytometry',
            'elisa', 'immunohistochemistry', 'rna-seq', 'chip-seq', 'mass spectrometry',
            'microscopy', 'cell culture', 'transfection', 'cloning', 'sequencing'
        ]
        
        found_terms = []
        description_lower = description.lower()
        
        for keyword in methodology_keywords:
            if keyword in description_lower:
                found_terms.append(keyword)
        
        return found_terms
    
    def _find_methodology_profiles(self, terms: List[str]) -> List[MethodologyProfile]:
        """Find methodology profiles matching the given terms"""
        # This would query the methodology_profiles table
        # For now, return empty list as placeholder
        return []
    
    def _create_predictive_recommendation(self, resource_name: str, 
                                        profile: MethodologyProfile) -> Optional[ResourceRecommendation]:
        """Create a predictive recommendation based on methodology profile"""
        # This would create recommendations based on typical resource usage patterns
        # For now, return None as placeholder
        return None


# Example usage and testing
if __name__ == "__main__":
    async def test_recommendation_engine():
        engine = SmartRecommendationEngine()
        
        # Test recommendation generation
        recommendations = await engine.recommend_alternatives(
            "anti-beta-tubulin", 
            "antibody",
            context={
                'target_protein': 'beta-tubulin',
                'species_reactivity': ['mouse', 'rat'],
                'applications': ['western blot', 'immunofluorescence']
            }
        )
        
        print(f"Generated {len(recommendations)} recommendations for anti-beta-tubulin:")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec.recommended_resource} ({rec.vendor})")
            print(f"   Confidence: {rec.confidence_score:.2f}")
            print(f"   Type: {rec.recommendation_type}")
            print(f"   Reasoning: {rec.reasoning}")
            print()
    
    # Run the test
    asyncio.run(test_recommendation_engine())
    print("Smart Recommendation Engine tested successfully!")
