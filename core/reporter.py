"""
Reporter - Save scan results as JSON and TXT reports
Always saves report, even if no duplicates found (clean report)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from PIL import Image

from .scanner import ScanResult

# Config import
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from config import REPORTS_DIR as CONFIG_REPORTS_DIR
except ImportError:
    CONFIG_REPORTS_DIR = Path(__file__).parent.parent / "reports"


class Reporter:
    """Save and manage scan reports"""

    DEFAULT_REPORTS_DIR = CONFIG_REPORTS_DIR

    def __init__(self, reports_dir: Optional[Path] = None):
        self.reports_dir = Path(reports_dir) if reports_dir else self.DEFAULT_REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format bytes to human readable string"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"

    @staticmethod
    def get_file_info(filepath: str) -> Dict:
        """Get detailed file information including resolution"""
        try:
            stat_info = os.stat(filepath)
            info = {
                'path': filepath,
                'filename': os.path.basename(filepath),
                'size_bytes': stat_info.st_size,
                'size_mb': stat_info.st_size / (1024 * 1024),
                'modified_time': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                'created_time': datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                'exists': True
            }
            # Add resolution info
            try:
                with Image.open(filepath) as img:
                    info['width'] = img.width
                    info['height'] = img.height
                    info['resolution'] = f"{img.width}x{img.height}"
            except:
                info['width'] = 0
                info['height'] = 0
                info['resolution'] = "N/A"
            return info
        except Exception as e:
            return {
                'path': filepath,
                'filename': os.path.basename(filepath),
                'error': str(e),
                'exists': False,
                'width': 0,
                'height': 0,
                'resolution': "N/A"
            }

    def save_duplicate_report(
        self,
        result: ScanResult,
        prefix: str = "duplicate_report"
    ) -> Tuple[str, str]:
        """
        Save exact duplicate scan report
        Always saves, even if no duplicates (clean report)

        Args:
            result: ScanResult from DuplicateScanner
            prefix: Filename prefix

        Returns:
            Tuple of (json_path, txt_path)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.reports_dir / f"{prefix}_{timestamp}.json"
        txt_path = self.reports_dir / f"{prefix}_{timestamp}.txt"

        # Build JSON report
        report = {
            'metadata': {
                'report_type': 'duplicate',
                'scan_date': datetime.now().isoformat(),
                'scanned_directory': result.scanned_directory,
                'total_images_scanned': result.total_scanned,
                'unique_images': result.unique_count,
                'duplicate_groups': len(result.groups),
                'total_duplicate_files': result.duplicate_count,
                'space_can_free_bytes': result.space_can_free,
                'space_can_free_mb': result.space_can_free / (1024 ** 2),
                'space_can_free_gb': result.space_can_free / (1024 ** 3),
                'is_clean': not result.has_duplicates
            },
            'duplicate_groups': []
        }

        for group in result.groups:
            group_data = {
                'hash': group['hash'],
                'hash_algorithm': group.get('hash_algorithm', 'md5'),
                'count': group['count'],
                'files': [self.get_file_info(f) for f in group['files']]
            }
            report['duplicate_groups'].append(group_data)

        # Save JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Save TXT
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("DUPLICATE IMAGES REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Tarama Tarihi: {report['metadata']['scan_date']}\n")
            f.write(f"Taranan Klasör: {result.scanned_directory}\n")
            f.write(f"Toplam Resim: {result.total_scanned}\n")
            f.write(f"Unique Resim: {result.unique_count}\n")
            f.write(f"Duplicate Grup: {len(result.groups)}\n")
            f.write(f"Silinebilecek Dosya: {result.duplicate_count}\n")
            f.write(f"Kazanılabilecek Alan: {self.format_size(result.space_can_free)}\n\n")

            if result.has_duplicates:
                f.write("-" * 80 + "\n")
                f.write("DUPLICATE GRUPLAR\n")
                f.write("-" * 80 + "\n")

                for idx, group in enumerate(result.groups, 1):
                    f.write(f"\nGrup {idx}: {group['count']} aynı dosya\n")
                    f.write(f"Hash: {group['hash']}\n")
                    f.write("Dosyalar:\n")
                    for filepath in group['files']:
                        info = self.get_file_info(filepath)
                        size = self.format_size(info.get('size_bytes', 0))
                        f.write(f"  - {info['filename']} ({size})\n")
                        f.write(f"    {filepath}\n")
            else:
                f.write("-" * 80 + "\n")
                f.write("SONUÇ: TEMİZ\n")
                f.write("-" * 80 + "\n")
                f.write("\nBu klasörde duplicate resim bulunamadı.\n")
                f.write("Tüm resimler benzersiz.\n")

        return str(json_path), str(txt_path)

    def save_similar_report(
        self,
        result: ScanResult,
        threshold: int = 10,
        algorithm: str = 'average_hash',
        prefix: str = "similar_report"
    ) -> Tuple[str, str]:
        """
        Save similar images scan report
        Always saves, even if no similar images (clean report)

        Args:
            result: ScanResult from SimilarScanner
            threshold: Similarity threshold used
            algorithm: Hash algorithm used
            prefix: Filename prefix

        Returns:
            Tuple of (json_path, txt_path)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.reports_dir / f"{prefix}_{timestamp}.json"
        txt_path = self.reports_dir / f"{prefix}_{timestamp}.txt"

        total_similar = sum(g.get('similarity_count', len(g['files'])) for g in result.groups)
        removable = sum(g.get('similarity_count', len(g['files'])) - 1 for g in result.groups)

        # Build JSON report
        report = {
            'metadata': {
                'report_type': 'similar',
                'scan_date': datetime.now().isoformat(),
                'scanned_directory': result.scanned_directory,
                'similarity_threshold': threshold,
                'hash_algorithm': algorithm,
                'total_images_scanned': result.total_scanned,
                'images_processed': result.unique_count,
                'similar_groups_found': len(result.groups),
                'total_similar_files': total_similar,
                'removable_files': removable,
                'estimated_space_bytes': result.space_can_free,
                'estimated_space_mb': result.space_can_free / (1024 ** 2),
                'estimated_space_gb': result.space_can_free / (1024 ** 3),
                'is_clean': not result.has_duplicates
            },
            'similar_groups': []
        }

        for group in result.groups:
            # Files now have distance info: {'path': ..., 'distance': ...}
            files_with_info = []
            for f in group['files']:
                file_info = self.get_file_info(f['path'])
                # Convert numpy int to Python int for JSON serialization
                file_info['distance'] = int(f.get('distance', 0))
                files_with_info.append(file_info)

            group_data = {
                'reference_hash': group.get('reference_hash', ''),
                'similarity_count': group.get('similarity_count', len(group['files'])),
                'files': files_with_info
            }
            report['similar_groups'].append(group_data)

        # Save JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Save TXT
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("SIMILAR IMAGES REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Tarama Tarihi: {report['metadata']['scan_date']}\n")
            f.write(f"Taranan Klasör: {result.scanned_directory}\n")
            f.write(f"Benzerlik Eşiği: {threshold}\n")
            f.write(f"Hash Algoritması: {algorithm}\n")
            f.write(f"Toplam Resim: {result.total_scanned}\n")
            f.write(f"İşlenen Resim: {result.unique_count}\n")
            f.write(f"Benzer Grup: {len(result.groups)}\n")
            f.write(f"Silinebilecek Dosya: {removable}\n")
            f.write(f"Tahmini Kazanç: {self.format_size(result.space_can_free)}\n\n")

            if result.has_duplicates:
                f.write("-" * 80 + "\n")
                f.write("BENZER RESİM GRUPLARI\n")
                f.write("-" * 80 + "\n")

                for idx, group in enumerate(result.groups, 1):
                    count = group.get('similarity_count', len(group['files']))
                    f.write(f"\nGrup {idx}: {count} benzer resim\n")
                    f.write(f"Referans Hash: {group.get('reference_hash', 'N/A')}\n")
                    f.write("Dosyalar:\n")
                    for file_info in group['files']:
                        filepath = file_info['path']
                        distance = file_info.get('distance', 0)
                        info = self.get_file_info(filepath)
                        size = self.format_size(info.get('size_bytes', 0))
                        dist_str = f" [mesafe: {distance}]" if distance > 0 else " [referans]"
                        f.write(f"  - {info['filename']} ({size}){dist_str}\n")
                        f.write(f"    {filepath}\n")
            else:
                f.write("-" * 80 + "\n")
                f.write("SONUÇ: TEMİZ\n")
                f.write("-" * 80 + "\n")
                f.write(f"\nBu klasörde benzer resim bulunamadı (eşik: {threshold}).\n")
                f.write("Tüm resimler görsel olarak benzersiz.\n")

        return str(json_path), str(txt_path)

    def get_reports(self, report_type: Optional[str] = None) -> List[Dict]:
        """
        List available reports

        Args:
            report_type: Filter by 'duplicate', 'similar', or None for all

        Returns:
            List of report metadata
        """
        reports = []

        for filepath in self.reports_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                metadata = data.get('metadata', {})
                rtype = metadata.get('report_type', 'unknown')

                if report_type and rtype != report_type:
                    continue

                reports.append({
                    'filename': filepath.name,
                    'filepath': str(filepath),
                    'type': rtype,
                    'scan_date': metadata.get('scan_date', 'N/A'),
                    'scanned_directory': metadata.get('scanned_directory', 'N/A'),
                    'total_scanned': metadata.get('total_images_scanned', 0),
                    'groups_found': metadata.get('duplicate_groups', metadata.get('similar_groups_found', 0)),
                    'is_clean': metadata.get('is_clean', False),
                    'space_mb': metadata.get('space_can_free_mb', metadata.get('estimated_space_mb', 0)),
                })
            except (json.JSONDecodeError, IOError):
                continue

        reports.sort(key=lambda x: x['scan_date'], reverse=True)
        return reports

    def load_report(self, filename: str) -> Optional[Dict]:
        """Load a report by filename"""
        filepath = self.reports_dir / filename
        if not filepath.exists():
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def delete_report(self, filename: str) -> Tuple[bool, str]:
        """Delete a report (both JSON and TXT)"""
        json_path = self.reports_dir / filename
        txt_path = self.reports_dir / filename.replace('.json', '.txt')

        deleted = []
        for path in [json_path, txt_path]:
            if path.exists():
                try:
                    os.remove(path)
                    deleted.append(path.name)
                except Exception as e:
                    return False, f"Silme hatası: {e}"

        if deleted:
            return True, f"Silindi: {', '.join(deleted)}"
        return False, "Silinecek dosya bulunamadı"
