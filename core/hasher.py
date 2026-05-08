"""
Hasher - MD5 and Perceptual Hash functions
"""

import hashlib
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False


class Hasher:
    """Hash calculation utilities"""

    # Supported image extensions
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

    # Available perceptual hash algorithms
    HASH_ALGORITHMS = {
        'average_hash': 'Average Hash (hızlı, genel amaçlı)',
        'phash': 'Perceptual Hash (dönüşümlere dayanıklı)',
        'dhash': 'Difference Hash (gradyan tabanlı)',
    }

    @staticmethod
    def calculate_md5(filepath: str) -> Optional[str]:
        """
        Calculate MD5 hash of a file

        Args:
            filepath: Path to the file

        Returns:
            MD5 hash string or None if error
        """
        hasher = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    @staticmethod
    def calculate_perceptual_hash(filepath: str, algorithm: str = 'average_hash'):
        """
        Calculate perceptual hash of an image

        Args:
            filepath: Path to image file
            algorithm: Hash algorithm (average_hash, phash, dhash)

        Returns:
            ImageHash object or None if error
        """
        if not IMAGEHASH_AVAILABLE:
            return None

        hash_funcs = {
            'average_hash': imagehash.average_hash,
            'phash': imagehash.phash,
            'dhash': imagehash.dhash,
        }

        hash_func = hash_funcs.get(algorithm, imagehash.average_hash)

        try:
            with Image.open(filepath) as img:
                return hash_func(img)
        except Exception:
            return None

    @staticmethod
    def is_perceptual_hash_available() -> bool:
        """Check if perceptual hashing libraries are available"""
        return IMAGEHASH_AVAILABLE

    @staticmethod
    def is_image_file(filepath: str) -> bool:
        """Check if file is a supported image format"""
        return Path(filepath).suffix.lower() in Hasher.IMAGE_EXTENSIONS
