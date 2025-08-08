"""
Django management command to populate the Article database with all bioRxiv papers
from Europe PMC using the year-by-year search functionality.

Usage:
    python manage.py populate_articles [options]

Examples:
    # Populate all years (2020-2025)
    python manage.py populate_articles
    
    # Populate specific years
    python manage.py populate_articles --start-year 2023 --end-year 2025
    
    # Test with limited papers per year
    python manage.py populate_articles --limit-per-year 100
    
    # Update existing database (skip already processed)
    python manage.py populate_articles --update-only
    
    # Force refresh all papers (overwrites existing)
    python manage.py populate_articles --force-refresh
"""

import json
import time
from datetime import datetime
from typing import List, Dict, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

# Import our models
from web.models import Article

# Import our Europe PMC fetcher
import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from europepmc_fetcher import EuropePMCFetcher


class Command(BaseCommand):
    help = 'Populate Article database with bioRxiv papers from Europe PMC using year-by-year search'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-year',
            type=int,
            default=2020,
            help='Starting year for article retrieval (default: 2020)'
        )
        parser.add_argument(
            '--end-year',
            type=int,
            default=2025,
            help='Ending year for article retrieval (default: 2025)'
        )
        parser.add_argument(
            '--limit-per-year',
            type=int,
            help='Limit number of papers per year (for testing)'
        )
        parser.add_argument(
            '--update-only',
            action='store_true',
            help='Only add new papers, skip existing DOIs'
        )
        parser.add_argument(
            '--force-refresh',
            action='store_true',
            help='Force refresh all papers, overwriting existing data'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making database changes'
        )
        parser.add_argument(
            '--stats-only',
            action='store_true',
            help='Only show statistics without downloading papers'
        )

    def handle(self, *args, **options):
        """Main command handler"""
        self.start_time = time.time()
        self.options = options
        
        # Print header
        self.stdout.write(self.style.SUCCESS('\n🚀 bioRxiv Article Database Population'))
        self.stdout.write('=' * 60)
        
        # Initialize fetcher
        try:
            self.fetcher = EuropePMCFetcher()
            self.stdout.write(self.style.SUCCESS('✅ Europe PMC fetcher initialized'))
        except Exception as e:
            raise CommandError(f'Failed to initialize Europe PMC fetcher: {e}')
        
        # Show configuration
        self.show_configuration()
        
        # Get statistics first
        year_stats = self.get_year_statistics()
        
        if options['stats_only']:
            self.show_final_statistics(year_stats, 0, 0, 0)
            return
        
        # Populate database
        try:
            created, updated, skipped = self.populate_database(year_stats)
            self.show_final_statistics(year_stats, created, updated, skipped)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️  Population interrupted by user'))
            self.show_current_database_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Population failed: {e}'))
            raise CommandError(f'Database population failed: {e}')

    def show_configuration(self):
        """Show current configuration"""
        self.stdout.write('\n📋 Configuration:')
        self.stdout.write(f'   Years: {self.options["start_year"]} - {self.options["end_year"]}')
        
        if self.options['limit_per_year']:
            self.stdout.write(f'   Limit per year: {self.options["limit_per_year"]:,}')
        else:
            self.stdout.write('   Limit per year: No limit (ALL papers)')
            
        if self.options['update_only']:
            self.stdout.write('   Mode: Update only (skip existing)')
        elif self.options['force_refresh']:
            self.stdout.write('   Mode: Force refresh (overwrite existing)')
        else:
            self.stdout.write('   Mode: Standard (add new, update if needed)')
            
        if self.options['dry_run']:
            self.stdout.write(self.style.WARNING('   🔍 DRY RUN MODE - No database changes'))

    def get_year_statistics(self) -> Dict[int, int]:
        """Get paper count statistics by year"""
        self.stdout.write('\n📊 Getting bioRxiv paper statistics...')
        
        try:
            year_stats = self.fetcher.get_year_statistics(
                start_year=self.options['start_year'],
                end_year=self.options['end_year']
            )
            
            self.stdout.write('\n📈 Paper counts by year:')
            total_papers = 0
            for year, count in year_stats.items():
                self.stdout.write(f'   {year}: {count:,} papers')
                total_papers += count
            
            self.stdout.write(f'\n🎯 Total papers available: {total_papers:,}')
            
            if self.options['limit_per_year']:
                limited_total = min(self.options['limit_per_year'], max(year_stats.values())) * len(year_stats)
                self.stdout.write(f'🔢 Total with limit: {limited_total:,} papers')
            
            return year_stats
            
        except Exception as e:
            raise CommandError(f'Failed to get year statistics: {e}')

    def populate_database(self, year_stats: Dict[int, int]) -> tuple:
        """Populate the database with articles"""
        self.stdout.write('\n🔄 Starting database population...')
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Get papers year by year
        all_papers = self.get_all_papers(year_stats)
        
        if not all_papers:
            self.stdout.write(self.style.WARNING('⚠️  No papers retrieved'))
            return created_count, updated_count, skipped_count
        
        self.stdout.write(f'\n💾 Processing {len(all_papers):,} papers for database storage...')
        
        # Process papers in batches for better performance
        batch_size = 100
        total_papers = len(all_papers)
        
        for i in range(0, total_papers, batch_size):
            batch = all_papers[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_papers + batch_size - 1) // batch_size
            
            self.stdout.write(f'\n📦 Processing batch {batch_num}/{total_batches} ({len(batch)} papers)...')
            
            if self.options['dry_run']:
                self.stdout.write(f'   🔍 DRY RUN: Would process papers {i+1}-{min(i+batch_size, total_papers)}')
                continue
            
            batch_created, batch_updated, batch_skipped = self.process_batch(batch)
            
            created_count += batch_created
            updated_count += batch_updated
            skipped_count += batch_skipped
            
            # Show progress
            progress = (i + len(batch)) / total_papers * 100
            self.stdout.write(f'   ✅ Batch complete: +{batch_created} created, +{batch_updated} updated, +{batch_skipped} skipped')
            self.stdout.write(f'   📊 Progress: {progress:.1f}% ({i + len(batch):,}/{total_papers:,})')
        
        return created_count, updated_count, skipped_count

    def get_all_papers(self, year_stats: Dict[int, int]) -> List[Dict]:
        """Retrieve all papers using year-by-year search"""
        self.stdout.write('\n🔍 Retrieving papers from Europe PMC...')
        
        try:
            papers = self.fetcher.search_all_biorxiv_papers_by_year(
                start_year=self.options['start_year'],
                end_year=self.options['end_year'],
                limit_per_year=self.options.get('limit_per_year')
            )
            
            self.stdout.write(f'✅ Retrieved {len(papers):,} papers total')
            return papers
            
        except Exception as e:
            raise CommandError(f'Failed to retrieve papers: {e}')

    def process_batch(self, papers: List[Dict]) -> tuple:
        """Process a batch of papers and store in database"""
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for paper_data in papers:
                try:
                    result = self.process_single_paper(paper_data)
                    if result == 'created':
                        created_count += 1
                    elif result == 'updated':
                        updated_count += 1
                    else:
                        skipped_count += 1
                        
                except Exception as e:
                    self.stdout.write(f'   ⚠️  Error processing paper {paper_data.get("doi", "no DOI")}: {e}')
                    skipped_count += 1
        
        return created_count, updated_count, skipped_count

    def process_single_paper(self, paper_data: Dict) -> str:
        """Process a single paper and return action taken"""
        doi = paper_data.get('doi')
        if not doi or doi == 'No DOI':
            return 'skipped'  # Skip papers without DOI
        
        # Check if article already exists
        try:
            article = Article.objects.get(doi=doi)
            
            if self.options['update_only'] and not self.options['force_refresh']:
                return 'skipped'
            
            # Update existing article
            self.update_article_from_data(article, paper_data)
            return 'updated'
            
        except Article.DoesNotExist:
            # Create new article
            article = self.create_article_from_data(paper_data)
            return 'created'

    def create_article_from_data(self, paper_data: Dict) -> Article:
        """Create a new Article from paper data"""
        # Parse authors
        authors_raw = paper_data.get('authors', '')
        if isinstance(authors_raw, str):
            try:
                authors = json.loads(authors_raw) if authors_raw.startswith('[') else [authors_raw]
            except json.JSONDecodeError:
                authors = [authors_raw] if authors_raw else []
        else:
            authors = authors_raw or []
        
        # Parse keywords
        keywords_raw = paper_data.get('keywords', '')
        if isinstance(keywords_raw, str):
            try:
                keywords = json.loads(keywords_raw) if keywords_raw.startswith('[') else [keywords_raw]
            except json.JSONDecodeError:
                keywords = [keywords_raw] if keywords_raw else []
        else:
            keywords = keywords_raw or []
        
        # Parse publication date
        pub_date = None
        if paper_data.get('publication_date'):
            try:
                pub_date = datetime.strptime(paper_data['publication_date'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pub_date = None
        
        # Create article
        article = Article.objects.create(
            doi=paper_data.get('doi'),
            title=paper_data.get('title', ''),
            authors=json.dumps(authors),
            abstract=paper_data.get('abstract', ''),
            publication_date=pub_date,
            journal=paper_data.get('journal', ''),
            keywords=json.dumps(keywords),
            total_sessions=0
        )
        
        return article

    def update_article_from_data(self, article: Article, paper_data: Dict):
        """Update existing Article with new data"""
        # Only update if force refresh is enabled
        if not self.options['force_refresh']:
            return
        
        # Update fields
        article.title = paper_data.get('title', article.title)
        article.abstract = paper_data.get('abstract', article.abstract)
        article.journal = paper_data.get('journal', article.journal)
        
        # Update publication date if available
        if paper_data.get('publication_date'):
            try:
                article.publication_date = datetime.strptime(paper_data['publication_date'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        
        # Update authors and keywords
        if paper_data.get('authors'):
            authors_raw = paper_data['authors']
            if isinstance(authors_raw, str):
                try:
                    authors = json.loads(authors_raw) if authors_raw.startswith('[') else [authors_raw]
                except json.JSONDecodeError:
                    authors = [authors_raw]
            else:
                authors = authors_raw or []
            article.authors = json.dumps(authors)
        
        if paper_data.get('keywords'):
            keywords_raw = paper_data['keywords']
            if isinstance(keywords_raw, str):
                try:
                    keywords = json.loads(keywords_raw) if keywords_raw.startswith('[') else [keywords_raw]
                except json.JSONDecodeError:
                    keywords = [keywords_raw]
            else:
                keywords = keywords_raw or []
            article.keywords = json.dumps(keywords)
        
        article.last_processed = timezone.now()
        article.save()

    def show_current_database_status(self):
        """Show current database status"""
        total_articles = Article.objects.count()
        articles_with_sessions = Article.objects.filter(total_sessions__gt=0).count()
        
        self.stdout.write('\n📊 Current Database Status:')
        self.stdout.write(f'   Total articles: {total_articles:,}')
        self.stdout.write(f'   Articles with KRT sessions: {articles_with_sessions:,}')
        self.stdout.write(f'   Articles without sessions: {total_articles - articles_with_sessions:,}')

    def show_final_statistics(self, year_stats: Dict[int, int], created: int, updated: int, skipped: int):
        """Show final statistics"""
        elapsed_time = time.time() - self.start_time
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('🎉 DATABASE POPULATION COMPLETE'))
        self.stdout.write('=' * 60)
        
        # Year statistics
        self.stdout.write('\n📊 Source Statistics:')
        total_available = sum(year_stats.values())
        for year, count in year_stats.items():
            self.stdout.write(f'   {year}: {count:,} papers available')
        self.stdout.write(f'   TOTAL: {total_available:,} papers available')
        
        # Processing statistics
        if not self.options['stats_only']:
            total_processed = created + updated + skipped
            self.stdout.write('\n💾 Database Operations:')
            self.stdout.write(f'   Created: {created:,} articles')
            self.stdout.write(f'   Updated: {updated:,} articles')
            self.stdout.write(f'   Skipped: {skipped:,} articles')
            self.stdout.write(f'   TOTAL: {total_processed:,} articles processed')
            
            # Database status
            self.show_current_database_status()
        
        # Performance
        self.stdout.write('\n⏱️  Performance:')
        self.stdout.write(f'   Total time: {elapsed_time:.1f} seconds')
        if not self.options['stats_only'] and (created + updated) > 0:
            rate = (created + updated) / elapsed_time
            self.stdout.write(f'   Processing rate: {rate:.1f} articles/second')
        
        # Next steps
        self.stdout.write('\n💡 Next Steps:')
        self.stdout.write('   📖 Browse articles: python manage.py runserver → /articles/')
        self.stdout.write('   🔄 Update database: python manage.py populate_articles --update-only')
        self.stdout.write('   📊 Admin interface: /admin/ (if superuser created)')
        
        self.stdout.write(self.style.SUCCESS('\n✅ All done! 🚀'))