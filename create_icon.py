#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal AI Memory Hub - Official Icon Generator
Generates high-resolution cyber neural cortex icons (PNG and multi-size Windows ICO).
"""

from PIL import Image, ImageDraw
import math
import os


def generate_app_icon(output_png="app_icon.png", output_ico="app_icon.ico"):
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Outer rounded container with cyber gradient feel
    padding = 24
    corner_radius = 110
    draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=corner_radius,
        fill=(13, 17, 23, 255),
        outline=(56, 189, 248, 200),
        width=6
    )

    # 2. Concentric radiant glow rings
    center_x, center_y = size // 2, size // 2
    for r, alpha in [(190, 20), (160, 35), (130, 55)]:
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            outline=(99, 102, 241, alpha),
            width=3
        )

    # 3. Neural Synaptic Nodes & Interconnects (Bilateral Cortex)
    left_nodes = [
        (160, 160), (130, 240), (150, 320), (200, 380),
        (210, 180), (190, 260), (220, 320)
    ]
    right_nodes = [
        (size - x, y) for (x, y) in left_nodes
    ]

    # Synaptic connections (Left lobe)
    synapse_color = (34, 211, 238, 180)
    for i in range(len(left_nodes)):
        for j in range(i + 1, len(left_nodes)):
            x1, y1 = left_nodes[i]
            x2, y2 = left_nodes[j]
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < 125:
                draw.line([(x1, y1), (x2, y2)], fill=synapse_color, width=3)

    # Synaptic connections (Right lobe)
    for i in range(len(right_nodes)):
        for j in range(i + 1, len(right_nodes)):
            x1, y1 = right_nodes[i]
            x2, y2 = right_nodes[j]
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < 125:
                draw.line([(x1, y1), (x2, y2)], fill=synapse_color, width=3)

    # Cross-hemisphere bridges
    bridge_color = (168, 85, 247, 190)
    bridges = [(left_nodes[4], right_nodes[4]), (left_nodes[5], right_nodes[5]), (left_nodes[6], right_nodes[6])]
    for n1, n2 in bridges:
        draw.line([n1, n2], fill=bridge_color, width=4)

    # Draw Nodes
    for x, y in left_nodes + right_nodes:
        # Outer glow
        draw.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(56, 189, 248, 80))
        # Inner node
        draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 255, 255, 255))

    # 4. Central Diamond Core - The AI Intelligence Spark
    core_r = 44
    diamond = [
        (center_x, center_y - core_r),
        (center_x + core_r, center_y),
        (center_x, center_y + core_r),
        (center_x - core_r, center_y)
    ]
    # Core outer aura
    aura_r = 58
    aura = [
        (center_x, center_y - aura_r),
        (center_x + aura_r, center_y),
        (center_x, center_y + aura_r),
        (center_x - aura_r, center_y)
    ]
    draw.polygon(aura, fill=(129, 140, 248, 120))
    draw.polygon(diamond, fill=(255, 255, 255, 255), outline=(56, 189, 248, 255))

    # Core inner pulse
    inner_r = 16
    draw.ellipse([center_x - inner_r, center_y - inner_r, center_x + inner_r, center_y + inner_r], fill=(99, 102, 241, 255))

    # Save PNG
    img.save(output_png, "PNG")
    print(f"Saved {output_png}")

    # Generate multi-size ICO
    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(output_ico, format="ICO", sizes=icon_sizes)
    print(f"Saved {output_ico}")


if __name__ == "__main__":
    generate_app_icon()
