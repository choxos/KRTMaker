# 📊 KRT Maker Database Population Guide

This guide explains how to set up and populate the KRT Maker database with the complete bioRxiv article collection from Europe PMC.

## 🎯 Overview

The KRT Maker can access **19,405 bioRxiv papers** (2020-2025) through the Europe PMC API using an intelligent year-by-year search strategy. This guide covers:

- Database setup and migration
- Article database population
- Performance optimization
- Maintenance and updates

---

## 📋 Prerequisites

### 1. Django Environment Setup
```bash
# Ensure you're in the project directory
cd /path/to/KRTMaker

# Activate virtual environment
source venv/bin/activate  # or your specific venv path

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Configuration

#### Option A: SQLite (Recommended for Development)
```python
# krt_web/settings.py - Already configured by default
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

#### Option B: PostgreSQL (Recommended for Production)
```python
# krt_web/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'krt_production',
        'USER': 'krt_user',
        'PASSWORD': 'your_secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 3. Run Database Migrations
```bash
# Create database tables
python manage.py migrate

# Create superuser (optional, for admin access)
python manage.py createsuperuser
```

---

## 🚀 Article Database Population

### Quick Start: Populate All Articles
```bash
# Populate complete bioRxiv database (19,405 articles)
python manage.py populate_articles

# Expected output:
# 📊 Getting bioRxiv paper statistics...
# 📅 2020: 2,897 papers
# 📅 2021: 2,765 papers  
# 📅 2022: 3,848 papers
# 📅 2023: 4,063 papers
# 📅 2025: 2,298 papers (latest year)
# 📅 2024: 3,534 papers
# 🎯 Total papers available: 19,405
# ...
# 🎉 DATABASE POPULATION COMPLETE
```

### Performance Specifications
- **Time**: ~4-5 minutes for complete database
- **Data Size**: ~40MB of metadata
- **API Calls**: ~20 total (very efficient!)
- **Rate Limiting**: 200ms delays (respectful to Europe PMC)

---

## 🛠️ Command Options

### 1. Statistics Only (Fast Preview)
```bash
# Get paper counts without downloading
python manage.py populate_articles --stats-only

# Output shows available papers by year
```

### 2. Specific Year Population
```bash
# Populate papers from specific years
python manage.py populate_articles --start-year 2023 --end-year 2025

# Popular year choices:
python manage.py populate_articles --start-year 2023 --end-year 2023  # 4,063 papers
python manage.py populate_articles --start-year 2025 --end-year 2025  # 2,298 papers (latest year)
# python manage.py populate_articles --start-year 2024 --end-year 2024  # 3,534 papers
```

### 3. Update Mode (Add New Articles Only)
```bash
# Only add new papers, skip existing
python manage.py populate_articles --update-only

# Perfect for periodic updates
```

### 4. Test Mode (Limited Papers)
```bash
# Limit papers per year for testing
python manage.py populate_articles --limit-per-year 100

# Test with small dataset first
python manage.py populate_articles --limit-per-year 10 --start-year 2025 --end-year 2025
```

### 5. Advanced Options
```bash
# Dry run (see what would be done)
python manage.py populate_articles --dry-run

# Force refresh (overwrite existing data)
python manage.py populate_articles --force-refresh

# Combine options
python manage.py populate_articles --start-year 2024 --end-year 2026 --update-only
```

---

## 📊 Database Management Interface

### Web Interface Access
1. **Start Django server**:
   ```bash
   python manage.py runserver 127.0.0.1:8015
   ```

2. **Visit Database Management**:
   - URL: `http://127.0.0.1:8015/database/`
   - Features:
     - Population progress tracking
     - Article statistics by year/journal
     - One-click population buttons
     - Recent articles overview

3. **Admin Interface** (Optional):
   - URL: `http://127.0.0.1:8015/admin/`
   - Direct database management
   - Advanced filtering and search
   - Bulk operations

---

## 📈 Database Statistics

### Expected Article Distribution
```
Year        Papers    Percentage
────────────────────────────────
2020        2,897        14.9%
2021        2,765        14.2%
2022        3,848        19.8%
2023        4,063        20.9% (Peak Year!)
2025        2,298        11.8%        (latest)
2024        3,534        18.2%
────────────────────────────────
TOTAL      19,405       100.0%
```

### Article Metadata Included
- **DOI**: Unique identifier for each paper
- **Title**: Full article title
- **Authors**: Complete author list (JSON format)
- **Abstract**: Full abstract text
- **Publication Date**: Date of bioRxiv publication
- **Journal**: Source journal information
- **Keywords**: Subject keywords (where available)
- **PMCID/PMID**: Cross-reference identifiers

---

## 🔄 Periodic Updates

### Recommended Update Schedule
```bash
# Weekly updates (add new papers)
python manage.py populate_articles --update-only

# Monthly full refresh (overwrite existing)
python manage.py populate_articles --force-refresh --start-year 2025 --end-year 2025
```

### Automated Updates (Optional)
```bash
# Add to cron job for automatic updates
# Run every Sunday at 2 AM
0 2 * * 0 cd /path/to/KRTMaker && python manage.py populate_articles --update-only
```

---

## 🚨 Troubleshooting

### Common Issues

#### 1. Memory Issues
```bash
# If running out of memory, use smaller batches
python manage.py populate_articles --limit-per-year 500 --start-year 2020 --end-year 2020
# Then continue with other years
python manage.py populate_articles --limit-per-year 500 --start-year 2021 --end-year 2021
```

#### 2. Network Timeouts
```bash
# The command handles network issues automatically with retries
# If it fails, restart from where it left off:
python manage.py populate_articles --update-only
```

#### 3. Database Corruption
```bash
# Reset database if needed
rm db.sqlite3
python manage.py migrate
python manage.py populate_articles
```

#### 4. Checking Population Status
```bash
# View current database status
python manage.py shell
>>> from web.models import Article
>>> Article.objects.count()
19405  # Expected for complete population
```

### Performance Optimization

#### For Large Deployments
1. **Use PostgreSQL** instead of SQLite
2. **Add database indexes**:
   ```sql
   CREATE INDEX idx_article_doi ON web_article(doi);
   CREATE INDEX idx_article_publication_date ON web_article(publication_date);
   CREATE INDEX idx_article_journal ON web_article(journal);
   ```
3. **Configure connection pooling**
4. **Use background task queue** (Celery) for population

---

## 🎯 Post-Population Usage

### After successful population, you can:

1. **Browse Articles**: Visit `/articles/` to see all papers
2. **Search by DOI**: Direct access via `/articles/10.1101/...`
3. **Generate KRTs**: Use any DOI in the KRT maker
4. **Analyze Trends**: View year/journal distributions
5. **Export Data**: Use admin interface for bulk exports

### Example Workflows

#### 1. Find Papers by Topic
```python
# Django shell
python manage.py shell

>>> from web.models import Article
>>> cancer_papers = Article.objects.filter(title__icontains='cancer')
>>> print(f"Found {cancer_papers.count()} cancer papers")
```

#### 2. Get Recent Papers
```python
>>> recent = Article.objects.filter(publication_date__year=2025).order_by('-publication_date')[:10]
>>> for paper in recent:
...     print(f"{paper.title[:60]}... - {paper.publication_date}")
```

#### 3. Generate KRT for Any Paper
1. Copy DOI from articles page
2. Go to `/maker/`
3. Select "bioRxiv URL or DOI"
4. Paste DOI and process

---

## ✅ Verification Checklist

After population, verify:

- [ ] Database contains ~19,405 articles
- [ ] Articles span years 2020-2025
- [ ] DOIs are properly formatted
- [ ] Publication dates are present
- [ ] Author information is populated
- [ ] Web interface shows statistics
- [ ] Article search works
- [ ] KRT generation works with DOIs

### Quick Verification Commands
```bash
# Check total count
python manage.py shell -c "from web.models import Article; print(f'Total articles: {Article.objects.count()}')"

# Check year distribution
python manage.py shell -c "
from web.models import Article
from django.db.models import Count
years = Article.objects.values('publication_date__year').annotate(count=Count('id')).order_by('publication_date__year')
for y in years:
    print(f'{y[\"publication_date__year\"]}: {y[\"count\"]} papers')
"
```

---

## 🌟 Success!

Once populated, your KRT Maker will have:

✅ **Complete bioRxiv Database**: All 19,405 papers accessible  
✅ **Fast DOI Lookup**: Instant access to any paper  
✅ **Rich Metadata**: Authors, abstracts, dates, journals  
✅ **Year-by-Year Organization**: Easy temporal analysis  
✅ **Web Management Interface**: User-friendly database control  
✅ **Admin Tools**: Advanced database management  
✅ **Update Capability**: Keep database current  

**Your KRT Maker is now ready for production use with the complete bioRxiv dataset!** 🚀

---

## 📞 Support

If you encounter issues:

1. Check the command output for specific error messages
2. Use `--dry-run` to test commands safely
3. Start with `--stats-only` to verify API connectivity
4. Use `--limit-per-year 10` for testing
5. Check Django logs for detailed error information

For technical support, refer to the main README.md or create an issue in the project repository.