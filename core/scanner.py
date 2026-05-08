"""
Scanner - Find duplicate and similar images
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Callable, Generator
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .hasher import Hasher

# Config import - parent directory'den
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from config import MAX_WORKERS, DEFAULT_THRESHOLD, MAX_THRESHOLD as CONFIG_MAX_THRESHOLD
except ImportError:
    MAX_WORKERS = os.cpu_count() or 4
    DEFAULT_THRESHOLD = 10
    CONFIG_MAX_THRESHOLD = 64


@dataclass
class ScanResult:
    """Result of a duplicate/similar scan"""
    total_scanned: int
    unique_count: int
    groups: List[Dict]
    space_can_free: int
    scanned_directory: str

    @property
    def has_duplicates(self) -> bool:
        return len(self.groups) > 0

    @property
    def duplicate_count(self) -> int:
        """Number of files that can be removed"""
        return sum(len(g['files']) - 1 for g in self.groups)


class DuplicateScanner:
    """Find exact duplicate images using MD5 hash"""

    def __init__(self):
        self.hasher = Hasher()

    def scan_directory(self, directory: str, recursive: bool = True) -> List[str]:
        """
        Scan directory for image files

        Args:
            directory: Path to scan
            recursive: Whether to scan subdirectories

        Returns:
            List of image file paths
        """
        image_files = []
        dir_path = Path(directory)

        if not dir_path.exists() or not dir_path.is_dir():
            return image_files

        if recursive:
            for root, _, files in os.walk(directory):
                for filename in files:
                    if Hasher.is_image_file(filename):
                        image_files.append(os.path.join(root, filename))
        else:
            for item in dir_path.iterdir():
                if item.is_file() and Hasher.is_image_file(str(item)):
                    image_files.append(str(item))

        return sorted(image_files)

    def find_duplicates(
        self,
        directory: str,
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> ScanResult:
        """
        Find exact duplicate images

        Args:
            directory: Directory to scan
            recursive: Scan subdirectories
            progress_callback: Optional callback(current, total, message)

        Returns:
            ScanResult with duplicate groups
        """
        # Scan for images
        if progress_callback:
            progress_callback(0, 0, "Resim dosyaları taranıyor...")

        image_files = self.scan_directory(directory, recursive)
        total = len(image_files)

        if total == 0:
            return ScanResult(
                total_scanned=0,
                unique_count=0,
                groups=[],
                space_can_free=0,
                scanned_directory=directory
            )

        # Calculate hashes
        hash_map = defaultdict(list)

        for idx, filepath in enumerate(image_files, 1):
            if progress_callback and (idx % 50 == 0 or idx == total):
                progress_callback(idx, total, f"Hash hesaplanıyor: {idx}/{total}")

            file_hash = Hasher.calculate_md5(filepath)
            if file_hash:
                hash_map[file_hash].append(filepath)

        # Find duplicates (groups with more than 1 file)
        groups = []
        for file_hash, files in hash_map.items():
            if len(files) > 1:
                groups.append({
                    'hash': file_hash,
                    'hash_algorithm': 'md5',
                    'files': files,
                    'count': len(files)
                })

        # Sort by count (most duplicates first)
        groups.sort(key=lambda x: x['count'], reverse=True)

        # Calculate space savings
        space_can_free = 0
        for group in groups:
            try:
                file_size = os.path.getsize(group['files'][0])
                space_can_free += file_size * (len(group['files']) - 1)
            except OSError:
                pass

        return ScanResult(
            total_scanned=total,
            unique_count=len(hash_map),
            groups=groups,
            space_can_free=space_can_free,
            scanned_directory=directory
        )

    def find_duplicates_generator(
        self,
        directory: str,
        recursive: bool = True
    ) -> Generator[Tuple[int, int, str], None, ScanResult]:
        """
        Find duplicates with generator for progress updates

        Yields:
            Tuple of (current, total, status_message)

        Returns:
            ScanResult
        """
        yield 0, 0, "Resim dosyaları taranıyor..."

        image_files = self.scan_directory(directory, recursive)
        total = len(image_files)

        if total == 0:
            yield 0, 0, "Resim dosyası bulunamadı"
            return ScanResult(
                total_scanned=0,
                unique_count=0,
                groups=[],
                space_can_free=0,
                scanned_directory=directory
            )

        yield 0, total, f"{total} resim bulundu, hash hesaplanıyor..."

        hash_map = defaultdict(list)

        for idx, filepath in enumerate(image_files, 1):
            if idx % 50 == 0 or idx == total:
                yield idx, total, f"Hash hesaplanıyor: {idx}/{total}"

            file_hash = Hasher.calculate_md5(filepath)
            if file_hash:
                hash_map[file_hash].append(filepath)

        # Build groups
        groups = []
        for file_hash, files in hash_map.items():
            if len(files) > 1:
                groups.append({
                    'hash': file_hash,
                    'hash_algorithm': 'md5',
                    'files': files,
                    'count': len(files)
                })

        groups.sort(key=lambda x: x['count'], reverse=True)

        space_can_free = 0
        for group in groups:
            try:
                file_size = os.path.getsize(group['files'][0])
                space_can_free += file_size * (len(group['files']) - 1)
            except OSError:
                pass

        return ScanResult(
            total_scanned=total,
            unique_count=len(hash_map),
            groups=groups,
            space_can_free=space_can_free,
            scanned_directory=directory
        )


class SimilarScanner:
    """Find visually similar images using perceptual hashing"""

    DEFAULT_THRESHOLD = DEFAULT_THRESHOLD  # From config
    MAX_THRESHOLD = CONFIG_MAX_THRESHOLD   # From config

    def __init__(self, max_workers: int = None):
        self.hasher = Hasher()
        self.max_workers = max_workers or MAX_WORKERS

    def scan_directory(self, directory: str, recursive: bool = True) -> List[str]:
        """Scan directory for image files"""
        return DuplicateScanner().scan_directory(directory, recursive)

    def find_similar(
        self,
        directory: str,
        threshold: int = 10,
        algorithm: str = 'average_hash',
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> ScanResult:
        """
        Find visually similar images

        Args:
            directory: Directory to scan
            threshold: Max Hamming distance (0=identical, 64=different)
            algorithm: Hash algorithm to use
            recursive: Scan subdirectories
            progress_callback: Optional callback(current, total, message)

        Returns:
            ScanResult with similar groups
        """
        if not Hasher.is_perceptual_hash_available():
            return ScanResult(
                total_scanned=0,
                unique_count=0,
                groups=[],
                space_can_free=0,
                scanned_directory=directory
            )

        # Scan for images
        if progress_callback:
            progress_callback(0, 0, "Resim dosyaları taranıyor...")

        image_files = self.scan_directory(directory, recursive)
        total = len(image_files)

        if total == 0:
            return ScanResult(
                total_scanned=0,
                unique_count=0,
                groups=[],
                space_can_free=0,
                scanned_directory=directory
            )

        # Calculate perceptual hashes in parallel
        image_hashes = {}
        completed = 0

        def calc_hash(filepath):
            return filepath, Hasher.calculate_perceptual_hash(filepath, algorithm)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(calc_hash, fp): fp for fp in image_files}

            for future in as_completed(futures):
                completed += 1
                if progress_callback and (completed % 25 == 0 or completed == total):
                    progress_callback(completed, total, f"Hash hesaplanıyor: {completed}/{total} ({self.max_workers} worker)")

                filepath, img_hash = future.result()
                if img_hash is not None:
                    image_hashes[filepath] = img_hash

        if not image_hashes:
            return ScanResult(
                total_scanned=total,
                unique_count=0,
                groups=[],
                space_can_free=0,
                scanned_directory=directory
            )

        # Find similar groups
        if progress_callback:
            progress_callback(0, len(image_hashes), "Benzerlikler karşılaştırılıyor...")

        groups = []
        processed = set()
        file_list = list(image_hashes.keys())

        for i, file1 in enumerate(file_list):
            if file1 in processed:
                continue

            if progress_callback and (i + 1) % 50 == 0:
                progress_callback(i + 1, len(file_list), f"Karşılaştırılıyor: {i+1}/{len(file_list)}")

            hash1 = image_hashes[file1]
            # First file is reference with distance 0
            group_files = [{'path': file1, 'distance': 0}]

            for file2 in file_list[i + 1:]:
                if file2 in processed:
                    continue

                hash2 = image_hashes[file2]
                distance = hash1 - hash2

                if distance <= threshold:
                    group_files.append({'path': file2, 'distance': distance})
                    processed.add(file2)

            if len(group_files) > 1:
                # Sort by distance (most similar first)
                group_files.sort(key=lambda x: x['distance'])
                groups.append({
                    'reference_hash': str(hash1),
                    'hash_algorithm': algorithm,
                    'threshold': threshold,
                    'files': group_files,
                    'similarity_count': len(group_files)
                })
                processed.add(file1)

        groups.sort(key=lambda x: x['similarity_count'], reverse=True)

        # Calculate estimated space savings
        space_can_free = 0
        for group in groups:
            sizes = []
            for file_info in group['files']:
                try:
                    sizes.append(os.path.getsize(file_info['path']))
                except OSError:
                    pass
            if sizes:
                avg_size = sum(sizes) / len(sizes)
                space_can_free += int(avg_size * (len(sizes) - 1))

        return ScanResult(
            total_scanned=total,
            unique_count=len(image_hashes),
            groups=groups,
            space_can_free=space_can_free,
            scanned_directory=directory
        )

    def find_similar_generator(
        self,
        directory: str,
        threshold: int = 10,
        algorithm: str = 'average_hash',
        recursive: bool = True
    ) -> Generator[Tuple[int, int, str], None, ScanResult]:
        """
        Find similar images with generator for progress updates

        Yields:
            Tuple of (current, total, status_message)

        Returns:
            ScanResult
        """
        if not Hasher.is_perceptual_hash_available():
            yield 0, 0, "Hata: imagehash kütüphanesi yüklü değil"
            return ScanResult(
                total_scanned=0, unique_count=0, groups=[],
                space_can_free=0, scanned_directory=directory
            )

        yield 0, 0, "Resim dosyaları taranıyor..."

        image_files = self.scan_directory(directory, recursive)
        total = len(image_files)

        if total == 0:
            yield 0, 0, "Resim dosyası bulunamadı"
            return ScanResult(
                total_scanned=0, unique_count=0, groups=[],
                space_can_free=0, scanned_directory=directory
            )

        yield 0, total, f"{total} resim bulundu, hash hesaplanıyor ({self.max_workers} worker)..."

        # Calculate perceptual hashes in parallel
        image_hashes = {}
        completed = 0

        def calc_hash(filepath):
            return filepath, Hasher.calculate_perceptual_hash(filepath, algorithm)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(calc_hash, fp): fp for fp in image_files}

            for future in as_completed(futures):
                completed += 1
                if completed % 25 == 0 or completed == total:
                    yield completed, total, f"Hash hesaplanıyor: {completed}/{total} ({self.max_workers} worker)"

                filepath, img_hash = future.result()
                if img_hash is not None:
                    image_hashes[filepath] = img_hash

        if not image_hashes:
            yield 0, 0, "Hiçbir resimden hash alınamadı"
            return ScanResult(
                total_scanned=total, unique_count=0, groups=[],
                space_can_free=0, scanned_directory=directory
            )

        yield 0, len(image_hashes), "Benzerlikler karşılaştırılıyor..."

        groups = []
        processed = set()
        file_list = list(image_hashes.keys())

        for i, file1 in enumerate(file_list):
            if file1 in processed:
                continue

            if (i + 1) % 50 == 0:
                yield i + 1, len(file_list), f"Karşılaştırılıyor: {i+1}/{len(file_list)}"

            hash1 = image_hashes[file1]
            # First file is reference with distance 0
            group_files = [{'path': file1, 'distance': 0}]

            for file2 in file_list[i + 1:]:
                if file2 in processed:
                    continue

                hash2 = image_hashes[file2]
                distance = hash1 - hash2

                if distance <= threshold:
                    group_files.append({'path': file2, 'distance': distance})
                    processed.add(file2)

            if len(group_files) > 1:
                # Sort by distance (most similar first)
                group_files.sort(key=lambda x: x['distance'])
                groups.append({
                    'reference_hash': str(hash1),
                    'hash_algorithm': algorithm,
                    'threshold': threshold,
                    'files': group_files,
                    'similarity_count': len(group_files)
                })
                processed.add(file1)

        groups.sort(key=lambda x: x['similarity_count'], reverse=True)

        space_can_free = 0
        for group in groups:
            sizes = []
            for file_info in group['files']:
                try:
                    sizes.append(os.path.getsize(file_info['path']))
                except OSError:
                    pass
            if sizes:
                avg_size = sum(sizes) / len(sizes)
                space_can_free += int(avg_size * (len(sizes) - 1))

        return ScanResult(
            total_scanned=total,
            unique_count=len(image_hashes),
            groups=groups,
            space_can_free=space_can_free,
            scanned_directory=directory
        )
