# media-deduplicator

> Görsel dataset'lerde duplicate tespiti — birebir (MD5) ve benzer (perceptual hash).
> Şu an **görsel** odaklı; video desteği gelecek sürümlerde planlanıyor.
> Duplicate'ları rapor eder, opsiyonel olarak `/rejected`'a taşır veya siler.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/built%20with-uv-261230)](https://github.com/astral-sh/uv)

`media-dataset-prep` pipeline'ının **02. adımı**. Standalone kullanılabilir; meta repo'ya bağlı değil.

---

## 🎯 Ne yapıyor?

İki modlu duplicate tespiti:

| Mod | Algoritma | Bulduğu |
|---|---|---|
| **`exact`** (default) | MD5 (byte-level hash) | %100 birebir aynı dosyalar |
| **`similar`** | Perceptual hash (`phash`/`ahash`/`dhash`/`whash`) | Görsel olarak benzer (resize/recompress versiyonları) |

Her duplicate grubundan **bir dosya korunur** (`--keep-strategy`), diğerleri rapor / move / delete edilir.

### Keep stratejileri

| Strateji | Hangi dosya korunur |
|---|---|
| `first` (default) | Path sırasında ilk gelen |
| `largest` | En büyük byte size |
| `smallest` | En küçük byte size |
| `highest_resolution` | En yüksek çözünürlük (width × height); tie-breaker: size |
| `best` | **BPP-aware** composite skor — aşağıda detaylı |

#### `best` stratejisi nasıl çalışır?

Naif "en yüksek çözünürlük" yanıltıcı olabilir: `1024×1024 50KB` (aşırı sıkıştırılmış, JPG artifacts) vs `512×512 200KB` (temiz). Pixel sayısı yüksek olan **bilgi olarak daha bozuk** olabilir.

`best` stratejisi **bytes-per-pixel (BPP)** ile quality göstergesi katar.
Eşikler **AI training (VAE encoder, diffusion model)** için ayarlandı — göz değil:

| BPP | Yorum | Skor cezası |
|---|---|---|
| `< 0.05` | Yıkıcı (q<10 JPG, ağır artifact) — model bile öğrenemez | **Diskalifiye** |
| `0.05 – 0.5` | Suboptimal (JPG q70 altı) — block-artifact'ler training noise olur | Orantılı (BPP/0.5) |
| `≥ 0.5` | **AI training-ready** (JPG q90+, WebP q90+, PNG) | Tam puan |

> **Niçin 0.5 eşiği?** Göz JPG q40-60'ı temiz görür ama block-artifact'leri
> diffusion model VAE encode sırasında "öğrenilecek pattern" gibi gözükür
> ve training kalitesini düşürür. AI dataset için 0.5+ baseline (q90+ veya
> lossless) önerilir.

**Skor:** 3-tuple descending — `(qualified_pixels, raw_pixels, size_bytes)`.

Senaryolar:
- Aynı görselin q40 vs q90 (aynı resolution) → q90 kazanır (size tie-breaker)
- 1024×1024 q40 (BPP 0.048, DQ) vs 512×512 q95 (BPP 0.76, tam) → 512 kazanır
- 1024×1024 q90 vs 512×512 q90 (ikisi de quality OK) → 1024 kazanır
- Tüm grup BPP < 0.05 (hepsi bozuk) → en yüksek raw_pixels kazanır (en az kötü)

**Eşik tuning:** `core/actions.py` içinde `DISQUALIFY_BPP=0.05` ve `FULL_SCORE_BPP=0.5` sabitleri. Insan-gözü kullanımı için `FULL_SCORE_BPP`'yi 0.15'e düşürebilirsin (eski default).

---

## 🚀 Kurulum

```bash
git clone https://github.com/faraday208/media-deduplicator
cd media-deduplicator
uv sync
```

veya `media-dataset-prep` workspace'i altında:

```bash
cd media-dataset-prep
make install
```

---

## 🛠️ Kullanım — CLI

### Exact duplicate (default)

```bash
uv run python run.py -i ./dataset
```

Çıktı:
- Console: özet + grup listesi
- JSON: `./dataset/duplicate_report.json`

### Similar (perceptual hash)

```bash
uv run python run.py -i ./dataset --mode similar --threshold 8 --algorithm phash
```

### Duplicate'ları taşı (undoable)

```bash
uv run python run.py -i ./dataset \
    --invalid-action move \
    --invalid-dir ./rejected \
    --keep-strategy largest
```

### Duplicate'ları sil (irreversible — onay sorar)

```bash
uv run python run.py -i ./dataset --invalid-action delete

# Onay sormadan:
uv run python run.py -i ./dataset --invalid-action delete --yes
```

### Dry-run (önizleme)

```bash
uv run python run.py -i ./dataset \
    --invalid-action move --invalid-dir ./rejected \
    --dry-run
```

### Geri al (undo)

```bash
uv run python run.py --undo ./rejected/duplicate_report.json
```

---

## 📋 Operation modes — özet

| Mod | Komut | Etki | Undo |
|---|---|---|---|
| **Sadece rapor** | `--invalid-action none` (default) | Dosyalara dokunulmaz | – |
| **Move** | `--invalid-action move --invalid-dir D` | Duplicate'lar D'ye taşınır | ✓ |
| **Delete** | `--invalid-action delete` | Duplicate'lar silinir | ✗ irreversible |
| **Dry-run** | + `--dry-run` | Rapor üretilir, fiziksel değişiklik yok | – |
| **Undo** | `--undo REPORT` | move-action geri alınır | – |

---

## 🚩 Tüm CLI flag'leri

| Flag | Tip | Default | Açıklama |
|---|---|---|---|
| `-i, --input` | str | – | Input klasörü (zorunlu, `--undo` hariç) |
| `-o, --output` | str | `<input>/duplicate_report.json` | Rapor JSON çıktısı |
| `--mode` | `exact\|similar` | `exact` | Tarama modu |
| `--recursive` / `--no-recursive` | flag | True | Alt klasörleri dahil et / etme |
| `--limit N` | int | 0 (limitsiz) | Max grup sayısı |
| `--threshold` | int | 10 | Similar Hamming distance (0-64) |
| `--algorithm` | `phash\|ahash\|dhash\|whash` | `phash` | Perceptual hash algoritması |
| `--workers N` | int | CPU count | Similar mode paralel worker |
| `--invalid-action` | `none\|move\|delete` | `none` | Duplicate aksiyonu |
| `--invalid-dir` | str | – | move için hedef |
| `--keep-strategy` | `first\|largest\|smallest\|highest_resolution\|best` | `first` | Hangi dosya korunsun |
| `--dry-run` | flag | False | Aksiyonu simüle et |
| `--yes` | flag | False | Onay sorma (delete için) |
| `--undo` | str | – | Validate raporundan undo |

---

## ⚙️ Config

Tüm parametreler **CLI flag'leri** üzerinden ayarlanır (`--threshold`, `--algorithm`, `--workers`, vs.). Tool dışı dosya tabanlı config yok — `media-validator`'dan farklı olarak deduplicator'ın tüm girdileri komut satırında.

In-process kullanımda eşikler `core/actions.py` içindeki sabitlerle ayarlanır (BPP eşikleri için `DISQUALIFY_BPP=0.05`, `FULL_SCORE_BPP=0.5`).

---

## 🔌 In-process (library) kullanım

```python
from core import (
    find_exact_duplicates, find_similar_images,
    apply_action, undo_from_report, write_report,
)

# Exact (md5)
result = find_exact_duplicates("./dataset", recursive=True)
print(f"{len(result.groups)} duplicate grubu")

# Similar (phash)
result = find_similar_images("./dataset", threshold=8, algorithm="phash")

# Aksiyon (opsiyonel)
ar = apply_action(
    result,
    action="move",
    invalid_dir="./rejected",
    keep_strategy="largest",
)
print(f"Taşınan: {len(ar.entries)}")

# Rapor + undo
write_report("./rejected/duplicate_report.json",
             scan_result=result, action_result=ar,
             recursive=True, config={"mode":"exact","algorithm":"md5"})
# undo_from_report("./rejected/duplicate_report.json")
```

`media-dataset-prep` meta UI bu yolla in-process kullanıyor — subprocess yok.

---

## 📄 Rapor formatı

```jsonc
{
  "version": "1",
  "tool": "media-deduplicator",
  "source_root": "/abs/path/to/dataset",
  "recursive": true,
  "mode": "exact",
  "config": { "mode": "exact", "threshold": null, "algorithm": "md5", "workers": null },
  "summary": {
    "total_scanned": 100,
    "unique": 87,
    "groups": 5,
    "duplicates": 13,
    "space_freeable_bytes": 12345678,
    "space_freeable_human": "11.8 MB"
  },
  "groups": [
    {
      "hash": "3cf39fdc...",
      "algorithm": "md5",
      "count": 3,
      "files": [
        {"path": "/abs/.../a1.jpg", "size_bytes": 4096},
        {"path": "/abs/.../a2.jpg", "size_bytes": 4096}
      ],
      "kept": "/abs/.../a1.jpg"
    }
  ],
  "action": "move",
  "invalid_dir": "/abs/path/to/rejected",
  "keep_strategy": "first",
  "actions": [
    {"original": "/abs/.../a2.jpg", "group_hash": "3cf...", "algorithm": "md5",
     "moved_to": "/abs/rejected/a2.jpg"}
  ],
  "skipped": 0
}
```

`actions` listesi `--undo` için kullanılır.

---

## 🧪 Test

```bash
uv sync --group dev
uv run pytest
```

---

## ⚠️ Limitations

- `--invalid-action delete` **irreversible** — silinen dosya geri gelmez.
- Similar mode için `imagehash` kütüphanesi gerekli (`uv sync` ile gelir).
- Recursive move'da invalid'ler **flat** olarak `invalid_dir`'e iner (alt klasör yapısı korunmaz). İsim çakışması için `_1`, `_2` eklenir.
- Perceptual hash false positive üretebilir — küçük/tek-renk görsellerde özellikle. Threshold'u dikkatli seç.
- Şu an sadece **görsel** duplicate (MD5 her dosyada çalışır ama anlamlı kullanım görsel için). Video duplicate (frame-level) planlı.

---

## 🏷️ Sürüm

**v1.2.0** — `FULL_SCORE_BPP` 0.15 → **0.5** (AI training context). Eşik göz-odaklı baseline'dan (JPG q70+) AI-odaklıya (JPG q90+ / lossless) yükseltildi: VAE encoder block-artifact'leri training noise olarak gözüktüğü için JPG q70 altı suboptimal. UI BPP renk eşikleri de senkron (sarı 0.05-0.5, yeşil ≥0.5). 2 yeni test (65 toplam). Insan-gözü kullanımı için sabit override edilebilir.

**v1.1.0** — `keep_strategy="best"` BPP-aware composite skor (`(qualified_pixels, raw_pixels, size_bytes)` 3-tuple). Aşırı sıkıştırılmış (BPP < 0.05) dosyalar diskalifiye; "büyük resolution ama bozuk piksel" tuzağı çözüldü. Scanner sonuçlarına `width`/`height` eklendi (sadece grup üyelerine — IO maliyet az). Bonus bugfix: similar mode `distance` field'ı `int()` cast (eski `numpy.int64` JSON serialize fail ediyordu). 22 yeni test (63 toplam).

**v1.0.0** — clean release. Convention §uyumlu refactor:
- Tek `run.py` (4 ayrı entry point birleştirildi)
- argparse + standart flag'ler
- Sidecar JSON şeması (`{tool, source_root, summary, groups, actions}`)
- Action layer (move/delete) + undo
- Paket adı `duplicate-image-finder` → `media-deduplicator` (organizer/validator ile tutarlılık)
- `config.py` API kalıntıları temizlendi
- README 8 bölüm, MIT LICENSE, 30+ test

Önceki sürümler (`duplicate-image-finder`): v0.1.0 → v4.0.0 (CHANGELOG yok, tag yok).

---

## 📜 Lisans

[MIT](LICENSE)
