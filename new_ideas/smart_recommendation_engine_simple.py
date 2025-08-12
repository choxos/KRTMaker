"""
Simplified Smart Recommendation Engine (No External Dependencies)

Provides working resource recommendation functionality without requiring
external ML libraries, using intelligent pattern matching and mock data.
"""

import time
import random
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class ResourceRecommendation:
    """Data class for resource recommendations"""
    recommended_resource: str
    vendor: str
    catalog_number: str
    recommendation_type: str  # 'functional_equivalent', 'alternative_vendor', etc.
    similarity_score: float
    confidence_score: float
    reasoning: str
    availability_status: str = "unknown"
    price_comparison: Dict[str, Any] = None


class SmartRecommendationEngine:
    """Simplified recommendation engine with realistic mock responses"""
    
    def __init__(self):
        # Mock recommendation database
        self.recommendation_db = {
            "dapi": [
                {
                    "name": "Hoechst 33342",
                    "vendor": "Thermo Fisher",
                    "catalog": "H3570",
                    "type": "functional_equivalent",
                    "similarity": 0.92,
                    "confidence": 0.88,
                    "reasoning": "Alternative nuclear stain with similar blue fluorescence and DNA binding properties",
                    "availability": "in_stock"
                },
                {
                    "name": "Hoechst 33258", 
                    "vendor": "Sigma-Aldrich",
                    "catalog": "94403",
                    "type": "functional_equivalent",
                    "similarity": 0.89,
                    "confidence": 0.85,
                    "reasoning": "DNA-binding fluorescent dye, similar excitation/emission spectrum",
                    "availability": "in_stock"
                },
                {
                    "name": "DAPI",
                    "vendor": "Sigma-Aldrich", 
                    "catalog": "D9542",
                    "type": "alternative_vendor",
                    "similarity": 1.0,
                    "confidence": 0.95,
                    "reasoning": "Same compound from alternative vendor with competitive pricing",
                    "availability": "in_stock"
                }
            ],
            "anti-beta-tubulin": [
                {
                    "name": "Anti-alpha-tubulin",
                    "vendor": "Cell Signaling Technology",
                    "catalog": "2144S",
                    "type": "functional_equivalent", 
                    "similarity": 0.87,
                    "confidence": 0.82,
                    "reasoning": "Targets related tubulin subunit, similar cytoskeletal labeling pattern",
                    "availability": "in_stock"
                },
                {
                    "name": "Anti-beta-tubulin",
                    "vendor": "Cell Signaling Technology",
                    "catalog": "86298S",
                    "type": "alternative_vendor",
                    "similarity": 1.0,
                    "confidence": 0.93,
                    "reasoning": "Same target from reputable alternative vendor",
                    "availability": "in_stock"
                },
                {
                    "name": "Anti-tubulin DM1A",
                    "vendor": "Santa Cruz",
                    "catalog": "sc-32293",
                    "type": "functional_equivalent",
                    "similarity": 0.91,
                    "confidence": 0.88,
                    "reasoning": "Widely used tubulin antibody clone with excellent specificity",
                    "availability": "limited_stock"
                }
            ],
            "imagej": [
                {
                    "name": "FIJI",
                    "vendor": "ImageJ Team",
                    "catalog": "Open Source",
                    "type": "updated_version",
                    "similarity": 0.98,
                    "confidence": 0.96,
                    "reasoning": "Enhanced version of ImageJ with additional plugins and tools",
                    "availability": "free_download"
                },
                {
                    "name": "CellProfiler",
                    "vendor": "Broad Institute", 
                    "catalog": "Open Source",
                    "type": "functional_equivalent",
                    "similarity": 0.75,
                    "confidence": 0.79,
                    "reasoning": "Alternative image analysis software with automated pipeline features",
                    "availability": "free_download"
                },
                {
                    "name": "QuPath",
                    "vendor": "University of Edinburgh",
                    "catalog": "Open Source",
                    "type": "functional_equivalent",
                    "similarity": 0.71,
                    "confidence": 0.74,
                    "reasoning": "Specialized for digital pathology and bioimage analysis",
                    "availability": "free_download"
                }
            ],
            "fitc": [
                {
                    "name": "Alexa Fluor 488",
                    "vendor": "Thermo Fisher",
                    "catalog": "A20000",
                    "type": "functional_equivalent",
                    "similarity": 0.93,
                    "confidence": 0.89,
                    "reasoning": "Similar green fluorescence with improved photostability",
                    "availability": "in_stock"
                },
                {
                    "name": "DyLight 488",
                    "vendor": "Thermo Fisher",
                    "catalog": "46409",
                    "type": "functional_equivalent",
                    "similarity": 0.88,
                    "confidence": 0.84,
                    "reasoning": "Green fluorophore with compatible excitation/emission",
                    "availability": "in_stock"
                }
            ],
            "dmso": [
                {
                    "name": "DMSO, Cell Culture Grade",
                    "vendor": "Sigma-Aldrich",
                    "catalog": "D2650",
                    "type": "price_optimization",
                    "similarity": 1.0,
                    "confidence": 0.94,
                    "reasoning": "Same compound in cell culture grade with cost savings",
                    "availability": "in_stock"
                },
                {
                    "name": "Ethanol (alternative solvent)",
                    "vendor": "Various",
                    "catalog": "Multiple",
                    "type": "functional_equivalent",
                    "similarity": 0.65,
                    "confidence": 0.58,
                    "reasoning": "Alternative solvent for some applications (verify compatibility)",
                    "availability": "widely_available"
                }
            ]
        }
    
    async def recommend_alternatives(self, resource_name: str, resource_type: str = "",
                                   context: Dict[str, Any] = None, max_recommendations: int = 5) -> List[ResourceRecommendation]:
        """Generate alternative resource recommendations"""
        # Simulate processing time
        await self._simulate_async_delay()
        
        resource_lower = resource_name.lower().strip()
        recommendations = []
        
        # Check for direct matches
        for key, recs in self.recommendation_db.items():
            if (key in resource_lower or 
                any(word in resource_lower for word in key.split('-')) or
                resource_lower in key):
                
                for rec in recs[:max_recommendations]:
                    recommendations.append(ResourceRecommendation(
                        recommended_resource=rec["name"],
                        vendor=rec["vendor"],
                        catalog_number=rec["catalog"],
                        recommendation_type=rec["type"],
                        similarity_score=rec["similarity"],
                        confidence_score=rec["confidence"],
                        reasoning=rec["reasoning"],
                        availability_status=rec["availability"]
                    ))
                break
        
        # If no matches, generate generic recommendations
        if not recommendations:
            recommendations = self._generate_generic_recommendations(
                resource_name, resource_type, context
            )
        
        # Add context-based scoring adjustments
        if context:
            recommendations = self._adjust_for_context(recommendations, context)
        
        # Sort by confidence score
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        return recommendations[:max_recommendations]
    
    def _generate_generic_recommendations(self, resource_name: str, resource_type: str,
                                        context: Dict[str, Any]) -> List[ResourceRecommendation]:
        """Generate generic recommendations when no specific match is found"""
        recommendations = []
        
        # Pattern-based recommendations
        if "antibody" in resource_type.lower() or "anti-" in resource_name.lower():
            recommendations.extend([
                ResourceRecommendation(
                    recommended_resource=f"Alternative {resource_name}",
                    vendor="Multiple Vendors",
                    catalog_number="Various",
                    recommendation_type="alternative_vendor",
                    similarity_score=0.85,
                    confidence_score=0.72,
                    reasoning="Consider checking multiple antibody vendors for better pricing or availability",
                    availability_status="check_vendors"
                ),
                ResourceRecommendation(
                    recommended_resource="Recombinant alternative",
                    vendor="Multiple Vendors", 
                    catalog_number="Various",
                    recommendation_type="updated_version",
                    similarity_score=0.88,
                    confidence_score=0.75,
                    reasoning="Recombinant antibodies often provide better consistency and reproducibility",
                    availability_status="check_vendors"
                )
            ])
        elif "software" in resource_type.lower():
            recommendations.append(
                ResourceRecommendation(
                    recommended_resource="Open Source Alternative",
                    vendor="Open Source Community",
                    catalog_number="Free",
                    recommendation_type="price_optimization",
                    similarity_score=0.70,
                    confidence_score=0.68,
                    reasoning="Consider open source alternatives for cost savings and customization",
                    availability_status="free_download"
                )
            )
        else:
            recommendations.append(
                ResourceRecommendation(
                    recommended_resource="Generic alternative",
                    vendor="Multiple Vendors",
                    catalog_number="Various",
                    recommendation_type="alternative_vendor",
                    similarity_score=0.60,
                    confidence_score=0.55,
                    reasoning="Compare multiple vendors for this resource type",
                    availability_status="check_vendors"
                )
            )
        
        return recommendations
    
    def _adjust_for_context(self, recommendations: List[ResourceRecommendation], 
                          context: Dict[str, Any]) -> List[ResourceRecommendation]:
        """Adjust recommendation scores based on context"""
        applications = context.get('applications', [])
        budget_conscious = context.get('budget_conscious', False)
        
        for rec in recommendations:
            # Budget adjustments
            if budget_conscious and rec.recommendation_type == "price_optimization":
                rec.confidence_score = min(0.98, rec.confidence_score + 0.15)
            
            # Application-specific adjustments  
            if applications:
                if "fluorescence" in str(applications).lower() and "fluor" in rec.recommended_resource.lower():
                    rec.confidence_score = min(0.95, rec.confidence_score + 0.08)
                if "microscopy" in str(applications).lower() and any(term in rec.recommended_resource.lower() 
                                                                    for term in ["dapi", "hoechst", "alexa"]):
                    rec.confidence_score = min(0.95, rec.confidence_score + 0.05)
        
        return recommendations
    
    async def _simulate_async_delay(self, min_delay: float = 0.2, max_delay: float = 0.8):
        """Simulate realistic processing time"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
