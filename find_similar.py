#!/usr/bin/env python3
"""
Similar Image Finder - CLI
Finds visually similar images using perceptual hashing
"""

import sys
from pathlib import Path

from core import SimilarScanner, Reporter, Hasher


def print_progress(current: int, total: int, message: str):
    """Print progress to console"""
    if total > 0:
        print(f"\r  {message} ({current*100//total}%)", end="", flush=True)
    else:
        print(f"\r  {message}", end="", flush=True)


def display_results(result, threshold):
    """Display scan results"""
    print("\n")
    print("=" * 80)
    print("SONUÇLAR")
    print("=" * 80)

    total_similar = sum(g['count'] for g in result.groups)
    removable = sum(g['count'] - 1 for g in result.groups)

    print(f"\nToplam resim tarandı: {result.total_scanned}")
    print(f"İşlenen resim: {result.unique_count}")
    print(f"Benzer grup: {len(result.groups)}")
    print(f"Toplam benzer dosya: {total_similar}")
    print(f"Silinebilecek dosya: {removable}")
    print(f"Tahmini kazanç: {Reporter.format_size(result.space_can_free)}")

    if result.has_duplicates:
        print("\n" + "=" * 80)
        print("BENZER RESİM GRUPLARI")
        print("=" * 80)

        for idx, group in enumerate(result.groups, 1):
            print(f"\nGrup {idx}: {group['count']} benzer resim")
            print(f"Referans Hash: {group.get('reference_hash', 'N/A')}")
            for filepath in group['files']:
                try:
                    size = Reporter.format_size(Path(filepath).stat().st_size)
                except:
                    size = "N/A"
                print(f"  - {Path(filepath).name} ({size})")
                print(f"    {filepath}")
    else:
        print("\n" + "-" * 40)
        print(f"TEMİZ: Benzer resim bulunamadı (eşik: {threshold})")
        print("-" * 40)


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python3 find_similar.py <klasör_yolu> [eşik]")
        print("\nArgümanlar:")
        print("  klasör_yolu  : Taranacak klasör")
        print("  eşik         : Benzerlik eşiği (0-64, düşük=daha benzer, varsayılan: 10)")
        print("\nÖrnek:")
        print('  python3 find_similar.py "/path/to/images"')
        print('  python3 find_similar.py "/path/to/images" 5')
        print("\nEşik rehberi:")
        print("  0-5   : Çok benzer (katı)")
        print("  6-10  : Benzer (önerilen)")
        print("  11-15 : Biraz benzer")
        print("  16+   : Gevşek benzerlik")
        sys.exit(1)

    target_dir = sys.argv[1]

    # Get threshold
    threshold = 10
    if len(sys.argv) >= 3:
        try:
            threshold = int(sys.argv[2])
            if threshold < 0 or threshold > 64:
                print("Uyarı: Eşik 0-64 arası olmalı. Varsayılan 10 kullanılıyor.")
                threshold = 10
        except ValueError:
            print("Uyarı: Geçersiz eşik. Varsayılan 10 kullanılıyor.")
            threshold = 10

    if not Path(target_dir).exists():
        print(f"Hata: Klasör bulunamadı: {target_dir}")
        sys.exit(1)

    if not Path(target_dir).is_dir():
        print(f"Hata: Bu bir klasör değil: {target_dir}")
        sys.exit(1)

    # Check if imagehash is available
    if not Hasher.is_perceptual_hash_available():
        print("Hata: imagehash kütüphanesi yüklü değil!")
        print("Yüklemek için: pip install Pillow imagehash")
        sys.exit(1)

    print(f"Taranıyor: {target_dir}")
    print(f"Benzerlik eşiği: {threshold}")
    print("=" * 80)

    # Scan using core
    scanner = SimilarScanner()
    result = scanner.find_similar(
        target_dir,
        threshold=threshold,
        algorithm='average_hash',
        recursive=True,
        progress_callback=print_progress
    )

    # Display results
    display_results(result, threshold)

    # Save report (always, even if clean)
    reporter = Reporter()
    json_path, txt_path = reporter.save_similar_report(
        result,
        threshold=threshold,
        algorithm='average_hash'
    )

    print("\n" + "=" * 80)
    print("Raporlar kaydedildi:")
    print(f"  JSON: {json_path}")
    print(f"  TXT:  {txt_path}")


if __name__ == "__main__":
    main()
