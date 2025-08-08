"""
bioRxiv paper fetcher - Download XML content directly from bioRxiv
"""
from __future__ import annotations

import re
import requests
import tempfile
import os
import zipfile
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse

# Import S3 functionality
from s3_downloader import build_s3_client, BIO_RXIV_BUCKET, BIO_RXIV_REGION
from botocore.exceptions import ClientError


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
            # Use the correct bioRxiv API format: /pubs/biorxiv/{DOI}
            url = f"{self.API_BASE}/pubs/biorxiv/{doi}"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            # Check if we have a collection with papers
            if data.get('collection') and len(data['collection']) > 0:
                return data['collection'][0]
            
            return None
            
        except Exception as e:
            print(f"Error fetching metadata for {doi}: {e}")
            return None
    
    def _get_s3_folder_from_date(self, date_str: str) -> str:
        """
        Convert a date string (YYYY-MM-DD) to bioRxiv S3 folder format.
        Examples: '2022-07-10' -> 'July_2022', '2021-03-15' -> 'March_2021'
        """
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            month_name = date_obj.strftime('%B')  # Full month name
            year = date_obj.year
            return f"{month_name}_{year}"
        except:
            return None
    
    def download_xml_from_s3(self, doi: str, metadata: dict) -> Optional[str]:
        """
        Download XML from bioRxiv S3 bucket (official recommended method).
        Returns path to extracted XML file, or None if failed.
        """
        try:
            # Get paper date and convert to S3 folder format
            preprint_date = metadata.get('preprint_date', '')
            if not preprint_date:
                raise ValueError("No preprint date available")
            
            s3_folder = self._get_s3_folder_from_date(preprint_date)
            if not s3_folder:
                raise ValueError(f"Could not parse date: {preprint_date}")
            
            # Extract paper ID for searching
            paper_id = doi.replace('10.1101/', '')
            
            # Set up S3 client
            s3_client = build_s3_client()
            
            # Search for the paper in the appropriate monthly folder
            prefix = f"Current_Content/{s3_folder}/"
            
            try:
                # List objects in the monthly folder
                response = s3_client.list_objects_v2(
                    Bucket=BIO_RXIV_BUCKET,
                    Prefix=prefix,
                    RequestPayer='requester'
                )
                
                # Look for files containing our paper ID
                meca_key = None
                if 'Contents' in response:
                    for obj in response['Contents']:
                        if paper_id in obj['Key'] and obj['Key'].endswith('.meca'):
                            meca_key = obj['Key']
                            break
                
                if not meca_key:
                    raise ValueError(f"Paper {paper_id} not found in S3 folder {s3_folder}")
                
                # Download the .meca file (it's actually a zip)
                temp_fd, temp_meca_path = tempfile.mkstemp(suffix='.meca', prefix='biorxiv_')
                os.close(temp_fd)
                
                s3_client.download_file(
                    BIO_RXIV_BUCKET,
                    meca_key,
                    temp_meca_path,
                    ExtraArgs={'RequestPayer': 'requester'}
                )
                
                # Extract XML from the .meca zip file
                xml_path = self._extract_xml_from_meca(temp_meca_path, paper_id)
                
                # Clean up .meca file
                try:
                    os.unlink(temp_meca_path)
                except:
                    pass
                
                return xml_path
                
            except ClientError as e:
                # Try alternative folder structures if needed
                if "NoSuchKey" in str(e):
                    # Maybe try Back_Content or different naming
                    raise ValueError(f"Paper not found in S3: {e}")
                else:
                    raise ValueError(f"S3 access error: {e}")
        
        except Exception as e:
            print(f"Error downloading XML from S3 for {doi}: {e}")
            return None
    
    def _extract_xml_from_meca(self, meca_path: str, paper_id: str) -> Optional[str]:
        """
        Extract XML file from a .meca zip file.
        Returns path to extracted XML file.
        """
        try:
            with zipfile.ZipFile(meca_path, 'r') as zip_file:
                # Look for XML files in the content folder
                xml_files = [f for f in zip_file.namelist() 
                           if f.endswith('.xml') and 'content/' in f and 'manifest' not in f.lower()]
                
                if not xml_files:
                    raise ValueError("No XML files found in .meca archive")
                
                # Usually there's one main XML file
                xml_file = xml_files[0]
                
                # Extract to temporary file
                temp_fd, temp_xml_path = tempfile.mkstemp(suffix='.xml', prefix='biorxiv_extracted_')
                
                with os.fdopen(temp_fd, 'wb') as temp_file:
                    temp_file.write(zip_file.read(xml_file))
                
                return temp_xml_path
        
        except Exception as e:
            print(f"Error extracting XML from .meca file: {e}")
            return None
    
    def download_xml(self, doi: str) -> Optional[str]:
        """
        Download the XML file for a bioRxiv paper using the official S3 method.
        Falls back to direct URL method if S3 fails.
        Returns the path to the downloaded file, or None if failed.
        """
        try:
            # Get metadata first to verify the paper exists
            metadata = self.get_paper_metadata(doi)
            if not metadata:
                raise ValueError(f"Paper not found: {doi}")
            
            # Try S3 download first (official method)
            xml_path = self.download_xml_from_s3(doi, metadata)
            if xml_path:
                return xml_path
            
            # If S3 fails, fall back to direct URL method
            print(f"S3 download failed for {doi}, trying direct URL method...")
            return self._download_xml_direct(doi, metadata)
        
        except Exception as e:
            print(f"Error downloading XML for {doi}: {e}")
            return None
    
    def _download_xml_direct(self, doi: str, metadata: dict) -> Optional[str]:
        """
        Fallback method: try to download XML directly from bioRxiv URLs.
        """
        try:
            # Extract the paper identifier for download URL
            paper_id = doi.replace('10.1101/', '')
            
            # Try different XML download URLs using correct field names
            preprint_date = metadata.get('preprint_date', '')
            xml_urls = [
                f"{self.BASE_URL}/content/biorxiv/early/{preprint_date.replace('-', '/')}/{paper_id}.source.xml",
                f"{self.BASE_URL}/content/early/{preprint_date.replace('-', '/')}/{paper_id}.source.xml",
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
            print(f"Error downloading XML directly for {doi}: {e}")
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