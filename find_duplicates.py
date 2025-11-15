#!/usr/bin/env python3
"""
Duplicate Image Finder - Hash Based
Finds exact duplicate images by comparing file hashes
"""

import os
import sys
import json
import hashlib
from collections import defaultdict
from pathlib import Path
from datetime import datetime


def calculate_file_hash(filepath, algorithm='md5'):
    """
    Calculate hash of a file

    Args:
        filepath: Path to the file
        algorithm: Hash algorithm (md5, sha256, etc.)

    Returns:
        Hash string or None if error
    """
    hasher = hashlib.new(algorithm)

    try:
        with open(filepath, 'rb') as f:
            # Read file in chunks to handle large files efficiently
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def get_file_size_mb(filepath):
    """Get file size in MB"""
    return os.path.getsize(filepath) / (1024 * 1024)


def get_file_info(filepath):
    """
    Get detailed file information

    Returns:
        Dictionary with file metadata
    """
    try:
        stat_info = os.stat(filepath)
        return {
            'path': filepath,
            'filename': os.path.basename(filepath),
            'size_bytes': stat_info.st_size,
            'size_mb': stat_info.st_size / (1024 * 1024),
            'modified_time': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            'created_time': datetime.fromtimestamp(stat_info.st_ctime).isoformat()
        }
    except Exception as e:
        return {
            'path': filepath,
            'filename': os.path.basename(filepath),
            'error': str(e)
        }


def find_duplicate_images(directory):
    """
    Find duplicate images in a directory

    Args:
        directory: Path to search for images

    Returns:
        Dictionary of hash -> list of files
    """
    # Supported image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

    # Dictionary to store: hash -> [list of files]
    hash_map = defaultdict(list)

    print(f"Scanning directory: {directory}")
    print("=" * 80)

    # Find all image files
    print("Finding image files...")
    image_files = []

    for root, dirs, files in os.walk(directory):
        for filename in files:
            ext = Path(filename).suffix.lower()
            if ext in image_extensions:
                filepath = os.path.join(root, filename)
                image_files.append(filepath)

    total_files = len(image_files)
    print(f"Found {total_files} image files")
    print()

    # Calculate hash for each file
    print("Calculating file hashes...")
    for idx, filepath in enumerate(image_files, 1):
        if idx % 100 == 0 or idx == total_files:
            print(f"  Progress: {idx}/{total_files} ({idx*100//total_files}%)")

        file_hash = calculate_file_hash(filepath)
        if file_hash:
            hash_map[file_hash].append(filepath)

    return hash_map, total_files


def display_results(hash_map, total_files):
    """Display duplicate findings"""
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)

    # Find duplicates (hash with more than 1 file)
    duplicates = {h: files for h, files in hash_map.items() if len(files) > 1}

    if not duplicates:
        print("\nNo duplicate images found!")
        print(f"All {total_files} images are unique.")
        return

    # Calculate statistics
    unique_files = len(hash_map)
    duplicate_groups = len(duplicates)
    total_duplicate_files = sum(len(files) - 1 for files in duplicates.values())

    print(f"\nTotal images scanned: {total_files}")
    print(f"Unique images: {unique_files}")
    print(f"Duplicate groups: {duplicate_groups}")
    print(f"Duplicate files (can be removed): {total_duplicate_files}")
    print()

    # Calculate space that can be freed
    space_can_free = 0
    for files in duplicates.values():
        # Keep first file, others can be deleted
        file_size = os.path.getsize(files[0])
        space_can_free += file_size * (len(files) - 1)

    print(f"Space that can be freed: {space_can_free / (1024**2):.2f} MB ({space_can_free / (1024**3):.2f} GB)")
    print()
    print("=" * 80)
    print("DUPLICATE GROUPS:")
    print("=" * 80)

    # Display each duplicate group
    for idx, (file_hash, files) in enumerate(sorted(duplicates.items(),
                                                     key=lambda x: len(x[1]),
                                                     reverse=True), 1):
        print(f"\nGroup {idx}: {len(files)} identical files")
        print(f"Hash: {file_hash}")
        print(f"Size: {get_file_size_mb(files[0]):.2f} MB")
        print("Files:")
        for filepath in files:
            print(f"  - {os.path.basename(filepath)}")
            print(f"    {filepath}")

    return duplicates


def save_report(hash_map, total_files, output_file="duplicate_report.txt"):
    """Save detailed report to file"""
    duplicates = {h: files for h, files in hash_map.items() if len(files) > 1}

    if not duplicates:
        return

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("DUPLICATE IMAGES REPORT\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total images scanned: {total_files}\n")
        f.write(f"Unique images: {len(hash_map)}\n")
        f.write(f"Duplicate groups: {len(duplicates)}\n\n")

        for idx, (file_hash, files) in enumerate(sorted(duplicates.items(),
                                                         key=lambda x: len(x[1]),
                                                         reverse=True), 1):
            f.write(f"\nGroup {idx}: {len(files)} identical files\n")
            f.write(f"Hash: {file_hash}\n")
            f.write(f"Size: {get_file_size_mb(files[0]):.2f} MB\n")
            f.write("Files:\n")
            for filepath in files:
                f.write(f"  {filepath}\n")

    print(f"\nDetailed report saved to: {output_file}")


def save_json_report(hash_map, total_files, target_dir, output_file="duplicate_report.json"):
    """Save detailed JSON report with metadata"""
    duplicates = {h: files for h, files in hash_map.items() if len(files) > 1}

    # Calculate statistics
    unique_files = len(hash_map)
    duplicate_groups = len(duplicates)
    total_duplicate_files = sum(len(files) - 1 for files in duplicates.values())

    # Calculate space that can be freed
    space_can_free_bytes = 0
    for files in duplicates.values():
        file_size = os.path.getsize(files[0])
        space_can_free_bytes += file_size * (len(files) - 1)

    # Build JSON structure
    report = {
        'metadata': {
            'scan_date': datetime.now().isoformat(),
            'scanned_directory': target_dir,
            'total_images_scanned': total_files,
            'unique_images': unique_files,
            'duplicate_groups': duplicate_groups,
            'total_duplicate_files': total_duplicate_files,
            'space_can_free_bytes': space_can_free_bytes,
            'space_can_free_mb': space_can_free_bytes / (1024 ** 2),
            'space_can_free_gb': space_can_free_bytes / (1024 ** 3)
        },
        'duplicate_groups': []
    }

    # Add each duplicate group
    for file_hash, files in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
        group = {
            'hash': file_hash,
            'hash_algorithm': 'md5',
            'count': len(files),
            'files': [get_file_info(f) for f in files]
        }
        report['duplicate_groups'].append(group)

    # Save to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"JSON report saved to: {output_file}")


def main():
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python3 find_duplicates.py <directory_path> [output_file]")
        print("\nExample:")
        print('  python3 find_duplicates.py "/path/to/images"')
        print('  python3 find_duplicates.py "/path/to/images" "my_report.txt"')
        sys.exit(1)

    # Get target directory from command line
    target_dir = sys.argv[1]

    # Create reports directory if it doesn't exist
    reports_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # Get output file path (optional, default to reports directory)
    if len(sys.argv) >= 3:
        base_name = sys.argv[2]
        # Remove extension if provided
        base_name = os.path.splitext(base_name)[0]
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.join(reports_dir, f"duplicate_report_{timestamp}")

    report_txt_path = base_name + ".txt"
    report_json_path = base_name + ".json"

    # Check if directory exists
    if not os.path.exists(target_dir):
        print(f"Error: Directory not found: {target_dir}")
        sys.exit(1)

    if not os.path.isdir(target_dir):
        print(f"Error: Not a directory: {target_dir}")
        sys.exit(1)

    # Find duplicates
    hash_map, total_files = find_duplicate_images(target_dir)

    # Display results
    display_results(hash_map, total_files)

    # Save reports (both text and JSON)
    save_report(hash_map, total_files, report_txt_path)
    save_json_report(hash_map, total_files, target_dir, report_json_path)


if __name__ == "__main__":
    main()
