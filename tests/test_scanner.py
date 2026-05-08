"""Scanner: collect_images, find_exact_duplicates, find_similar_images."""
from pathlib import Path

import pytest
from PIL import Image

from core import (
    DEFAULT_IMAGE_EXTS,
    collect_images,
    find_exact_duplicates,
    find_similar_images,
)
from core.scanner import _calc_space_freeable, _file_info


# ---------- collect_images ----------

def test_collect_top_level_only(exact_dup_dataset: Path):
    files = collect_images(exact_dup_dataset, recursive=False)
    names = [p.name for p in files]
    assert "a1.jpg" in names
    assert "a4.jpg" not in names  # alt klasör


def test_collect_recursive(exact_dup_dataset: Path):
    files = collect_images(exact_dup_dataset, recursive=True)
    names = [p.name for p in files]
    assert "a4.jpg" in names
    assert "d.jpg" in names


def test_collect_filters_by_extension(tmp_path: Path):
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.txt").write_bytes(b"hi")
    out = collect_images(tmp_path, allowed_exts={".jpg"})
    assert [p.name for p in out] == ["a.jpg"]


def test_collect_invalid_dir(tmp_path: Path):
    assert collect_images(tmp_path / "nope") == []


def test_collect_is_sorted(exact_dup_dataset: Path):
    paths = [str(p) for p in collect_images(exact_dup_dataset, recursive=True)]
    assert paths == sorted(paths)


# ---------- find_exact_duplicates ----------

def test_exact_finds_md5_groups(exact_dup_dataset: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    assert res.mode == "exact"
    assert res.total_scanned == 7
    # 1 grup — a1+a2+a3+a4 (4 dosya). b, c, d unique.
    assert len(res.groups) == 1
    g = res.groups[0]
    assert g.algorithm == "md5"
    assert g.count == 4
    assert all(f["path"].endswith(".jpg") for f in g.files)


def test_exact_no_duplicates_returns_empty_groups(all_unique_dataset: Path):
    res = find_exact_duplicates(all_unique_dataset, recursive=True)
    assert res.total_scanned == 3
    assert res.unique_count == 3
    assert not res.has_duplicates


def test_exact_unique_count(exact_dup_dataset: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    # 4 unique md5 (a*, b, c, d)
    assert res.unique_count == 4


def test_exact_recursive_off_skips_subdirs(exact_dup_dataset: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=False)
    # Top-level: a1, a2, a3, b, c (5 dosya). a4, d alt klasörde
    assert res.total_scanned == 5
    g = res.groups[0]
    assert g.count == 3  # a1+a2+a3 (a4 atlandı)


def test_exact_progress_callback(exact_dup_dataset: Path):
    calls = []

    def cb(current, total, msg):
        calls.append((current, total, msg))

    find_exact_duplicates(exact_dup_dataset, recursive=True, progress_cb=cb)
    assert len(calls) >= 1
    # Son çağrıda current >= total olmalı
    assert calls[-1][0] >= 1


def test_exact_empty_dir(tmp_path: Path):
    res = find_exact_duplicates(tmp_path, recursive=True)
    assert res.total_scanned == 0
    assert res.groups == []


# ---------- find_similar_images ----------

def test_similar_returns_scan_result(all_unique_dataset: Path):
    """Smoke: similar mode crash etmesin, ScanResult döndürsün."""
    res = find_similar_images(all_unique_dataset, threshold=10, algorithm="phash")
    assert res.mode == "similar"
    assert res.total_scanned == 3


def test_similar_groups_for_near_duplicates(tmp_path: Path):
    """Aynı görselin iki yakın versiyonu → similar grup."""
    img = Image.new("RGB", (256, 256), (255, 100, 100))
    img.save(tmp_path / "a.jpg", quality=95)
    img.save(tmp_path / "b.jpg", quality=70)  # aynı içerik, farklı kalite
    res = find_similar_images(tmp_path, threshold=10, algorithm="phash")
    assert res.has_duplicates
    g = res.groups[0]
    assert g.algorithm == "phash"
    assert g.threshold == 10


def test_similar_threshold_zero_only_identical(tmp_path: Path):
    """Threshold=0 → sadece phash-identical olanlar grupta."""
    Image.new("RGB", (256, 256), "red").save(tmp_path / "x.jpg", quality=85)
    Image.new("RGB", (256, 256), "red").save(tmp_path / "x_copy.jpg", quality=85)
    Image.new("RGB", (256, 256), "blue").save(tmp_path / "y.jpg", quality=85)
    res = find_similar_images(tmp_path, threshold=0, algorithm="phash")
    # x ve x_copy aynı içerik → 1 grup
    assert any(g.count >= 2 for g in res.groups)


# ---------- helpers ----------

def test_file_info_returns_size(tmp_path: Path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    info = _file_info(p)
    assert info["size_bytes"] == 11
    assert info["path"] == str(p)


def test_file_info_missing_returns_zero(tmp_path: Path):
    info = _file_info(tmp_path / "nope.jpg")
    assert info["size_bytes"] == 0


def test_default_image_exts_contains_common():
    assert ".jpg" in DEFAULT_IMAGE_EXTS
    assert ".png" in DEFAULT_IMAGE_EXTS
    assert ".webp" in DEFAULT_IMAGE_EXTS


# ---------- dimension enrichment (v1.1.0) ----------

def test_exact_groups_have_width_height(exact_dup_dataset: Path):
    """find_exact_duplicates grup üyelerine width/height ekler (best stratejisi için)."""
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    assert res.groups, "Beklenen duplicate grup yok"
    for g in res.groups:
        for f in g.files:
            assert f.get("width", 0) > 0, f"width eksik: {f}"
            assert f.get("height", 0) > 0, f"height eksik: {f}"


def test_similar_groups_have_width_height(tmp_path: Path):
    """find_similar_images grup üyelerine width/height ekler."""
    img = Image.new("RGB", (256, 256), (255, 100, 100))
    img.save(tmp_path / "a.jpg", quality=95)
    img.save(tmp_path / "b.jpg", quality=70)
    res = find_similar_images(tmp_path, threshold=10, algorithm="phash")
    assert res.groups
    for g in res.groups:
        for f in g.files:
            assert f.get("width") == 256
            assert f.get("height") == 256


def test_dimension_enrichment_skips_corrupt_file(tmp_path: Path):
    """Bozuk dosya PIL.Image.open fail eder, _enrich_with_dimensions hata yutar."""
    from core.scanner import _enrich_with_dimensions
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not a real image")
    info = {"path": str(bad), "size_bytes": bad.stat().st_size}
    _enrich_with_dimensions(info)  # exception fırlatmamalı
    # width/height yok kalır → best stratejisi size'a fallback yapar
    assert "width" not in info
    assert "height" not in info


# ---------- numpy.int64 distance → JSON serializable (v1.1.0 bugfix) ----------

def test_similar_distance_is_python_int_for_json(tmp_path: Path):
    """imagehash distance numpy.int64 dönebilir; cast edilmeli ki write_report
    JSON serialize edebilsin."""
    import json
    from core import write_report
    from core.actions import apply_action

    img = Image.new("RGB", (256, 256), (255, 100, 100))
    img.save(tmp_path / "a.jpg", quality=95)
    img.save(tmp_path / "b.jpg", quality=70)
    res = find_similar_images(tmp_path, threshold=20, algorithm="phash")
    assert res.groups

    # Tüm distance'lar Python int olmalı (numpy int64 değil)
    for g in res.groups:
        for f in g.files:
            d = f.get("distance")
            assert isinstance(d, int), f"distance Python int değil: {type(d)}"
            assert not isinstance(d, bool)  # int subclass

    # Asıl regression testi: write_report crash etmemeli
    ar = apply_action(res, action="none")
    report_path = tmp_path / "test_report.json"
    write_report(report_path, scan_result=res, action_result=ar,
                 recursive=True, config={"mode": "similar"})
    # JSON parse edilebiliyor mu?
    data = json.loads(report_path.read_text())
    assert data["mode"] == "similar"
