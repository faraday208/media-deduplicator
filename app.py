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

try:
    from PIL import Image
    import imagehash
    SIMILAR_AVAILABLE = True
except ImportError:
    SIMILAR_AVAILABLE = False


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


def get_image_hash(filepath, hash_func=None):
    """Calculate perceptual hash of an image"""
    if hash_func is None:
        hash_func = imagehash.average_hash

    try:
        with Image.open(filepath) as img:
            return hash_func(img)
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None


def find_similar_images(directory, threshold=10):
    """Find similar images using perceptual hashing"""
    if not SIMILAR_AVAILABLE:
        print("Error: Pillow and imagehash are required for similar image detection")
        print("Please run: source venv/bin/activate && pip install -r requirements.txt")
        return {}, 0, []

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

    print(f"\nScanning for similar images...")
    print(f"Similarity threshold: {threshold} (Hamming distance)")
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
        return {}, 0, []

    # Calculate perceptual hash for each image
    print("Calculating perceptual hashes...")
    image_hashes = {}

    for idx, filepath in enumerate(image_files, 1):
        if idx % 100 == 0 or idx == total_files:
            print(f"  Progress: {idx}/{total_files} ({idx*100//total_files}%)")

        img_hash = get_image_hash(filepath, imagehash.average_hash)
        if img_hash is not None:
            image_hashes[filepath] = img_hash

    print(f"\nSuccessfully processed {len(image_hashes)} images")
    print()

    # Find similar images by comparing hashes
    print("Finding similar images...")
    similar_groups = []
    processed = set()

    file_list = list(image_hashes.keys())

    for i, file1 in enumerate(file_list):
        if file1 in processed:
            continue

        hash1 = image_hashes[file1]
        group = [file1]

        # Compare with remaining images
        for file2 in file_list[i+1:]:
            if file2 in processed:
                continue

            hash2 = image_hashes[file2]
            distance = hash1 - hash2  # Hamming distance

            if distance <= threshold:
                group.append(file2)
                processed.add(file2)

        # If group has more than 1 image, it's a similar group
        if len(group) > 1:
            similar_groups.append({
                'files': group,
                'reference_hash': str(hash1),
                'count': len(group)
            })
            processed.add(file1)

    return image_hashes, total_files, similar_groups


def display_similar_results(similar_groups, total_files):
    """Display similar image findings"""
    print()
    print("=" * 80)
    print("SIMILAR IMAGES RESULTS")
    print("=" * 80)

    if not similar_groups:
        print("\nNo similar images found!")
        print(f"All {total_files} images are visually unique.")
        return

    total_similar_files = sum(group['count'] for group in similar_groups)
    removable_files = sum(group['count'] - 1 for group in similar_groups)

    print(f"\nTotal images scanned: {total_files}")
    print(f"Similar groups found: {len(similar_groups)}")
    print(f"Total similar files: {total_similar_files}")
    print(f"Files that can be removed: {removable_files}")
    print()

    # Calculate potential space savings
    total_space = 0
    for group in similar_groups:
        sizes = [os.path.getsize(f) for f in group['files'] if os.path.exists(f)]
        if sizes:
            avg_size = sum(sizes) / len(sizes)
            total_space += avg_size * (len(sizes) - 1)

    print(f"Estimated space that can be freed: {total_space / (1024**2):.2f} MB ({total_space / (1024**3):.2f} GB)")
    print()


def save_similar_reports(similar_groups, total_files, target_dir, threshold, output_dir):
    """Save similar images reports"""
    # Create reports directory
    reports_dir = os.path.join(output_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_file = os.path.join(reports_dir, f"similar_report_{timestamp}.txt")
    json_file = os.path.join(reports_dir, f"similar_report_{timestamp}.json")

    # Save text report
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("SIMILAR IMAGES REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Scan date: {datetime.now().isoformat()}\n")
        f.write(f"Scanned directory: {target_dir}\n")
        f.write(f"Similarity threshold: {threshold}\n")
        f.write(f"Total images scanned: {total_files}\n")
        f.write(f"Similar groups found: {len(similar_groups)}\n\n")

        if similar_groups:
            for idx, group in enumerate(sorted(similar_groups, key=lambda x: x['count'], reverse=True), 1):
                f.write(f"\nGroup {idx}: {group['count']} similar images\n")
                f.write(f"Reference hash: {group['reference_hash']}\n")
                f.write("Files:\n")
                for filepath in group['files']:
                    size_mb = os.path.getsize(filepath) / (1024**2) if os.path.exists(filepath) else 0
                    f.write(f"  {filepath} ({size_mb:.2f} MB)\n")

    # Save JSON report
    total_similar_files = sum(group['count'] for group in similar_groups)
    removable_files = sum(group['count'] - 1 for group in similar_groups)

    total_space = 0
    for group in similar_groups:
        sizes = [os.path.getsize(f) for f in group['files'] if os.path.exists(f)]
        if sizes:
            avg_size = sum(sizes) / len(sizes)
            total_space += avg_size * (len(sizes) - 1)

    report = {
        'metadata': {
            'scan_date': datetime.now().isoformat(),
            'scanned_directory': target_dir,
            'similarity_threshold': threshold,
            'hash_algorithm': 'average_hash',
            'total_images_scanned': total_files,
            'similar_groups_found': len(similar_groups),
            'total_similar_files': total_similar_files,
            'removable_files': removable_files,
            'estimated_space_bytes': int(total_space),
            'estimated_space_mb': total_space / (1024**2),
            'estimated_space_gb': total_space / (1024**3)
        },
        'similar_groups': []
    }

    for group in sorted(similar_groups, key=lambda x: x['count'], reverse=True):
        group_data = {
            'reference_hash': group['reference_hash'],
            'similarity_count': group['count'],
            'files': [get_file_info(f) for f in group['files']]
        }
        report['similar_groups'].append(group_data)

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nSimilar images reports saved:")
    print(f"  Text: {txt_file}")
    print(f"  JSON: {json_file}")


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

    # Similar image detection
    print()
    print("=" * 80)
    print()

    if not SIMILAR_AVAILABLE:
        print("Similar image detection is not available.")
        print("To enable it, install dependencies:")
        print("  source venv/bin/activate")
        print("  pip install -r requirements.txt")
        print("\nDone!")
        return

    similar_response = input("Benzer resimlere bakalım mı? (e/h): ").strip().lower()

    if similar_response in ['e', 'evet']:
        print()
        print("Benzerlik threshold'u belirleyin:")
        print("  0-5   : Çok benzer (strict)")
        print("  6-10  : Benzer (önerilen)")
        print("  11-15 : Biraz benzer")
        print("  16+   : Gevşek benzerlik")
        print()

        threshold = 10  # Default
        threshold_input = input("Threshold (0-64, varsayılan 10): ").strip()

        if threshold_input:
            try:
                threshold = int(threshold_input)
                if threshold < 0 or threshold > 64:
                    print("Uyarı: Threshold 0-64 arası olmalı. Varsayılan 10 kullanılıyor.")
                    threshold = 10
            except ValueError:
                print("Uyarı: Geçersiz değer. Varsayılan 10 kullanılıyor.")
                threshold = 10

        # Find similar images
        image_hashes, total_similar_files, similar_groups = find_similar_images(directory, threshold)

        # Display results
        display_similar_results(similar_groups, total_similar_files)

        # Save reports
        if similar_groups or total_similar_files > 0:
            save_similar_reports(similar_groups, total_similar_files, directory, threshold, output_dir)

        # Information message (no deletion for similar images yet)
        if similar_groups:
            print()
            print("=" * 80)
            print("NOT: Benzer resimleri otomatik silme henüz desteklenmiyor.")
            print("Raporları kontrol edip manuel inceleme yapmanız önerilir.")
            print("=" * 80)

    print("\nDone!")


if __name__ == "__main__":
    main()
