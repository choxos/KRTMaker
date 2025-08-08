#!/usr/bin/env python3
"""
Example: Explore bioRxiv S3 bucket contents
"""

from krt_maker.s3_downloader import list_objects


def explore_biorxiv_bucket():
    """Explore what's available in the bioRxiv S3 bucket."""

    print("=== Exploring bioRxiv S3 Bucket ===")
    print("Note: This requires AWS credentials and may incur small charges")

    # List recent content
    print("\n--- Recent Content (last 20 files) ---")
    recent_files = []
    for obj in list_objects(prefix="Current_Content/", max_keys=20):
        recent_files.append(obj)
        print(f"{obj.key} ({obj.size:,} bytes)")

    # Show monthly folders
    print("\n--- Available Monthly Folders ---")
    folders = set()
    for obj in list_objects(max_keys=100):
        if "/" in obj.key:
            folder = obj.key.split("/")[0]
            folders.add(folder)

    for folder in sorted(folders):
        print(f"- {folder}/")

    # Count .meca files in current content
    print("\n--- Statistics ---")
    meca_count = 0
    total_size = 0

    for obj in list_objects(prefix="Current_Content/", max_keys=1000):
        if obj.key.endswith(".meca"):
            meca_count += 1
            total_size += obj.size

    print(f"Found {meca_count} .meca files in Current_Content/")
    print(f"Total size: {total_size / (1024*1024):.1f} MB")


if __name__ == "__main__":
    try:
        explore_biorxiv_bucket()
    except Exception as e:
        print(f"Error accessing S3: {e}")
        print("Make sure you have AWS credentials configured!")
