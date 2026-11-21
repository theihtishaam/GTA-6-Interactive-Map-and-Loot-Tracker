"""Trace candidate roads from the distributed, registered YANIS v18 raster.
Build-time only: python -m pip install Pillow numpy scipy scikit-image
The browser uses the prebuilt graph. See docs/NAVIGATION.md for limitations.
"""
from pathlib import Path
import json

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.morphology import disk, skeletonize

ROOT = Path(__file__).resolve().parents[1]
NEIGHBORS = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]

# Half-scale pixel boundaries traced on the pinned map. The bright runway
# markings at VCIA and Mile Zero can otherwise look like connected streets.
# The terminals and public approach roads remain outside these polygons.
RUNWAY_INTERIORS = (
    [(816, 1340), (848, 1329), (1031, 1330), (1040, 1354),
     (975, 1369), (975, 1411), (1042, 1458), (1048, 1499),
     (1023, 1505), (919, 1476), (820, 1396)],
    [(358, 2187), (396, 2067), (431, 2062), (470, 2176),
     (468, 2199), (365, 2201)],
)


def road_mask(image):
    r, g, b = np.asarray(image).transpose(2, 0, 1)
    paint = (r > 224) & (g > 229) & (b > 177)
    # Subtract broad fills such as large roofs before following narrow strokes.
    broad = ndimage.binary_opening(paint, structure=disk(7))
    paint &= ~ndimage.binary_dilation(broad, iterations=2)
    # Connect antialiased line breaks at the full source resolution. Test each
    # source pixel before pooling, which preserves fine bridge and ramp strokes.
    paint = ndimage.binary_closing(paint, structure=np.ones((5, 5), dtype=bool))
    h, w = paint.shape
    pooled = paint.reshape(h // 2, 2, w // 2, 2).any(axis=(1, 3))
    forbidden = Image.new("1", (w // 2, h // 2))
    pen = ImageDraw.Draw(forbidden)
    for polygon in RUNWAY_INTERIORS:
        pen.polygon(polygon, fill=1)
    return pooled & ~np.asarray(forbidden)


def build():
    image = Image.open(ROOT / "public/map.webp").convert("RGB")
    if image.size != (3456, 4864):
        raise ValueError("Expected the registered 3456 × 4864 YANIS v18 raster")
    center_lines = skeletonize(road_mask(image))
    components, count = ndimage.label(center_lines, structure=np.ones((3, 3), dtype=bool))
    lengths = np.bincount(components.ravel())
    keep = lengths > 100
    keep[0] = False
    line = keep[components]
    height, width = line.shape
    # Each retained skeleton pixel is part of a junction or a simple chain.
    cells = set(map(int, np.flatnonzero(line)))
    def neighbors(i):
        x, y = i % width, i // width
        return [i + dx + dy * width for dx, dy in NEIGHBORS
                if 0 <= x + dx < width and 0 <= y + dy < height and i + dx + dy * width in cells
                and not (dx and dy and (i + dx in cells or i + dy * width in cells))]
    adjacent = {i: neighbors(i) for i in cells}
    keys = {i for i, ns in adjacent.items() if len(ns) != 2}
    # A closed isolated loop has no natural endpoints. Preserve the loop by
    # giving its component a single starting vertex.
    circular = set(np.flatnonzero(keep)) - {components.flat[i] for i in keys}
    for i in sorted(cells):
        label = components.flat[i]
        if label in circular:
            keys.add(i)
            circular.remove(label)
    links, nodes, edges = {}, [], []
    def node(i):
        if i not in links:
            links[i] = len(nodes)
            nodes.append([i % width, i // width])
        return links[i]
    visited = set()
    for start in sorted(keys):
        for nxt in adjacent[start]:
            if (start, nxt) in visited:
                continue
            chain = [start]
            current, previous = nxt, start
            while True:
                visited.add((previous, current))
                visited.add((current, previous))
                chain.append(current)
                if current in keys:
                    break
                a, b = adjacent[current]
                previous, current = current, b if a == previous else a
            # Include bend samples, so curves do not become long straight shortcuts.
            samples = chain[::5]
            if samples[-1] != chain[-1]:
                samples.append(chain[-1])
            for a, b in zip(samples, samples[1:]):
                edges.append([node(a), node(b)])
    data = {"frame": "gtadb-v18", "width": width, "height": height,
            "source": "YANIS v18 · GTADB and contributors · CC BY 4.0",
            "method": "cartographic road tracing", "nodes": nodes, "edges": edges}
    dest = ROOT / "public/roads.json"
    dest.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"{len(nodes):,} nodes, {len(edges):,} edges, {dest.stat().st_size:,} bytes; {count} input components.")


if __name__ == "__main__":
    build()

