#!/usr/bin/env python3
"""
Duplicate Image Finder - CLI
Finds exact duplicate images by comparing MD5 hashes
"""

import sys
from pathlib import Path

from core import DuplicateScanner, Reporter


def print_progress(current: int, total: int, message: str):
    """Print progress to console"""
    if total > 0:
        print(f"\r  {message} ({current*100//total}%)", end="", flush=True)
    else:
        print(f"\r  {message}", end="", flush=True)


def display_results(result):
    """Display scan results"""
    print("\n")
    print("=" * 80)
    print("SONUÇLAR")
    print("=" * 80)

    print(f"\nToplam resim tarandı: {result.total_scanned}")
    print(f"Unique resim: {result.unique_count}")
    print(f"Duplicate grup: {len(result.groups)}")
    print(f"Silinebilecek dosya: {result.duplicate_count}")
    print(f"Kazanılabilecek alan: {Reporter.format_size(result.space_can_free)}")

    if result.has_duplicates:
        print("\n" + "=" * 80)
        print("DUPLICATE GRUPLAR")
        print("=" * 80)

        for idx, group in enumerate(result.groups, 1):
            print(f"\nGrup {idx}: {group['count']} aynı dosya")
            print(f"Hash: {group['hash']}")
            for filepath in group['files']:
                size = Reporter.format_size(Path(filepath).stat().st_size)
                print(f"  - {Path(filepath).name} ({size})")
                print(f"    {filepath}")
    else:
        print("\n" + "-" * 40)
        print("TEMİZ: Duplicate resim bulunamadı!")
        print("-" * 40)


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python3 find_duplicates.py <klasör_yolu>")
        print("\nÖrnek:")
        print('  python3 find_duplicates.py "/path/to/images"')
        sys.exit(1)

    target_dir = sys.argv[1]

    if not Path(target_dir).exists():
        print(f"Hata: Klasör bulunamadı: {target_dir}")
        sys.exit(1)

    if not Path(target_dir).is_dir():
        print(f"Hata: Bu bir klasör değil: {target_dir}")
        sys.exit(1)

    print(f"Taranıyor: {target_dir}")
    print("=" * 80)

    # Scan using core
    scanner = DuplicateScanner()
    result = scanner.find_duplicates(
        target_dir,
        recursive=True,
        progress_callback=print_progress
    )

    # Display results
    display_results(result)

    # Save report (always, even if clean)
    reporter = Reporter()
    json_path, txt_path = reporter.save_duplicate_report(result)

    print("\n" + "=" * 80)
    print("Raporlar kaydedildi:")
    print(f"  JSON: {json_path}")
    print(f"  TXT:  {txt_path}")


if __name__ == "__main__":
    main()
