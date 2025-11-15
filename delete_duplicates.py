#!/usr/bin/env python3
"""
Delete Duplicate Images
Safely deletes duplicate images, keeping one copy from each group
"""

import os
import sys
import json
from datetime import datetime


def parse_json_report(report_path):
    """
    Parse the JSON report file to extract duplicate groups

    Returns:
        Tuple: (metadata dict, list of duplicate groups)
        Each group is a list of file info dicts
    """
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metadata = data.get('metadata', {})
        duplicate_groups = data.get('duplicate_groups', [])

        # Extract file paths from each group
        groups = []
        for group in duplicate_groups:
            file_list = [file_info['path'] for file_info in group.get('files', [])]
            groups.append(file_list)

        return metadata, groups

    except Exception as e:
        print(f"Error reading JSON report file: {e}")
        return {}, []


def find_keeper_file(file_list):
    """
    Find the first existing file in the list to keep

    Args:
        file_list: List of file paths

    Returns:
        Path to keep, or None if no files exist
    """
    for filepath in file_list:
        if os.path.exists(filepath) and os.path.isfile(filepath):
            return filepath
    return None


def delete_duplicates(groups, dry_run=True):
    """
    Delete duplicate files, keeping one from each group

    Args:
        groups: List of duplicate groups
        dry_run: If True, only simulate deletion without actually deleting
    """
    total_groups = len(groups)
    total_deleted = 0
    total_kept = 0
    total_space_freed = 0
    total_errors = 0

    print("=" * 80)
    if dry_run:
        print("DRY RUN MODE - No files will be deleted")
    else:
        print("DELETION MODE - Files will be permanently deleted!")
    print("=" * 80)
    print()

    deletion_log = []

    for group_idx, file_list in enumerate(groups, 1):
        print(f"Group {group_idx}/{total_groups}: {len(file_list)} files")

        # Find which file to keep
        keeper = find_keeper_file(file_list)

        if not keeper:
            print(f"  WARNING: No files exist in this group! Skipping...")
            total_errors += 1
            deletion_log.append({
                'group': group_idx,
                'status': 'error',
                'reason': 'no files exist',
                'files': file_list
            })
            continue

        print(f"  KEEPING: {os.path.basename(keeper)}")
        total_kept += 1

        # Delete the rest
        deleted_in_group = []
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

                if dry_run:
                    print(f"  WOULD DELETE: {os.path.basename(filepath)} ({file_size / (1024**2):.2f} MB)")
                    deleted_in_group.append(filepath)
                    total_space_freed += file_size
                    total_deleted += 1
                else:
                    # Actually delete the file
                    os.remove(filepath)
                    print(f"  DELETED: {os.path.basename(filepath)} ({file_size / (1024**2):.2f} MB)")
                    deleted_in_group.append(filepath)
                    total_space_freed += file_size
                    total_deleted += 1

            except Exception as e:
                print(f"  ERROR deleting {os.path.basename(filepath)}: {e}")
                total_errors += 1

        deletion_log.append({
            'group': group_idx,
            'keeper': keeper,
            'deleted': deleted_in_group,
            'status': 'success'
        })

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total groups processed: {total_groups}")
    print(f"Files kept: {total_kept}")
    print(f"Files deleted: {total_deleted}")
    print(f"Errors: {total_errors}")
    print(f"Space freed: {total_space_freed / (1024**2):.2f} MB ({total_space_freed / (1024**3):.2f} GB)")

    if dry_run:
        print("\nThis was a DRY RUN. No files were actually deleted.")
        print("Run with --execute flag to actually delete files.")

    return deletion_log


def save_deletion_log(log, output_path):
    """Save deletion log to file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"DELETION LOG - {timestamp}\n")
        f.write("=" * 80 + "\n\n")

        for entry in log:
            f.write(f"Group {entry['group']}: {entry['status']}\n")
            if entry['status'] == 'success':
                f.write(f"  Kept: {entry['keeper']}\n")
                f.write(f"  Deleted ({len(entry['deleted'])}):\n")
                for filepath in entry['deleted']:
                    f.write(f"    - {filepath}\n")
            elif entry['status'] == 'error':
                f.write(f"  Reason: {entry['reason']}\n")
                f.write(f"  Files:\n")
                for filepath in entry['files']:
                    f.write(f"    - {filepath}\n")
            f.write("\n")

    print(f"\nDeletion log saved to: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 delete_duplicates.py <json_report_file> [--execute]")
        print("\nOptions:")
        print("  --execute    Actually delete files (default is dry-run)")
        print("\nExample:")
        print('  python3 delete_duplicates.py duplicate_report.json')
        print('  python3 delete_duplicates.py duplicate_report.json --execute')
        sys.exit(1)

    report_file = sys.argv[1]

    # Check if execute flag is present
    dry_run = True
    if len(sys.argv) >= 3 and sys.argv[2] == '--execute':
        dry_run = False

    # Check if report file exists
    if not os.path.exists(report_file):
        print(f"Error: Report file not found: {report_file}")
        sys.exit(1)

    # Check if it's a JSON file
    if not report_file.lower().endswith('.json'):
        print(f"Error: Please provide a JSON report file (*.json)")
        print(f"You can generate one using find_duplicates.py")
        sys.exit(1)

    # Parse JSON report
    print(f"Reading JSON report file: {report_file}")
    metadata, groups = parse_json_report(report_file)

    if not groups:
        print("No duplicate groups found in report file.")
        sys.exit(0)

    # Display metadata
    if metadata:
        print(f"\nReport Information:")
        print(f"  Scan date: {metadata.get('scan_date', 'N/A')}")
        print(f"  Scanned directory: {metadata.get('scanned_directory', 'N/A')}")
        print(f"  Total images: {metadata.get('total_images_scanned', 'N/A')}")
        print(f"  Duplicate groups: {metadata.get('duplicate_groups', 'N/A')}")
        print(f"  Space can be freed: {metadata.get('space_can_free_mb', 0):.2f} MB")
        print()

    print(f"Found {len(groups)} duplicate groups to process")
    print()

    # Confirm before deletion if in execute mode
    if not dry_run:
        print("WARNING: You are about to PERMANENTLY DELETE files!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)
        print()

    # Delete duplicates
    log = delete_duplicates(groups, dry_run=dry_run)

    # Save log
    log_filename = "deletion_log.txt"
    save_deletion_log(log, log_filename)


if __name__ == "__main__":
    main()
