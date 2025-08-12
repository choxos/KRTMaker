"""
Europe PMC bioRxiv fetcher - Complete result retrieval with multiple pagination methods
"""
from __future__ import annotations

import re
import requests
import tempfile
import xml.etree.ElementTree as ET
import time
from typing import Optional, Tuple, Dict, List
from urllib.parse import urlparse, quote

# Try to import pyeuropepmc for automatic pagination
try:
    from pyeuropepmc.search import SearchClient
    PYEUROPEPMC_AVAILABLE = True
    print("✅ pyeuropepmc library available - will use automatic pagination")
except ImportError:
    PYEUROPEPMC_AVAILABLE = False
    print("⚠️  pyeuropepmc not available - using manual pagination methods")

class EuropePMCFetcher:
    """Fetch bioRxiv papers via Europe PMC API"""
    
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'KRT-Maker/1.0 (research tool for Key Resource Tables)'
        })
    
    def parse_biorxiv_identifier(self, identifier: str) -> Optional[str]:
        """
        Parse bioRxiv URL or DOI to extract the DOI.
        
        Supports formats like:
        - https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1
        - https://biorxiv.org/content/early/2023/01/01/2023.01.01.123456
        - 10.1101/2023.01.01.123456
        - 2023.01.01.123456
        """
        if not identifier:
            return None
        
        identifier = identifier.strip()
        
        # If it's already a proper DOI, return it
        if identifier.startswith('10.1101/'):
            return identifier
        
        # If it's just the ID part, add the DOI prefix
        if re.match(r'^\d{4}\.\d{2}\.\d{2}\.\d{6}(v\d+)?$', identifier):
            return f"10.1101/{identifier}"
        
        # If it's a URL, extract the DOI
        if 'biorxiv.org' in identifier.lower():
            # Try to extract DOI from URL
            patterns = [
                r'10\.1101/(\d{4}\.\d{2}\.\d{2}\.\d{6}(?:v\d+)?)',
                r'/content/(?:early/\d{4}/\d{2}/\d{2}/)?(\d{4}\.\d{2}\.\d{2}\.\d{6}(?:v\d+)?)',
                r'/(\d{4}\.\d{2}\.\d{2}\.\d{6}(?:v\d+)?)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, identifier)
                if match:
                    return f"10.1101/{match.group(1)}"
        
        return None
    
    def search_epmc_for_doi(self, doi: str) -> Optional[str]:
        """
        Search Europe PMC for a bioRxiv paper by DOI and return the EPMC ID.
        """
        try:
            # Search for the specific DOI (simplified query - don't filter by journal)
            # This handles both published articles and preprints (PPR source)
            query = f'DOI:"{doi}"'
            url = f"{self.BASE_URL}/search"
            
            params = {
                'query': query,
                'format': 'xml',
                'resultType': 'lite',
                'pageSize': 100  # Increased from 10
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            
            # Look for results
            results = root.findall('.//result')
            
            for result in results:
                # Check if this result has the right DOI
                result_doi = result.find('doi')
                if result_doi is not None and result_doi.text == doi:
                    # Get the fullTextId first (for published articles)
                    fulltext_ids = result.findall('.//fullTextId')
                    if fulltext_ids:
                        return fulltext_ids[0].text
                    
                    # Fallback to regular ID (for preprints like PPR972306)
                    id_elem = result.find('id')
                    if id_elem is not None:
                        return id_elem.text
            
            return None
            
        except Exception as e:
            print(f"Error searching Europe PMC for {doi}: {e}")
            return None
    
    def check_full_text_availability(self, epmc_id: str) -> Dict[str, any]:
        """
        Check if full text XML is available for download from Europe PMC.
        Returns a dict with availability status and details.
        """
        if not epmc_id:
            return {
                'available': False,
                'error': 'No EPMC ID provided',
                'status_code': None,
                'content_length': None
            }
        
        try:
            xml_url = f"{self.BASE_URL}/{epmc_id}/fullTextXML"
            
            # Use HEAD request to check availability without downloading
            response = self.session.head(xml_url, timeout=30)
            
            if response.status_code == 200:
                content_length = response.headers.get('content-length')
                return {
                    'available': True,
                    'url': xml_url,
                    'status_code': 200,
                    'content_length': int(content_length) if content_length else None,
                    'content_type': response.headers.get('content-type', 'unknown')
                }
            else:
                return {
                    'available': False,
                    'error': f'HTTP {response.status_code}',
                    'status_code': response.status_code,
                    'url': xml_url
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'available': False,
                'error': str(e),
                'status_code': None,
                'url': f"{self.BASE_URL}/{epmc_id}/fullTextXML"
            }
        except Exception as e:
            return {
                'available': False,
                'error': f'Unexpected error: {str(e)}',
                'status_code': None
            }

    def download_xml_from_epmc(self, epmc_id: str) -> Optional[str]:
        """
        Download full text XML from Europe PMC using EPMC ID.
        Returns path to downloaded XML file, or None if failed.
        """
        try:
            url = f"{self.BASE_URL}/{epmc_id}/fullTextXML"
            
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            # Check if we got XML content
            content_type = response.headers.get('content-type', '').lower()
            if 'xml' not in content_type:
                raise ValueError(f"Invalid content type: {content_type}")
            
            # Create temporary file in system temp directory (NOT in project directory)
            # This prevents Django auto-reloader from detecting the file and restarting
            system_temp_dir = tempfile.gettempdir()
            
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.xml',
                delete=False,
                encoding='utf-8',
                dir=system_temp_dir  # Explicitly use system temp directory
            )
            temp_file.write(response.text)
            temp_file.close()
            
            return temp_file.name
            
        except Exception as e:
            print(f"Error downloading XML from Europe PMC for {epmc_id}: {e}")
            return None
    
    def get_paper_metadata(self, doi: str) -> Optional[Dict]:
        """
        Get paper metadata from Europe PMC.
        Returns a dict with paper information compatible with bioRxiv API format.
        """
        try:
            # Search for the paper (simplified query to handle both published and preprint versions)
            query = f'DOI:"{doi}"'
            url = f"{self.BASE_URL}/search"
            
            params = {
                'query': query,
                'format': 'xml',
                'resultType': 'core',  # Get more detailed metadata
                'pageSize': 50  # Increased from 5
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            
            # Look for our paper
            results = root.findall('.//result')
            
            for result in results:
                result_doi = result.find('doi')
                if result_doi is not None and result_doi.text == doi:
                    # Extract comprehensive metadata from Europe PMC
                    title_elem = result.find('title')
                    authors_elem = result.find('authorString')
                    pub_date_elem = result.find('firstPublicationDate')
                    abstract_elem = result.find('abstractText')
                    journal_elem = result.find('journalTitle')
                    pmcid_elem = result.find('pmcid')
                    pmid_elem = result.find('pmid')
                    
                    # Extract author list if available
                    author_list_elem = result.find('authorList')
                    authors_detailed = []
                    if author_list_elem is not None:
                        for author in author_list_elem.findall('.//author'):
                            fullName = author.find('fullName')
                            if fullName is not None:
                                authors_detailed.append(fullName.text)
                    
                    # Extract keywords/mesh terms if available
                    keywords = []
                    mesh_heading_list = result.find('meshHeadingList')
                    if mesh_heading_list is not None:
                        for mesh_heading in mesh_heading_list.findall('.//meshHeading'):
                            descriptor_name = mesh_heading.find('descriptorName')
                            if descriptor_name is not None:
                                keywords.append(descriptor_name.text)
                    
                    # Extract authors as a proper list
                    authors = self._extract_authors(result)
                    
                    return {
                        'preprint_doi': doi,
                        'preprint_title': title_elem.text if title_elem is not None else 'Unknown title',
                        'preprint_authors': authors,  # Now returns a list
                        'preprint_authors_detailed': authors,  # Use the same list for consistency
                        'preprint_date': pub_date_elem.text if pub_date_elem is not None else None,
                        'preprint_abstract': abstract_elem.text if abstract_elem is not None else None,
                        'preprint_platform': journal_elem.text if journal_elem is not None else 'bioRxiv',
                        'preprint_keywords': keywords if keywords else None,
                        'pmcid': pmcid_elem.text if pmcid_elem is not None else None,
                        'pmid': pmid_elem.text if pmid_elem is not None else None,
                        'source': 'europe_pmc'
                    }
            
            return None
            
        except Exception as e:
            print(f"Error getting metadata from Europe PMC for {doi}: {e}")
            return None
    
    def download_xml(self, doi: str) -> Optional[str]:
        """
        Download XML for a bioRxiv paper using Europe PMC.
        Returns path to downloaded XML file, or None if failed.
        """
        try:
            # First, search for the EPMC ID
            epmc_id = self.search_epmc_for_doi(doi)
            
            if not epmc_id:
                raise ValueError(f"Paper not found in Europe PMC: {doi}")
            
            print(f"Found EPMC ID: {epmc_id} for DOI: {doi}")
            
            # Download the XML
            xml_path = self.download_xml_from_epmc(epmc_id)
            
            if not xml_path:
                raise ValueError(f"Could not download XML from Europe PMC for {epmc_id}")
            
            return xml_path
            
        except Exception as e:
            print(f"Error downloading XML for {doi}: {e}")
            return None
    
    def fetch_paper_info(self, identifier: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Fetch both metadata and XML file for a bioRxiv paper.
        
        Args:
            identifier: bioRxiv URL, DOI, or paper ID
            
        Returns:
            Tuple of (metadata_dict, xml_file_path)
        """
        # Parse the identifier to get a clean DOI
        doi = self.parse_biorxiv_identifier(identifier)
        
        if not doi:
            return None, None
        
        # Get metadata
        metadata = self.get_paper_metadata(doi)
        
        if not metadata:
            return None, None
        
        # Download XML
        xml_path = self.download_xml(doi)
        
        return metadata, xml_path
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """Clean up a temporary file"""
        try:
            import os
            os.unlink(file_path)
        except Exception:
            pass  # Ignore cleanup errors
    
    def search_all_biorxiv_papers(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Search ALL bioRxiv papers in Europe PMC with complete pagination.
        Returns a list of paper metadata dictionaries.
        
        Args:
            limit: Optional limit on number of papers to retrieve (for testing)
        """
        print("🔍 Searching ALL bioRxiv papers in Europe PMC...")
        
        query = 'JOURNAL:("bioRxiv : the preprint server for biology")'
        return self.search_complete_results(query, limit=limit)
    
    def search_all_biorxiv_papers_by_year(self, start_year: int = 2020, end_year: int = 2025, limit_per_year: Optional[int] = None) -> List[Dict]:
        """
        Search ALL bioRxiv papers year by year for better efficiency and progress tracking.
        
        Args:
            start_year: Starting year (default: 2020)
            end_year: Ending year (default: 2025) 
            limit_per_year: Optional limit per year for testing
            
        Returns:
            List of all paper metadata dictionaries across all years
        """
        print(f"📅 Searching bioRxiv papers year by year ({start_year}-{end_year})...")
        
        all_papers = []
        total_papers_found = 0
        
        for year in range(start_year, end_year + 1):
            print(f"\n📆 === YEAR {year} ===")
            
            # Create year-specific query
            query = f'JOURNAL:("bioRxiv : the preprint server for biology") AND (FIRST_PDATE:[{year} TO {year}])'
            
            # Search for this year
            year_papers = self.search_complete_results(query, limit=limit_per_year)
            
            # Add year information to each paper
            for paper in year_papers:
                paper['search_year'] = year
                
            all_papers.extend(year_papers)
            total_papers_found += len(year_papers)
            
            print(f"✅ Year {year}: {len(year_papers):,} papers (Total so far: {total_papers_found:,})")
            
            # Short pause between years to be respectful
            time.sleep(1)
        
        print(f"\n🎉 COMPLETE! Total papers across all years: {total_papers_found:,}")
        
        # Sort by publication date if available
        sorted_papers = sorted(all_papers, key=lambda x: x.get('publication_date', ''), reverse=True)
        
        return sorted_papers
    
    def get_year_statistics(self, start_year: int = 2020, end_year: int = 2025) -> Dict[int, int]:
        """
        Get paper count statistics by year without downloading full data.
        
        Args:
            start_year: Starting year (default: 2020)
            end_year: Ending year (default: 2025)
            
        Returns:
            Dictionary mapping year -> paper count
        """
        print(f"📊 Getting bioRxiv statistics by year ({start_year}-{end_year})...")
        
        year_stats = {}
        total_papers = 0
        
        for year in range(start_year, end_year + 1):
            query = f'JOURNAL:("bioRxiv : the preprint server for biology") AND (FIRST_PDATE:[{year} TO {year}])'
            url = f"{self.BASE_URL}/search"
            
            params = {
                'query': query,
                'format': 'xml',
                'resultType': 'lite',
                'pageSize': 1,  # Just need the count
                'retstart': 0
            }
            
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                root = ET.fromstring(response.content)
                hit_count_elem = root.find('.//hitCount')
                
                if hit_count_elem is not None:
                    count = int(hit_count_elem.text)
                    year_stats[year] = count
                    total_papers += count
                    print(f"📅 {year}: {count:,} papers")
                else:
                    year_stats[year] = 0
                    print(f"📅 {year}: 0 papers")
                    
            except Exception as e:
                print(f"❌ Error getting stats for {year}: {e}")
                year_stats[year] = 0
            
            time.sleep(0.1)  # Small delay between requests
        
        print(f"\n📈 TOTAL across all years: {total_papers:,} papers")
        print(f"📊 Year breakdown: {year_stats}")
        
        return year_stats
    
    def search_complete_results(self, query: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Search Europe PMC with complete pagination to get ALL results.
        
        Args:
            query: Search query string
            limit: Optional limit on number of results (for testing)
        """
        all_results = []
        page_size = 1000  # Maximum allowed by Europe PMC
        ret_start = 0
        total_count = None
        
        print(f"📊 Starting complete search: {query}")
        
        while True:
            print(f"🔄 Fetching page: retstart={ret_start}, pageSize={page_size}")
            
            url = f"{self.BASE_URL}/search"
            params = {
                'query': query,
                'format': 'xml',
                'resultType': 'core',  # Get detailed metadata
                'pageSize': page_size,
                'retstart': ret_start
            }
            
            try:
                response = self.session.get(url, params=params, timeout=60)
                response.raise_for_status()
                
                # Parse XML response
                root = ET.fromstring(response.content)
                
                # Get total count on first request
                if total_count is None:
                    hit_count_elem = root.find('.//hitCount')
                    if hit_count_elem is not None:
                        total_count = int(hit_count_elem.text)
                        print(f"📈 Total papers found: {total_count:,}")
                        
                        if limit and total_count > limit:
                            print(f"⚠️  Limiting to {limit:,} papers for testing")
                            total_count = limit
                
                # Extract results from this page
                results = root.findall('.//result')
                page_results = []
                
                for result in results:
                    paper_data = self._extract_paper_data(result)
                    if paper_data:
                        page_results.append(paper_data)
                        
                        # Check limit
                        if limit and len(all_results) >= limit:
                            break
                
                all_results.extend(page_results)
                print(f"✅ Retrieved {len(page_results)} papers (total: {len(all_results):,})")
                
                # Check if we have all results or hit limit
                if (len(page_results) < page_size or 
                    (limit and len(all_results) >= limit) or
                    (total_count and len(all_results) >= total_count)):
                    break
                
                # Prepare for next page
                ret_start += page_size
                
                # Rate limiting - be respectful to Europe PMC
                time.sleep(0.2)  # 200ms delay between requests
                
            except Exception as e:
                print(f"❌ Error fetching page {ret_start}: {e}")
                break
        
        print(f"🎉 Complete! Retrieved {len(all_results):,} total papers")
        return all_results
    
    def _extract_paper_data(self, result_elem) -> Optional[Dict]:
        """Extract paper data from a Europe PMC result element"""
        try:
            # Essential fields
            title_elem = result_elem.find('title')
            doi_elem = result_elem.find('doi')
            id_elem = result_elem.find('id')
            
            # Debug: Print what we found
            doi_text = doi_elem.text if doi_elem is not None else None
            title_text = title_elem.text if title_elem is not None else None
            id_text = id_elem.text if id_elem is not None else None
            
            # Must have either DOI or ID to be valid
            if not doi_text and not id_text:
                print(f"⚠️  Skipping paper: no DOI or ID found")
                return None
            
            # Extract comprehensive metadata
            paper_data = {
                'doi': doi_text or 'No DOI',
                'epmc_id': id_text,
                'title': title_text if title_text else 'Unknown title',
                'authors': self._extract_authors(result_elem),
                'abstract': self._extract_abstract(result_elem),
                'publication_date': self._extract_date(result_elem),
                'journal': self._extract_journal(result_elem),
                'keywords': self._extract_keywords(result_elem),
                'pmcid': self._extract_text(result_elem, 'pmcid'),
                'pmid': self._extract_text(result_elem, 'pmid'),
                'source': 'europe_pmc_complete'
            }
            
            # Optional debug output
            # print(f"✅ Extracted: {doi_text or id_text} - {title_text[:50] if title_text else 'No title'}...")
            
            return paper_data
            
        except Exception as e:
            print(f"❌ Error extracting paper data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_authors(self, result_elem) -> List[str]:
        """Extract authors from result element as a list"""
        # Try detailed author list first
        author_list_elem = result_elem.find('authorList')
        if author_list_elem is not None:
            authors = []
            for author in author_list_elem.findall('.//author'):
                fullName = author.find('fullName')
                if fullName is not None and fullName.text:
                    authors.append(fullName.text.strip())
            if authors:
                return authors
        
        # Fall back to author string - split by comma and clean up
        authors_elem = result_elem.find('authorString')
        if authors_elem is not None and authors_elem.text:
            # Split by comma and clean up whitespace
            authors = [author.strip() for author in authors_elem.text.split(',')]
            # Filter out empty strings
            authors = [author for author in authors if author]
            return authors
        
        return ['Unknown authors']
    
    def _extract_abstract(self, result_elem) -> Optional[str]:
        """Extract abstract from result element"""
        abstract_elem = result_elem.find('abstractText')
        return abstract_elem.text if abstract_elem is not None else None
    
    def _extract_date(self, result_elem) -> Optional[str]:
        """Extract publication date from result element"""
        date_elem = result_elem.find('firstPublicationDate')
        return date_elem.text if date_elem is not None else None
    
    def _extract_journal(self, result_elem) -> str:
        """Extract journal name from result element"""
        journal_elem = result_elem.find('journalTitle')
        return journal_elem.text if journal_elem is not None else 'bioRxiv'
    
    def _extract_keywords(self, result_elem) -> List[str]:
        """Extract keywords/mesh terms from result element"""
        keywords = []
        mesh_heading_list = result_elem.find('meshHeadingList')
        if mesh_heading_list is not None:
            for mesh_heading in mesh_heading_list.findall('.//meshHeading'):
                descriptor_name = mesh_heading.find('descriptorName')
                if descriptor_name is not None:
                    keywords.append(descriptor_name.text)
        return keywords
    
    def _extract_text(self, result_elem, field_name: str) -> Optional[str]:
        """Extract text content from a field"""
        elem = result_elem.find(field_name)
        return elem.text if elem is not None else None
    
    def search_by_dois(self, dois: List[str]) -> Dict[str, Dict]:
        """
        Search for multiple DOIs and return comprehensive metadata.
        
        Args:
            dois: List of DOI strings to search for
            
        Returns:
            Dictionary mapping DOI -> metadata dict
        """
        print(f"🔍 Searching for {len(dois)} specific DOIs...")
        
        results = {}
        
        # Search in batches to be efficient
        batch_size = 50
        for i in range(0, len(dois), batch_size):
            batch = dois[i:i+batch_size]
            print(f"📄 Processing batch {i//batch_size + 1}: {len(batch)} DOIs")
            
            # Create OR query for this batch
            doi_queries = [f'DOI:"{doi}"' for doi in batch]
            query = f'JOURNAL:("bioRxiv : the preprint server for biology") AND ({" OR ".join(doi_queries)})'
            
            batch_results = self.search_complete_results(query)
            
            # Map results by DOI
            for paper in batch_results:
                if paper['doi'] in batch:
                    results[paper['doi']] = paper
            
            time.sleep(0.5)  # Rate limiting between batches
        
        print(f"✅ Found {len(results)} papers out of {len(dois)} DOIs")
        return results
    
    def get_all_biorxiv_dois(self, limit: Optional[int] = None) -> List[str]:
        """
        Get all bioRxiv DOIs from Europe PMC.
        
        Args:
            limit: Optional limit for testing
            
        Returns:
            List of DOI strings
        """
        print("📋 Retrieving all bioRxiv DOIs...")
        
        papers = self.search_all_biorxiv_papers(limit=limit)
        dois = [paper['doi'] for paper in papers if paper.get('doi')]
        
        print(f"📊 Total DOIs extracted: {len(dois):,}")
        return dois