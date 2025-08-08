KRT Maker
=========

Generates Key Resources Tables (KRT) in JSON format from bioRxiv articles. Downloads full-texts from bioRxiv's S3 bucket, analyzes the content, and extracts research resources with proper categorization.

## Features

✅ **Complete KRT Compliance**: Exact column names and resource types as specified  
🤖 **Dual Extraction Modes**: AI-powered (LLM) and pattern-based (regex) analysis  
☁️ **Direct bioRxiv Integration**: Downloads from bioRxiv S3 bucket with requester-pays  
🚀 **Batch Processing**: Process multiple articles in parallel  
🔌 **Multiple LLM Providers**: OpenAI, Claude, Gemini, local Llama, DeepSeek, Grok  
✅ **Validation & Error Handling**: Comprehensive input validation and clear error messages  

## Quick Start

### Single Article Processing

```bash
# Process single XML file with regex
python -m krt_maker.cli article.xml --regex -o output.json

# Process with OpenAI GPT-4o-mini
OPENAI_API_KEY=sk-... python -m krt_maker.cli article.xml --llm --provider openai --model gpt-4o-mini -o output.json

# Process with Claude
ANTHROPIC_API_KEY=... python -m krt_maker.cli article.xml --llm --provider anthropic --model claude-3-5-sonnet-latest -o output.json
```

### Batch Processing from bioRxiv S3

```bash
# Process 10 recent articles with regex (requires AWS credentials)
python -m krt_maker.cli --batch-s3 --regex --max-articles 10 --out-dir outputs/

# Process 5 articles with LLM
OPENAI_API_KEY=sk-... python -m krt_maker.cli --batch-s3 --llm --provider openai --max-articles 5 --out-dir llm_outputs/
```

## Installation

```bash
pip install -r krt_maker/requirements.txt
```

For bioRxiv S3 access, configure AWS credentials:
```bash
aws configure
# or set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

## LLM Providers

| Provider | Environment Variable | Example Usage |
|----------|---------------------|---------------|
| OpenAI | `OPENAI_API_KEY` | `--provider openai --model gpt-4o-mini` |
| Claude | `ANTHROPIC_API_KEY` | `--provider anthropic --model claude-3-5-sonnet-latest` |
| Gemini | `GOOGLE_API_KEY` | `--provider gemini --model gemini-1.5-pro` |
| Local Llama | `KRT_MAKER_LLM_*` | `--provider openai_compatible --base-url http://localhost:11434/v1` |
| DeepSeek | `KRT_MAKER_LLM_*` | `--provider openai_compatible --base-url https://api.deepseek.com/v1` |

## Output Format

```json
{
  "title": "Article Title",
  "abstract": "Article abstract...",
  "mode": "regex|llm",
  "source": "path/to/article.xml",
  "rows": [
    {
      "RESOURCE TYPE": "Dataset",
      "RESOURCE NAME": "GSE12345 RNA-seq data",
      "SOURCE": "GEO",
      "IDENTIFIER": "GSE12345",
      "NEW/REUSE": "Reuse",
      "ADDITIONAL INFORMATION": "Gene expression profiles"
    }
  ]
}
```

## KRT Specification Compliance

✅ **Column Names**: RESOURCE TYPE, RESOURCE NAME, SOURCE, IDENTIFIER, NEW/REUSE, ADDITIONAL INFORMATION  
✅ **Resource Types**: Dataset, Software/code, Protocol, Antibody, Bacterial strain, Viral vector, Biological sample, Chemical/peptide/recombinant protein, Critical commercial assay, Experimental model: Cell line, Experimental model: Organism/strain, Oligonucleotide, Recombinant DNA, Other  
✅ **Required Fields**: RESOURCE TYPE, RESOURCE NAME, IDENTIFIER, NEW/REUSE cannot be empty  
✅ **Validation**: Automatic defaults ("Unknown resource", "No identifier exists", "Reuse")  

## Examples

See `krt_maker/examples/` for complete usage examples:
- `single_article_example.py` - Process single articles with different methods
- `batch_example.py` - Batch processing with various configurations  
- `s3_explorer.py` - Explore bioRxiv S3 bucket contents

## CLI Options

```
usage: krt-maker [-h] [-o OUT] [--out-dir OUT_DIR] [--max-articles MAX_ARTICLES] 
                 [--s3-prefix S3_PREFIX] [--regex | --llm] [--provider PROVIDER] 
                 [--model MODEL] [--base-url BASE_URL] [--api-key API_KEY] 
                 [--extra EXTRA] (xml | --batch-s3)

Build Key Resources Tables (KRT) from bioRxiv JATS XML

options:
  xml                      Path to JATS XML file
  --batch-s3              Download and process articles from bioRxiv S3
  -o OUT, --out OUT       Output JSON path; default prints to stdout
  --out-dir OUT_DIR       Output directory for batch processing
  --max-articles N        Max articles to process in batch mode (default: 10)
  --s3-prefix PREFIX      S3 prefix for batch processing (default: Current_Content/)
  --regex                 Use regex/heuristics extractor
  --llm                   Use LLM extractor
  --provider PROVIDER     LLM provider (openai, openai_compatible, anthropic, gemini)
  --model MODEL           LLM model name
  --base-url BASE_URL     Base URL for OpenAI-compatible endpoints
  --api-key API_KEY       API key for the selected provider
  --extra EXTRA           Extra instructions for the LLM
```

