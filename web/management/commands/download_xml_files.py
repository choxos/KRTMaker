import os
import json
import hashlib
import time
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from europepmc_fetcher import EuropePMCFetcher
from web.models import XMLFile, Article


class Command(BaseCommand):
    help = 'Download XML files for bioRxiv papers and store them locally'

    def add_arguments(self, parser):
        parser.add_argument('--start-year', type=int, default=2020,
                           help='Starting year for XML download (default: 2020)')
        parser.add_argument('--end-year', type=int, default=datetime.now().year,
                           help='Ending year for XML download (default: current year)')
        parser.add_argument('--limit-per-year', type=int,
                           help='Limit number of papers per year (for testing)')
        parser.add_argument('--dry-run', action='store_true',
                           help='Show what would be done without downloading files')
        parser.add_argument('--update-only', action='store_true',
                           help='Only download XML for papers not already in database')
        parser.add_argument('--force-redownload', action='store_true',
                           help='Force redownload of all XML files')
        parser.add_argument('--verify-files', action='store_true',
                           help='Verify existing XML files and redownload if corrupted')
        parser.add_argument('--stats-only', action='store_true',
                           help='Only show statistics without downloading')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 bioRxiv XML File Download Manager'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        fetcher = EuropePMCFetcher()
        self.stdout.write(self.style.SUCCESS('✅ Europe PMC fetcher initialized'))

        start_year = options['start_year']
        end_year = options['end_year']
        limit_per_year = options['limit_per_year']
        dry_run = options['dry_run']
        update_only = options['update_only']
        force_redownload = options['force_redownload']
        verify_files = options['verify_files']
        stats_only = options['stats_only']

        # Configuration display
        self.stdout.write('\n📋 Configuration:')
        self.stdout.write(f'   Years: {start_year} - {end_year}')
        self.stdout.write(f'   Limit per year: {"No limit (ALL papers)" if limit_per_year is None else limit_per_year}')
        self.stdout.write(f'   XML Storage: {settings.XML_STORAGE_DIR}')
        
        mode_flags = []
        if dry_run: mode_flags.append('Dry Run')
        if update_only: mode_flags.append('Update Only')
        if force_redownload: mode_flags.append('Force Redownload')
        if verify_files: mode_flags.append('Verify Files')
        if stats_only: mode_flags.append('Stats Only')
        
        self.stdout.write(f'   Mode: {" + ".join(mode_flags) if mode_flags else "Standard Download"}')

        # Current database stats
        existing_xmls = XMLFile.objects.filter(is_available=True).count()
        total_articles = Article.objects.count()
        
        self.stdout.write(f'\n📊 Current Database Status:')
        self.stdout.write(f'   XML Files in Database: {existing_xmls:,}')
        self.stdout.write(f'   Articles in Database: {total_articles:,}')

        if verify_files:
            self.stdout.write('\n🔍 Verifying existing XML files...')
            self._verify_existing_files()

        if stats_only:
            # Just show statistics about what's available
            self.stdout.write('\n📈 Getting bioRxiv paper statistics...')
            year_stats = fetcher.get_year_statistics(start_year, end_year)
            
            total_available = sum(year_stats.values())
            self.stdout.write(f'\n📊 Papers available by year:')
            for year, count in year_stats.items():
                existing_for_year = XMLFile.objects.filter(
                    publication_date__year=year,
                    is_available=True
                ).count()
                
                percentage = (existing_for_year / count * 100) if count > 0 else 0
                self.stdout.write(f'   {year}: {count:,} available, {existing_for_year:,} downloaded ({percentage:.1f}%)')
            
            self.stdout.write(f'\n🎯 Total: {total_available:,} papers available, {existing_xmls:,} downloaded')
            coverage = (existing_xmls / total_available * 100) if total_available > 0 else 0
            self.stdout.write(f'📈 Coverage: {coverage:.1f}%')
            
            return

        # Download XML files
        self.stdout.write('\n🔄 Starting XML file download...')
        start_time = time.time()
        
        downloaded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for year in range(start_year, end_year + 1):
            self.stdout.write(f'\n📆 === YEAR {year} ===')
            
            # Get papers for this year
            papers = fetcher.search_all_biorxiv_papers_by_year(year, year, limit_per_year)
            
            year_downloaded = 0
            year_failed = 0
            year_skipped = 0
            
            for i, paper in enumerate(papers, 1):
                doi = paper.get('doi')
                epmc_id = paper.get('epmc_id')
                
                if not doi or doi == 'No DOI':
                    continue
                
                self.stdout.write(f'   {i:4d}/{len(papers):4d} Processing: {doi}', ending='')
                
                # Check if already exists and not forcing redownload
                if not force_redownload:
                    existing = XMLFile.objects.filter(doi=doi, is_available=True).first()
                    if existing and update_only:
                        self.stdout.write(' ⏭️  Skipped (exists)')
                        year_skipped += 1
                        continue
                
                if dry_run:
                    self.stdout.write(' 🔍 Would download')
                    year_downloaded += 1
                    continue
                
                # Download the XML file
                success = self._download_xml_for_paper(paper, fetcher)
                
                if success:
                    self.stdout.write(' ✅ Downloaded')
                    year_downloaded += 1
                else:
                    self.stdout.write(' ❌ Failed')
                    year_failed += 1
                
                # Rate limiting to be respectful to Europe PMC
                time.sleep(0.1)
            
            self.stdout.write(f'   Year {year} Summary: {year_downloaded} downloaded, {year_failed} failed, {year_skipped} skipped')
            
            downloaded_count += year_downloaded
            failed_count += year_failed
            skipped_count += year_skipped

        # Final summary
        total_time = time.time() - start_time
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('🎉 XML DOWNLOAD COMPLETE'))
        self.stdout.write('=' * 60)
        
        self.stdout.write(f'\n📊 Final Statistics:')
        self.stdout.write(f'   Total Downloaded: {downloaded_count:,}')
        self.stdout.write(f'   Total Failed: {failed_count:,}')
        self.stdout.write(f'   Total Skipped: {skipped_count:,}')
        self.stdout.write(f'   Total Time: {total_time/60:.1f} minutes')
        
        if downloaded_count > 0:
            avg_time = total_time / downloaded_count
            self.stdout.write(f'   Average per file: {avg_time:.2f} seconds')

        # Updated database stats
        final_xmls = XMLFile.objects.filter(is_available=True).count()
        self.stdout.write(f'\n📈 Database Status:')
        self.stdout.write(f'   XML Files Before: {existing_xmls:,}')
        self.stdout.write(f'   XML Files After: {final_xmls:,}')
        self.stdout.write(f'   New Files Added: {final_xmls - existing_xmls:,}')

    def _verify_existing_files(self):
        """Verify that existing XML files still exist and are valid"""
        xml_files = XMLFile.objects.filter(is_available=True)
        
        missing_count = 0
        corrupted_count = 0
        
        for xml_file in xml_files:
            if not xml_file.verify_file_exists():
                missing_count += 1
                self.stdout.write(f'   ❌ Missing: {xml_file.doi}')
            else:
                # Verify file hash
                current_hash = xml_file.calculate_file_hash()
                if current_hash and current_hash != xml_file.file_hash:
                    corrupted_count += 1
                    xml_file.is_available = False
                    xml_file.error_message = "File hash mismatch - corrupted"
                    xml_file.save()
                    self.stdout.write(f'   ⚠️  Corrupted: {xml_file.doi}')
        
        self.stdout.write(f'   Verification complete: {missing_count} missing, {corrupted_count} corrupted')

    def _download_xml_for_paper(self, paper, fetcher):
        """Download XML file for a single paper and save to database"""
        doi = paper.get('doi')
        epmc_id = paper.get('epmc_id')
        
        if not epmc_id:
            epmc_id = fetcher.search_epmc_for_doi(doi)
            if not epmc_id:
                return False
        
        # Download XML content
        xml_content = self._download_xml_content(epmc_id, fetcher)
        if not xml_content:
            return False
        
        # Calculate file hash
        file_hash = hashlib.sha256(xml_content).hexdigest()
        
        # Generate file path (organized by year)
        pub_date = paper.get('publication_date')
        if isinstance(pub_date, str):
            try:
                pub_date = datetime.strptime(pub_date[:10], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pub_date = None
        
        year_dir = str(pub_date.year) if pub_date else 'unknown_year'
        filename = f"{doi.replace('10.1101/', '').replace('/', '_')}.xml"
        relative_path = os.path.join(year_dir, filename)
        
        # Create directory structure
        full_dir = os.path.join(settings.XML_STORAGE_DIR, year_dir)
        os.makedirs(full_dir, exist_ok=True)
        
        # Write file
        full_path = os.path.join(settings.XML_STORAGE_DIR, relative_path)
        
        try:
            with open(full_path, 'wb') as f:
                f.write(xml_content)
            
            file_size = len(xml_content)
            
            # Save to database
            with transaction.atomic():
                # Remove any existing entry
                XMLFile.objects.filter(doi=doi).delete()
                
                # Create new entry
                xml_file = XMLFile.objects.create(
                    doi=doi,
                    epmc_id=epmc_id,
                    file_path=relative_path,
                    file_size=file_size,
                    file_hash=file_hash,
                    title=paper.get('title', ''),
                    authors=json.dumps(paper.get('authors', [])) if paper.get('authors') else None,
                    publication_date=pub_date,
                    journal=paper.get('journal', 'bioRxiv'),
                    is_available=True
                )
                
                # Update related Article if exists
                article = Article.objects.filter(doi=doi).first()
                if article:
                    article.xml_file = xml_file
                    article.save()
            
            return True
            
        except Exception as e:
            # Clean up file if database save failed
            if os.path.exists(full_path):
                try:
                    os.unlink(full_path)
                except:
                    pass
            return False

    def _download_xml_content(self, epmc_id, fetcher):
        """Download XML content from Europe PMC"""
        try:
            url = f"{fetcher.BASE_URL}/{epmc_id}/fullTextXML"
            response = fetcher.session.get(url, timeout=60)
            response.raise_for_status()
            
            # Verify we got XML content
            content_type = response.headers.get('content-type', '').lower()
            if 'xml' not in content_type:
                return None
            
            return response.content
            
        except Exception as e:
            return None