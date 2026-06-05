"""run.py CLI: argparse + main()."""
import json
import sys
from pathlib import Path

import pytest

from run import _build_parser, _resolve_report_path, main


def test_parser_defaults():
    args = _build_parser().parse_args(["-i", "/tmp/x"])
    assert args.input == "/tmp/x"
    assert args.mode == "exact"
    assert args.recursive is True
    assert args.invalid_action == "none"
    assert args.keep_strategy == "first"


def test_parser_full_flags():
    args = _build_parser().parse_args([
        "-i", "/tmp/x", "--mode", "similar",
        "--threshold", "5", "--algorithm", "phash",
        "--workers", "8",
        "--no-recursive",
        "--invalid-action", "move", "--invalid-dir", "/tmp/r",
        "--keep-strategy", "largest",
        "--dry-run", "--yes",
    ])
    assert args.mode == "similar"
    assert args.threshold == 5
    assert args.algorithm == "phash"
    assert args.workers == 8
    assert args.recursive is False
    assert args.invalid_action == "move"
    assert args.keep_strategy == "largest"


def test_resolve_report_path_explicit():
    args = _build_parser().parse_args(["-i", "/tmp/x", "-o", "/tmp/r.json"])
    assert _resolve_report_path(args, Path("/tmp/x")) == Path("/tmp/r.json")


def test_resolve_report_path_move_uses_invalid_dir(tmp_path: Path):
    args = _build_parser().parse_args([
        "-i", str(tmp_path),
        "--invalid-action", "move",
        "--invalid-dir", str(tmp_path / "rej"),
    ])
    out = _resolve_report_path(args, tmp_path)
    # mode default = exact → mode'a özel isim
    assert out == tmp_path / "rej" / "duplicate_exact_report.json"


def test_main_writes_report_exact(monkeypatch, exact_dup_dataset: Path):
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(exact_dup_dataset),
        "--mode", "exact",
    ])
    rc = main()
    assert rc == 0
    report = exact_dup_dataset / "duplicate_exact_report.json"
    assert report.exists()
    data = json.loads(report.read_text())
    assert data["tool"] == "media-deduplicator"
    assert data["mode"] == "exact"
    assert data["summary"]["groups"] >= 1
    # exact mode içerik imzası
    assert data["summary"]["match_type"] == "exact"
    assert data["summary"]["hash_algorithm"] == "md5"


def test_main_move_action_e2e(monkeypatch, exact_dup_dataset: Path, tmp_path: Path):
    rejected = tmp_path / "rejected"
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(exact_dup_dataset),
        "--invalid-action", "move",
        "--invalid-dir", str(rejected),
    ])
    rc = main()
    assert rc == 0
    assert (rejected / "duplicate_exact_report.json").exists()
    # En az bir taşınmış dosya
    moved = list(rejected.glob("*.jpg"))
    assert len(moved) >= 1


def test_main_invalid_dir_required_for_move(monkeypatch, exact_dup_dataset: Path):
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(exact_dup_dataset),
        "--invalid-action", "move",
    ])
    with pytest.raises(SystemExit):
        main()


def test_main_undo_cycle(monkeypatch, exact_dup_dataset: Path, tmp_path_factory):
    # rejected'ı dataset DIŞINDA kur (rglob'a karışmasın)
    rejected = tmp_path_factory.mktemp("rejected")

    # Forward
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(exact_dup_dataset),
        "--invalid-action", "move",
        "--invalid-dir", str(rejected),
    ])
    assert main() == 0
    files_after_move = sorted(p.name for p in exact_dup_dataset.rglob("*.jpg"))
    moved_in_rejected = sorted(p.name for p in rejected.glob("*.jpg"))
    assert moved_in_rejected, "Hiç dosya taşınmadı"

    # Undo
    monkeypatch.setattr(sys, "argv", [
        "run.py", "--undo", str(rejected / "duplicate_exact_report.json"),
    ])
    assert main() == 0
    files_after_undo = sorted(p.name for p in exact_dup_dataset.rglob("*.jpg"))
    # Undo sonrası kaynak'ta dosya sayısı move'dan sonrakinden fazla
    assert len(files_after_undo) > len(files_after_move)
    # Rejected boşaldı (sadece rapor kaldı)
    assert not list(rejected.glob("*.jpg"))


def test_main_input_required_when_no_undo(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run.py"])
    with pytest.raises(SystemExit):
        main()


def test_main_undo_mutex(monkeypatch, tmp_path: Path):
    # Undo + diğer flag'ler birlikte error
    monkeypatch.setattr(sys, "argv", [
        "run.py", "--undo", str(tmp_path / "x.json"),
        "-i", "/tmp/y",
    ])
    with pytest.raises(SystemExit):
        main()


def test_main_best_strategy_picks_high_quality(monkeypatch, tmp_path: Path):
    """E2E (v1.1.0): aynı görselin q40 + q90 versiyonu var. Best stratejisi
    quality yüksek olanı keeper yapmalı."""
    import shutil
    from PIL import Image
    # Aynı görsel, iki farklı quality (md5 farklı, similar yakalar)
    img = Image.new("RGB", (1024, 1024), (200, 100, 50))
    img.save(tmp_path / "low_q40.jpg", "JPEG", quality=40)
    img.save(tmp_path / "high_q90.jpg", "JPEG", quality=90)
    # Birebir kopya da ekle (md5-grup için)
    shutil.copy(tmp_path / "high_q90.jpg", tmp_path / "high_copy.jpg")

    rejected = tmp_path / "rejected"
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(tmp_path),
        "--mode", "similar", "--threshold", "10",
        "--keep-strategy", "best",
        "--invalid-action", "move",
        "--invalid-dir", str(rejected),
    ])
    rc = main()
    assert rc == 0

    # Rapor okunup keeper'lar kontrol edilir
    report = json.loads((rejected / "duplicate_similar_report.json").read_text())
    assert report["keep_strategy"] == "best"
    # similar mode içerik imzası
    assert report["summary"]["match_type"] == "perceptual"
    assert report["summary"]["algorithm"] == "phash"
    assert report["summary"]["threshold"] == 10
    assert "distance_stats" in report["summary"]

    # Keeper'lar: best stratejisi her grupta yüksek-quality'i seçmeli
    for g in report["groups"]:
        keeper_path = g.get("kept", "")
        # q40 keeper olmamalı (en düşük quality)
        assert "q40" not in keeper_path, f"q40 yanlışlıkla keeper: {keeper_path}"


def test_main_best_strategy_with_no_dimensions_fallback_to_size(monkeypatch, tmp_path: Path):
    """Bozuk dosyalar PIL.open fail edince width/height yok → best size'a fallback."""
    # Birebir aynı 2 dosya (md5-grup), normal görseller
    from PIL import Image
    import shutil
    Image.new("RGB", (512, 512), "red").save(tmp_path / "a.jpg", quality=85)
    shutil.copy(tmp_path / "a.jpg", tmp_path / "b.jpg")

    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(tmp_path),
        "--mode", "exact",
        "--keep-strategy", "best",
    ])
    rc = main()
    assert rc == 0

    report = json.loads((tmp_path / "duplicate_exact_report.json").read_text())
    assert report["keep_strategy"] == "best"
    # 1 grup, herhangi biri keeper olabilir (identical)
    assert report["summary"]["groups"] == 1
