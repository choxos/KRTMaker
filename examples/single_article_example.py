#!/usr/bin/env python3
"""
Example: Process a single article with different extraction methods
"""

import json
import os
from krt_maker.builder import BuildOptions, build_from_xml_path


def demo_single_article(xml_path: str):
    """Demo processing single article with different methods."""

    if not os.path.exists(xml_path):
        print(f"XML file not found: {xml_path}")
        return

    print(f"Processing: {xml_path}")

    # Method 1: Regex extraction
    print("\n=== Regex Extraction ===")
    regex_options = BuildOptions(mode="regex")
    regex_result = build_from_xml_path(xml_path, regex_options)
    print(f"Found {len(regex_result['rows'])} resources with regex")

    # Method 2: LLM extraction (if available)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print("\n=== LLM Extraction (OpenAI) ===")
        llm_options = BuildOptions(
            mode="llm", provider="openai", model="gpt-4o-mini", api_key=openai_key
        )
        llm_result = build_from_xml_path(xml_path, llm_options)
        print(f"Found {len(llm_result['rows'])} resources with LLM")

        # Compare results
        print("\n=== Comparison ===")
        print(
            "Regex types found:",
            set(row["RESOURCE TYPE"] for row in regex_result["rows"]),
        )
        print(
            "LLM types found:", set(row["RESOURCE TYPE"] for row in llm_result["rows"])
        )

    # Save results
    with open("example_regex_output.json", "w") as f:
        json.dump(regex_result, f, indent=2)
    print(f"\nSaved regex results to: example_regex_output.json")


if __name__ == "__main__":
    # You can provide a path to your XML file
    xml_file = input("Enter path to JATS XML file: ").strip()
    if xml_file:
        demo_single_article(xml_file)
    else:
        print("No XML file provided")
