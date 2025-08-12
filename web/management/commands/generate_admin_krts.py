import os
import json
import time
from datetime import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from web.models import XMLFile, AdminKRT, Article
import sys

# Add the project root to sys.path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from builder import build_from_xml_path
except ImportError as e:
    print(f"Warning: Import error - {e}")
    build_from_xml_path = None

# Define fallback exception classes
class LLMProviderError(Exception):
    """Generic LLM provider error"""
    pass

class RateLimitError(LLMProviderError):
    """Rate limit exceeded error"""
    pass


class Command(BaseCommand):
    help = 'Generate KRTs for bioRxiv papers using admin-specified LLM models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            type=str,
            choices=['openai', 'anthropic', 'gemini', 'openai_compatible'],
            default='anthropic',
            help='LLM provider to use (default: anthropic)'
        )
        
        parser.add_argument(
            '--model',
            type=str,
            help='Model name to use (e.g., claude-3-5-sonnet-20241022, gpt-4o, gemini-1.5-pro)'
        )
        
        parser.add_argument(
            '--base-url',
            type=str,
            help='Base URL for OpenAI-compatible APIs (e.g., http://localhost:11434/v1)'
        )
        
        parser.add_argument(
            '--dois',
            type=str,
            nargs='+',
            help='Specific DOIs to process (space-separated)'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of papers to process (default: 10)'
        )
        
        parser.add_argument(
            '--random',
            action='store_true',
            help='Select papers randomly instead of oldest first'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration even if AdminKRT already exists for this DOI+provider+model'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually generating KRTs'
        )
        
        parser.add_argument(
            '--user',
            type=str,
            help='Username of the admin creating these KRTs (for tracking)'
        )
        
        parser.add_argument(
            '--auto-approve',
            action='store_true',
            help='Automatically approve generated KRTs (mark as approved)'
        )
        
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Delay between requests in seconds (default: 1.0)'
        )

    def handle(self, *args, **options):
        if build_from_xml_path is None:
            raise CommandError("Could not import KRT builder functions. Check your imports.")
        
        # Validate arguments
        provider = options['provider']
        model = options['model']
        
        if not model:
            default_models = {
                'anthropic': 'claude-3-5-sonnet-20241022',
                'gemini': 'gemini-1.5-pro',
                'openai': 'gpt-4o',
                'openai_compatible': 'llama3.2'
            }
            model = default_models.get(provider)
            if not model:
                raise CommandError(f"No default model for provider {provider}. Please specify --model")
        
        self.stdout.write(f"🤖 Admin KRT Generator")
        self.stdout.write(f"Provider: {provider}")
        self.stdout.write(f"Model: {model}")
        if options['base_url']:
            self.stdout.write(f"Base URL: {options['base_url']}")
        self.stdout.write(f"Limit: {options['limit']}")
        
        # Get user for tracking
        user = None
        if options['user']:
            try:
                user = User.objects.get(username=options['user'])
                self.stdout.write(f"Admin User: {user.username}")
            except User.DoesNotExist:
                self.stderr.write(f"Warning: User '{options['user']}' not found")
        
        # Get papers to process
        if options['dois']:
            # Process specific DOIs
            xml_files = XMLFile.objects.filter(
                doi__in=options['dois'],
                is_available=True
            )
            papers_to_process = list(xml_files)
            
            missing_dois = set(options['dois']) - set(f.doi for f in papers_to_process)
            if missing_dois:
                self.stderr.write(f"Warning: Could not find XML files for DOIs: {missing_dois}")
                
        else:
            # Get papers that don't have AdminKRT for this provider+model yet
            if options['force']:
                xml_files = XMLFile.objects.filter(is_available=True)
            else:
                # Exclude papers that already have AdminKRT for this provider+model
                existing_dois = AdminKRT.objects.filter(
                    provider=provider,
                    model_name=model
                ).values_list('doi', flat=True)
                
                xml_files = XMLFile.objects.filter(
                    is_available=True
                ).exclude(doi__in=existing_dois)
            
            if options['random']:
                papers_to_process = list(xml_files.order_by('?')[:options['limit']])
            else:
                papers_to_process = list(xml_files.order_by('publication_date')[:options['limit']])
        
        if not papers_to_process:
            self.stdout.write("✅ No papers to process")
            return
        
        self.stdout.write(f"📋 Found {len(papers_to_process)} papers to process")
        
        if options['dry_run']:
            self.stdout.write("\n🔍 DRY RUN - Papers that would be processed:")
            for xml_file in papers_to_process:
                existing = AdminKRT.objects.filter(
                    doi=xml_file.doi,
                    provider=provider,
                    model_name=model
                ).first()
                
                status = "NEW" if not existing else f"EXISTS ({existing.status})"
                self.stdout.write(f"  📄 {xml_file.doi} - {xml_file.title[:60]}... [{status}]")
            return
        
        # Process papers
        self.stdout.write(f"\n🚀 Starting KRT generation...")
        processed = 0
        succeeded = 0
        failed = 0
        skipped = 0
        
        for i, xml_file in enumerate(papers_to_process, 1):
            self.stdout.write(f"\n[{i}/{len(papers_to_process)}] Processing {xml_file.doi}")
            
            try:
                # Check if AdminKRT already exists
                existing = AdminKRT.objects.filter(
                    doi=xml_file.doi,
                    provider=provider,
                    model_name=model
                ).first()
                
                if existing and not options['force']:
                    self.stdout.write(f"  ⏭️  AdminKRT already exists (status: {existing.status})")
                    skipped += 1
                    continue
                
                # Verify XML file exists on disk
                if not xml_file.verify_file_exists():
                    self.stderr.write(f"  ❌ XML file missing on disk: {xml_file.full_file_path}")
                    failed += 1
                    continue
                
                # Create or update AdminKRT record
                if existing and options['force']:
                    admin_krt = existing
                    admin_krt.status = 'processing'
                    admin_krt.retry_count += 1
                    admin_krt.error_message = None
                    admin_krt.save()
                    self.stdout.write(f"  🔄 Updating existing AdminKRT (retry #{admin_krt.retry_count})")
                else:
                    # Get or create Article if it doesn't exist
                    article, _ = Article.objects.get_or_create(
                        doi=xml_file.doi,
                        defaults={
                            'title': xml_file.title,
                            'authors': xml_file.authors,
                            'publication_date': xml_file.publication_date,
                            'journal': xml_file.journal,
                            'xml_file': xml_file
                        }
                    )
                    
                    admin_krt = AdminKRT.objects.create(
                        xml_file=xml_file,
                        article=article,
                        provider=provider,
                        model_name=model,
                        base_url=options['base_url'],
                        status='processing',
                        created_by=user
                    )
                    self.stdout.write(f"  ✨ Created new AdminKRT record")
                
                # Generate KRT using the builder
                start_time = time.time()
                
                try:
                    self.stdout.write(f"  🧠 Generating KRT with {provider}/{model}...")
                    
                    result = build_from_xml_path(
                        xml_path=xml_file.full_file_path,
                        mode='llm',
                        provider=provider,
                        model=model,
                        base_url=options['base_url'],
                        extra_instructions=None
                    )
                    
                    processing_time = time.time() - start_time
                    
                    if result and 'krt_data' in result:
                        # Save successful result
                        with transaction.atomic():
                            admin_krt.krt_data = result['krt_data']
                            admin_krt.processing_time = processing_time
                            admin_krt.status = 'completed'
                            admin_krt.update_analytics()
                            
                            # Auto-approve if requested
                            if options['auto_approve']:
                                admin_krt.status = 'approved'
                                admin_krt.approved_by = user
                                admin_krt.approved_at = timezone.now()
                                admin_krt.quality_rating = 'good'  # Default rating
                            
                            # Try to extract token usage if available
                            if 'token_usage' in result:
                                admin_krt.token_usage = result['token_usage']
                            
                            admin_krt.save()
                        
                        self.stdout.write(f"  ✅ Success! Found {admin_krt.resources_found} resources in {processing_time:.1f}s")
                        succeeded += 1
                        
                    else:
                        # No KRT data found
                        admin_krt.status = 'completed'
                        admin_krt.processing_time = processing_time
                        admin_krt.admin_notes = "No resources found in the paper"
                        admin_krt.save()
                        
                        self.stdout.write(f"  ⚠️  Completed but no resources found ({processing_time:.1f}s)")
                        succeeded += 1
                
                except (LLMProviderError, RateLimitError) as e:
                    # LLM-specific errors
                    admin_krt.status = 'failed'
                    admin_krt.error_message = str(e)
                    admin_krt.processing_time = time.time() - start_time
                    admin_krt.save()
                    
                    self.stderr.write(f"  ❌ LLM Error: {e}")
                    failed += 1
                    
                    # If rate limited, add extra delay
                    if isinstance(e, RateLimitError):
                        self.stdout.write(f"  ⏳ Rate limited, waiting 30 seconds...")
                        time.sleep(30)
                
                except Exception as e:
                    # General errors
                    admin_krt.status = 'failed'
                    admin_krt.error_message = f"Generation error: {str(e)}"
                    admin_krt.processing_time = time.time() - start_time
                    admin_krt.save()
                    
                    self.stderr.write(f"  ❌ Error: {e}")
                    failed += 1
                
                processed += 1
                
                # Rate limiting delay
                if options['delay'] > 0 and i < len(papers_to_process):
                    time.sleep(options['delay'])
                
            except Exception as e:
                self.stderr.write(f"  💥 Unexpected error: {e}")
                failed += 1
                continue
        
        # Final summary
        self.stdout.write(f"\n📊 Generation Summary:")
        self.stdout.write(f"  📋 Total processed: {processed}")
        self.stdout.write(f"  ✅ Succeeded: {succeeded}")
        self.stdout.write(f"  ❌ Failed: {failed}")
        self.stdout.write(f"  ⏭️  Skipped: {skipped}")
        
        if succeeded > 0:
            # Show statistics
            stats = AdminKRT.get_statistics()
            self.stdout.write(f"\n📈 Overall AdminKRT Statistics:")
            self.stdout.write(f"  🎯 Total AdminKRTs: {stats['total']}")
            self.stdout.write(f"  ✅ Completed: {stats['completed']}")
            self.stdout.write(f"  🏆 Approved: {stats['approved']}")
            self.stdout.write(f"  📈 Completion Rate: {stats['completion_rate']:.1f}%")
            self.stdout.write(f"  🌟 Approval Rate: {stats['approval_rate']:.1f}%")
        
        self.stdout.write(f"\n🎉 Admin KRT generation completed!")