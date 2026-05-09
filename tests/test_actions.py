"""Actions: apply_action (move/delete/none) + undo_from_report."""
from pathlib import Path

import pytest

from dedup_core import (
    apply_action,
    find_exact_duplicates,
    undo_from_report,
    write_report,
)


# ---------- apply_action ----------

def test_action_none_marks_keeper(exact_dup_dataset: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    ar = apply_action(res, action="none")
    assert ar.action == "none"
    assert ar.entries == []
    # Keeper işaretlenmiş olmalı
    assert all(g.kept for g in res.groups)
    # Dosyalar yerinde
    assert (exact_dup_dataset / "a1.jpg").exists()
    assert (exact_dup_dataset / "a2.jpg").exists()


def test_action_move_relocates_duplicates(exact_dup_dataset: Path, tmp_path: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    rejected = tmp_path / "rejected"
    ar = apply_action(res, action="move", invalid_dir=rejected, keep_strategy="first")

    assert ar.action == "move"
    # 4 a* dosyasından 1 keeper, 3 taşındı
    assert len(ar.entries) == 3
    # Keeper duruyor
    keeper = res.groups[0].kept
    assert Path(keeper).exists()
    # Taşınanlar /rejected'da
    moved_names = {Path(e.moved_to).name for e in ar.entries}
    assert moved_names <= {"a1.jpg", "a2.jpg", "a3.jpg", "a4.jpg"}


def test_action_move_dry_run_no_filesystem_change(exact_dup_dataset: Path, tmp_path: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    rejected = tmp_path / "rejected"
    ar = apply_action(res, action="move", invalid_dir=rejected,
                       keep_strategy="first", dry_run=True)
    assert len(ar.entries) == 3
    # Dosyalar yerinde
    assert (exact_dup_dataset / "a1.jpg").exists()
    assert (exact_dup_dataset / "a2.jpg").exists()
    assert not rejected.exists()


def test_action_delete_removes_duplicates(exact_dup_dataset: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    ar = apply_action(res, action="delete", keep_strategy="first")
    assert ar.action == "delete"
    assert all(e.deleted for e in ar.entries)
    # Keeper var, diğerleri yok
    keeper = Path(res.groups[0].kept)
    assert keeper.exists()


def test_action_keep_strategy_largest(exact_dup_dataset: Path, tmp_path: Path):
    """largest stratejisi en büyük dosyayı tutar (md5'leri aynı olduğu için size eşit
    aslında — ama strategy logic test edilebilir)."""
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    ar = apply_action(res, action="move",
                       invalid_dir=tmp_path / "rej",
                       keep_strategy="largest")
    assert ar.keep_strategy == "largest"
    # Keeper en az birinin path'i (sub_a/a4 dahil 4 aday içinden)
    assert res.groups[0].kept


def test_action_move_requires_invalid_dir(all_unique_dataset: Path):
    res = find_exact_duplicates(all_unique_dataset, recursive=True)
    with pytest.raises(ValueError, match="invalid_dir"):
        apply_action(res, action="move", invalid_dir=None)


def test_action_invalid_value_raises(all_unique_dataset: Path):
    res = find_exact_duplicates(all_unique_dataset, recursive=True)
    with pytest.raises(ValueError, match="action"):
        apply_action(res, action="burn")


def test_action_no_groups_no_op(all_unique_dataset: Path, tmp_path: Path):
    """Duplicate yoksa apply_action sessizce başarılı olur, log boş."""
    res = find_exact_duplicates(all_unique_dataset, recursive=True)
    ar = apply_action(res, action="move", invalid_dir=tmp_path / "rej")
    assert ar.entries == []
    assert ar.skipped == 0


def test_action_move_preserves_tree_hierarchy(tmp_path: Path):
    """v1.2.2: aynı isimli dosyalar farklı subdir'lerde → tree-mirror move
    (eski davranış: flat + _unique_target _1 suffix; yeni: relative_to mirror)."""
    a = tmp_path / "src" / "a"; a.mkdir(parents=True)
    b = tmp_path / "src" / "b"; b.mkdir()
    from PIL import Image
    img = Image.new("RGB", (256, 256), "red")
    img.save(a / "dup.jpg", quality=85)
    import shutil
    shutil.copy(a / "dup.jpg", b / "dup.jpg")

    res = find_exact_duplicates(tmp_path / "src", recursive=True)
    rejected = tmp_path / "rej"
    ar = apply_action(res, action="move", invalid_dir=rejected, keep_strategy="first")

    # 2 dosya, 1 keeper, 1 taşındı
    assert len(ar.entries) == 1
    moved = Path(ar.entries[0].moved_to)
    assert moved.exists()
    # Tree-preserving: subdir altında (rejected/a/dup.jpg veya rejected/b/dup.jpg)
    assert moved.parent != rejected.resolve(), "Tree korunmamış (flat)"
    assert moved.parent.parent == rejected.resolve()
    assert moved.parent.name in {"a", "b"}


# ---------- undo_from_report ----------

def test_undo_restores_moved_files(exact_dup_dataset: Path, tmp_path: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    rejected = tmp_path / "rejected"
    ar = apply_action(res, action="move", invalid_dir=rejected, keep_strategy="first")

    report = rejected / "duplicate_report.json"
    write_report(report, scan_result=res, action_result=ar,
                 recursive=True, config={"mode": "exact", "algorithm": "md5"})

    summary = undo_from_report(report)
    assert summary["restored"] == len(ar.entries)
    assert summary["skipped"] == 0
    assert summary["irreversible_deletes"] == 0


def test_undo_dry_run_no_filesystem_change(exact_dup_dataset: Path, tmp_path: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    rejected = tmp_path / "rejected"
    ar = apply_action(res, action="move", invalid_dir=rejected, keep_strategy="first")

    report = rejected / "duplicate_report.json"
    write_report(report, scan_result=res, action_result=ar,
                 recursive=True, config={"mode": "exact"})

    summary = undo_from_report(report, dry_run=True)
    assert summary["restored"] == len(ar.entries)
    # Dosyalar hala /rejected'ta
    assert any(p.is_file() for p in rejected.iterdir() if p.suffix == ".jpg")


def test_undo_irreversible_for_delete(exact_dup_dataset: Path, tmp_path: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    ar = apply_action(res, action="delete", keep_strategy="first")
    report = tmp_path / "report.json"
    write_report(report, scan_result=res, action_result=ar,
                 recursive=True, config={"mode": "exact"})
    summary = undo_from_report(report)
    assert summary["irreversible_deletes"] == len(ar.entries)
    assert summary["restored"] == 0


def test_undo_rejects_wrong_tool(tmp_path: Path):
    import json
    report = tmp_path / "fake.json"
    report.write_text(json.dumps({"tool": "some-other-tool", "actions": []}))
    with pytest.raises(ValueError, match="tool mismatch"):
        undo_from_report(report)


def test_undo_skips_when_original_path_taken(exact_dup_dataset: Path, tmp_path: Path):
    res = find_exact_duplicates(exact_dup_dataset, recursive=True)
    rejected = tmp_path / "rejected"
    ar = apply_action(res, action="move", invalid_dir=rejected, keep_strategy="first")

    # Original konumlardan birinde yeni dosya yarat
    if ar.entries:
        Path(ar.entries[0].original).write_bytes(b"new file content")

    report = rejected / "duplicate_report.json"
    write_report(report, scan_result=res, action_result=ar,
                 recursive=True, config={"mode": "exact"})

    summary = undo_from_report(report)
    # En az 1 skipped (üzerine yazma yok)
    assert summary["skipped"] >= 1
