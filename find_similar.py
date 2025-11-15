#!/usr/bin/env python3
"""
Similar Image Finder - Perceptual Hash Based
Finds visually similar images using perceptual hashing
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

try:
    from PIL import Image
    import imagehash
except ImportError:
    print("Error: Required libraries not found!")
    print("Please install dependencies:")
    print("  pip3 install -r requirements.txt")
    sys.exit(1)


def get_image_hash(filepath, hash_func=imagehash.average_hash):
    """
    Calculate perceptual hash of an image

    Args:
        filepath: Path to image file
        hash_func: Hash function to use (average_hash, phash, dhash)

    Returns:
        ImageHash object or None if error
    """
    try:
        with Image.open(filepath) as img:
            return hash_func(img)
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
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


def find_similar_images(directory, threshold=10, hash_func=imagehash.average_hash):
    """
    Find similar images using perceptual hashing

    Args:
        directory: Directory to scan
        threshold: Maximum Hamming distance for similarity (lower = more similar)
        hash_func: Hash function to use

    Returns:
        Tuple: (image_hashes dict, total_files, similar_groups)
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

    print(f"\nScanning directory: {directory}")
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

        img_hash = get_image_hash(filepath, hash_func)
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


def display_results(similar_groups, total_files):
    """Display similar image findings"""
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)

    if not similar_groups:
        print("\nNo similar images found!")
        print(f"All {total_files} images are unique.")
        return

    total_similar_files = sum(group['count'] for group in similar_groups)
    # Files that can be removed (keep one from each group)
    removable_files = sum(group['count'] - 1 for group in similar_groups)

    print(f"\nTotal images scanned: {total_files}")
    print(f"Similar groups found: {len(similar_groups)}")
    print(f"Total similar files: {total_similar_files}")
    print(f"Files that can be removed: {removable_files}")
    print()

    # Calculate potential space savings
    total_space = 0
    for group in similar_groups:
        # Calculate average file size in group
        sizes = [os.path.getsize(f) for f in group['files'] if os.path.exists(f)]
        if sizes:
            avg_size = sum(sizes) / len(sizes)
            # Space saved = avg_size * (count - 1)
            total_space += avg_size * (len(sizes) - 1)

    print(f"Estimated space that can be freed: {total_space / (1024**2):.2f} MB ({total_space / (1024**3):.2f} GB)")
    print()


def save_reports(similar_groups, total_files, target_dir, threshold, output_dir):
    """Save reports to files"""
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

    print(f"\nReports saved:")
    print(f"  Text: {txt_file}")
    print(f"  JSON: {json_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 find_similar.py <directory_path> [threshold]")
        print("\nArguments:")
        print("  directory_path  : Directory to scan for similar images")
        print("  threshold       : Similarity threshold (0-64, lower = more similar, default: 10)")
        print("\nExample:")
        print('  python3 find_similar.py "/path/to/images"')
        print('  python3 find_similar.py "/path/to/images" 5')
        print("\nThreshold guide:")
        print("  0-5   : Very similar (strict)")
        print("  6-10  : Similar (recommended)")
        print("  11-15 : Somewhat similar")
        print("  16+   : Loosely similar")
        sys.exit(1)

    target_dir = sys.argv[1]

    # Get threshold (default 10)
    threshold = 10
    if len(sys.argv) >= 3:
        try:
            threshold = int(sys.argv[2])
            if threshold < 0 or threshold > 64:
                print("Warning: Threshold should be between 0-64. Using default: 10")
                threshold = 10
        except ValueError:
            print("Warning: Invalid threshold value. Using default: 10")
            threshold = 10

    # Check if directory exists
    if not os.path.exists(target_dir):
        print(f"Error: Directory not found: {target_dir}")
        sys.exit(1)

    if not os.path.isdir(target_dir):
        print(f"Error: Not a directory: {target_dir}")
        sys.exit(1)

    # Find similar images
    image_hashes, total_files, similar_groups = find_similar_images(
        target_dir,
        threshold=threshold,
        hash_func=imagehash.average_hash
    )

    # Display results
    display_results(similar_groups, total_files)

    # Save reports
    output_dir = os.path.dirname(os.path.abspath(__file__))
    save_reports(similar_groups, total_files, target_dir, threshold, output_dir)

    print("\nDone!")


if __name__ == "__main__":
    main()
