"""
Duplicate Image Finder - Merkezi Konfigürasyon
Environment variable ile override edilebilir.
"""

import os
from pathlib import Path

# =============================================================================
# PARALEL İŞLEM
# =============================================================================
# Hash hesaplama için kullanılacak worker sayısı
# Default: 16 (sistemin yarısı, acımasız olmayalım)
MAX_WORKERS = int(os.getenv('DUP_MAX_WORKERS', 16))

# =============================================================================
# API AYARLARI
# =============================================================================
API_HOST = os.getenv('DUP_API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('DUP_API_PORT', 8001))

# =============================================================================
# SIMILAR SCAN AYARLARI
# =============================================================================
# Benzerlik eşiği (0 = tam eşleşme, düşük = daha benzer)
DEFAULT_THRESHOLD = int(os.getenv('DUP_DEFAULT_THRESHOLD', 10))
MAX_THRESHOLD = 64

# Default hash algoritması: phash, ahash, dhash, whash
DEFAULT_ALGORITHM = os.getenv('DUP_DEFAULT_ALGORITHM', 'phash')

# =============================================================================
# DOSYA YOLLARI
# =============================================================================
# Bu dosyanın bulunduğu dizin
BASE_DIR = Path(__file__).parent

# Raporların kaydedileceği dizin
REPORTS_DIR = Path(os.getenv('DUP_REPORTS_DIR', BASE_DIR / 'reports'))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# TIMEOUT AYARLARI (saniye)
# =============================================================================
SCAN_TIMEOUT = int(os.getenv('DUP_SCAN_TIMEOUT', 600))      # 10 dakika
DELETE_TIMEOUT = int(os.getenv('DUP_DELETE_TIMEOUT', 60))   # 1 dakika
HEALTH_CHECK_TIMEOUT = int(os.getenv('DUP_HEALTH_TIMEOUT', 5))

# =============================================================================
# DESTEKLENEN UZANTILAR
# =============================================================================
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

# =============================================================================
# LOG AYARLARI
# =============================================================================
LOG_LEVEL = os.getenv('DUP_LOG_LEVEL', 'INFO')
