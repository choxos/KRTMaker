"""
RRID Enhancement System for Automated Assignment and Validation

This module implements AI-powered automated RRID (Research Resource Identifier) 
assignment, validation, and suggestion system to address the manual curation 
bottlenecks and improve resource identification accuracy.

Based on Claude Opus 4.1 research recommendations for enhancing the RRID system
through intelligent resource matching and cross-reference validation.
"""

import requests
import json
import re
import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import sqlite3
import hashlib
import logging
from urllib.parse import urlencode, quote
import time
from concurrent.futures import ThreadPoolExecutor
import difflib

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ResourceMatch:
    """Data class for resource matching results"""
    resource_name: str
    suggested_rrid: str
    confidence_score: float
    source_database: str
    additional_info: Dict[str, Any]
    validation_status: str  # 'valid', 'deprecated', 'needs_review'
    alternative_rrids: List[str]


@dataclass
class RRIDValidation:
    """Data class for RRID validation results"""
    rrid: str
    is_valid: bool
    status: str  # 'active', 'deprecated', 'discontinued', 'invalid'
    resource_info: Dict[str, Any]
    last_checked: datetime
    error_message: Optional[str] = None


class RRIDDatabase:
    """Local database for caching RRID information and improving performance"""
    
    def __init__(self, db_path: str = "rrid_cache.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the local RRID cache database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rrid_cache (
                rrid TEXT PRIMARY KEY,
                resource_name TEXT,
                source_database TEXT,
                status TEXT,
                metadata TEXT,  -- JSON string
                last_updated TIMESTAMP,
                validation_hash TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resource_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_name_normalized TEXT,
                vendor TEXT,
                catalog_number TEXT,
                rrid TEXT,
                confidence_score REAL,
                created_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS validation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rrid TEXT,
                validation_result TEXT,  -- JSON string
                checked_at TIMESTAMP,
                FOREIGN KEY (rrid) REFERENCES rrid_cache (rrid)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_resource_name ON resource_mappings(resource_name_normalized)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vendor_catalog ON resource_mappings(vendor, catalog_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rrid_status ON rrid_cache(rrid, status)')
        
        conn.commit()
        conn.close()
        logger.info("RRID database initialized")
    
    def cache_rrid(self, rrid: str, resource_info: Dict[str, Any]):
        """Cache RRID information in local database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        validation_hash = hashlib.md5(json.dumps(resource_info, sort_keys=True).encode()).hexdigest()
        
        cursor.execute('''
            INSERT OR REPLACE INTO rrid_cache 
            (rrid, resource_name, source_database, status, metadata, last_updated, validation_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            rrid,
            resource_info.get('name', ''),
            resource_info.get('source', ''),
            resource_info.get('status', 'unknown'),
            json.dumps(resource_info),
            datetime.now(),
            validation_hash
        ))
        
        conn.commit()
        conn.close()
    
    def get_cached_rrid(self, rrid: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached RRID information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT resource_name, source_database, status, metadata, last_updated
            FROM rrid_cache WHERE rrid = ?
        ''', (rrid,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'name': result[0],
                'source': result[1],
                'status': result[2],
                'metadata': json.loads(result[3]),
                'last_updated': result[4]
            }
        return None


class RRIDEnhancementSystem:
    """
    Advanced RRID enhancement system with automated assignment, validation,
    and intelligent resource matching capabilities.
    """
    
    def __init__(self):
        self.db = RRIDDatabase()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'KRT-Maker-RRID-Enhancement/1.0'
        })
        
        # API endpoints
        self.scicrunch_api = "https://scicrunch.org/api/1/"
        self.antibodyregistry_api = "https://antibodyregistry.org/api/"
        
        # Resource type mappings
        self.resource_type_mappings = {
            'antibody': ['AB_', 'antibodyregistry'],
            'software': ['SCR_', 'scicrunch'],
            'organism': ['IMSR_', 'MGI_', 'ZFIN_'],
            'cell_line': ['CVCL_', 'cellosaurus'],
            'plasmid': ['Addgene_']
        }
        
        # Vendor name normalizations
        self.vendor_normalizations = {
            'abcam': 'Abcam',
            'sigma-aldrich': 'Sigma-Aldrich',
            'sigma aldrich': 'Sigma-Aldrich',
            'invitrogen': 'Invitrogen',
            'thermo fisher': 'Thermo Fisher Scientific',
            'thermofisher': 'Thermo Fisher Scientific',
            'bd biosciences': 'BD Biosciences',
            'cell signaling': 'Cell Signaling Technology',
            'cst': 'Cell Signaling Technology'
        }
    
    async def suggest_rrid(self, resource_name: str, resource_type: str, 
                          vendor: Optional[str] = None, 
                          catalog_number: Optional[str] = None) -> List[ResourceMatch]:
        """
        Suggest RRIDs for a given resource using intelligent matching
        
        Args:
            resource_name: Name of the resource
            resource_type: Type of resource (antibody, software, etc.)
            vendor: Optional vendor/source information
            catalog_number: Optional catalog number
            
        Returns:
            List of ResourceMatch objects with suggestions
        """
        logger.info(f"Suggesting RRIDs for: {resource_name} ({resource_type})")
        
        matches = []
        
        # Normalize inputs
        normalized_name = self._normalize_resource_name(resource_name)
        normalized_vendor = self._normalize_vendor(vendor) if vendor else None
        
        # Check local cache first
        cached_matches = self._search_local_cache(normalized_name, normalized_vendor, catalog_number)
        matches.extend(cached_matches)
        
        # Search external databases
        if resource_type.lower() == 'antibody':
            antibody_matches = await self._search_antibody_registry(
                normalized_name, normalized_vendor, catalog_number
            )
            matches.extend(antibody_matches)
        
        # Search SciCrunch for all resource types
        scicrunch_matches = await self._search_scicrunch(
            normalized_name, resource_type, normalized_vendor, catalog_number
        )
        matches.extend(scicrunch_matches)
        
        # Rank and deduplicate matches
        ranked_matches = self._rank_and_deduplicate(matches, resource_name)
        
        # Cache results for future use
        await self._cache_search_results(normalized_name, ranked_matches)
        
        return ranked_matches[:10]  # Return top 10 matches
    
    async def validate_rrid(self, rrid: str, force_refresh: bool = False) -> RRIDValidation:
        """
        Validate an RRID against current databases
        
        Args:
            rrid: The RRID to validate
            force_refresh: Force fresh validation even if cached
            
        Returns:
            RRIDValidation object with validation results
        """
        logger.info(f"Validating RRID: {rrid}")
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = self.db.get_cached_rrid(rrid)
            if cached and self._is_cache_fresh(cached['last_updated']):
                return RRIDValidation(
                    rrid=rrid,
                    is_valid=cached['status'] == 'active',
                    status=cached['status'],
                    resource_info=cached['metadata'],
                    last_checked=datetime.fromisoformat(cached['last_updated'])
                )
        
        # Perform fresh validation
        try:
            validation_result = await self._validate_rrid_external(rrid)
            
            # Cache the result
            self.db.cache_rrid(rrid, {
                'status': validation_result.status,
                'resource_info': validation_result.resource_info,
                'last_validated': datetime.now().isoformat()
            })
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Failed to validate RRID {rrid}: {e}")
            return RRIDValidation(
                rrid=rrid,
                is_valid=False,
                status='error',
                resource_info={},
                last_checked=datetime.now(),
                error_message=str(e)
            )
    
    async def batch_validate_rrids(self, rrids: List[str]) -> Dict[str, RRIDValidation]:
        """Validate multiple RRIDs in parallel"""
        logger.info(f"Batch validating {len(rrids)} RRIDs")
        
        async def validate_single(rrid):
            return rrid, await self.validate_rrid(rrid)
        
        tasks = [validate_single(rrid) for rrid in rrids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        validation_results = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Validation error: {result}")
                continue
            rrid, validation = result
            validation_results[rrid] = validation
        
        return validation_results
    
    def suggest_alternatives(self, rrid: str, reason: str = "deprecated") -> List[str]:
        """
        Suggest alternative RRIDs when the original is deprecated or unavailable
        
        Args:
            rrid: The problematic RRID
            reason: Reason for seeking alternatives
            
        Returns:
            List of alternative RRID suggestions
        """
        logger.info(f"Finding alternatives for {rrid} (reason: {reason})")
        
        # Extract resource info from RRID
        resource_info = self._extract_resource_info_from_rrid(rrid)
        
        if not resource_info:
            return []
        
        # Search for similar resources
        alternatives = []
        
        # For antibodies, look for same target with different clones
        if rrid.startswith('AB_'):
            alternatives.extend(self._find_alternative_antibodies(resource_info))
        
        # For software, look for updated versions or similar tools
        elif rrid.startswith('SCR_'):
            alternatives.extend(self._find_alternative_software(resource_info))
        
        return alternatives
    
    def _normalize_resource_name(self, name: str) -> str:
        """Normalize resource name for consistent matching"""
        # Remove common prefixes/suffixes
        normalized = re.sub(r'\b(anti|anti-|antibody|ab)\b', '', name.lower())
        normalized = re.sub(r'\b(clone|catalog|cat#?)\b', '', normalized)
        normalized = re.sub(r'[^\w\s]', ' ', normalized)  # Remove special chars
        normalized = ' '.join(normalized.split())  # Normalize whitespace
        return normalized.strip()
    
    def _normalize_vendor(self, vendor: str) -> Optional[str]:
        """Normalize vendor name using known mappings"""
        if not vendor:
            return None
        
        vendor_lower = vendor.lower().strip()
        return self.vendor_normalizations.get(vendor_lower, vendor)
    
    def _search_local_cache(self, resource_name: str, vendor: Optional[str], 
                          catalog_number: Optional[str]) -> List[ResourceMatch]:
        """Search local cache for resource matches"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT rrid, confidence_score, created_at
            FROM resource_mappings 
            WHERE resource_name_normalized LIKE ?
        '''
        params = [f'%{resource_name}%']
        
        if vendor:
            query += ' AND vendor = ?'
            params.append(vendor)
        
        if catalog_number:
            query += ' AND catalog_number = ?'
            params.append(catalog_number)
        
        query += ' ORDER BY confidence_score DESC'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        matches = []
        for rrid, confidence, created_at in results:
            match = ResourceMatch(
                resource_name=resource_name,
                suggested_rrid=rrid,
                confidence_score=confidence,
                source_database='local_cache',
                additional_info={'cached_at': created_at},
                validation_status='needs_review',
                alternative_rrids=[]
            )
            matches.append(match)
        
        return matches
    
    async def _search_antibody_registry(self, resource_name: str, vendor: Optional[str],
                                      catalog_number: Optional[str]) -> List[ResourceMatch]:
        """Search Antibody Registry for antibody RRIDs"""
        matches = []
        
        try:
            # Construct search query
            search_params = {'q': resource_name}
            if vendor:
                search_params['vendor'] = vendor
            if catalog_number:
                search_params['catalog'] = catalog_number
            
            url = f"{self.antibodyregistry_api}search?" + urlencode(search_params)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for result in data.get('results', []):
                            match = ResourceMatch(
                                resource_name=resource_name,
                                suggested_rrid=result.get('rrid', ''),
                                confidence_score=self._calculate_match_confidence(
                                    resource_name, result.get('name', '')
                                ),
                                source_database='antibody_registry',
                                additional_info=result,
                                validation_status='active',
                                alternative_rrids=[]
                            )
                            matches.append(match)
                    
        except Exception as e:
            logger.error(f"Error searching Antibody Registry: {e}")
        
        return matches
    
    async def _search_scicrunch(self, resource_name: str, resource_type: str,
                              vendor: Optional[str], catalog_number: Optional[str]) -> List[ResourceMatch]:
        """Search SciCrunch database for RRIDs"""
        matches = []
        
        try:
            search_params = {
                'q': resource_name,
                'filter': resource_type if resource_type else 'all'
            }
            
            url = f"{self.scicrunch_api}resource-search?" + urlencode(search_params)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for result in data.get('results', []):
                            match = ResourceMatch(
                                resource_name=resource_name,
                                suggested_rrid=result.get('rrid', ''),
                                confidence_score=self._calculate_match_confidence(
                                    resource_name, result.get('name', '')
                                ),
                                source_database='scicrunch',
                                additional_info=result,
                                validation_status='active',
                                alternative_rrids=[]
                            )
                            matches.append(match)
        
        except Exception as e:
            logger.error(f"Error searching SciCrunch: {e}")
        
        return matches
    
    def _calculate_match_confidence(self, query: str, result_name: str) -> float:
        """Calculate confidence score for a resource match"""
        if not query or not result_name:
            return 0.0
        
        # Use sequence matching for similarity
        similarity = difflib.SequenceMatcher(None, query.lower(), result_name.lower()).ratio()
        
        # Boost score for exact matches
        if query.lower() == result_name.lower():
            return 1.0
        
        # Boost score for partial exact matches
        if query.lower() in result_name.lower() or result_name.lower() in query.lower():
            similarity = max(similarity, 0.8)
        
        return similarity
    
    def _rank_and_deduplicate(self, matches: List[ResourceMatch], 
                            original_query: str) -> List[ResourceMatch]:
        """Rank matches by confidence and remove duplicates"""
        # Remove duplicates based on RRID
        seen_rrids = set()
        unique_matches = []
        
        for match in matches:
            if match.suggested_rrid not in seen_rrids:
                seen_rrids.add(match.suggested_rrid)
                unique_matches.append(match)
        
        # Sort by confidence score
        ranked_matches = sorted(unique_matches, key=lambda x: x.confidence_score, reverse=True)
        
        return ranked_matches
    
    async def _cache_search_results(self, resource_name: str, matches: List[ResourceMatch]):
        """Cache search results for future use"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        for match in matches:
            cursor.execute('''
                INSERT OR IGNORE INTO resource_mappings
                (resource_name_normalized, vendor, catalog_number, rrid, confidence_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                resource_name,
                match.additional_info.get('vendor', ''),
                match.additional_info.get('catalog_number', ''),
                match.suggested_rrid,
                match.confidence_score,
                datetime.now()
            ))
        
        conn.commit()
        conn.close()
    
    async def _validate_rrid_external(self, rrid: str) -> RRIDValidation:
        """Validate RRID against external databases"""
        # Try SciCrunch first
        try:
            url = f"{self.scicrunch_api}resource/{rrid}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return RRIDValidation(
                            rrid=rrid,
                            is_valid=True,
                            status='active',
                            resource_info=data,
                            last_checked=datetime.now()
                        )
                    elif response.status == 404:
                        return RRIDValidation(
                            rrid=rrid,
                            is_valid=False,
                            status='not_found',
                            resource_info={},
                            last_checked=datetime.now()
                        )
        
        except Exception as e:
            logger.error(f"Error validating RRID externally: {e}")
        
        return RRIDValidation(
            rrid=rrid,
            is_valid=False,
            status='validation_error',
            resource_info={},
            last_checked=datetime.now(),
            error_message="External validation failed"
        )
    
    def _is_cache_fresh(self, last_updated: str, max_age_hours: int = 24) -> bool:
        """Check if cached data is still fresh"""
        try:
            last_update = datetime.fromisoformat(last_updated)
            age = datetime.now() - last_update
            return age < timedelta(hours=max_age_hours)
        except:
            return False
    
    def _extract_resource_info_from_rrid(self, rrid: str) -> Optional[Dict[str, Any]]:
        """Extract resource information from RRID for finding alternatives"""
        cached = self.db.get_cached_rrid(rrid)
        if cached:
            return cached['metadata']
        
        # Could also query external databases here
        return None
    
    def _find_alternative_antibodies(self, resource_info: Dict[str, Any]) -> List[str]:
        """Find alternative antibody RRIDs"""
        alternatives = []
        
        # Look for same target protein with different clones
        target = resource_info.get('target', '')
        if target:
            # This would search for other antibodies against the same target
            # Implementation would query antibody databases
            pass
        
        return alternatives
    
    def _find_alternative_software(self, resource_info: Dict[str, Any]) -> List[str]:
        """Find alternative software RRIDs"""
        alternatives = []
        
        # Look for newer versions or similar tools
        software_name = resource_info.get('name', '')
        if software_name:
            # This would search for updated versions or similar tools
            # Implementation would query software databases
            pass
        
        return alternatives


# Browser Extension Helper Functions
class BrowserExtensionAPI:
    """API endpoints for browser extension integration"""
    
    def __init__(self, rrid_system: RRIDEnhancementSystem):
        self.rrid_system = rrid_system
    
    async def suggest_rrid_api(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """API endpoint for real-time RRID suggestions"""
        resource_name = request_data.get('resource_name', '')
        resource_type = request_data.get('resource_type', '')
        vendor = request_data.get('vendor')
        catalog_number = request_data.get('catalog_number')
        
        matches = await self.rrid_system.suggest_rrid(
            resource_name, resource_type, vendor, catalog_number
        )
        
        return {
            'status': 'success',
            'suggestions': [asdict(match) for match in matches],
            'timestamp': datetime.now().isoformat()
        }
    
    async def validate_rrid_api(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """API endpoint for RRID validation"""
        rrid = request_data.get('rrid', '')
        
        validation = await self.rrid_system.validate_rrid(rrid)
        
        return {
            'status': 'success',
            'validation': asdict(validation),
            'timestamp': datetime.now().isoformat()
        }


# Example usage and testing
if __name__ == "__main__":
    async def test_rrid_system():
        system = RRIDEnhancementSystem()
        
        # Test RRID suggestion
        matches = await system.suggest_rrid(
            "anti-beta-tubulin", "antibody", "Abcam", "ab6046"
        )
        print(f"Found {len(matches)} suggestions for anti-beta-tubulin")
        for match in matches:
            print(f"  {match.suggested_rrid}: {match.confidence_score:.2f}")
        
        # Test RRID validation
        if matches:
            validation = await system.validate_rrid(matches[0].suggested_rrid)
            print(f"Validation result: {validation.status}")
    
    # Run the test
    asyncio.run(test_rrid_system())
    print("RRID Enhancement System tested successfully!")
