#!/usr/bin/env python3
"""
Example usage of the year-by-year Europe PMC search functionality
"""

from europepmc_fetcher import EuropePMCFetcher

def example_get_statistics():
    """Example: Get paper count statistics by year"""
    print("📊 Example: Getting bioRxiv statistics by year")
    
    fetcher = EuropePMCFetcher()
    
    # Get statistics for 2020-2025
    stats = fetcher.get_year_statistics(2020, 2025)
    
    print("Year breakdown:")
    for year, count in stats.items():
        print(f"  {year}: {count:,} papers")
    
    return stats

def example_get_recent_papers():
    """Example: Get papers from recent years only"""
    print("\n📅 Example: Getting papers from 2024-2025")
    
    fetcher = EuropePMCFetcher()
    
    # Get papers from just 2024-2025 (without limits = ALL papers)
    papers = fetcher.search_all_biorxiv_papers_by_year(
        start_year=2024, 
        end_year=2025
        # No limit = get ALL papers from these years
    )
    
    print(f"Total papers retrieved: {len(papers)}")
    
    # Show breakdown by year
    year_counts = {}
    for paper in papers:
        year = paper.get('search_year', 'Unknown')
        year_counts[year] = year_counts.get(year, 0) + 1
    
    for year in sorted(year_counts.keys()):
        print(f"  {year}: {year_counts[year]:,} papers")
    
    return papers

def example_get_all_papers():
    """Example: Get ALL bioRxiv papers from 2020-2025"""
    print("\n🚀 Example: Getting ALL bioRxiv papers (2020-2025)")
    print("⚠️  This is a demonstration - would retrieve ~19,405 papers")
    
    fetcher = EuropePMCFetcher()
    
    # To get ALL papers (uncomment the line below)
    # papers = fetcher.search_all_biorxiv_papers_by_year(2020, 2025)
    
    # For demo, just show what the call would look like
    print("Code to retrieve ALL papers:")
    print("```python")
    print("fetcher = EuropePMCFetcher()")
    print("all_papers = fetcher.search_all_biorxiv_papers_by_year(2020, 2025)")
    print("print(f'Retrieved {len(all_papers):,} papers')")
    print("```")
    
    print("\n📈 Expected results based on statistics:")
    stats = {2020: 2897, 2021: 2765, 2022: 3848, 2023: 4063, 2024: 3534, 2025: 2298}
    total = sum(stats.values())
    
    for year, count in stats.items():
        print(f"  {year}: {count:,} papers")
    print(f"  TOTAL: {total:,} papers")
    
    print(f"\n⏱️  Estimated time: ~4-5 minutes with rate limiting")
    print(f"💾 Estimated data: ~{total * 2:.1f}KB of metadata")

if __name__ == "__main__":
    print("🌟 Europe PMC Year-by-Year Search Examples")
    print("=" * 50)
    
    # Example 1: Get statistics
    stats = example_get_statistics()
    
    # Example 2: Get recent papers (commented out to avoid long run)
    # papers = example_get_recent_papers()
    
    # Example 3: Show how to get all papers
    example_get_all_papers()
    
    print("\n✅ Examples completed!")
    print("\n💡 Key Benefits of Year-by-Year Approach:")
    print("   - Better progress tracking")
    print("   - Resumable if interrupted")
    print("   - Organized by publication year")
    print("   - Efficient API usage")
    print("   - Can process specific year ranges")