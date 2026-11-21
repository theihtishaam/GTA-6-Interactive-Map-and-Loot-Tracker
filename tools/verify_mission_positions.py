"""Recheck mission markers against the pinned full in-game map reference."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from verify_activity_positions import PROJECT, reference_features, screenshot_data


def setup_matcher():
    cv2.setNumThreads(2)
    cv2.setRNGSeed(26)
    sift = cv2.SIFT_create(nfeatures=14000, contrastThreshold=.012)
    points, descriptors = reference_features(PROJECT / ".atlas" / "powerpyx-map-original.png", sift)
    matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=90))
    matcher.add([descriptors])
    matcher.train()
    return sift, matcher, points


def fit_map(image, sift, matcher, target):
    if image is None or image.shape not in {(1080, 1920), (720, 1280)}:
        raise ValueError("Unexpected screenshot dimensions.")
    normalization = 1920 / image.shape[1]
    if normalization != 1:
        image = cv2.resize(image, (1920, 1080), interpolation=cv2.INTER_CUBIC)
    mask = np.full_like(image, 255)
    mask[:, :76] = 0
    mask[:80, :] = 0
    mask[345:900, 1010:1650] = 0
    mask[:140, 1700:] = 0
    mask[790:, 1680:] = 0
    mask[985:, :] = 0
    keypoints, descriptors = sift.detectAndCompute(image, mask)
    if descriptors is None or len(descriptors) < 20:
        raise ValueError("Insufficient map features.")
    matches = [m for m, n in matcher.knnMatch(descriptors, k=2) if m.distance < .76 * n.distance]
    distinct = {}
    for match in sorted(matches, key=lambda item: item.distance):
        distinct.setdefault(match.trainIdx, match)
    unique = list(distinct.values())
    if len(unique) < 110:
        raise ValueError("Too few distinct candidate controls.")
    source = np.float32([keypoints[m.queryIdx].pt for m in unique])
    destination = target[[m.trainIdx for m in unique]]
    permutation = np.random.default_rng(20261121).permutation(len(unique))
    fit, holdout = np.split(permutation, [len(unique) * 4 // 5])
    matrix, flags = cv2.estimateAffinePartial2D(
        source[fit], destination[fit], method=cv2.RANSAC, ransacReprojThreshold=4,
    )
    if matrix is None:
        raise ValueError("No consistent map registration.")
    inliers = source[fit][flags.ravel().astype(bool)]
    errors = np.linalg.norm(source[holdout] @ matrix[:, :2].T + matrix[:, 2] - destination[holdout], axis=1)
    accepted = errors <= 4
    scale = float(np.linalg.norm(matrix[:, 0]))
    if (len(inliers) < 75 or accepted.sum() < 15 or np.any(np.ptp(inliers, axis=0) < [300, 380])
            or not .10 < scale < 2 or abs(matrix[0, 1]) > .018 * scale):
        raise ValueError("Map controls or geometry are inadequate.")
    p90 = float(np.quantile(errors[accepted], .9))
    if p90 > 3:
        raise ValueError("Held-out controls disagree.")
    return matrix, inliers, int(accepted.sum()), p90, scale, normalization


def project_marker(fit, marker, registration):
    matrix, controls, held, p90, scale, normalization = fit
    marker = marker * normalization
    distances = np.linalg.norm(controls - marker, axis=1)
    nearby = int(sum(distances < 360))
    if nearby < 4 or distances.min() > 260:
        raise ValueError("Too few road or coastline controls near the selected mission.")
    point = matrix[:, :2] @ marker + matrix[:, 2]
    affine = np.array(registration["matrix"])
    x, y = np.linalg.solve(affine[:, :2], point - affine[:, 2])
    return point, x / registration["inputWidth"], y / registration["inputHeight"], {
        "inliers": len(controls), "heldOutMatches": held, "nearbyControls": nearby,
        "p90ImagePixels": round(p90, 3), "referenceScale": round(scale, 5),
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--screenshots", type=Path, default=PROJECT / ".atlas" / "mission-screenshots")
    cli.add_argument("--download", action="store_true")
    args = cli.parse_args()
    catalogue = json.loads((PROJECT / "public" / "mission-positions.json").read_text(encoding="utf-8"))
    registration = json.loads((PROJECT / "public" / "game-map-meta.json").read_text(encoding="utf-8"))["registration"]
    affine = np.array(registration["matrix"])
    matcher = setup_matcher()
    max_delta = 0
    for mission_id, row in catalogue.items():
        image = screenshot_data(args.screenshots, row, args.download)
        point, _, _, stats = project_marker(fit_map(image, *matcher), np.array(row["sourceMarkerPixel"]), registration)
        shipped = np.array((row["x"] * registration["inputWidth"], row["y"] * registration["inputHeight"]))
        delta = np.linalg.norm(point - (affine[:, :2] @ shipped + affine[:, 2]))
        max_delta = max(max_delta, delta)
        if delta > 3 or stats["p90ImagePixels"] > 3:
            raise ValueError(f"{mission_id} alignment changed by {delta:.2f} reference pixels.")
    print(f"{len(catalogue)} mission markers reproduced; largest position difference {max_delta:.2f} reference pixels.")


if __name__ == "__main__":
    main()
