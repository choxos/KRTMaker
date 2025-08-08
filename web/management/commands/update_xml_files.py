import os
import json
import hashlib
import time
from datetime import datetime, date, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from europepmc_fetcher import EuropePMCFetcher
from web.models import XMLFile, Article


class Command(BaseCommand):
    help = 'Update XML files database with new bioRxiv papers since last download'

    def add_arguments(self, parser):
        parser.add_argument('--days-back', type=int, default=7,
                           help='Number of days to look back from the latest XML file (default: 7)')
        parser.add_argument('--force-update-recent', action='store_true',
                           help='Force update of recent papers (last 30 days)')
        parser.add_argument('--dry-run', action='store_true',
                           help='Show what would be done without downloading files')
        parser.add_argument('--limit', type=int,
                           help='Limit number of new papers to download (for testing)')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔄 bioRxiv XML Files Incremental Update'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        fetcher = EuropePMCFetcher()
        self.stdout.write(self.style.SUCCESS('✅ Europe PMC fetcher initialized'))

        days_back = options['days_back']
        force_update_recent = options['force_update_recent']
        dry_run = options['dry_run']
        limit = options['limit']

        # Configuration display
        self.stdout.write('\n📋 Configuration:')
        self.stdout.write(f'   Days back from latest: {days_back}')
        self.stdout.write(f'   Force update recent: {force_update_recent}')
        self.stdout.write(f'   Limit: {limit or "No limit"}')
        self.stdout.write(f'   Mode: {"Dry Run" if dry_run else "Update"}')
        self.stdout.write(f'   XML Storage: {settings.XML_STORAGE_DIR}')

        # Get current database status
        total_xmls = XMLFile.objects.filter(is_available=True).count()
        latest_xml = XMLFile.objects.filter(is_available=True).order_by('-downloaded_at').first()
        
        self.stdout.write(f'\n📊 Current Database Status:')
        self.stdout.write(f'   Total XML files: {total_xmls:,}')
        
        if latest_xml:
            self.stdout.write(f'   Latest download: {latest_xml.downloaded_at.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write(f'   Latest paper date: {latest_xml.publication_date or "Unknown"}')
        else:
            self.stdout.write(f'   No XML files found - run full download first')
            return

        # Determine date range for update
        if force_update_recent:
            # Update last 30 days
            start_date = date.today() - timedelta(days=30)
            self.stdout.write(f'\n🔄 Force updating recent papers (last 30 days)')
        else:
            # Update from latest file date minus days_back buffer
            if latest_xml.publication_date:
                start_date = latest_xml.publication_date - timedelta(days=days_back)
            else:
                # Fallback: use latest download date
                start_date = latest_xml.downloaded_at.date() - timedelta(days=days_back)
        
        end_date = date.today()
        
        self.stdout.write(f'\n📅 Update Date Range:')
        self.stdout.write(f'   From: {start_date}')
        self.stdout.write(f'   To: {end_date}')
        
        # Search for papers in the date range
        self.stdout.write(f'\n🔍 Searching for papers in date range...')
        
        # Build query for date range
        query = f'JOURNAL:("bioRxiv : the preprint server for biology") AND (FIRST_PDATE:[{start_date.strftime("%Y-%m-%d")} TO {end_date.strftime("%Y-%m-%d")}])'
        
        papers = fetcher.search_complete_results(query, limit=limit)
        
        self.stdout.write(f'📊 Found {len(papers):,} papers in date range')
        
        if not papers:
            self.stdout.write(self.style.SUCCESS('\n✅ No new papers found - database is up to date!'))
            return

        # Filter for truly new papers
        new_papers = []
        updated_papers = []
        
        for paper in papers:
            doi = paper.get('doi')
            if not doi or doi == 'No DOI':
                continue
                
            existing = XMLFile.objects.filter(doi=doi).first()
            
            if not existing:
                new_papers.append(paper)
            elif force_update_recent:
                updated_papers.append(paper)
        
        self.stdout.write(f'\n📈 Analysis Results:')
        self.stdout.write(f'   New papers: {len(new_papers):,}')
        self.stdout.write(f'   Papers to update: {len(updated_papers):,}')
        
        total_to_process = len(new_papers) + len(updated_papers)
        
        if total_to_process == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ No new papers to download - database is up to date!'))
            return

        if dry_run:
            self.stdout.write(f'\n🔍 DRY RUN - Would process {total_to_process:,} papers')
            self._show_sample_papers(new_papers[:5], "New papers (sample):")
            if updated_papers:
                self._show_sample_papers(updated_papers[:5], "Papers to update (sample):")
            return

        # Download new and updated papers
        self.stdout.write(f'\n🔄 Starting incremental download...')
        start_time = time.time()
        
        downloaded_count = 0
        failed_count = 0
        
        # Process new papers
        if new_papers:
            self.stdout.write(f'\n📥 Processing {len(new_papers):,} new papers...')
            for i, paper in enumerate(new_papers, 1):
                self.stdout.write(f'   {i:4d}/{len(new_papers):4d} {paper.get("doi", "Unknown DOI")}', ending='')
                
                success = self._download_xml_for_paper(paper, fetcher)
                if success:
                    self.stdout.write(' ✅ Downloaded')
                    downloaded_count += 1
                else:
                    self.stdout.write(' ❌ Failed')
                    failed_count += 1
                
                time.sleep(0.1)  # Rate limiting

        # Process updated papers
        if updated_papers:
            self.stdout.write(f'\n🔄 Updating {len(updated_papers):,} existing papers...')
            for i, paper in enumerate(updated_papers, 1):
                self.stdout.write(f'   {i:4d}/{len(updated_papers):4d} {paper.get("doi", "Unknown DOI")}', ending='')
                
                success = self._download_xml_for_paper(paper, fetcher, force_update=True)
                if success:
                    self.stdout.write(' ✅ Updated')
                    downloaded_count += 1
                else:
                    self.stdout.write(' ❌ Failed')
                    failed_count += 1
                
                time.sleep(0.1)  # Rate limiting

        # Final summary
        total_time = time.time() - start_time
        new_total = XMLFile.objects.filter(is_available=True).count()
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('🎉 INCREMENTAL UPDATE COMPLETE'))
        self.stdout.write('=' * 60)
        
        self.stdout.write(f'\n📊 Final Statistics:')
        self.stdout.write(f'   Papers processed: {total_to_process:,}')
        self.stdout.write(f'   Successfully downloaded: {downloaded_count:,}')
        self.stdout.write(f'   Failed downloads: {failed_count:,}')
        self.stdout.write(f'   Total time: {total_time/60:.1f} minutes')
        
        if downloaded_count > 0:
            avg_time = total_time / downloaded_count
            self.stdout.write(f'   Average per file: {avg_time:.2f} seconds')

        self.stdout.write(f'\n📈 Database Status:')
        self.stdout.write(f'   XML files before: {total_xmls:,}')
        self.stdout.write(f'   XML files after: {new_total:,}')
        self.stdout.write(f'   Net change: +{new_total - total_xmls:,}')

        # Show next recommended update
        next_update = datetime.now() + timedelta(days=1)
        self.stdout.write(f'\n💡 Recommendation:')
        self.stdout.write(f'   Run this command daily or weekly to stay current')
        self.stdout.write(f'   Next suggested run: {next_update.strftime("%Y-%m-%d")}')

    def _show_sample_papers(self, papers, title):
        """Show a sample of papers for dry run"""
        self.stdout.write(f'\n{title}')
        for paper in papers:
            doi = paper.get('doi', 'Unknown DOI')
            title = paper.get('title', 'Unknown Title')
            date = paper.get('publication_date', 'Unknown Date')
            self.stdout.write(f'   • {doi} - {title[:60]}... ({date})')

    def _download_xml_for_paper(self, paper, fetcher, force_update=False):
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
                if force_update:
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