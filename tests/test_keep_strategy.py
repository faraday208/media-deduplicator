"""keep_strategy senaryoları, özellikle BPP-aware 'best'."""
from core.actions import (
    DISQUALIFY_BPP,
    FULL_SCORE_BPP,
    _best_score,
    _bpp,
    _pick_best,
    _pick_keeper,
)


def _f(path: str, w: int = 0, h: int = 0, size: int = 0) -> dict:
    return {"path": path, "width": w, "height": h, "size_bytes": size}


# ---------- _bpp ----------

def test_bpp_zero_when_no_dimensions():
    assert _bpp(_f("x", size=1000)) == 0.0


def test_bpp_normal():
    # 100×100 (10K pix), 5KB → 0.5 BPP
    f = _f("x", w=100, h=100, size=5000)
    assert _bpp(f) == 0.5


# ---------- _best_score yapı ----------

def test_best_score_tuple_structure():
    f = _f("x", w=512, h=512, size=200_000)  # BPP ≈ 0.76 → tam puan
    score = _best_score(f)
    assert score == (262144, 262144, 200_000)
    # qualified_pixels == raw_pixels (BPP yüksek olduğu için ceza yok)


def test_best_score_no_dimensions_returns_size_only():
    f = _f("x", size=5000)
    assert _best_score(f) == (0, 0, 5000)


def test_best_score_disqualified_bpp():
    # 1024×1024 (1M pix), 50KB → BPP = 0.048 → < DISQUALIFY_BPP (0.05)
    f = _f("x", w=1024, h=1024, size=50_000)
    score = _best_score(f)
    assert score[0] == 0  # qualified=0 (diskalifiye)
    assert score[1] == 1024 * 1024  # raw_pixels yine var
    assert score[2] == 50_000


def test_best_score_partial_penalty():
    # 800×600 (480K pix), BPP=0.10 → factor = 0.10/0.15 ≈ 0.667
    f = _f("x", w=800, h=600, size=48_000)
    qualified, raw, size = _best_score(f)
    assert raw == 480_000
    # qualified ≈ 480000 × 0.667 ≈ 320000 (±1)
    assert 318_000 <= qualified <= 322_000


# ---------- senaryolar — kullanıcının BPP argümanı ----------

def test_best_picks_clean_lower_res_over_artifacted_high_res():
    """Kullanıcının orijinal noktası: 1024×1024 q40 (artifact) vs 512×512 q95 (temiz).
    1024'ün BPP=0.048 (DISQUALIFY altı) → diskalifiye, 512 kazanır."""
    files = [
        _f("/big_artifact.jpg", w=1024, h=1024, size=50_000),   # BPP 0.048 → DQ
        _f("/small_clean.jpg",  w=512,  h=512,  size=200_000),  # BPP 0.76 → tam
    ]
    assert _pick_best(files) == 1  # küçük + temiz kazandı


def test_best_picks_high_res_when_quality_acceptable():
    """1024 ve 512 ikisi de quality OK → resolution kazanır (downscale her zaman var)."""
    files = [
        _f("/big_clean.jpg",   w=1024, h=1024, size=300_000),  # BPP 0.29 → tam
        _f("/small_clean.jpg", w=512,  h=512,  size=80_000),   # BPP 0.30 → tam
    ]
    assert _pick_best(files) == 0


def test_best_picks_higher_quality_when_same_resolution():
    """Aynı resolution → daha yüksek quality (size) kazanır."""
    files = [
        _f("/q60.jpg", w=1024, h=1024, size=80_000),   # BPP 0.076 → ceza
        _f("/q90.jpg", w=1024, h=1024, size=300_000),  # BPP 0.29 → tam
    ]
    assert _pick_best(files) == 1


def test_best_size_only_fallback_when_no_dimensions():
    """Width/height eksikse (PIL.Image.open hata verdiyse) → size'a düşer."""
    files = [
        _f("/a.jpg", size=10_000),
        _f("/b.jpg", size=50_000),
    ]
    assert _pick_best(files) == 1


def test_best_all_disqualified_picks_least_bad():
    """Tüm dosyalar BPP < 0.05 ise (hepsi bozuk) en yüksek raw_pixels kazanır."""
    files = [
        _f("/tiny_artifact.jpg",  w=512,  h=512,  size=10_000),   # BPP 0.038
        _f("/big_artifact.jpg",   w=2048, h=2048, size=150_000),  # BPP 0.036
    ]
    # İkisi de qualified=0; raw_pixels: 2048×2048 > 512×512 → büyük olan
    assert _pick_best(files) == 1


# ---------- diğer stratejiler — regression ----------

def test_first_strategy():
    files = [_f("a", size=10), _f("b", size=100)]
    assert _pick_keeper(files, "first") == 0


def test_largest_strategy():
    files = [_f("a", size=10), _f("b", size=100), _f("c", size=50)]
    assert _pick_keeper(files, "largest") == 1


def test_smallest_strategy():
    files = [_f("a", size=10), _f("b", size=100), _f("c", size=50)]
    assert _pick_keeper(files, "smallest") == 0


def test_highest_resolution_strategy():
    """Naif resolution; tie-breaker size."""
    files = [
        _f("/512.jpg",  w=512,  h=512,  size=200_000),
        _f("/1024.jpg", w=1024, h=1024, size=50_000),
    ]
    # highest_resolution **naif** — quality umrunda değil, sadece pixel
    assert _pick_keeper(files, "highest_resolution") == 1


def test_highest_resolution_tie_breaker_size():
    """Aynı resolution → size tie-breaker."""
    files = [
        _f("/q60.jpg", w=1024, h=1024, size=50_000),
        _f("/q90.jpg", w=1024, h=1024, size=300_000),
    ]
    assert _pick_keeper(files, "highest_resolution") == 1
