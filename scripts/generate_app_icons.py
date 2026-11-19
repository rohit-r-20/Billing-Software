#!/usr/bin/env python3
"""
App Icon Generator for Anti-Matrix Billing V2.
Generates genuine multi-resolution platform icons:
- macOS: assets/app_icon.icns (via macOS native iconutil)
- Windows: assets/app_icon.ico
- Linux / Web: assets/app_icon.png (512x512)
"""

import os
import sys
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJ_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJ_ROOT / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def create_master_icon(size: int = 1024) -> Image.Image:
    """Create a high-resolution 1024x1024 master icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. macOS Squircle / Rounded Rectangle
    corner_radius = int(size * 0.22)
    padding = int(size * 0.05)
    box = [padding, padding, size - padding, size - padding]

    # Gradient background simulation: dark navy/slate to deep cobalt
    steps = 100
    for i in range(steps):
        factor = i / steps
        r = int(15 + factor * 20)    # 15 -> 35
        g = int(23 + factor * 40)    # 23 -> 63
        b = int(42 + factor * 90)    # 42 -> 132
        curr_pad = padding + int((1 - factor) * (size * 0.02))
        curr_box = [curr_pad, curr_pad, size - curr_pad, size - curr_pad]
        draw.rounded_rectangle(curr_box, radius=corner_radius, fill=(r, g, b, 255))

    # Outer border / subtle ring
    draw.rounded_rectangle(box, radius=corner_radius, outline=(56, 189, 248, 180), width=int(size * 0.015))

    # 2. Geometric Grid / Matrix lines (Cyber/Tech ERP vibe)
    grid_color = (14, 165, 233, 45)
    for x in range(int(size * 0.2), int(size * 0.8), int(size * 0.08)):
        draw.line([(x, int(size * 0.2)), (x, int(size * 0.8))], fill=grid_color, width=2)
    for y in range(int(size * 0.2), int(size * 0.8), int(size * 0.08)):
        draw.line([(int(size * 0.2), y), (int(size * 0.8), y)], fill=grid_color, width=2)

    # 3. Central Brand Monogram: "AM" in modern tech sans
    # Use standard system font if available, fallback to basic geometric drawing
    font_size = int(size * 0.38)
    font = None
    system_fonts = [
        "/System/Library/Fonts/SFPro-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    for fp in system_fonts:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue

    text = "AM"
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (size - tw) // 2
        ty = int(size * 0.28)
        # Drop shadow
        draw.text((tx + int(size * 0.01), ty + int(size * 0.015)), text, font=font, fill=(5, 10, 20, 160))
        # Main text
        draw.text((tx, ty), text, font=font, fill=(248, 250, 252, 255))
    else:
        # Geometric fallback
        draw.text((size // 4, size // 3), text, fill=(248, 250, 252, 255))

    # 4. Currency Subtext / Badge: "₹ BILLING"
    badge_box = [int(size * 0.22), int(size * 0.72), int(size * 0.78), int(size * 0.84)]
    draw.rounded_rectangle(badge_box, radius=int(size * 0.04), fill=(2, 132, 199, 230), outline=(56, 189, 248, 255), width=2)

    sub_font_size = int(size * 0.065)
    sub_font = None
    for fp in system_fonts:
        if os.path.exists(fp):
            try:
                sub_font = ImageFont.truetype(fp, sub_font_size)
                break
            except Exception:
                continue

    sub_text = "₹ BILLING ERP"
    if sub_font:
        s_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
        sw = s_bbox[2] - s_bbox[0]
        sx = (size - sw) // 2
        sy = int(size * 0.745)
        draw.text((sx, sy), sub_text, font=sub_font, fill=(255, 255, 255, 255))

    return img


def generate_all_icons():
    master = create_master_icon(1024)

    # 1. Save standard PNG
    png_path = ASSETS_DIR / "app_icon.png"
    master.save(png_path, "PNG")
    print(f"[✓] Generated master PNG: {png_path} ({master.width}x{master.height})")

    # 2. Save Windows .ico containing multi-resolution frames
    ico_path = ASSETS_DIR / "app_icon.ico"
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(ico_path, format="ICO", sizes=ico_sizes)
    print(f"[✓] Generated Windows ICO: {ico_path} with sizes {ico_sizes}")

    # 3. macOS .icns generation via native iconutil
    if sys.platform == "darwin":
        iconset_dir = ASSETS_DIR / "app_icon.iconset"
        iconset_dir.mkdir(parents=True, exist_ok=True)

        icon_specs = [
            ("icon_16x16.png", 16),
            ("icon_16x16@2x.png", 32),
            ("icon_32x32.png", 32),
            ("icon_32x32@2x.png", 64),
            ("icon_128x128.png", 128),
            ("icon_128x128@2x.png", 256),
            ("icon_256x256.png", 256),
            ("icon_256x256@2x.png", 512),
            ("icon_512x512.png", 512),
            ("icon_512x512@2x.png", 1024),
        ]

        for fname, sz in icon_specs:
            resized = master.resize((sz, sz), Image.Resampling.LANCZOS)
            resized.save(iconset_dir / fname, "PNG")

        icns_path = ASSETS_DIR / "app_icon.icns"
        proc = subprocess.run(
            ["/usr/bin/iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and icns_path.exists():
            print(f"[✓] Generated macOS ICNS: {icns_path} (File size: {icns_path.stat().st_size} bytes)")
            # Clean up temporary iconset directory
            for f in iconset_dir.iterdir():
                f.unlink()
            iconset_dir.rmdir()
        else:
            print(f"[!] iconutil warning: {proc.stderr}")


if __name__ == "__main__":
    generate_all_icons()
