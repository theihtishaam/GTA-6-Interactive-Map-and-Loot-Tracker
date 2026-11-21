"""Recheck published activity pins against their selected in-game map screenshots."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
SOURCE_HOST = "www.powerpyx.com"
UPLOAD_PREFIX = "/wp-content/uploads/"


def reference_features(path, sift):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("Install the in-game reference with tools/install_local_maps.py --layer game.")
    keypoints, descriptors = sift.detectAndCompute(image, None)
    return np.float32([point.pt for point in keypoints]), descriptors


def screenshot_data(root, record, download):
    parsed = urlparse(record["sourceImage"])
    filename = Path(parsed.path).name
    if (parsed.scheme, parsed.netloc, parsed.path) != (
        "https", SOURCE_HOST, UPLOAD_PREFIX + filename,
    ) or parsed.query or parsed.fragment:
        raise ValueError(f"Unexpected screenshot source: {record['sourceImage']}")
    path = root / filename
    if download and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(record["sourceImage"], timeout=30) as response:
            path.write_bytes(response.read())
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != record["sourceImageSha256"]:
        raise ValueError(f"Source screenshot changed: {filename}")
    return cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def align(image, marker, sift, matcher, target, precision="map-marker"):
    if image is None or image.shape != (1080, 1920):
        raise ValueError("Unexpected screenshot dimensions.")
    mask = np.full_like(image, 255)
    # Omit map chrome, the detail panel, and the credit across the bottom.
    if precision == "map-marker":
        mask[:, :545] = 0
        mask[300:763, 1015:1590] = 0
    else:
        mask[:, :75] = 0
        mask[:80, :] = 0
        mask[380:900, 1010:1630] = 0
    mask[:140, 1700:] = 0
    mask[790:, 1680:] = 0
    mask[985:, :] = 0
    keypoints, descriptors = sift.detectAndCompute(image, mask)
    matches = [m for m, n in matcher.knnMatch(descriptors, k=2) if m.distance < .76 * n.distance]
    best_per_target = {}
    for match in sorted(matches, key=lambda match: match.distance):
        best_per_target.setdefault(match.trainIdx, match)
    unique = list(best_per_target.values())
    if len(unique) < 110:
        raise ValueError(f"Only {len(unique)} distinct road and coastline matches.")
    source_points = np.float32([keypoints[match.queryIdx].pt for match in unique])
    target_points = target[[match.trainIdx for match in unique]]
    permutation = np.random.default_rng(20261121).permutation(len(unique))
    fit, holdout = np.split(permutation, [len(unique) * 4 // 5])
    matrix, flags = cv2.estimateAffinePartial2D(source_points[fit], target_points[fit],
                                               method=cv2.RANSAC, ransacReprojThreshold=4)
    if matrix is None:
        raise ValueError("No consistent registration.")
    rectangle = np.ptp(source_points[fit][flags.ravel().astype(bool)], axis=0)
    errors = np.linalg.norm(source_points[holdout] @ matrix[:, :2].T + matrix[:, 2]
                            - target_points[holdout], axis=1)
    accepted = errors <= 4
    if (flags.sum() < 80 or accepted.sum() < 14 or np.any(rectangle < [300, 400])
            or abs(np.linalg.norm(matrix[:, 0]) - 1) > .01):
        raise ValueError("Too few controls or unexpectedly different screenshot scale.")
    point = matrix[:, :2] @ marker + matrix[:, 2]
    return point, int(accepted.sum()), float(np.quantile(errors[accepted], .9))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=PROJECT / ".atlas" / "activity-screenshots")
    parser.add_argument("--download", action="store_true", help="Fetch missing source screenshots into the local cache.")
    args = parser.parse_args()
    cv2.setNumThreads(2)
    cv2.setRNGSeed(26)
    sift = cv2.SIFT_create(nfeatures=14000, contrastThreshold=.012)
    points, descriptors = reference_features(PROJECT / ".atlas" / "powerpyx-map-original.png", sift)
    matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=90))
    matcher.add([descriptors])
    matcher.train()
    meta = json.loads((PROJECT / "public" / "game-map-meta.json").read_text(encoding="utf-8"))
    ref = meta["registration"]
    matrix = np.array(ref["matrix"])
    catalogue = json.loads((PROJECT / "public" / "guide-positions.json").read_text(encoding="utf-8"))

    summary = []
    for guide_id, record in catalogue.items():
        if not record.get("sourceImage"):
            continue
        image = screenshot_data(args.screenshots, record, args.download)
        point, inliers, error = align(image, np.array(record["sourceMarkerPixel"]), sift,
                                      matcher, points, record["precision"])
        source = np.array([record["x"] * ref["inputWidth"], record["y"] * ref["inputHeight"]])
        delta = np.linalg.norm(point - (matrix[:, :2] @ source + matrix[:, 2]))
        if delta > 3 or error > 3:
            raise ValueError(f"{guide_id} failed independent registration ({delta:.2f} px; p90 {error:.2f} px).")
        summary.append((inliers, error, delta))
    print(f"{len(summary)} pins checked. Each had at least {min(row[0] for row in summary)} held-out matches.")
    print(f"Largest held-out p90 residual {max(row[1] for row in summary):.2f} px.")
    print(f"Largest variation from shipped marker {max(row[2] for row in summary):.2f} px.")


if __name__ == "__main__":
    main()
