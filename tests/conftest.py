"""Test fixture'ları — media-deduplicator için."""
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

# Repo kökünü path'e ekle ki `from core import ...` çalışsın
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _save_jpg(path: Path, size: tuple[int, int], color: str = "red") -> None:
    Image.new("RGB", size, color).save(path, "JPEG", quality=85)


@pytest.fixture
def exact_dup_dataset(tmp_path: Path) -> Path:
    """Birebir aynı dosyaların olduğu dataset.

    Yapı:
        tmp_path/
            a1.jpg, a2.jpg, a3.jpg  (3'ü md5-eşit)
            b.jpg                   (unique)
            c.jpg                   (unique)
            sub/
                a4.jpg              (a1 ile md5-eşit, alt klasör)
                d.jpg               (unique)
    """
    _save_jpg(tmp_path / "a1.jpg", (512, 512), "red")
    shutil.copy(tmp_path / "a1.jpg", tmp_path / "a2.jpg")
    shutil.copy(tmp_path / "a1.jpg", tmp_path / "a3.jpg")

    _save_jpg(tmp_path / "b.jpg", (512, 512), "blue")
    _save_jpg(tmp_path / "c.jpg", (512, 512), "green")

    sub = tmp_path / "sub"
    sub.mkdir()
    shutil.copy(tmp_path / "a1.jpg", sub / "a4.jpg")
    _save_jpg(sub / "d.jpg", (512, 512), "yellow")
    return tmp_path


@pytest.fixture
def all_unique_dataset(tmp_path: Path) -> Path:
    """3 tamamen farklı dosya."""
    _save_jpg(tmp_path / "x.jpg", (512, 512), "red")
    _save_jpg(tmp_path / "y.jpg", (512, 512), "blue")
    _save_jpg(tmp_path / "z.jpg", (512, 512), "green")
    return tmp_path
