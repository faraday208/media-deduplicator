#!/usr/bin/env python3
"""
Media Deduplicator — CLI

Kullanım örnekleri:
  # Exact duplicate (md5) tespit, sadece raporla (default)
  python run.py -i ./dataset

  # Similar (perceptual hash) tespit, threshold 8
  python run.py -i ./dataset --mode similar --threshold 8 --algorithm phash

  # Duplicate'ları /rejected'a taşı (undoable)
  python run.py -i ./dataset --invalid-action move --invalid-dir ./rejected

  # En büyük dosyayı tut, diğerlerini sil
  python run.py -i ./dataset --invalid-action delete --keep-strategy largest

  # Geri al (move-action raporundan)
  python run.py --undo ./rejected/duplicate_report.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core import (
    DEFAULT_IMAGE_EXTS,
    DEFAULT_REPORT_NAME,
    Hasher,
    apply_action,
    find_exact_duplicates,
    find_similar_images,
    humanize_bytes,
    undo_from_report,
    write_report,
)


def _print_progress(current: int, total: int, msg: str) -> None:
    if total > 0:
        pct = current * 100 // total
        print(f"\r  {msg} ({pct}%)", end="", flush=True)
    else:
        print(f"\r  {msg}", end="", flush=True)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Media Deduplicator (CLI) — exact (MD5) + similar (perceptual hash)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-i", "--input", help="Input klasörü (validation modu için zorunlu)")
    p.add_argument("-o", "--output", help=f"JSON rapor çıktısı (default: <input>/{DEFAULT_REPORT_NAME})")
    p.add_argument(
        "--mode",
        choices=["exact", "similar"],
        default="exact",
        help="exact (md5, birebir) | similar (perceptual hash). Default: exact",
    )
    p.add_argument("--recursive", action="store_true", default=True,
                   help="Alt klasörleri de tara (default: True)")
    p.add_argument("--no-recursive", action="store_false", dest="recursive",
                   help="Sadece üst seviye tara")
    p.add_argument("--limit", type=int, default=0, help="Max dosya sayısı (0 = limitsiz)")

    # Similar modu
    p.add_argument("--threshold", type=int, default=10,
                   help="Similar mode için Hamming distance eşiği (0-64, düşük=daha sıkı). Default: 10")
    p.add_argument("--algorithm", choices=["phash", "ahash", "dhash", "whash", "average_hash"],
                   default="phash", help="Perceptual hash algoritması")
    p.add_argument("--workers", type=int, default=None,
                   help="Paralel worker sayısı (similar mode). Default: CPU count")

    # Aksiyon
    p.add_argument(
        "--invalid-action",
        choices=["none", "move", "delete"],
        default="none",
        help="Duplicate dosyalar için aksiyon (default: none = sadece rapor)",
    )
    p.add_argument("--invalid-dir", help="--invalid-action move için hedef klasör")
    p.add_argument(
        "--keep-strategy",
        choices=["first", "largest", "smallest", "highest_resolution", "best"],
        default="first",
        help="Her gruptan hangi dosya korunsun. Default: first",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Aksiyonu simüle et, dosyalara dokunma (rapor yine yazılır)")
    p.add_argument("--yes", action="store_true",
                   help="Onay sorma (özellikle --invalid-action delete için)")

    # Undo
    p.add_argument("--undo", help="Duplicate raporundan aksiyonu geri al (sadece move-action)")

    return p


def _confirm_delete(count: int, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    print(f"\n⚠  {count} dosya KALICI olarak silinecek. Bu işlem GERİ ALINAMAZ.")
    answer = input("Devam? [y/N]: ").strip().lower()
    return answer in {"y", "yes", "evet"}


def _run_undo(args: argparse.Namespace) -> int:
    report_path = Path(args.undo)
    if not report_path.exists():
        print(f"Rapor bulunamadı: {report_path}", file=sys.stderr)
        return 1
    print(f"Undo başlıyor (dry-run={args.dry_run}): {report_path}")
    summary = undo_from_report(report_path, dry_run=args.dry_run)
    print(f"  Restored:               {summary['restored']}")
    print(f"  Skipped:                {summary['skipped']}")
    print(f"  Irreversible (deleted): {summary['irreversible_deletes']}")
    if summary["irreversible_deletes"]:
        print("  → Silinmiş dosyalar geri getirilemez.")
    return 0


def _resolve_report_path(args: argparse.Namespace, input_dir: Path) -> Path:
    if args.output:
        return Path(args.output)
    if args.invalid_action == "move" and args.invalid_dir:
        return Path(args.invalid_dir) / DEFAULT_REPORT_NAME
    return input_dir / DEFAULT_REPORT_NAME


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.undo:
        if args.input or args.invalid_action != "none":
            parser.error("--undo ile -i/--input veya --invalid-action birlikte kullanılamaz")
        return _run_undo(args)

    if not args.input:
        parser.error("--input gerekli (veya --undo kullan)")

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(f"Geçerli bir dizin değil: {input_dir}", file=sys.stderr)
        return 1

    if args.invalid_action == "move" and not args.invalid_dir:
        parser.error("--invalid-action move için --invalid-dir gerekli")

    if args.mode == "similar" and not Hasher.is_perceptual_hash_available():
        print("Hata: imagehash kütüphanesi yüklü değil. `uv sync` ile yükleyin.",
              file=sys.stderr)
        return 1

    # Tarama
    print(f"\n{'='*70}")
    print(f"Media Deduplicator — mode={args.mode}")
    print(f"{'='*70}")
    print(f"Input:        {input_dir}")
    print(f"Recursive:    {args.recursive}")
    if args.mode == "similar":
        print(f"Threshold:    {args.threshold} (algorithm={args.algorithm})")
        print(f"Workers:      {args.workers or 'CPU count'}")
    print(f"Action:       {args.invalid_action}{' (DRY-RUN)' if args.dry_run else ''}")
    print(f"Keep:         {args.keep_strategy}")
    print(f"{'='*70}\n")

    if args.mode == "exact":
        scan_result = find_exact_duplicates(
            input_dir,
            recursive=args.recursive,
            allowed_exts=DEFAULT_IMAGE_EXTS,
            progress_cb=_print_progress,
        )
    else:
        scan_result = find_similar_images(
            input_dir,
            threshold=args.threshold,
            algorithm=args.algorithm,
            recursive=args.recursive,
            workers=args.workers,
            allowed_exts=DEFAULT_IMAGE_EXTS,
            progress_cb=_print_progress,
        )

    if args.limit > 0:
        scan_result.groups = scan_result.groups[: args.limit]

    print(f"\n\n{'='*70}")
    print(f"SONUÇLAR")
    print(f"{'='*70}")
    print(f"Total scanned:     {scan_result.total_scanned}")
    print(f"Unique:            {scan_result.unique_count}")
    print(f"Duplicate gruplar: {len(scan_result.groups)}")
    print(f"Silinebilecek:     {scan_result.removable_count}")
    print(f"Kazanılabilecek:   {humanize_bytes(scan_result.space_freeable_bytes)}")

    if not scan_result.has_duplicates:
        print("\nTEMİZ: Duplicate bulunamadı.")

    # Aksiyon
    if args.invalid_action == "delete" and scan_result.removable_count > 0 and not args.dry_run:
        if not _confirm_delete(scan_result.removable_count, assume_yes=args.yes):
            print("İptal edildi.")
            return 2

    action_res = apply_action(
        scan_result,
        action=args.invalid_action,
        invalid_dir=args.invalid_dir,
        keep_strategy=args.keep_strategy,
        dry_run=args.dry_run,
    )

    if args.invalid_action != "none":
        print(f"\nAksiyon: {args.invalid_action}{' (DRY-RUN)' if args.dry_run else ''}")
        if action_res.action == "move":
            print(f"  Taşınan:  {len(action_res.entries)}")
            print(f"  Hedef:    {action_res.invalid_dir}")
        elif action_res.action == "delete":
            print(f"  Silinen:  {len(action_res.entries)}")
        if action_res.skipped:
            print(f"  Atlanan:  {action_res.skipped}")

    # Rapor
    config_summary = {
        "mode": args.mode,
        "threshold": args.threshold if args.mode == "similar" else None,
        "algorithm": args.algorithm if args.mode == "similar" else "md5",
        "workers": args.workers,
    }
    report_path = _resolve_report_path(args, input_dir)
    write_report(
        report_path,
        scan_result=scan_result,
        action_result=action_res,
        recursive=args.recursive,
        config=config_summary,
    )
    print(f"\nRapor: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
