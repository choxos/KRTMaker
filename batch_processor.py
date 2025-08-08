from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .builder import BuildOptions, build_from_xml_path
# Note: S3 functionality removed - using Europe PMC for bioRxiv papers


def process_multiple_xmls(
    xml_paths: List[str],
    options: Optional[BuildOptions] = None,
    output_dir: Optional[str] = None,
    max_workers: int = 4,
) -> List[Dict[str, object]]:
    """Process multiple XML files in parallel."""
    options = options or BuildOptions()
    results: List[Dict[str, object]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_path = {
            executor.submit(build_from_xml_path, xml_path, options): xml_path
            for xml_path in xml_paths
        }

        # Collect results
        for future in as_completed(future_to_path):
            xml_path = future_to_path[future]
            try:
                result = future.result()
                results.append(result)

                # Save individual result if output_dir specified
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    filename = Path(xml_path).stem + "_krt.json"
                    output_path = os.path.join(output_dir, filename)
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)

            except Exception as e:
                print(f"Error processing {xml_path}: {e}")

    return results


def process_biorxiv_batch(
    prefix: str = "Current_Content/",
    max_articles: int = 10,
    options: Optional[BuildOptions] = None,
    output_dir: str = "krt_outputs",
) -> List[Dict[str, object]]:
    """Download and process bioRxiv articles from S3."""
    print(f"Listing bioRxiv articles with prefix: {prefix}")

    # List available files
    article_keys = []
    for obj in list_objects(prefix=prefix):
        if obj.key.endswith(".meca") and len(article_keys) < max_articles:
            article_keys.append(obj.key)

    if not article_keys:
        print("No .meca files found")
        return []

    print(f"Found {len(article_keys)} articles, downloading...")

    # Download files
    temp_dir = "temp_downloads"
    local_paths = download_objects(article_keys, temp_dir)

    # Extract XML files from .meca archives (they're zip files)
    import zipfile

    xml_paths = []

    for meca_path in local_paths:
        try:
            with zipfile.ZipFile(meca_path, "r") as zip_ref:
                # Find the XML file in the content folder
                for file_info in zip_ref.filelist:
                    if (
                        file_info.filename.endswith(".xml")
                        and "content/" in file_info.filename
                    ):
                        xml_filename = os.path.basename(file_info.filename)
                        extract_path = os.path.join(temp_dir, xml_filename)
                        with zip_ref.open(file_info) as source, open(
                            extract_path, "wb"
                        ) as target:
                            target.write(source.read())
                        xml_paths.append(extract_path)
                        break
        except Exception as e:
            print(f"Error extracting {meca_path}: {e}")

    print(f"Extracted {len(xml_paths)} XML files, processing...")

    # Process XML files
    results = process_multiple_xmls(xml_paths, options, output_dir)

    # Cleanup temp files
    import shutil

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    return results
