# XTEink Manga Tools

A collection of command-line tools to convert manga (CBZ) and images to XTC format for the **XTEink X4** e-reader. Optimized for fast loading and readable text on e-ink displays.

## 🚀 Features

- **cbz2xtc** - Batch convert CBZ manga files to XTC format
  - Automatic page splitting and rotation for optimal reading (optional)
  - Multithreaded processing (up to 4x faster)
  - Multiple dithering algorithms (Floyd-Steinberg, Ordered, Rasterize, None)
  - Dithering enabled by default for better quality
  - Progress tracking with time estimates
  - Optional full-page mode (no splitting)
  
- **image2bw** - Convert images to 1-bit black & white BMP for ultra-fast backgrounds
  - Multiple dithering algorithms (Floyd-Steinberg, Ordered, Rasterize)
  - Perfect for wallpapers and backgrounds
  - Always outputs BMP (XTEink doesn't support PNG)
  - Instant loading on device

**Note:** For converting individual images to XTC, use `png2xtc.py` from epub2xtc directly.

## 📋 Requirements

- Python 3.7+
- [Pillow](https://pillow.readthedocs.io/) (Python Imaging Library)
- [epub2xtc](https://github.com/jonasdiemer/epub2xtc) (for png2xtc.py)
- Git (for automatic epub2xtc installation)

## 🔧 Installation

### 1. Install Python dependencies

**Using pip (recommended):**
```bash
pip install pillow
```

**Platform-specific alternatives:**

**macOS (with Homebrew):**
```bash
brew install pillow
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install python3-pil
# or
pip install pillow
```

**Windows:**
```bash
pip install pillow
```

### 2. Clone this repository

```bash
git clone https://github.com/tazua/cbz2xtc.git
cd cbz2xtc
```

### 3. Install epub2xtc

**Automatic (recommended):**

Just run any tool - it will prompt you to install epub2xtc automatically!

```bash
cbz2xtc
# Will ask: "Would you like to clone epub2xtc now? (Y/n)"
```

**Manual:**

```bash
git clone https://github.com/jonasdiemer/epub2xtc.git
```

### 4. Setup (Optional)

**Linux/Mac:**
```bash
# Add to PATH
sudo ln -s $(pwd)/cbz2xtc.py /usr/local/bin/cbz2xtc
sudo ln -s $(pwd)/image2bw.py /usr/local/bin/image2bw
chmod +x *.py
```

**Windows:**
- Add the folder to your PATH environment variable
- Or use the included `.bat` files

## 📖 Usage

### cbz2xtc - Convert CBZ to XTC

```bash
# Basic usage (split pages + dithering enabled by default)
cbz2xtc

# Full pages, no splitting (1 manga page = 1 XTC page)
cbz2xtc --no-split

# Disable dithering (for clean line art)
cbz2xtc --no-dither

# Use different dithering algorithm
cbz2xtc --dither-algo ordered     # Grid pattern, good for text
cbz2xtc --dither-algo none        # Pure threshold, sharpest
cbz2xtc --dither-algo rasterize   # Halftone style

# With cleanup (auto-delete temp files)
cbz2xtc --clean

# Combine options
cbz2xtc --no-split --clean
cbz2xtc --dither-algo ordered --clean

# Specific folder
cbz2xtc /path/to/manga/folder

# Show help
cbz2xtc --help
```

**What it does:**
1. Extracts images from CBZ files
2. Splits each page in half horizontally (unless --no-split)
3. Rotates 90° for optimal portrait reading (if split)
4. Resizes to 480×800 with white padding
5. Converts to grayscale PNG with dithering (Floyd-Steinberg by default)
6. Converts to XTC format using png2xtc.py
7. Processes multiple files in parallel (4 threads)

**Output:** `./xtc_output/*.xtc`

**Dithering Algorithms:**
- **floyd** (default) - Smooth diffusion, best for photos/gradients
- **ordered** - Grid pattern, often better for text-heavy manga
- **rasterize** - Halftone newspaper style
- **none** - Pure threshold, sharpest (use --no-dither or --dither-algo none)

**When to use --no-split:**
- Reading on larger screens
- Want to see full page context
- Don't need the text magnification from splitting

---

### image2bw - Convert to 1-bit Black & White BMP

Perfect for backgrounds and wallpapers - loads **instantly** on XTEink X4!

```bash
# Convert to 1-bit B&W BMP (default: Floyd-Steinberg dithering)
image2bw wallpaper.jpg

# Try different dithering algorithms
image2bw manga_page.jpg --dither none      # Sharpest text
image2bw manga_page.jpg --dither ordered   # Grid pattern
image2bw manga_page.jpg --dither rasterize # Halftone

# Batch convert folder
image2bw backgrounds/

# Show help
image2bw --help
```

**Dithering algorithms:**
- **none** - Pure threshold, sharpest (best for text-heavy manga)
- **ordered** - Grid/Bayer pattern (good balance for text + images)
- **floyd** - Floyd-Steinberg diffusion (smooth, best for photos) - default
- **rasterize** - Halftone newspaper style

**Output:** Ultra-small BMP files (15-40KB) that load instantly!

**Note:** Always outputs BMP format because XTEink X4 doesn't support PNG images.

## 🎯 Recommended Workflow

### For Most Manga:
```bash
# Default settings work great (split + Floyd-Steinberg dithering)
cbz2xtc --clean
```

### For Text-Heavy Manga (Hunter x Hunter, Death Note):
```bash
# Ordered dithering often clearer for dense text
cbz2xtc --dither-algo ordered --clean

# Or pure threshold for maximum sharpness
cbz2xtc --dither-algo none --clean
```

### For Full-Page Reading:
```bash
# Keep pages whole, no splitting
cbz2xtc --no-split --clean
```

### For Clean Line Art (No Screentones):
```bash
# Disable dithering for crisp lines
cbz2xtc --no-dither --clean
```

### For Fast-Loading Backgrounds:
```bash
# Ultra-small 1-bit BMP images
image2bw wallpaper.jpg --dither ordered
```

## ⚙️ Advanced Configuration

### Set png2xtc.py location

If png2xtc.py is in a non-standard location:

```bash
# Linux/Mac
export PNG2XTC_PATH=/path/to/png2xtc.py

# Windows
set PNG2XTC_PATH=C:\path\to\png2xtc.py
```

### Multithreading

cbz2xtc automatically uses up to 4 threads. This is hardcoded but can be modified in the script (line ~32):

```python
max_workers = min(4, os.cpu_count() or 1)  # Change 4 to desired thread count
```

## 📐 XTEink X4 Specifications

- **Screen:** 4.3" e-ink display
- **Resolution:** 480×800 pixels (portrait)
- **PPI:** 220
- **Supported formats:** XTC, JPG, BMP, TXT, EPUB
- **Processor:** ESP32 (128MB RAM)

## 🐛 Troubleshooting

**"No module named 'PIL'"**
- Pillow is not installed
- Run: `pip install pillow`
- Or on macOS: `brew install pillow`

**"png2xtc.py not found"**
- The tool will prompt you to clone epub2xtc automatically
- Or clone manually: `git clone https://github.com/jonasdiemer/epub2xtc.git`
- Or set `PNG2XTC_PATH` environment variable

**Images look weird/grainy**
- Dithering is ON by default. Try disabling: `cbz2xtc --no-dither`
- For image2bw, experiment with `--dither none`, `--dither ordered`, etc.

**Slow conversion**
- Use `--clean` to save disk space
- Check if multithreading is working (should show "Threads: 4")
- SSD recommended for temp file storage

**Text hard to read**
- For text-heavy manga: Try `cbz2xtc --no-dither`
- Or use `image2bw` with `--dither none` for individual pages
- Adjust source image quality (higher resolution CBZ files work better)

## 🤝 Contributing

Contributions welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Share your optimized settings

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Credits

- [epub2xtc](https://github.com/jonasdiemer/epub2xtc) by jonasdiemer - XTC conversion library
- XTEink X4 community for testing and feedback

## 📧 Support

For issues or questions:
- Open a GitHub issue
- Check existing issues for solutions

## ⚠️ Disclaimer

This project was created through an iterative "vibecoding" process with an AI assistant (Claude). While the tools work and have been tested, the code may not follow all best practices or handle every edge case. Contributions to improve code quality, error handling, and robustness are very welcome! 

Use at your own risk, and always keep backups of your original CBZ files.

---

**Enjoy reading manga on your XTEink X4!** 📚✨
