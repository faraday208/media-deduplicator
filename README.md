# Duplicate Image Finder

Duplicate ve benzer görselleri bulan, REST API ve CLI desteği sunan güçlü bir araç. Dataset hazırlama, fotoğraf arşivi temizleme ve media asset yönetimi için ideal.

## Özellikler

### Exact Duplicate Detection (MD5 Hash)
- **Hash tabanlı tespit**: MD5 hash ile birebir aynı dosyaları bulur
- **Hızlı işlem**: Binlerce görseli saniyeler içinde tarar
- **Güvenli silme**: Onay adımları ve dry-run modu
- **Alan takibi**: Kazanılabilecek disk alanını gösterir

### Similar Image Detection (Perceptual Hash)
- **Görsel benzerlik**: Perceptual hash ile görsel olarak benzer resimleri bulur
- **Çoklu algoritma**: `average_hash`, `phash`, `dhash` desteği
- **Ayarlanabilir eşik**: 0-64 arası hassasiyet kontrolü
- **Varyasyon tespiti**: Yeniden boyutlandırılmış, sıkıştırılmış versiyonları yakalar

### REST API (FastAPI)
- **HTTP endpoint'leri**: Gradio UI ve diğer tüketiciler için
- **Async task desteği**: Büyük dizinler için arka plan tarama
- **Progress tracking**: Task ilerleme durumu takibi
- **Swagger UI**: Interaktif API dokümantasyonu (`/docs`)

### Paralel İşlem
- **Multi-threaded**: ThreadPoolExecutor ile paralel hash hesaplama
- **Configurable workers**: Varsayılan 16 worker, environment variable ile ayarlanabilir

## Desteklenen Formatlar

JPG/JPEG, PNG, GIF, BMP, WebP, TIFF/TIF

## Kurulum

### Temel Kurulum

```bash
cd 02-duplicate

# Virtual environment oluştur
python3 -m venv venv

# Aktifleştir
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate     # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### Gereksinimler

```
Python 3.8+
Pillow>=10.0.0
imagehash>=4.3.1
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
```

## Kullanım

### 1. Interactive CLI (Önerilen)

```bash
source venv/bin/activate
python3 app.py
```

Uygulama sırasıyla:
1. Dizin yolunu sorar
2. Exact duplicate'ları tarar
3. Raporları `reports/` dizinine kaydeder
4. Silme onayı ister
5. Benzer resim taraması yapmak isteyip istemediğinizi sorar
6. Threshold değeri alır (0-64)

### 2. REST API Server

```bash
# API'yi başlat
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# veya
python -m api.main
```

**API Endpoints:**

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |
| `POST` | `/api/v1/scan/duplicates` | Senkron duplicate tarama |
| `POST` | `/api/v1/scan/duplicates/async` | Asenkron duplicate tarama |
| `POST` | `/api/v1/scan/similar` | Senkron benzer resim tarama |
| `POST` | `/api/v1/scan/similar/async` | Asenkron benzer resim tarama |
| `POST` | `/api/v1/delete` | Dosya silme |
| `POST` | `/api/v1/delete/from-groups` | Gruplardan akıllı silme |
| `GET` | `/api/v1/reports` | Raporları listele |
| `GET` | `/api/v1/reports/{filename}` | Rapor detayı |
| `GET` | `/api/v1/tasks/{task_id}` | Task durumu |

**Örnek API Çağrıları:**

```bash
# Duplicate tarama
curl -X POST http://localhost:8001/api/v1/scan/duplicates \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/images", "recursive": true}'

# Benzer resim tarama
curl -X POST http://localhost:8001/api/v1/scan/similar \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/images", "threshold": 10, "algorithm": "phash"}'

# Akıllı silme (en büyük dosyayı tut)
curl -X POST http://localhost:8001/api/v1/delete/from-groups \
  -H "Content-Type: application/json" \
  -d '{"groups": [...], "keep_strategy": "largest", "dry_run": false}'
```

### 3. CLI Araçları

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

## HTTP API Kullanımı

```
Method: POST
URL: http://localhost:8001/api/v1/scan/duplicates
Body Content Type: JSON
Body: {"directory": "/path/to/images"}
```

Detaylı endpoint dokümantasyonu için Swagger UI: `http://localhost:8001/docs`

## Konfigürasyon

### Environment Variables

| Variable | Varsayılan | Açıklama |
|----------|------------|----------|
| `DUP_MAX_WORKERS` | 16 | Paralel worker sayısı |
| `DUP_API_HOST` | 0.0.0.0 | API host |
| `DUP_API_PORT` | 8001 | API port |
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

`/api/v1/delete/from-groups` endpoint'i için `keep_strategy` seçenekleri:

| Strateji | Açıklama |
|----------|----------|
| `first` | Gruptaki ilk dosyayı tut (varsayılan) |
| `largest` | En büyük dosyayı tut (byte size) |
| `smallest` | En küçük dosyayı tut |
| `highest_resolution` | En yüksek çözünürlüğü tut |
| `best` | En iyi kalite (resolution + size) |

## Proje Yapısı

```
02-duplicate/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI REST API
│   └── schemas.py           # Pydantic request/response modelleri
├── core/
│   ├── __init__.py
│   ├── hasher.py            # MD5 ve perceptual hash fonksiyonları
│   ├── scanner.py           # DuplicateScanner, SimilarScanner sınıfları
│   └── reporter.py          # JSON/TXT rapor oluşturma
├── scripts/
│   └── restart-api.sh       # API restart script
├── reports/                 # Oluşturulan raporlar (gitignore)
├── venv/                    # Virtual environment (gitignore)
├── app.py                   # Interactive CLI uygulaması
├── find_duplicates.py       # CLI: Exact duplicate bulma
├── find_similar.py          # CLI: Benzer resim bulma
├── delete_duplicates.py     # CLI: Duplicate silme
├── config.py                # Merkezi konfigürasyon
├── requirements.txt         # Python bağımlılıkları
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
        {
          "path": "/path/to/file1.jpg",
          "distance": 0
        },
        {
          "path": "/path/to/file2.jpg",
          "distance": 5
        }
      ]
    }
  ]
}
```

## Güvenlik Özellikleri

- **Dry-run modu**: Silmeden önce simülasyon
- **Çift onay**: CLI'da iki aşamalı onay
- **İlk dosyayı tut**: Her gruptan en az bir kopya kalır
- **Hata yönetimi**: Erişilemeyen dosyaları atlar
- **Detaylı loglama**: Tutulan ve silinen dosyalar listelenir

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
- Arşivleme öncesi organizasyon

### Content Management
- Media asset'lerden duplicate kaldırma
- Yeniden boyutlandırılmış versiyonları tespit etme
- Web optimizasyonu öncesi temizlik

### Backup Temizliği
- Yedek klasörlerden duplicate bulma
- Disk alanı optimizasyonu

## Sorun Giderme

**"imagehash library not available"**
```bash
source venv/bin/activate
pip install imagehash Pillow
```

**Çok fazla false positive**
- Threshold değerini düşürün (5-8 arası deneyin)
- `phash` algoritmasını kullanın

**Benzer resimler bulunamıyor**
- Threshold değerini artırın (12-15 arası)

**API başlamıyor**
```bash
# Port kontrolü
lsof -i :8001

# Restart
./scripts/restart-api.sh
```

**Permission hatası**
- Hedef dizinde yazma izni kontrolü
- `reports/` dizininin yazılabilir olduğundan emin olun

## Sınırlamalar

- Benzer resim tespiti ek kütüphane gerektirir (imagehash, Pillow)
- Perceptual hash false positive/negative üretebilir
- Çok büyük resimler (>50MB) daha uzun sürer
- Benzer resimler için otomatik silme önerilmez (manuel inceleme gerekli)

## API vs CLI Karşılaştırması

| Özellik | CLI | API |
|---------|-----|-----|
| Interaktivite | Yüksek | Gradio UI üstünden |
| Multi-tüketici | Tek terminal | Paralel istemci |
| Progress Tracking | Terminal | Task endpoint |
| Batch İşlem | Sınırlı | Kolay |

## Version History

### v3.0.0 - REST API & Paralel İşlem
- FastAPI REST API eklendi
- Paralel hash hesaplama (ThreadPoolExecutor)
- Async task desteği ve progress tracking
- Akıllı silme stratejileri (largest, smallest, best, highest_resolution)
- Merkezi konfigürasyon (config.py)
- Çoklu hash algoritması desteği (phash, dhash, average_hash)
- Pydantic schema'ları ile tip güvenliği

### v2.0.0 - Similar Image Detection
- Perceptual hash tabanlı benzer resim tespiti
- `find_similar.py` CLI aracı
- Interactive threshold seçimi
- Virtual environment desteği

### v1.0.0 - Initial Release
- MD5 hash ile exact duplicate tespiti
- Interactive ve CLI modları
- Güvenli silme onay adımları
- JSON ve TXT raporları

## Lisans

MIT License - Serbestçe kullanın ve değiştirin.

## Katkıda Bulunma

Fork yapın ve geliştirin! Öneriler memnuniyetle karşılanır.

---

**Dataset temizleme ve görsel arşiv yönetimi için güçlü bir araç.**
