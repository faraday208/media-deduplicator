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
DEFAULT_REPORT_NAME = "duplicate_report.json"


def humanize_bytes(n: int) -> str:
    """Byte değerini KB/MB/GB olarak göster."""
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    if n < 1024**3:
        return f"{n / (1024**2):.1f} MB"
    return f"{n / (1024**3):.2f} GB"


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
