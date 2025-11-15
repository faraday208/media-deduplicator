#!/usr/bin/env python3
"""
Interactive Duplicate Image Finder
Terminal application for finding duplicate images
"""

import os
import sys
import json
import hashlib
import readline  # Enable arrow keys in input
from collections import defaultdict
from pathlib import Path
from datetime import datetime


def calculate_file_hash(filepath, algorithm='md5'):
    """Calculate hash of a file"""
    hasher = hashlib.new(algorithm)
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def get_file_info(filepath):
    """Get detailed file information"""
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
    """Find duplicate images in a directory"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    hash_map = defaultdict(list)

    print(f"\nScanning directory: {directory}")
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

    if total_files == 0:
        return hash_map, total_files

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

    duplicates = {h: files for h, files in hash_map.items() if len(files) > 1}

    if not duplicates:
        print("\nNo duplicate images found!")
        print(f"All {total_files} images are unique.")
        return duplicates

    unique_files = len(hash_map)
    duplicate_groups = len(duplicates)
    total_duplicate_files = sum(len(files) - 1 for files in duplicates.values())

    print(f"\nTotal images scanned: {total_files}")
    print(f"Unique images: {unique_files}")
    print(f"Duplicate groups: {duplicate_groups}")
    print(f"Duplicate files (can be removed): {total_duplicate_files}")
    print()

    space_can_free = 0
    for files in duplicates.values():
        file_size = os.path.getsize(files[0])
        space_can_free += file_size * (len(files) - 1)

    print(f"Space that can be freed: {space_can_free / (1024**2):.2f} MB ({space_can_free / (1024**3):.2f} GB)")
    print()

    return duplicates


def save_reports(hash_map, total_files, target_dir, output_dir):
    """Save both text and JSON reports"""
    duplicates = {h: files for h, files in hash_map.items() if len(files) > 1}

    # Create reports directory if it doesn't exist
    reports_dir = os.path.join(output_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # Prepare file paths
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_file = os.path.join(reports_dir, f"duplicate_report_{timestamp}.txt")
    json_file = os.path.join(reports_dir, f"duplicate_report_{timestamp}.json")

    # Save text report
    with open(txt_file, 'w', encoding='utf-8') as f:
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
            f.write(f"Size: {os.path.getsize(files[0]) / (1024**2):.2f} MB\n")
            f.write("Files:\n")
            for filepath in files:
                f.write(f"  {filepath}\n")

    # Save JSON report
    unique_files = len(hash_map)
    duplicate_groups = len(duplicates)
    total_duplicate_files = sum(len(files) - 1 for files in duplicates.values())
    space_can_free_bytes = sum(os.path.getsize(files[0]) * (len(files) - 1)
                               for files in duplicates.values())

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

    for file_hash, files in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
        group = {
            'hash': file_hash,
            'hash_algorithm': 'md5',
            'count': len(files),
            'files': [get_file_info(f) for f in files]
        }
        report['duplicate_groups'].append(group)

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nReports saved:")
    print(f"  Text: {txt_file}")
    print(f"  JSON: {json_file}")


def find_keeper_file(file_list):
    """Find the first existing file in the list to keep"""
    for filepath in file_list:
        if os.path.exists(filepath) and os.path.isfile(filepath):
            return filepath
    return None


def delete_duplicates(duplicates):
    """Delete duplicate files, keeping one from each group"""
    total_groups = len(duplicates)
    total_deleted = 0
    total_kept = 0
    total_space_freed = 0
    total_errors = 0

    print("=" * 80)
    print("DELETING DUPLICATES")
    print("=" * 80)
    print()

    for group_idx, (file_hash, file_list) in enumerate(duplicates.items(), 1):
        print(f"Group {group_idx}/{total_groups}: {len(file_list)} files")

        # Find which file to keep
        keeper = find_keeper_file(file_list)

        if not keeper:
            print(f"  WARNING: No files exist in this group! Skipping...")
            total_errors += 1
            continue

        print(f"  KEEPING: {os.path.basename(keeper)}")
        total_kept += 1

        # Delete the rest
        for filepath in file_list:
            if filepath == keeper:
                continue

            # Check if file exists
            if not os.path.exists(filepath):
                print(f"  SKIP (not found): {os.path.basename(filepath)}")
                continue

            # Get file size before deletion
            try:
                file_size = os.path.getsize(filepath)
                os.remove(filepath)
                print(f"  DELETED: {os.path.basename(filepath)} ({file_size / (1024**2):.2f} MB)")
                total_space_freed += file_size
                total_deleted += 1
            except Exception as e:
                print(f"  ERROR deleting {os.path.basename(filepath)}: {e}")
                total_errors += 1

        print()

    # Summary
    print("=" * 80)
    print("DELETION SUMMARY")
    print("=" * 80)
    print(f"Total groups processed: {total_groups}")
    print(f"Files kept: {total_kept}")
    print(f"Files deleted: {total_deleted}")
    print(f"Errors: {total_errors}")
    print(f"Space freed: {total_space_freed / (1024**2):.2f} MB ({total_space_freed / (1024**3):.2f} GB)")


def main():
    """Main application loop"""
    print("=" * 80)
    print("DUPLICATE IMAGE FINDER")
    print("=" * 80)
    print()

    # Get directory path from user
    directory = input("Enter the directory path to scan: ").strip()

    # Remove quotes if user pasted path with quotes
    directory = directory.strip('"').strip("'")

    # Check if directory exists
    if not os.path.exists(directory):
        print(f"\nError: Directory not found: {directory}")
        sys.exit(1)

    if not os.path.isdir(directory):
        print(f"\nError: Path is not a directory: {directory}")
        sys.exit(1)

    # Find duplicates
    hash_map, total_files = find_duplicate_images(directory)

    # Display results
    duplicates = display_results(hash_map, total_files)

    # Save reports (always, even if no duplicates)
    output_dir = os.path.dirname(os.path.abspath(__file__))
    save_reports(hash_map, total_files, directory, output_dir)

    # Ask user if they want to delete duplicates (only if duplicates exist)
    if duplicates:
        print()
        print("=" * 80)
        response = input("Duplicate dosyaları kaldırayım mı? (e/h): ").strip().lower()

        if response in ['e', 'evet']:
            print()
            confirm = input("UYARI: Dosyalar kalıcı olarak silinecek! Emin misiniz? (e/h): ").strip().lower()
            if confirm in ['e', 'evet']:
                print()
                delete_duplicates(duplicates)
            else:
                print("\nSilme işlemi iptal edildi.")
        else:
            print("\nDuplicate dosyalar silinmedi.")

    print("\nDone!")


if __name__ == "__main__":
    main()
