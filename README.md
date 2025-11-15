# Duplicate Image Finder

A powerful tool to find and remove duplicate and similar images using hash comparison and perceptual hashing.

## Features

### Exact Duplicate Detection
- 🔍 **Hash-based detection**: Uses MD5 hash for exact duplicate detection
- ⚡ **Fast processing**: Handles thousands of images efficiently
- 🗑️ **Safe deletion**: Confirmation prompts and dry-run mode
- 💾 **Space tracking**: Shows how much space can be freed

### Similar Image Detection (NEW!)
- 🎨 **Perceptual hashing**: Finds visually similar images
- 📏 **Adjustable threshold**: Control similarity sensitivity (0-64)
- 🔄 **Catches variations**: Finds resized, compressed, or slightly edited versions
- 📊 **Detailed reports**: Separate reports for similar images

### General Features
- 📊 **Dual reports**: TXT and JSON formats with timestamps
- 🔒 **Safe operation**: Multiple confirmation steps
- 📁 **Organized output**: All reports saved to `reports/` directory
- 🖥️ **Interactive app**: User-friendly terminal interface

## Supported Image Formats

JPG/JPEG, PNG, GIF, BMP, WebP, TIFF/TIF

## Installation

### Basic Installation (Exact Duplicates Only)

No external dependencies required! Uses only Python standard library.

```bash
# Clone or download the project
cd duplicate-image-finder
```

### Full Installation (Including Similar Image Detection)

For similar image detection, install additional dependencies:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

**Requirements:**
- Python 3.8+
- Pillow (for similar detection)
- imagehash (for similar detection)

## Usage

### Interactive Mode (Recommended)

Run the interactive application:

```bash
# Without venv (exact duplicates only)
python3 app.py

# With venv (exact + similar detection)
source venv/bin/activate
python3 app.py
```

**The app will:**
1. Ask for directory path
2. Scan for exact duplicates
3. Save reports to `reports/` directory
4. Prompt if you want to delete duplicates
5. Ask if you want to scan for similar images
6. If yes, ask for similarity threshold (0-64)
7. Save similar image reports

### Command Line Tools

#### 1. Find Exact Duplicates

```bash
python3 find_duplicates.py "/path/to/images"
```

**Output:**
- `reports/duplicate_report_TIMESTAMP.txt`
- `reports/duplicate_report_TIMESTAMP.json`

#### 2. Find Similar Images

```bash
python3 find_similar.py "/path/to/images" [threshold]
```

**Examples:**
```bash
# Very strict (only nearly identical)
python3 find_similar.py "/path/to/images" 5

# Recommended (similar images)
python3 find_similar.py "/path/to/images" 10

# Loose (more matches, some false positives)
python3 find_similar.py "/path/to/images" 15
```

**Output:**
- `reports/similar_report_TIMESTAMP.txt`
- `reports/similar_report_TIMESTAMP.json`

#### 3. Delete Duplicates

```bash
# Dry run (preview only)
python3 delete_duplicates.py reports/duplicate_report_*.json

# Actually delete files
python3 delete_duplicates.py reports/duplicate_report_*.json --execute
```

## How It Works

### Exact Duplicate Detection

1. **Scanning**: Recursively finds all image files
2. **Hashing**: Calculates MD5 hash for each file
3. **Grouping**: Groups files with identical hashes
4. **Reporting**: Generates detailed reports
5. **Deletion**: Keeps first existing file, deletes the rest

### Similar Image Detection

1. **Scanning**: Finds all image files
2. **Perceptual Hashing**: Generates visual hash using average hash algorithm
3. **Comparison**: Calculates Hamming distance between hashes
4. **Grouping**: Groups images within threshold distance
5. **Reporting**: Lists similar groups for manual review

**Note:** Similar images are not automatically deleted. Manual review is recommended.

## Similarity Threshold Guide

The threshold value determines how similar images must be to match:

| Threshold | Similarity Level | Use Case |
|-----------|------------------|----------|
| 0-5 | Very strict | Nearly identical images only |
| 6-10 | Similar (recommended) | Same image with minor edits/compression |
| 11-15 | Somewhat similar | Same subject, different crops/sizes |
| 16+ | Loose | May include false positives |

**Hamming Distance Explanation:**
- 0 = Identical images
- Lower values = More similar
- Higher values = Less similar
- Maximum distance = 64

## Reports

Reports are saved in the `reports/` directory with timestamps.

### Exact Duplicate Report (JSON)

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
      "files": [...]
    }
  ]
}
```

### Similar Images Report (JSON)

```json
{
  "metadata": {
    "scan_date": "2025-11-15T21:18:53",
    "scanned_directory": "/path/to/images",
    "similarity_threshold": 10,
    "hash_algorithm": "average_hash",
    "total_images_scanned": 1277,
    "similar_groups_found": 371,
    "total_similar_files": 1072,
    "removable_files": 701,
    "estimated_space_mb": 458.25,
    "estimated_space_gb": 0.45
  },
  "similar_groups": [
    {
      "reference_hash": "8f8f8f8f8f8f8f8f",
      "similarity_count": 3,
      "files": [...]
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
- **Conflict detection**: Warns about naming conflicts

## Project Structure

```
duplicate-image-finder/
├── app.py                 # Interactive terminal application
├── find_duplicates.py     # CLI tool to find exact duplicates
├── find_similar.py        # CLI tool to find similar images
├── delete_duplicates.py   # CLI tool to delete duplicates
├── requirements.txt       # Python dependencies for similar detection
├── venv/                  # Virtual environment (gitignored)
├── reports/               # Generated reports (gitignored)
├── .gitignore
└── README.md
```

## Examples

### Example 1: Quick Cleanup (Interactive)

```bash
# Activate venv for similar detection support
source venv/bin/activate

# Run interactive app
python3 app.py

# Follow prompts:
# 1. Enter directory path
# 2. Review exact duplicates
# 3. Delete duplicates? (e/h)
# 4. Check for similar images? (e/h)
# 5. Enter threshold (e.g., 10)
# 6. Review similar images in reports
```

### Example 2: Exact Duplicates Only

```bash
# Find duplicates
python3 find_duplicates.py "/home/user/Photos"

# Review reports in reports/ directory
# Delete if satisfied
python3 delete_duplicates.py reports/duplicate_report_*.json --execute
```

### Example 3: Find Similar Images for Manual Review

```bash
source venv/bin/activate

# Find similar images (strict threshold)
python3 find_similar.py "/home/user/Photos" 8

# Review reports/similar_report_*.json
# Manually delete unwanted files
```

### Example 4: Large Photo Library

```bash
source venv/bin/activate

# Process 5000+ photos
python3 app.py
# Enter: /media/PhotoLibrary
# Delete exact duplicates: e
# Check similar: e
# Threshold: 10

# Result:
# - Exact duplicates removed automatically
# - Similar images listed in report for review
# - Saved 2GB+ of space
```

## Use Cases

### Photography
- Clean up duplicate shots from burst mode
- Find nearly identical photos from same session
- Organize photo library before archival

### Downloaded Images
- Remove duplicate downloads
- Find similar memes/screenshots
- Clean up backup folders

### Content Management
- Deduplicate media assets
- Find resized/compressed versions
- Prepare images for web optimization

### Digital Asset Management
- Consolidate image collections
- Identify redundant files
- Optimize storage usage

## Comparison: Exact vs Similar Detection

| Feature | Exact Duplicates | Similar Images |
|---------|-----------------|----------------|
| Detection Method | MD5 hash | Perceptual hash |
| Speed | Very fast | Moderate |
| Accuracy | 100% | Adjustable |
| Catches | Identical files | Resized, compressed, edited |
| Auto-delete | Yes (with confirmation) | No (manual review) |
| Dependencies | None | Pillow, imagehash |

## Troubleshooting

**"Similar image detection is not available"**
- Install dependencies: `pip install -r requirements.txt`
- Activate virtual environment: `source venv/bin/activate`

**Too many false positives in similar detection**
- Lower the threshold (e.g., 5-8 instead of 10)

**Missing similar images**
- Increase the threshold (e.g., 12-15)

**Permission errors**
- Check write permissions in target directory
- Ensure reports/ directory is writable

## Performance

**Exact Duplicate Detection:**
- 1000 images: ~5-10 seconds
- 5000 images: ~30-60 seconds

**Similar Image Detection:**
- 1000 images: ~30-60 seconds
- 5000 images: ~3-5 minutes

*Performance varies based on image sizes and system specs*

## Limitations

- Similar detection requires additional libraries
- Perceptual hashing may have false positives/negatives
- Very large images (>50MB) may take longer to process
- Similar detection does not auto-delete (manual review required)

## Future Features (Planned)

- Similar image auto-deletion with safeguards
- Multiple perceptual hash algorithms (dHash, pHash)
- Image comparison preview (side-by-side)
- Batch processing of multiple directories
- Undo functionality

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Feel free to fork and enhance! Suggestions welcome.

## Version History

**v2.0.0** - Similar Image Detection
- Added perceptual hash-based similar detection
- New find_similar.py CLI tool
- Interactive threshold selection in app.py
- Virtual environment support
- Updated reports with similarity metadata

**v1.0.0** - Initial Release
- Exact duplicate detection (hash-based)
- Interactive and CLI modes
- Safe deletion with confirmations
- JSON and TXT reports

---

**Efficiently manage your image collection with both exact and similar duplicate detection.**
