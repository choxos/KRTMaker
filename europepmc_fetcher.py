"""
Europe PMC bioRxiv fetcher - Simple and reliable XML access
"""
from __future__ import annotations

import re
import requests
import tempfile
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, Dict
from urllib.parse import urlparse, quote

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
            # Search for the specific DOI in bioRxiv journal
            query = f'JOURNAL:("bioRxiv : the preprint server for biology") AND DOI:"{doi}"'
            url = f"{self.BASE_URL}/search"
            
            params = {
                'query': query,
                'format': 'xml',
                'resultType': 'lite',
                'pageSize': 10
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
                    # Get the fullTextId
                    fulltext_ids = result.findall('.//fullTextId')
                    if fulltext_ids:
                        return fulltext_ids[0].text
                    
                    # Fallback to regular ID
                    id_elem = result.find('id')
                    if id_elem is not None:
                        return id_elem.text
            
            return None
            
        except Exception as e:
            print(f"Error searching Europe PMC for {doi}: {e}")
            return None
    
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
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.xml',
                delete=False,
                encoding='utf-8'
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
            # Search for the paper
            query = f'JOURNAL:("bioRxiv : the preprint server for biology") AND DOI:"{doi}"'
            url = f"{self.BASE_URL}/search"
            
            params = {
                'query': query,
                'format': 'xml',
                'resultType': 'lite',
                'pageSize': 5
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
                    # Extract metadata in bioRxiv-compatible format
                    title_elem = result.find('title')
                    authors_elem = result.find('authorString')
                    pub_date_elem = result.find('firstPublicationDate')
                    
                    return {
                        'preprint_doi': doi,
                        'preprint_title': title_elem.text if title_elem is not None else 'Unknown title',
                        'preprint_authors': authors_elem.text if authors_elem is not None else 'Unknown authors',
                        'preprint_date': pub_date_elem.text if pub_date_elem is not None else None,
                        'preprint_platform': 'bioRxiv',
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