#!/usr/bin/env python3
"""
generate_cyber_portrait.py
--------------------------
Converts a portrait photo into an advanced Cyber-Biometric Neural HUD animated SVG
for Pranav Pushya's GitHub profile (assets/cyber-portrait.svg).

Features:
- Adaptive luminance mapping with edge & subject-aware background suppression.
- High-fidelity 14-character density ramp.
- Cyber theme gradient matching Pranav's engineering lab header (#0b1326, #55e5ed, #a692ff, #f0f5ff).
- Dual-phase SMIL animation:
  1. Matrix-style typewriter decryption reveal row-by-row with tracking cursor.
  2. Continuous post-typing living HUD: Biometric laser scanner sweep + pulsing telemetry reticles.
- 100% pure SVG with SMIL animations: natively supported by GitHub's markdown renderer.
"""

import argparse
import sys
from PIL import Image, ImageOps, ImageEnhance

# Character density ramp from darkest to brightest
RAMP = " ·.:;=-+*#%@&$"

# Cyber theme gradient stops (0.0 = darkest shadow -> 1.0 = brightest highlight)
GRADIENT_STOPS = [
    (0.00, (40, 52, 76)),     # Deep slate/navy (#28344c)
    (0.25, (113, 96, 221)),   # Neon purple (#7160dd)
    (0.60, (166, 146, 255)),  # Electric violet (#a692ff)
    (0.85, (85, 229, 237)),   # Electric cyan (#55e5ed)
    (1.00, (240, 245, 255)),  # Holographic white (#f0f5ff)
]

FONT_SIZE = 12.5
CHAR_W = FONT_SIZE * 0.605
LINE_H = FONT_SIZE * 1.18
PAD_X = 24
PAD_Y = 18
TITLEBAR_H = 38
FOOTERBAR_H = 36
TYPE_SPEED = 0.016
ROW_GAP = 0.015


def lerp(a, b, t):
    return a + (b - a) * t


def get_gradient_color(t):
    t = max(0.0, min(1.0, t))
    for i in range(len(GRADIENT_STOPS) - 1):
        t0, c0 = GRADIENT_STOPS[i]
        t1, c1 = GRADIENT_STOPS[i + 1]
        if t0 <= t <= t1:
            local_t = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            r = round(lerp(c0[0], c1[0], local_t))
            g = round(lerp(c0[1], c1[1], local_t))
            b = round(lerp(c0[2], c1[2], local_t))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#55e5ed"


def escape(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def image_to_ascii_grid(image_path, cols, rows, crop=(0.08, 0.02, 0.92, 0.88)):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    
    if crop:
        l, t, r, b = crop
        img = img.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
    
    small = img.resize((cols, rows), Image.LANCZOS)
    grid = []
    ramp_len = len(RAMP)
    
    for r in range(rows):
        row = []
        for c in range(cols):
            p = small.getpixel((c, r))
            # Background suppression: if pixel is pure/near white
            if p[0] > 232 and p[1] > 232 and p[2] > 232:
                row.append((" ", "#28344c"))
            else:
                lum = 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]
                if lum < 35:
                    row.append((" ", "#28344c"))
                else:
                    norm_val = max(0.0, min(1.0, (lum - 35) / 195.0))
                    idx = int(norm_val * (ramp_len - 1))
                    ch = RAMP[idx]
                    color = get_gradient_color(norm_val)
                    row.append((ch, color))
        grid.append(row)
    return grid


def group_row(row):
    """Collapse consecutive characters of the same color into single spans."""
    groups = []
    cur_char, cur_color = row[0]
    cur_run = cur_char
    for ch, color in row[1:]:
        if color == cur_color:
            cur_run += ch
        else:
            groups.append((cur_run, cur_color))
            cur_run = ch
            cur_color = color
    groups.append((cur_run, cur_color))
    return groups


def build_cyber_svg(grid, cols, rows):
    content_w = cols * CHAR_W
    content_h = rows * LINE_H
    width = content_w + PAD_X * 2
    height = content_h + TITLEBAR_H + FOOTERBAR_H + PAD_Y * 2
    
    content_x = PAD_X
    content_y = TITLEBAR_H + PAD_Y + FONT_SIZE
    
    row_durations = [max(0.08, len(r) * TYPE_SPEED) for r in grid]
    row_ids = [f"cyber_row_{i}" for i in range(rows)]
    
    # Cursor keytimes
    cursor_x_keytimes = []
    cursor_x_values = []
    cursor_time = 0.0
    for i in range(rows):
        row_w = len(grid[i]) * CHAR_W
        dur = row_durations[i]
        start_t = cursor_time
        end_t = start_t + dur
        cursor_x_keytimes.append(start_t)
        cursor_x_values.append(content_x)
        cursor_x_keytimes.append(end_t)
        cursor_x_values.append(content_x + row_w)
        cursor_time = end_t + ROW_GAP
    
    total_typing_dur = cursor_time
    norm_keytimes = [round(t / total_typing_dur, 5) if total_typing_dur > 0 else 0 for t in cursor_x_keytimes]
    for i in range(1, len(norm_keytimes)):
        if norm_keytimes[i] <= norm_keytimes[i - 1]:
            norm_keytimes[i] = norm_keytimes[i - 1] + 0.00001
    if norm_keytimes:
        norm_keytimes[0] = 0.0
        norm_keytimes[-1] = 1.0

    row_elements = []
    cursor_y_sets = []
    for i in range(rows):
        y = content_y + i * LINE_H
        groups = group_row(grid[i])
        row_w = len(grid[i]) * CHAR_W
        dur = row_durations[i]
        
        tspans = "".join(f'<tspan fill="{color}">{escape(text)}</tspan>' for text, color in groups)
        clip_id = f"cyber_clip_{i}"
        prev_id = row_ids[i - 1] if i > 0 else None
        begin_attr = "0.2s" if i == 0 else f"{prev_id}.end+{ROW_GAP}s"
        
        row_elements.append(f'''
    <clipPath id="{clip_id}">
      <rect x="{content_x}" y="{y - FONT_SIZE}" width="0" height="{LINE_H}">
        <animate id="{row_ids[i]}" attributeName="width" from="0" to="{row_w:.2f}"
                 begin="{begin_attr}" dur="{dur:.3f}s" fill="freeze" calcMode="linear"/>
      </rect>
    </clipPath>
    <text x="{content_x}" y="{y}" font-family="'JetBrains Mono','Fira Code','Courier New',monospace"
          font-size="{FONT_SIZE}" clip-path="url(#{clip_id})">{tspans}</text>''')
        
        cursor_y_sets.append(
            f'<set attributeName="y" to="{y - FONT_SIZE * 0.85:.2f}" begin="{begin_attr}"/>'
        )

    last_row_id = row_ids[-1]
    cursor_x_vals_attr = ";".join(f"{v:.2f}" for v in cursor_x_values)
    cursor_x_keytimes_attr = ";".join(f"{t:.5f}" for t in norm_keytimes)
    
    # Coordinates for reticles and scanline
    reticle_inset = 6
    top_y = TITLEBAR_H + PAD_Y - 4
    bottom_y = top_y + content_h + 10
    
    svg = f'''<svg viewBox="0 0 {width:.0f} {height:.0f}" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="Pranav Pushya - Cyber Biometric Neural Portrait">
  <title>Pranav Pushya — Biometric Neural ASCII Scan</title>
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&amp;display=swap');
      text {{ font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace; }}
    </style>
    <linearGradient id="cyberBorder" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#55e5ed" stop-opacity="0.8"/>
      <stop offset="50%" stop-color="#26344c" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#a692ff" stop-opacity="0.8"/>
    </linearGradient>
    <linearGradient id="laserGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#55e5ed" stop-opacity="0"/>
      <stop offset="15%" stop-color="#55e5ed" stop-opacity="0.6"/>
      <stop offset="50%" stop-color="#f0f5ff" stop-opacity="0.95"/>
      <stop offset="85%" stop-color="#a692ff" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#a692ff" stop-opacity="0"/>
    </linearGradient>
    <filter id="cyberGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <!-- Outer HUD Terminal Frame -->
  <rect x="0.5" y="0.5" width="{width - 1:.0f}" height="{height - 1:.0f}" rx="14" ry="14"
        fill="#0b1326" stroke="url(#cyberBorder)" stroke-width="1.2"/>

  <!-- Header Bar -->
  <rect x="0.5" y="0.5" width="{width - 1:.0f}" height="{TITLEBAR_H}" rx="14" ry="14" fill="#090d1a"/>
  <rect x="0.5" y="{TITLEBAR_H - 10}" width="{width - 1:.0f}" height="10" fill="#090d1a"/>
  <line x1="0" y1="{TITLEBAR_H}" x2="{width:.0f}" y2="{TITLEBAR_H}" stroke="#26344c" stroke-width="1"/>

  <!-- Live Status Beacon -->
  <circle cx="{PAD_X}" cy="{TITLEBAR_H / 2}" r="4" fill="#55e5ed">
    <animate attributeName="opacity" values="1;0.35;1" dur="2.4s" repeatCount="indefinite"/>
  </circle>
  <text x="{PAD_X + 14}" y="{TITLEBAR_H / 2 + 4:.0f}" font-size="11" fill="#97a9c4" letter-spacing="1.5" font-weight="600">
    BIO-SCAN // PRANAV_PUSHYA
  </text>
  
  <text x="{width - PAD_X:.0f}" y="{TITLEBAR_H / 2 + 4:.0f}" text-anchor="end" font-size="10" fill="#55e5ed" letter-spacing="1">
    SYS: AUTH_OK [0x7F]
  </text>

  <!-- Corner Reticles [+] -->
  <g fill="#55e5ed" opacity="0.65" font-size="10" font-weight="bold">
    <animate attributeName="opacity" values="0.65;0.25;0.65" dur="3s" repeatCount="indefinite"/>
    <text x="{content_x - reticle_inset}" y="{top_y + 4}">[+]</text>
    <text x="{content_x + content_w + reticle_inset - 16}" y="{top_y + 4}">[+]</text>
    <text x="{content_x - reticle_inset}" y="{bottom_y - 2}">[+]</text>
    <text x="{content_x + content_w + reticle_inset - 16}" y="{bottom_y - 2}">[+]</text>
  </g>

  <!-- Main ASCII Portrait Content -->
  <g filter="url(#cyberGlow)">
    {"".join(row_elements)}
  </g>

  <!-- Typewriter Decryption Cursor -->
  <rect id="cursor" x="{content_x}" width="{CHAR_W * 0.9:.2f}" height="{FONT_SIZE * 1.15:.2f}"
        y="{content_y - FONT_SIZE * 0.85:.2f}" fill="#55e5ed" opacity="1">
    {"".join(cursor_y_sets)}
    <animate attributeName="x" begin="0.2s" dur="{total_typing_dur:.3f}s" fill="freeze"
             calcMode="linear" keyTimes="{cursor_x_keytimes_attr}" values="{cursor_x_vals_attr}"/>
    <animate attributeName="opacity" begin="{last_row_id}.end" dur="0.9s"
             repeatCount="indefinite" calcMode="discrete" keyTimes="0;0.5" values="1;0"/>
  </rect>

  <!-- Continuous Living Biometric Laser Scanline (Activates post-decryption) -->
  <g filter="url(#cyberGlow)">
    <line x1="{content_x - 12}" y1="{top_y}" x2="{content_x + content_w + 12}" y2="{top_y}"
          stroke="url(#laserGrad)" stroke-width="2.5" opacity="0">
      <animate attributeName="y1" values="{top_y};{bottom_y};{top_y}" dur="5s"
               repeatCount="indefinite" begin="{last_row_id}.end + 0.5s"/>
      <animate attributeName="y2" values="{top_y};{bottom_y};{top_y}" dur="5s"
               repeatCount="indefinite" begin="{last_row_id}.end + 0.5s"/>
      <animate attributeName="opacity" values="0;0.85;0.85;0" dur="5s"
               repeatCount="indefinite" begin="{last_row_id}.end + 0.5s"/>
    </line>
  </g>

  <!-- Footer Telemetry Bar -->
  <line x1="0" y1="{height - FOOTERBAR_H}" x2="{width:.0f}" y2="{height - FOOTERBAR_H}" stroke="#26344c" stroke-width="1"/>
  <rect x="0.5" y="{height - FOOTERBAR_H}" width="{width - 1:.0f}" height="{FOOTERBAR_H}" rx="14" ry="14" fill="#090d1a"/>
  <rect x="0.5" y="{height - FOOTERBAR_H}" width="{width - 1:.0f}" height="10" fill="#090d1a"/>
  
  <text x="{PAD_X}" y="{height - FOOTERBAR_H / 2 + 4:.0f}" font-size="10.5" fill="#aab8ce" letter-spacing="1">
    IDENTITY: <tspan fill="#55e5ed" font-weight="600">VERIFIED</tspan> · AI/ML &amp; CYBERSECURITY
  </text>
  
  <text x="{width - PAD_X:.0f}" y="{height - FOOTERBAR_H / 2 + 4:.0f}" text-anchor="end" font-size="9.5" fill="#8d9eb8" letter-spacing="1">
    ZERO-TRUST // NODE_READY
  </text>
</svg>'''
    return svg


def main():
    parser = argparse.ArgumentParser(description="Generate Cyber Biometric Neural Portrait SVG.")
    parser.add_argument("--input", default="assets/avatar.png", help="Input image path")
    parser.add_argument("--output", default="assets/cyber-portrait.svg", help="Output SVG path")
    parser.add_argument("--cols", type=int, default=46, help="Character columns")
    parser.add_argument("--rows", type=int, default=26, help="Character rows")
    args = parser.parse_args()

    grid = image_to_ascii_grid(args.input, args.cols, args.rows)
    svg = build_cyber_svg(grid, args.cols, args.rows)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Generated {args.output} successfully! ({args.cols}x{args.rows} grid, {len(svg):,} bytes)")


if __name__ == "__main__":
    main()
