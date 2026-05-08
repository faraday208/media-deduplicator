"""
media-deduplicator — varsayılan config değerleri.

Run-time ayarlar `run.py`'den veya `from core import scan_*` çağırırken
config dict ile geçilir. Buradakiler **fallback default'lar** — env var
override pattern'i korunuyor.
"""

import os
from pathlib import Path

# Paralel hash hesaplama worker sayısı
MAX_WORKERS = int(os.getenv("DUP_MAX_WORKERS", os.cpu_count() or 4))

# Similar scan ayarları
DEFAULT_THRESHOLD = int(os.getenv("DUP_DEFAULT_THRESHOLD", 10))
MAX_THRESHOLD = 64
DEFAULT_ALGORITHM = os.getenv("DUP_DEFAULT_ALGORITHM", "phash")  # ahash|phash|dhash|whash

# Desteklenen uzantılar
IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"
})

# Tarama timeout (saniye) — büyük dataset'lerde fallback
SCAN_TIMEOUT = int(os.getenv("DUP_SCAN_TIMEOUT", 600))

# Bu dosyanın bulunduğu dizin
BASE_DIR = Path(__file__).parent
