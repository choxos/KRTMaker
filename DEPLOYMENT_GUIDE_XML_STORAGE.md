# 🗂️ KRT Maker XML Storage System Guide

This guide explains the new local XML storage system that enables the KRT Maker to work with downloaded bioRxiv XML files instead of relying on Europe PMC API calls during KRT extraction.

## 🎯 Overview

The KRT Maker now uses a **local XML storage system** that provides:

- **Fast KRT extraction** - No API calls during processing
- **Reliable operation** - No dependency on Europe PMC uptime
- **Complete dataset** - Download ALL bioRxiv papers (2020-2025)
- **Smart autocomplete** - Real-time DOI suggestions from local database
- **Incremental updates** - Daily/weekly new paper downloads

---

## 🏗️ Architecture

### Two-Stage Process

1. **Article Metadata** (`populate_articles`) - Fast metadata indexing
2. **XML File Storage** (`download_xml_files`) - Full text download for KRT extraction

### File Organization
```
xml_files/
├── 2020/
│   ├── 2020.01.01.123456.xml
│   ├── 2020.01.02.234567.xml
│   └── ...
├── 2021/
├── 2022/
├── 2023/
├── 2024/
└── 2025/
```

### Database Models

- **`XMLFile`** - Tracks downloaded XML files with metadata and integrity verification
- **`Article`** - Links to XMLFile for complete paper information
- **File integrity** - SHA256 hash verification for all downloaded files

---

## 📋 Prerequisites

### 1. Django Environment Setup
```bash
# Ensure you're in the project directory
cd /path/to/KRTMaker

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Migration
```bash
# Apply the new XMLFile model migrations
python manage.py migrate

# This creates the XMLFile table and updates Article model
```

### 3. Storage Space Requirements

| Dataset | Papers | Storage | Time Estimate |
|---------|--------|---------|---------------|
| 2025 only | ~2,300  | ~80 MB  | 30 min    |
| 2024 only | ~15,000 | ~500 MB | 2-3 hours |
| 2020-2025 | ~350,000 | ~12 GB | 24-48 hours |
| Full future | ~500,000+ | ~20 GB | Ongoing |

---

## 🚀 Initial Setup

### Step 1: Test with Small Dataset

```bash
# Test with 10 papers from 2025 (recommended first step - current year)
python manage.py download_xml_files --start-year 2025 --end-year 2025 --limit-per-year 10

# Alternative: Test with 2024 papers
# python manage.py download_xml_files --start-year 2024 --end-year 2024 --limit-per-year 10

# Verify the download worked
python manage.py download_xml_files --stats-only --start-year 2025 --end-year 2025
```

### Step 2: Download Recent Papers (2025)

```bash
# Download all 2025 papers (good for testing the complete system - current year)
python manage.py download_xml_files --start-year 2025 --end-year 2025

# Or download 2024 papers (larger dataset for comprehensive testing)
# python manage.py download_xml_files --start-year 2024 --end-year 2024

# Expected: ~15,000 papers, ~500 MB, 2-3 hours
```

### Step 3: Full Database Population (Optional)

```bash
# Download ALL bioRxiv papers (2020-2025)
# WARNING: This is a large download (12+ GB, 24-48 hours)
python manage.py download_xml_files --start-year 2020 --end-year 2025

# Consider running in screen/tmux for long downloads:
screen -S xml_download
python manage.py download_xml_files --start-year 2020 --end-year 2025
# Ctrl+A, D to detach
```

---

## 🔧 Management Commands

### `download_xml_files` - Primary Download Command

#### Syntax
```bash
python manage.py download_xml_files [options]
```

#### Key Options

| Option | Description | Example |
|--------|-------------|---------|
| `--start-year` | Starting year (default: 2020) | `--start-year 2023` |
| `--end-year` | Ending year (default: current year) | `--end-year 2024` |
| `--limit-per-year` | Limit papers per year (testing) | `--limit-per-year 100` |
| `--dry-run` | Show what would be downloaded | `--dry-run` |
| `--update-only` | Only download missing papers | `--update-only` |
| `--force-redownload` | Re-download existing files | `--force-redownload` |
| `--verify-files` | Check file integrity | `--verify-files` |
| `--stats-only` | Show statistics only | `--stats-only` |

#### Common Use Cases

##### Testing and Development
```bash
# Dry run to see what would be downloaded
python manage.py download_xml_files --start-year 2024 --end-year 2024 --limit-per-year 50 --dry-run

# Small test download
python manage.py download_xml_files --start-year 2024 --end-year 2024 --limit-per-year 100

# Check what's available without downloading
python manage.py download_xml_files --stats-only --start-year 2020 --end-year 2025
```

##### Production Setup
```bash
# Download recent papers (last 2 years)
python manage.py download_xml_files --start-year 2023 --end-year 2025

# Full dataset download (use screen/tmux)
python manage.py download_xml_files --start-year 2020 --end-year 2025

# Verify file integrity
python manage.py download_xml_files --verify-files --start-year 2024 --end-year 2024
```

##### Maintenance
```bash
# Update with only new papers
python manage.py download_xml_files --start-year 2024 --end-year 2025 --update-only

# Re-download corrupted files
python manage.py download_xml_files --verify-files --force-redownload --start-year 2024 --end-year 2024
```

### `update_xml_files` - Incremental Updates

#### Syntax
```bash
python manage.py update_xml_files [options]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--days-back` | Days to look back from latest | 7 |
| `--force-update-recent` | Force update last 30 days | False |
| `--dry-run` | Show what would be updated | False |
| `--limit` | Limit number of papers | None |

#### Usage Examples

```bash
# Daily update (recommended for cron jobs)
python manage.py update_xml_files

# Weekly update with more coverage
python manage.py update_xml_files --days-back 14

# Force update recent papers
python manage.py update_xml_files --force-update-recent

# Dry run to see what would be updated
python manage.py update_xml_files --dry-run
```

---

## 🌐 Web Interface

### DOI Autocomplete

The web interface now provides:

- **Real-time suggestions** - 10 random papers from local database
- **Smart search** - Type to filter by DOI or title
- **Instant availability** - Automatic checking without button clicks
- **Paper metadata** - Title, authors, date, file size displayed

### Database Management Page

Access at `/database/` for:

- **Statistics overview** - Total papers, storage usage, coverage by year
- **Population controls** - Web interface for running download commands
- **Recent downloads** - View latest additions
- **Health monitoring** - File integrity and availability status

---

## 📊 Monitoring and Maintenance

### Health Checks

```bash
# Check file integrity
python manage.py download_xml_files --verify-files --start-year 2024 --end-year 2024

# Database statistics
python manage.py download_xml_files --stats-only --start-year 2020 --end-year 2025

# Django admin interface
python manage.py runserver
# Visit http://localhost:8000/admin/web/xmlfile/
```

### Automated Updates

#### Daily Cron Job
```bash
# Add to crontab for daily updates
0 2 * * * cd /path/to/KRTMaker && source venv/bin/activate && python manage.py update_xml_files >> /var/log/krt_updates.log 2>&1
```

#### Weekly Full Check
```bash
# Weekly integrity verification
0 3 * * 0 cd /path/to/KRTMaker && source venv/bin/activate && python manage.py download_xml_files --verify-files --start-year 2024 --end-year 2025 >> /var/log/krt_verify.log 2>&1
```

### Storage Management

#### Disk Usage
```bash
# Check XML storage size
du -sh xml_files/

# Count files by year
find xml_files/ -name "*.xml" | cut -d/ -f2 | sort | uniq -c
```

#### Cleanup (if needed)
```bash
# Remove corrupted files (use with caution)
python manage.py shell
>>> from web.models import XMLFile
>>> corrupted = XMLFile.objects.filter(is_available=False)
>>> for xml_file in corrupted:
...     if os.path.exists(xml_file.full_file_path):
...         os.unlink(xml_file.full_file_path)
...     xml_file.delete()
```

---

## 🚨 Troubleshooting

### Common Issues

#### 1. Download Failures
```bash
# Check network connectivity
curl -I "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=test"

# Verify API access
python manage.py download_xml_files --start-year 2024 --end-year 2024 --limit-per-year 1 --dry-run
```

#### 2. Storage Issues
```bash
# Check disk space
df -h

# Verify XML directory permissions
ls -la xml_files/
```

#### 3. File Integrity Problems
```bash
# Re-download specific year
python manage.py download_xml_files --start-year 2024 --end-year 2024 --force-redownload

# Verify and fix
python manage.py download_xml_files --verify-files --force-redownload
```

#### 4. Database Inconsistencies
```bash
# Reset XMLFile table (CAUTION: removes all download records)
python manage.py shell
>>> from web.models import XMLFile
>>> XMLFile.objects.all().delete()

# Re-populate from existing files
python manage.py download_xml_files --start-year 2020 --end-year 2025 --update-only
```

---

## 📈 Performance Optimization

### Download Speed
- **Parallel processing** - Command uses efficient batch processing
- **Rate limiting** - Respectful 0.1s delay between downloads
- **Resume capability** - `--update-only` skips existing files
- **Verification** - SHA256 hashing prevents corruption

### Storage Optimization
- **Organized structure** - Year-based directory organization
- **Integrity checking** - Automatic hash verification
- **Compression** - XML files are stored as-is (already compact)
- **Database indexing** - Optimized queries on DOI, date, availability

### KRT Extraction Speed
- **Local access** - No API calls during extraction
- **Smart caching** - Files remain available after download
- **Section filtering** - Only methods/results/appendix sent to LLMs
- **Metadata optimization** - Fast DOI lookups and autocomplete

---

## 🎉 Success Metrics

After successful setup, you should have:

- ✅ **Local XML storage** - Papers accessible without API calls
- ✅ **Smart autocomplete** - Real-time DOI suggestions
- ✅ **Fast KRT extraction** - Local file processing
- ✅ **Automatic updates** - Daily incremental downloads
- ✅ **File integrity** - Hash verification and monitoring
- ✅ **Web management** - Dashboard for monitoring and control

### Verification Checklist

```bash
# 1. Check database status
python manage.py download_xml_files --stats-only

# 2. Test web interface
python manage.py runserver 127.0.0.1:8015
# Visit http://127.0.0.1:8015/maker/ and test autocomplete

# 3. Test KRT extraction
# Visit http://127.0.0.1:8015/maker/ and process a paper

# 4. Verify file integrity
python manage.py download_xml_files --verify-files --start-year 2024 --end-year 2024

# 5. Check storage usage
du -sh xml_files/
```

---

## 📞 Support

For issues with the XML storage system:

1. **Check logs** - Review command output for error messages
2. **Verify connectivity** - Ensure Europe PMC API access
3. **Storage space** - Confirm adequate disk space
4. **File permissions** - Check xml_files/ directory permissions
5. **Database integrity** - Use Django admin to inspect XMLFile records

The XML storage system provides a robust foundation for reliable, fast KRT extraction without external API dependencies during processing.