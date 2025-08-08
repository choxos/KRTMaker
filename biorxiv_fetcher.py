"""
bioRxiv paper fetcher - Download XML content via Europe PMC
"""
from __future__ import annotations

from europepmc_fetcher import EuropePMCFetcher
from typing import Optional, Tuple, Dict

class BioRxivFetcher:
    """Fetch bioRxiv papers via Europe PMC (wrapper for backward compatibility)"""
    
    def __init__(self):
        self.epmc_fetcher = EuropePMCFetcher()
    
    def parse_biorxiv_identifier(self, identifier: str) -> Optional[str]:
        """Parse bioRxiv URL or DOI to extract the DOI."""
        return self.epmc_fetcher.parse_biorxiv_identifier(identifier)
    
    def get_paper_metadata(self, doi: str) -> Optional[Dict]:
        """Get paper metadata from Europe PMC."""
        return self.epmc_fetcher.get_paper_metadata(doi)
    
    def download_xml(self, doi: str) -> Optional[str]:
        """Download XML for a bioRxiv paper using Europe PMC."""
        return self.epmc_fetcher.download_xml(doi)
    
    def fetch_paper_info(self, identifier: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Fetch both metadata and XML file for a bioRxiv paper."""
        return self.epmc_fetcher.fetch_paper_info(identifier)
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """Clean up a temporary file."""
        self.epmc_fetcher.cleanup_temp_file(file_path)