# Duplicate Image Finder

A simple and efficient tool to find and remove duplicate images based on file hash comparison.

## Features

- 🔍 Scans directories for duplicate images
- 🎯 Uses MD5 hash for exact duplicate detection
- 📊 Generates detailed reports (TXT and JSON formats)
- 🗑️ Safe deletion with confirmation prompts
- 💾 Shows space that can be freed
- ⚡ Fast and efficient processing

## Supported Image Formats

- JPG/JPEG
- PNG
- GIF
- BMP
- WebP
- TIFF/TIF

## Installation

No external dependencies required! Uses only Python standard library.

Requirements:
- Python 3.8+

## Usage

### Interactive Mode (Recommended)

Run the interactive application:

```bash
python3 app.py
```

The app will:
1. Ask for directory path
2. Scan for duplicates
3. Save reports to `reports/` directory
4. Prompt if you want to delete duplicates

### Command Line Tools

#### Find Duplicates

```bash
python3 find_duplicates.py "/path/to/images"
```

This generates:
- `duplicate_report.txt` - Human-readable text report
- `duplicate_report.json` - Structured JSON report with metadata

#### Delete Duplicates

```bash
# Dry run (preview only)
python3 delete_duplicates.py duplicate_report.json

# Actually delete files
python3 delete_duplicates.py duplicate_report.json --execute
```

## How It Works

1. **Scanning**: Recursively finds all image files in the specified directory
2. **Hashing**: Calculates MD5 hash for each file
3. **Grouping**: Groups files with identical hashes
4. **Reporting**: Generates detailed reports with file info and statistics
5. **Deletion**: Keeps first existing file from each group, deletes the rest

## Reports

Reports are saved in the `reports/` directory with timestamps.

### JSON Report Structure

```json
{
  "metadata": {
    "scan_date": "2025-11-15T20:35:45",
    "scanned_directory": "/path/to/images",
    "total_images_scanned": 1469,
    "unique_images": 1277,
    "duplicate_groups": 191,
    "total_duplicate_files": 192,
    "space_can_free_mb": 168.24,
    "space_can_free_gb": 0.16
  },
  "duplicate_groups": [
    {
      "hash": "abc123...",
      "hash_algorithm": "md5",
      "count": 2,
      "files": [
        {
          "path": "/full/path/to/image1.jpg",
          "filename": "image1.jpg",
          "size_bytes": 1024000,
          "size_mb": 0.98,
          "modified_time": "2023-08-15T12:00:00",
          "created_time": "2023-08-15T12:00:00"
        }
      ]
    }
  ]
}
```

## Safety Features

- **Dry-run mode**: Preview deletions before executing
- **Double confirmation**: Requires explicit confirmation before deleting
- **First-existing keeper**: Always keeps at least one copy
- **Error handling**: Gracefully handles missing or inaccessible files
- **Detailed logging**: Shows what was kept and what was deleted

## Project Structure

```
duplicate-image-finder/
├── app.py                 # Interactive terminal application
├── find_duplicates.py     # CLI tool to find duplicates
├── delete_duplicates.py   # CLI tool to delete duplicates
├── reports/              # Generated reports (gitignored)
├── .gitignore
└── README.md
```

## Examples

### Example 1: Quick Cleanup

```bash
# Run interactive app
python3 app.py

# Enter path when prompted
# Review results
# Answer 'e' to delete duplicates
```

### Example 2: Manual Review

```bash
# Find duplicates
python3 find_duplicates.py "/home/user/Photos"

# Review the reports in reports/ directory
# If satisfied, delete
python3 delete_duplicates.py reports/duplicate_report_*.json --execute
```

## License

MIT License - Feel free to use and modify as needed.

## Contributing

This is a simple tool for personal use. Feel free to fork and enhance!
