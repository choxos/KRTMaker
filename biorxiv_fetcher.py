"""
bioRxiv paper fetcher - Download XML content directly from bioRxiv
"""
from __future__ import annotations

import re
import requests
import tempfile
import os
from typing import Optional, Tuple
from urllib.parse import urlparse


class BioRxivFetcher:
    """Fetch bioRxiv papers by URL or DOI"""
    
    BASE_URL = "https://www.biorxiv.org"
    API_BASE = "https://api.biorxiv.org"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'KRT-Maker/1.0 (research tool for Key Resource Tables)'
        })
    
    def parse_biorxiv_identifier(self, identifier: str) -> Optional[str]:
        """
        Parse bioRxiv URL or DOI to extract the paper identifier.
        
        Supports formats like:
        - https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1
        - https://biorxiv.org/content/early/2023/01/01/2023.01.01.123456
        - 10.1101/2023.01.01.123456
        - 2023.01.01.123456
        
        Returns the DOI in format: 10.1101/YYYY.MM.DD.XXXXXX
        """
        if not identifier:
            return None
            
        identifier = identifier.strip()
        
        # If it's already a clean DOI, return it
        doi_pattern = r'10\.1101/(\d{4}\.\d{2}\.\d{2}\.\d{6})'
        doi_match = re.search(doi_pattern, identifier)
        if doi_match:
            return f"10.1101/{doi_match.group(1)}"
        
        # If it's just the date.number part, add the 10.1101 prefix
        date_pattern = r'^(\d{4}\.\d{2}\.\d{2}\.\d{6})v?\d*$'
        date_match = re.match(date_pattern, identifier)
        if date_match:
            return f"10.1101/{date_match.group(1)}"
        
        # Extract from bioRxiv URLs
        url_patterns = [
            r'biorxiv\.org/content/(?:early/\d{4}/\d{2}/\d{2}/)?(?:10\.1101/)?(\d{4}\.\d{2}\.\d{2}\.\d{6})',
            r'biorxiv\.org/content/(?:10\.1101/)?(\d{4}\.\d{2}\.\d{2}\.\d{6})',
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, identifier)
            if match:
                return f"10.1101/{match.group(1)}"
        
        return None
    
    def get_paper_metadata(self, doi: str) -> Optional[dict]:
        """Get paper metadata from bioRxiv API"""
        try:
            # Remove 10.1101/ prefix for API call
            paper_id = doi.replace('10.1101/', '')
            url = f"{self.API_BASE}/details/biorxiv/{paper_id}"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data.get('messages') and data['messages'][0].get('status') == 'ok':
                return data['collection'][0] if data.get('collection') else None
            
            return None
            
        except Exception as e:
            print(f"Error fetching metadata for {doi}: {e}")
            return None
    
    def download_xml(self, doi: str) -> Optional[str]:
        """
        Download the XML file for a bioRxiv paper.
        Returns the path to the downloaded file, or None if failed.
        """
        try:
            # Get metadata first to verify the paper exists
            metadata = self.get_paper_metadata(doi)
            if not metadata:
                raise ValueError(f"Paper not found: {doi}")
            
            # Extract the paper identifier for download URL
            paper_id = doi.replace('10.1101/', '')
            
            # Try different XML download URLs
            xml_urls = [
                f"{self.BASE_URL}/content/biorxiv/early/{metadata.get('date', '').replace('-', '/')}/{paper_id}.source.xml",
                f"{self.BASE_URL}/content/early/{metadata.get('date', '').replace('-', '/')}/{paper_id}.source.xml",
                f"{self.BASE_URL}/content/10.1101/{paper_id}.source.xml",
            ]
            
            for xml_url in xml_urls:
                try:
                    response = self.session.get(xml_url, timeout=60)
                    if response.status_code == 200 and 'xml' in response.headers.get('content-type', '').lower():
                        # Save to temporary file
                        temp_file = tempfile.NamedTemporaryFile(
                            mode='w', 
                            suffix='.xml', 
                            delete=False,
                            encoding='utf-8'
                        )
                        temp_file.write(response.text)
                        temp_file.close()
                        
                        return temp_file.name
                        
                except requests.RequestException:
                    continue
            
            raise ValueError(f"Could not download XML for {doi}. The paper may not have XML available.")
            
        except Exception as e:
            print(f"Error downloading XML for {doi}: {e}")
            return None
    
    def fetch_paper_info(self, identifier: str) -> Tuple[Optional[dict], Optional[str]]:
        """
        Fetch both metadata and XML file for a bioRxiv paper.
        
        Returns:
            (metadata_dict, xml_file_path) or (None, None) if failed
        """
        doi = self.parse_biorxiv_identifier(identifier)
        if not doi:
            return None, None
        
        metadata = self.get_paper_metadata(doi)
        if not metadata:
            return None, None
        
        xml_path = self.download_xml(doi)
        return metadata, xml_path
    
    def cleanup_temp_file(self, file_path: str):
        """Clean up temporary XML file"""
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass  # Ignore cleanup errors


def test_fetcher():
    """Test the bioRxiv fetcher with a sample paper"""
    fetcher = BioRxivFetcher()
    
    # Test with a well-known bioRxiv paper
    test_identifiers = [
        "2023.01.01.522482",  # Example format
        "10.1101/2023.01.01.522482",
        "https://www.biorxiv.org/content/10.1101/2023.01.01.522482v1",
    ]
    
    for identifier in test_identifiers:
        print(f"\nTesting: {identifier}")
        doi = fetcher.parse_biorxiv_identifier(identifier)
        print(f"Parsed DOI: {doi}")
        
        if doi:
            metadata = fetcher.get_paper_metadata(doi)
            if metadata:
                print(f"Title: {metadata.get('title', 'N/A')}")
                print(f"Authors: {metadata.get('authors', 'N/A')}")
                print(f"Date: {metadata.get('date', 'N/A')}")
            else:
                print("Metadata not found")


if __name__ == "__main__":
    test_fetcher()