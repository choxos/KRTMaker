from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from .builder import BuildOptions, build_from_xml_path
from .validation import validate_s3_access


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="krt-maker",
        description="Build Key Resources Tables (KRT) from bioRxiv JATS XML",
    )

    # Input options
    input_group = p.add_mutually_exclusive_group(required=True)
    input_group.add_argument("xml", nargs="?", help="Path to JATS XML file")
    input_group.add_argument(
        "--batch-s3",
        action="store_true",
        help="Download and process articles from bioRxiv S3",
    )

    p.add_argument("-o", "--out", help="Output JSON path; default prints to stdout")
    p.add_argument(
        "--out-dir", dest="out_dir", help="Output directory for batch processing"
    )

    # Batch processing options
    p.add_argument(
        "--max-articles",
        dest="max_articles",
        type=int,
        default=10,
        help="Max articles to process in batch mode (default: 10)",
    )
    p.add_argument(
        "--s3-prefix",
        dest="s3_prefix",
        default="Current_Content/",
        help="S3 prefix for batch processing (default: Current_Content/)",
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--regex", action="store_true", help="Use regex/heuristics extractor"
    )
    mode.add_argument("--llm", action="store_true", help="Use LLM extractor")

    # LLM options
    p.add_argument(
        "--provider", help="LLM provider (openai, openai_compatible, anthropic, gemini)"
    )
    p.add_argument("--model", help="LLM model name")
    p.add_argument(
        "--base-url",
        dest="base_url",
        help="Base URL for OpenAI-compatible (e.g., Ollama http://localhost:11434/v1, DeepSeek, Grok)",
    )
    p.add_argument(
        "--api-key", dest="api_key", help="API key for the selected provider"
    )
    p.add_argument("--extra", dest="extra", help="Extra instructions for the LLM")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_arg_parser().parse_args(argv)

    mode = "llm" if args.llm else "regex"
    options = BuildOptions(
        mode=mode,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        extra_instructions=args.extra,
    )

    if args.batch_s3:
        # Validate S3 access before proceeding
        s3_ok, s3_msg = validate_s3_access()
        if not s3_ok:
            print(f"Error: {s3_msg}")
            print("Batch processing requires AWS credentials for bioRxiv S3 access.")
            return 1

        # Batch processing from S3
        from .batch_processor import process_biorxiv_batch

        print(f"Processing up to {args.max_articles} articles from bioRxiv S3...")
        try:
            results = process_biorxiv_batch(
                prefix=args.s3_prefix,
                max_articles=args.max_articles,
                options=options,
                output_dir=args.out_dir or "krt_outputs",
            )
        except Exception as e:
            print(f"Error during batch processing: {e}")
            return 1

        # Create summary
        summary = {
            "total_articles": len(results),
            "mode": mode,
            "s3_prefix": args.s3_prefix,
            "articles": [
                {
                    "title": r.get("title", "Unknown"),
                    "source": r.get("source", ""),
                    "resources_found": len(r.get("rows", [])),
                }
                for r in results
            ],
        }

        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        else:
            print(json.dumps(summary, indent=2, ensure_ascii=False))

    else:
        # Single file processing
        if not args.xml:
            print("Error: XML file path required for single file processing")
            return 1

        try:
            result = build_from_xml_path(args.xml, options)
            out_str = json.dumps(result, indent=2, ensure_ascii=False)
            if args.out:
                os.makedirs(
                    os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True
                )
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(out_str)
            else:
                print(out_str)
        except Exception as e:
            print(f"Error processing XML file: {e}")
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
