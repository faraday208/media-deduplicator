# Duplicate Image Finder

Duplicate ve benzer görselleri bulan CLI aracı. MD5 ile birebir, perceptual hash ile görsel-benzer tespiti yapar. Dataset hazırlama, fotoğraf arşivi temizleme ve media asset yönetimi için.

## Özellikler

### Exact Duplicate Detection (MD5 Hash)
- Hash tabanlı tespit — birebir aynı dosyaları bulur
- Binlerce görseli saniyeler içinde tarar
- Onay adımları ve dry-run modu
- Kazanılabilecek disk alanını gösterir

### Similar Image Detection (Perceptual Hash)
- Görsel olarak benzer resimleri bulur
- `average_hash`, `phash`, `dhash` desteği
- 0-64 arası ayarlanabilir hassasiyet eşiği
- Yeniden boyutlandırılmış / sıkıştırılmış versiyonları yakalar

### Paralel İşlem
- Multi-threaded (ThreadPoolExecutor)
- Configurable workers (varsayılan 16, env var ile ayarlanır)

## Desteklenen Formatlar

JPG/JPEG, PNG, GIF, BMP, WebP, TIFF/TIF

## Kurulum

```bash
# uv ile (önerilen)
uv sync

# veya pip ile
pip install pillow imagehash
```

## Kullanım

### 1. Interactive CLI (Önerilen)

```bash
python3 app.py
```

Uygulama sırasıyla:
1. Dizin yolunu sorar
2. Exact duplicate'ları tarar
3. Raporları `reports/` dizinine kaydeder
4. Silme onayı ister
5. Benzer resim taraması yapmak isteyip istemediğinizi sorar
6. Threshold değeri alır (0-64)

### 2. CLI Araçları

```bash
# Exact duplicate bul
python3 find_duplicates.py "/path/to/images"

# Benzer resimleri bul (threshold: 10)
python3 find_similar.py "/path/to/images" 10

# Duplicate'ları sil (dry-run)
python3 delete_duplicates.py reports/duplicate_report_*.json

# Gerçekten sil
python3 delete_duplicates.py reports/duplicate_report_*.json --execute
```

### 3. Python Kütüphanesi (in-process)

dataset-prep meta-orchestrator veya kendi Python projende doğrudan kullan:

```python
from core import DuplicateScanner, SimilarScanner, Reporter

scanner = DuplicateScanner(workers=16)
result = scanner.scan("/path/to/images")
Reporter.save_json(result, "reports/dup.json")
```

## Konfigürasyon

### Environment Variables

| Variable | Varsayılan | Açıklama |
|----------|------------|----------|
| `DUP_MAX_WORKERS` | 16 | Paralel worker sayısı |
| `DUP_DEFAULT_THRESHOLD` | 10 | Varsayılan benzerlik eşiği |
| `DUP_DEFAULT_ALGORITHM` | phash | Varsayılan hash algoritması |
| `DUP_REPORTS_DIR` | ./reports | Rapor dizini |
| `DUP_SCAN_TIMEOUT` | 600 | Tarama timeout (saniye) |
| `DUP_LOG_LEVEL` | INFO | Log seviyesi |

### config.py

Tüm ayarlar `config.py` dosyasından veya environment variable'lardan okunur.

## Hash Algoritmaları

### Exact Duplicate (MD5)
- Dosya içeriğinin byte-level hash'i
- %100 doğruluk
- Çok hızlı

### Perceptual Hash Algoritmaları

| Algoritma | Açıklama | Kullanım |
|-----------|----------|----------|
| `average_hash` | Ortalama parlaklık tabanlı | Genel amaçlı, hızlı |
| `phash` | DCT tabanlı | Dönüşümlere dayanıklı (önerilen) |
| `dhash` | Gradyan tabanlı | Kenar tespiti için iyi |

## Benzerlik Threshold Rehberi

| Threshold | Benzerlik | Kullanım |
|-----------|-----------|----------|
| 0-5 | Çok benzer (strict) | Neredeyse aynı resimler |
| 6-10 | Benzer (önerilen) | Küçük düzenlemeler, sıkıştırma |
| 11-15 | Biraz benzer | Farklı crop, boyut |
| 16+ | Gevşek | False positive riski yüksek |

**Hamming Distance:**
- 0 = Birebir aynı
- Düşük = Daha benzer
- Yüksek = Daha farklı
- Maksimum = 64

## Akıllı Silme Stratejileri

`Reporter` ve `delete_duplicates.py` için `keep_strategy` seçenekleri:

| Strateji | Açıklama |
|----------|----------|
| `first` | Gruptaki ilk dosyayı tut (varsayılan) |
| `largest` | En büyük dosyayı tut (byte size) |
| `smallest` | En küçük dosyayı tut |
| `highest_resolution` | En yüksek çözünürlüğü tut |
| `best` | En iyi kalite (resolution + size) |

## Proje Yapısı

```
duplicate-image-finder/
├── core/
│   ├── __init__.py
│   ├── hasher.py            # MD5 ve perceptual hash fonksiyonları
│   ├── scanner.py           # DuplicateScanner, SimilarScanner sınıfları
│   └── reporter.py          # JSON/TXT rapor oluşturma
├── reports/                 # Oluşturulan raporlar (gitignore)
├── app.py                   # Interactive CLI uygulaması
├── find_duplicates.py       # CLI: Exact duplicate bulma
├── find_similar.py          # CLI: Benzer resim bulma
├── delete_duplicates.py     # CLI: Duplicate silme
├── config.py                # Merkezi konfigürasyon
├── pyproject.toml           # uv / pip bağımlılıkları
└── README.md
```

## Rapor Formatları

### Duplicate Report (JSON)

```json
{
  "metadata": {
    "scan_date": "2025-11-15T20:35:45",
    "scanned_directory": "/path/to/images",
    "total_images_scanned": 1469,
    "unique_images": 1277,
    "duplicate_groups": 191,
    "total_duplicate_files": 192,
    "space_can_free_mb": 168.24
  },
  "duplicate_groups": [
    {
      "hash": "abc123...",
      "hash_algorithm": "md5",
      "count": 2,
      "files": [
        {
          "path": "/path/to/file1.jpg",
          "filename": "file1.jpg",
          "size_bytes": 1024000,
          "size_mb": 1.0,
          "width": 1920,
          "height": 1080,
          "resolution": "1920x1080"
        }
      ]
    }
  ]
}
```

### Similar Report (JSON)

```json
{
  "metadata": {
    "scan_date": "2025-11-15T21:18:53",
    "scanned_directory": "/path/to/images",
    "similarity_threshold": 10,
    "hash_algorithm": "phash",
    "total_images_scanned": 1277,
    "similar_groups_found": 371,
    "removable_files": 701,
    "estimated_space_mb": 458.25
  },
  "similar_groups": [
    {
      "reference_hash": "8f8f8f8f8f8f8f8f",
      "similarity_count": 3,
      "files": [
        {"path": "/path/to/file1.jpg", "distance": 0},
        {"path": "/path/to/file2.jpg", "distance": 5}
      ]
    }
  ]
}
```

## Güvenlik Özellikleri

- Dry-run modu (silmeden önce simülasyon)
- Çift onay (CLI'da iki aşamalı)
- İlk dosyayı tut (her gruptan en az bir kopya kalır)
- Erişilemeyen dosyaları atlar
- Detaylı loglama

## Performans

### Exact Duplicate Detection
| Dosya Sayısı | Süre |
|--------------|------|
| 1,000 | ~5-10 saniye |
| 5,000 | ~30-60 saniye |
| 10,000 | ~1-2 dakika |

### Similar Image Detection (16 worker)
| Dosya Sayısı | Süre |
|--------------|------|
| 1,000 | ~20-40 saniye |
| 5,000 | ~2-3 dakika |
| 10,000 | ~5-8 dakika |

*Performans sistem özelliklerine göre değişir*

## Kullanım Senaryoları

### Dataset Hazırlama
- ML/AI training set'lerinden duplicate temizleme
- Veri artırma sonrası benzer görsel tespiti

### Fotoğraf Arşivi
- Burst mode çekimlerden duplicate temizleme
- Aynı oturumdan benzer fotoğrafları bulma

### Content Management
- Media asset'lerden duplicate kaldırma
- Yeniden boyutlandırılmış versiyonları tespit etme

## Sorun Giderme

**"imagehash library not available"**
```bash
uv sync   # veya: pip install imagehash Pillow
```

**Çok fazla false positive**
- Threshold değerini düşürün (5-8 arası deneyin)
- `phash` algoritmasını kullanın

**Benzer resimler bulunamıyor**
- Threshold değerini artırın (12-15 arası)

**Permission hatası**
- Hedef dizinde yazma izni kontrolü
- `reports/` dizininin yazılabilir olduğundan emin olun

## Sınırlamalar

- Benzer resim tespiti ek kütüphane gerektirir (imagehash, Pillow)
- Perceptual hash false positive/negative üretebilir
- Çok büyük resimler (>50MB) daha uzun sürer
- Benzer resimler için otomatik silme önerilmez (manuel inceleme gerekli)

## Version History

### v4.0.0 - Saf Kütüphane / CLI
- REST API kaldırıldı (in-process import paterni)
- FastAPI/Uvicorn/Pydantic dependency'leri silindi
- `core/` modülü Python kütüphanesi olarak kullanılır
- Gradio UI ve dataset-prep meta-orchestrator için import edilebilir

### v3.0.0 - Paralel İşlem
- Paralel hash hesaplama (ThreadPoolExecutor)
- Akıllı silme stratejileri (largest, smallest, best, highest_resolution)
- Merkezi konfigürasyon (config.py)
- Çoklu hash algoritması desteği (phash, dhash, average_hash)

### v2.0.0 - Similar Image Detection
- Perceptual hash tabanlı benzer resim tespiti
- `find_similar.py` CLI aracı
- Interactive threshold seçimi

### v1.0.0 - Initial Release
- MD5 hash ile exact duplicate tespiti
- Interactive ve CLI modları
- Güvenli silme onay adımları

## Lisans

MIT License — Serbestçe kullanın ve değiştirin.
