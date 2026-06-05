"""
Reporter — sidecar JSON rapor yazımı (tool-conventions §4 uyumlu).

Şema:
    {
      "version": "1",
      "tool": "media-deduplicator",
      "source_root": "/abs/path",
      "recursive": bool,
      "mode": "exact" | "similar",
      "config": { ... },
      "summary": {
        "total_scanned": N, "unique": N, "groups": N,
        "duplicates": N, "space_freeable_bytes": N
      },
      "groups": [ ... DuplicateGroup.to_dict() ],
      "action": "none" | "move" | "delete",
      "invalid_dir": "/abs/path" | null,
      "keep_strategy": "first" | "largest" | ...,
      "actions": [ ... ActionEntry.to_dict() ],
      "skipped": N
    }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .actions import ActionResult
from .scanner import ScanResult

REPORT_VERSION = "1"
REPORT_TOOL = "media-deduplicator"
# Generic isim — geriye dönük uyumluluk (eski raporlar, manuel undo yolları).
DEFAULT_REPORT_NAME = "duplicate_report.json"
# Mode'a özel isimler: exact ve similar raporları birbirini ezmesin, yan yana
# yaşasın (önce exact temizle → sonra similar review akışı için).
EXACT_REPORT_NAME = "duplicate_exact_report.json"
SIMILAR_REPORT_NAME = "duplicate_similar_report.json"


def report_name_for_mode(mode: str) -> str:
    """Mode'a göre kanonik rapor dosya ismi. Bilinmeyen mode → generic isim."""
    if mode == "exact":
        return EXACT_REPORT_NAME
    if mode == "similar":
        return SIMILAR_REPORT_NAME
    return DEFAULT_REPORT_NAME


def humanize_bytes(n: int) -> str:
    """Byte değerini KB/MB/GB olarak göster."""
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    if n < 1024**3:
        return f"{n / (1024**2):.1f} MB"
    return f"{n / (1024**3):.2f} GB"


def _distance_stats(scan_result: ScanResult) -> dict[str, Any]:
    """Similar gruplarda keeper'a uzaklık (hamming distance) dağılımı. Her grupta
    ilk dosya keeper (distance=0); istatistik duplicate'lerin uzaklığı üzerinden.
    Review'da 'ne kadar agresif eşleşti' sorusunu cevaplar."""
    distances = [
        f["distance"]
        for g in scan_result.groups
        for f in g.files[1:]
        if "distance" in f
    ]
    if not distances:
        return {"count": 0, "min": None, "max": None, "avg": None}
    return {
        "count": len(distances),
        "min": min(distances),
        "max": max(distances),
        "avg": round(sum(distances) / len(distances), 2),
    }


def write_report(
    report_path: Path | str,
    *,
    scan_result: ScanResult,
    action_result: ActionResult,
    recursive: bool,
    config: dict[str, Any],
) -> Path:
    """Sidecar JSON rapor yaz."""
    summary = {
        "total_scanned": scan_result.total_scanned,
        "unique": scan_result.unique_count,
        "groups": len(scan_result.groups),
        "duplicates": scan_result.removable_count,
        "space_freeable_bytes": scan_result.space_freeable_bytes,
        "space_freeable_human": humanize_bytes(scan_result.space_freeable_bytes),
    }
    # Mode'a özel rapor zenginleştirmesi: exact byte-identical (md5) kesinliğini,
    # similar ise perceptual-hash karar parametrelerini + benzerlik dağılımını
    # öne çıkarır. İki mode'un raporu artık hem isim hem içerikçe ayrışır.
    if scan_result.mode == "similar":
        summary["match_type"] = "perceptual"
        summary["algorithm"] = config.get("algorithm")
        summary["threshold"] = config.get("threshold")
        summary["distance_stats"] = _distance_stats(scan_result)
    else:
        summary["match_type"] = "exact"
        summary["hash_algorithm"] = "md5"

    payload = {
        "version": REPORT_VERSION,
        "tool": REPORT_TOOL,
        "source_root": scan_result.source_root,
        "recursive": recursive,
        "mode": scan_result.mode,
        "config": config,
        "summary": summary,
        "groups": [g.to_dict() for g in scan_result.groups],
        "action": action_result.action,
        "invalid_dir": action_result.invalid_dir,
        "keep_strategy": action_result.keep_strategy,
        "actions": [e.to_dict() for e in action_result.entries],
        "skipped": action_result.skipped,
    }
    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out
