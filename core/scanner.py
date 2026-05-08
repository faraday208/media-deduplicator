"""
Scanner — exact (MD5) ve similar (perceptual hash) tabanlı duplicate tespiti.

Public API (in-process import edenler için):
- collect_images(directory, recursive, allowed_exts) → list[Path]
- find_exact_duplicates(directory, recursive, progress_cb) → ScanResult
- find_similar_images(directory, threshold, algorithm, recursive, workers, progress_cb) → ScanResult
"""
from __future__ import annotations

import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .hasher import Hasher

DEFAULT_IMAGE_EXTS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"
})

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class DuplicateGroup:
    """Bir duplicate (exact) veya similar (perceptual) grubu.

    `kept` field'ı keep_strategy uygulandıktan sonra hangi dosyanın korunacağını
    işaretler — apply_action bu dışındakileri işler.
    """
    hash: str
    algorithm: str          # "md5" | "phash" | "ahash" | "dhash" | "whash"
    files: list[dict]       # her item: {"path": str, "size_bytes": int, "distance": int (similar için)}
    threshold: int | None = None  # similar için; exact'te None
    kept: str = ""          # apply_action sonrası set edilir

    @property
    def count(self) -> int:
        return len(self.files)

    @property
    def removable_count(self) -> int:
        return max(0, self.count - 1)

    def to_dict(self) -> dict:
        d = {
            "hash": self.hash,
            "algorithm": self.algorithm,
            "count": self.count,
            "files": list(self.files),
        }
        if self.threshold is not None:
            d["threshold"] = self.threshold
        if self.kept:
            d["kept"] = self.kept
        return d


@dataclass
class ScanResult:
    """Bir tarama sonucu — exact veya similar."""
    mode: str                          # "exact" | "similar"
    source_root: str
    total_scanned: int
    unique_count: int
    groups: list[DuplicateGroup] = field(default_factory=list)
    space_freeable_bytes: int = 0

    @property
    def has_duplicates(self) -> bool:
        return len(self.groups) > 0

    @property
    def removable_count(self) -> int:
        return sum(g.removable_count for g in self.groups)


def collect_images(
    directory: Path | str,
    *,
    recursive: bool = True,
    allowed_exts: Iterable[str] = DEFAULT_IMAGE_EXTS,
) -> list[Path]:
    """Bir dizindeki görselleri topla. Sıralı (deterministik) Path listesi."""
    root = Path(directory)
    if not root.is_dir():
        return []

    exts = {e.lower() for e in allowed_exts}
    out: list[Path] = []

    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() in exts:
                    out.append(p)
    else:
        for entry in root.iterdir():
            if entry.is_file() and entry.suffix.lower() in exts:
                out.append(entry)

    out.sort()
    return out


def _file_info(path: Path) -> dict:
    """Bir dosyanın size_bytes + path bilgisini topla. Hata durumunda size=0."""
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {"path": str(path), "size_bytes": size}


def _enrich_with_dimensions(file_dict: dict) -> None:
    """Dict'i in-place güncelle — width, height ekle. PIL gerek; hata yok kalır.

    Performans: tüm dataset için değil, sadece duplicate grup üyeleri için
    çağrılmalı (post-processing). Böylece 100k dosyalı dataset'te bile sadece
    grup üyelerine PIL.open uygulanır."""
    try:
        from PIL import Image
        with Image.open(file_dict["path"]) as img:
            file_dict["width"], file_dict["height"] = img.size
    except Exception:
        # Dosya bozuk/erişilemez → dimensions yok, downstream score'da 0 olarak ele alınır
        pass


def _enrich_groups_with_dimensions(groups: list[DuplicateGroup]) -> None:
    """Tüm grup üyelerine width/height ekle (post-scan). Sadece keeper-strategy
    'best' veya 'highest_resolution' için gerekli; ama her zaman zenginleştir
    (rapor JSON'da da bilgi var)."""
    for g in groups:
        for f in g.files:
            _enrich_with_dimensions(f)


def _calc_space_freeable(groups: list[DuplicateGroup]) -> int:
    """Her gruptan 1 dosya korunduğunda kazanılabilecek toplam byte."""
    total = 0
    for g in groups:
        if not g.files:
            continue
        # Korunan dosya hariç diğerlerinin boyutu
        sizes = [f.get("size_bytes", 0) for f in g.files]
        sizes.sort(reverse=True)
        total += sum(sizes[1:])  # en büyüğü tut, diğerlerini at varsayımı
    return total


def find_exact_duplicates(
    directory: Path | str,
    *,
    recursive: bool = True,
    allowed_exts: Iterable[str] = DEFAULT_IMAGE_EXTS,
    progress_cb: ProgressCallback | None = None,
) -> ScanResult:
    """MD5 hash ile birebir aynı dosyaları bul. Tek thread (md5 IO-bound)."""
    root = Path(directory).resolve()
    images = collect_images(root, recursive=recursive, allowed_exts=allowed_exts)
    total = len(images)

    if total == 0:
        return ScanResult(mode="exact", source_root=str(root), total_scanned=0, unique_count=0)

    if progress_cb:
        progress_cb(0, total, "MD5 hesaplanıyor")

    hash_map: dict[str, list[Path]] = defaultdict(list)
    for idx, p in enumerate(images, 1):
        h = Hasher.calculate_md5(str(p))
        if h:
            hash_map[h].append(p)
        if progress_cb and (idx % 50 == 0 or idx == total):
            progress_cb(idx, total, f"MD5: {idx}/{total}")

    groups: list[DuplicateGroup] = []
    for h, paths in hash_map.items():
        if len(paths) > 1:
            groups.append(DuplicateGroup(
                hash=h,
                algorithm="md5",
                files=[_file_info(p) for p in paths],
            ))
    groups.sort(key=lambda g: g.count, reverse=True)
    # keep_strategy='best'/'highest_resolution' için dimensions topla
    # (sadece grup üyeleri — 100k dosyalı dataset'te N grup × 2-5 üye)
    if progress_cb:
        progress_cb(total, total, "Dimensions topluyor (grup üyeleri)")
    _enrich_groups_with_dimensions(groups)

    return ScanResult(
        mode="exact",
        source_root=str(root),
        total_scanned=total,
        unique_count=len(hash_map),
        groups=groups,
        space_freeable_bytes=_calc_space_freeable(groups),
    )


def find_similar_images(
    directory: Path | str,
    *,
    threshold: int = 10,
    algorithm: str = "phash",
    recursive: bool = True,
    workers: int | None = None,
    allowed_exts: Iterable[str] = DEFAULT_IMAGE_EXTS,
    progress_cb: ProgressCallback | None = None,
) -> ScanResult:
    """Perceptual hash ile görsel olarak benzer dosyaları bul (paralel hash)."""
    if not Hasher.is_perceptual_hash_available():
        raise RuntimeError(
            "imagehash kütüphanesi yüklü değil. `uv sync` ile yükleyin."
        )

    root = Path(directory).resolve()
    images = collect_images(root, recursive=recursive, allowed_exts=allowed_exts)
    total = len(images)

    if total == 0:
        return ScanResult(mode="similar", source_root=str(root), total_scanned=0, unique_count=0)

    if workers is None:
        workers = os.cpu_count() or 4

    if progress_cb:
        progress_cb(0, total, f"Perceptual hash ({algorithm}, {workers} worker)")

    image_hashes: dict[Path, object] = {}
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(Hasher.calculate_perceptual_hash, str(p), algorithm): p for p in images}
        for fut in as_completed(futures):
            completed += 1
            p = futures[fut]
            try:
                h = fut.result()
            except Exception:
                h = None
            if h is not None:
                image_hashes[p] = h
            if progress_cb and (completed % 25 == 0 or completed == total):
                progress_cb(completed, total, f"Hash: {completed}/{total}")

    if not image_hashes:
        return ScanResult(mode="similar", source_root=str(root), total_scanned=total, unique_count=0)

    if progress_cb:
        progress_cb(0, len(image_hashes), "Benzerlik karşılaştırması")

    groups: list[DuplicateGroup] = []
    processed: set[Path] = set()
    paths = list(image_hashes.keys())

    for i, p1 in enumerate(paths):
        if p1 in processed:
            continue
        if progress_cb and (i + 1) % 50 == 0:
            progress_cb(i + 1, len(paths), f"Karşılaştırma: {i+1}/{len(paths)}")

        h1 = image_hashes[p1]
        files = [{**_file_info(p1), "distance": 0}]
        for p2 in paths[i + 1:]:
            if p2 in processed:
                continue
            # imagehash distance numpy.int64 dönebilir → JSON için Python int
            distance = int(h1 - image_hashes[p2])
            if distance <= threshold:
                files.append({**_file_info(p2), "distance": distance})
                processed.add(p2)

        if len(files) > 1:
            files.sort(key=lambda x: x["distance"])
            groups.append(DuplicateGroup(
                hash=str(h1),
                algorithm=algorithm,
                files=files,
                threshold=threshold,
            ))
            processed.add(p1)

    groups.sort(key=lambda g: g.count, reverse=True)
    # keep_strategy='best'/'highest_resolution' için dimensions topla
    if progress_cb:
        progress_cb(len(paths), len(paths), "Dimensions topluyor")
    _enrich_groups_with_dimensions(groups)

    return ScanResult(
        mode="similar",
        source_root=str(root),
        total_scanned=total,
        unique_count=len(image_hashes),
        groups=groups,
        space_freeable_bytes=_calc_space_freeable(groups),
    )
