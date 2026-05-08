"""
Action layer — duplicate group'larından her gruptan birini koru, diğerlerini
move/delete et. Sidecar JSON rapor + undo desteği.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

from .scanner import DuplicateGroup, ScanResult

KeepStrategy = Literal["first", "largest", "smallest", "highest_resolution", "best"]
ActionMode = Literal["none", "move", "delete"]


@dataclass
class ActionEntry:
    """Tek bir duplicate'ın aksiyon kaydı (sidecar JSON için)."""
    original: str           # taşınan/silinen dosyanın eski yolu
    group_hash: str         # hangi grupta olduğu
    algorithm: str          # md5 / phash / ...
    moved_to: str | None = None
    deleted: bool = False
    distance: int | None = None  # similar mode için

    def to_dict(self) -> dict:
        d = {
            "original": self.original,
            "group_hash": self.group_hash,
            "algorithm": self.algorithm,
        }
        if self.moved_to is not None:
            d["moved_to"] = self.moved_to
        if self.deleted:
            d["deleted"] = True
        if self.distance is not None:
            d["distance"] = self.distance
        return d


@dataclass
class ActionResult:
    """apply_action çıktısı."""
    action: str
    invalid_dir: str | None
    keep_strategy: str
    entries: list[ActionEntry] = field(default_factory=list)
    skipped: int = 0


def _pick_keeper(files: list[dict], strategy: KeepStrategy) -> int:
    """Bir grubun korunacak dosyasının files listesindeki indeksini döndür."""
    if not files:
        return -1
    if strategy == "first":
        return 0
    if strategy == "largest":
        return max(range(len(files)), key=lambda i: files[i].get("size_bytes", 0))
    if strategy == "smallest":
        return min(range(len(files)), key=lambda i: files[i].get("size_bytes", 0))
    if strategy == "highest_resolution":
        # Naif: en yüksek piksel sayısı; tie'da byte size
        def _key_hr(i: int) -> tuple[int, int]:
            f = files[i]
            pixels = f.get("width", 0) * f.get("height", 0)
            return (pixels, f.get("size_bytes", 0))
        return max(range(len(files)), key=_key_hr)
    if strategy == "best":
        return _pick_best(files)
    return 0


# BPP-aware "best" stratejisi parametreleri
# - DISQUALIFY_BPP altı: aşırı sıkıştırma → ağır artifact, "bozuk" sayılır
# - FULL_SCORE_BPP üstü: tam puan (resolution direkt sayılır)
# - Aralarında: orantılı ceza (BPP/FULL_SCORE_BPP)
DISQUALIFY_BPP = 0.05
FULL_SCORE_BPP = 0.15


def _bpp(f: dict) -> float:
    """Bytes per pixel — quality göstergesi. Width/height bilinmiyorsa 0."""
    pixels = f.get("width", 0) * f.get("height", 0)
    if pixels <= 0:
        return 0.0
    return f.get("size_bytes", 0) / pixels


def _best_score(f: dict) -> tuple[int, int, int]:
    """
    BPP-aware composite skor (3-tuple — descending tie-breaker chain):
      1) qualified_pixels: resolution × BPP-factor (artifact varsa ceza)
      2) raw_pixels: ham resolution (fallback — width/height yoksa 0)
      3) size_bytes: son tie-breaker (aynı resolution+quality'de büyük byte)

    DISQUALIFY_BPP altındaki dosyalar qualified_pixels=0 alır → diğer
    adaylar varsa bunlar son sırada. Tüm grup diskalifiyeyse en az "kötü"
    olanı (en yüksek BPP) seçilir, raw_pixels üzerinden.
    """
    width = f.get("width", 0)
    height = f.get("height", 0)
    size = f.get("size_bytes", 0)
    pixels = width * height
    bpp = _bpp(f)

    if pixels == 0:
        # Resolution bilgisi yok — sadece size'la sıralan
        return (0, 0, size)

    if bpp < DISQUALIFY_BPP:
        # Aşırı sıkıştırılmış — qualified_pixels=0, ama raw_pixels yine sayılır
        return (0, pixels, size)

    factor = min(bpp / FULL_SCORE_BPP, 1.0)
    qualified = int(pixels * factor)
    return (qualified, pixels, size)


def _pick_best(files: list[dict]) -> int:
    """BPP-aware best — composite score ile en kaliteli kopyayı seç."""
    return max(range(len(files)), key=lambda i: _best_score(files[i]))


def _unique_target(path: Path) -> Path:
    """Move sırasında çakışma varsa _1, _2 ekle."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    i = 1
    while True:
        cand = parent / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


def apply_action(
    scan_result: ScanResult,
    *,
    action: ActionMode = "none",
    invalid_dir: Path | str | None = None,
    keep_strategy: KeepStrategy = "first",
    dry_run: bool = False,
) -> ActionResult:
    """
    Duplicate gruplarına aksiyon uygula. Her gruptan keep_strategy'ye göre
    biri korunur, diğerleri move/delete edilir.

    Args:
        scan_result: find_exact_duplicates / find_similar_images çıktısı
        action: "none" | "move" | "delete"
        invalid_dir: action="move" için hedef
        keep_strategy: hangi dosya korunsun (first/largest/smallest/highest_resolution/best)
        dry_run: True → log üret, dosyaya dokunma
    """
    if action not in ("none", "move", "delete"):
        raise ValueError(f"action must be 'none'/'move'/'delete', got {action!r}")
    if action == "move" and invalid_dir is None:
        raise ValueError("action='move' requires invalid_dir")

    dst_root = Path(invalid_dir).resolve() if invalid_dir else None
    result = ActionResult(
        action=action,
        invalid_dir=str(dst_root) if dst_root else None,
        keep_strategy=keep_strategy,
    )

    if action == "none":
        # Yine de keeper'ı işaretle (rapor için)
        for g in scan_result.groups:
            if g.files:
                idx = _pick_keeper(g.files, keep_strategy)
                g.kept = g.files[idx]["path"]
        return result

    if action == "move" and dst_root and not dry_run:
        dst_root.mkdir(parents=True, exist_ok=True)

    for g in scan_result.groups:
        if not g.files:
            continue
        keeper_idx = _pick_keeper(g.files, keep_strategy)
        g.kept = g.files[keeper_idx]["path"]

        for i, f in enumerate(g.files):
            if i == keeper_idx:
                continue
            original = Path(f["path"])
            if not original.is_file():
                result.skipped += 1
                continue

            if action == "delete":
                if not dry_run:
                    try:
                        original.unlink()
                    except OSError:
                        result.skipped += 1
                        continue
                result.entries.append(ActionEntry(
                    original=str(original),
                    group_hash=g.hash,
                    algorithm=g.algorithm,
                    deleted=True,
                    distance=f.get("distance"),
                ))
            elif action == "move" and dst_root:
                target = _unique_target(dst_root / original.name)
                if not dry_run:
                    try:
                        shutil.move(str(original), str(target))
                    except OSError:
                        result.skipped += 1
                        continue
                result.entries.append(ActionEntry(
                    original=str(original),
                    group_hash=g.hash,
                    algorithm=g.algorithm,
                    moved_to=str(target),
                    distance=f.get("distance"),
                ))

    return result


def undo_from_report(
    report_path: Path | str,
    *,
    dry_run: bool = False,
) -> dict:
    """
    Rapor üzerinden geri alma — sadece move-action undoable.

    Returns: {"restored": N, "skipped": N, "irreversible_deletes": N}
    """
    import json
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    if report.get("tool") != "media-deduplicator":
        raise ValueError(
            f"Report tool mismatch: expected 'media-deduplicator', "
            f"got {report.get('tool')!r}"
        )

    restored = skipped = irreversible = 0
    for entry in report.get("actions", []):
        if entry.get("deleted"):
            irreversible += 1
            continue
        moved_to = entry.get("moved_to")
        original = entry.get("original")
        if not moved_to or not original:
            skipped += 1
            continue
        src = Path(moved_to)
        dst = Path(original)
        if not src.exists() or dst.exists():
            skipped += 1
            continue
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(src), str(dst))
            except OSError:
                skipped += 1
                continue
        restored += 1

    return {
        "restored": restored,
        "skipped": skipped,
        "irreversible_deletes": irreversible,
    }
