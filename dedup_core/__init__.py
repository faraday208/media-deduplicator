"""media-deduplicator — public API.

In-process kullanım için:
    from core import (
        find_exact_duplicates, find_similar_images, collect_images,
        apply_action, undo_from_report, write_report,
        DuplicateGroup, ScanResult,
    )
"""
from .actions import (
    ActionEntry,
    ActionResult,
    apply_action,
    undo_from_report,
)
from .hasher import Hasher
from .reporter import (
    DEFAULT_REPORT_NAME,
    EXACT_REPORT_NAME,
    REPORT_TOOL,
    REPORT_VERSION,
    SIMILAR_REPORT_NAME,
    humanize_bytes,
    report_name_for_mode,
    write_report,
)
from .scanner import (
    DEFAULT_IMAGE_EXTS,
    DuplicateGroup,
    ScanResult,
    collect_images,
    find_exact_duplicates,
    find_similar_images,
)

__all__ = [
    # Scanner
    "collect_images",
    "find_exact_duplicates",
    "find_similar_images",
    "DuplicateGroup",
    "ScanResult",
    "DEFAULT_IMAGE_EXTS",
    # Actions
    "apply_action",
    "undo_from_report",
    "ActionEntry",
    "ActionResult",
    # Reporter
    "write_report",
    "humanize_bytes",
    "report_name_for_mode",
    "DEFAULT_REPORT_NAME",
    "EXACT_REPORT_NAME",
    "SIMILAR_REPORT_NAME",
    "REPORT_TOOL",
    "REPORT_VERSION",
    # Hasher
    "Hasher",
]
