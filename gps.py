"""Opt-in local map screenshot registration and explicit coordinate input."""

import base64
import binascii
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import hypot, isfinite
from threading import Lock

LOCATE_BODY_LIMIT = 1_300_000
MAX_IMAGE_DIMENSION = 1200
MAX_JPEG_BYTES = 950_000
REFERENCES = (
    ("powerpyx-map-original.png", "game-map-meta.json"),
    ("day-map.webp", "day-map-meta.json"),
)
SOF_MARKERS = set(range(0xc0, 0xd0)) - {0xc4, 0xc8, 0xcc}
NO_MATCH = "Could not align this screenshot confidently. Try a wider, unobstructed pause-map view."


class GpsUnavailable(RuntimeError):
    """The local feature is temporarily unavailable."""


def bounded_number(value, lower, upper):
    return type(value) in (int, float) and lower <= value <= upper


def frame_coordinates(payload, public_dir):
    if payload == {"clear": True} and payload["clear"] is True:
        return None
    if set(payload) == {"x", "y"}:
        x, y = payload["x"], payload["y"]
        if not all(bounded_number(value, 0, 1) for value in (x, y)):
            raise ValueError("Normalized x and y must be numbers from 0 through 1.")
    elif set(payload) == {"gameX", "gameY"}:
        try:
            meta = json.loads((public_dir / "map-meta.json").read_text(encoding="utf-8-sig"))
            frame = meta["coordinateFrame"]
            low_x, high_x = frame["minX"], frame["maxX"]
            low_y, high_y = frame["minY"], frame["maxY"]
            if not (low_x < high_x and low_y < high_y):
                raise ValueError
        except (OSError, ValueError, TypeError, KeyError):
            raise GpsUnavailable("The game coordinate frame is unavailable.") from None
        a, b = payload["gameX"], payload["gameY"]
        if not (bounded_number(a, low_x, high_x) and bounded_number(b, low_y, high_y)):
            raise ValueError("The game coordinates are outside the supported map frame.")
        x, y = (a - low_x) / (high_x - low_x), (high_y - b) / (high_y - low_y)
    else:
        raise ValueError("Provide x and y, gameX and gameY, or clear:true.")
    return {"x": x, "y": y, "updatedAt": datetime.now(timezone.utc).isoformat()}


def jpeg_size(data):
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Send a JPEG screenshot.")
    index = 2
    while index + 4 < len(data) and data[index] == 0xff:
        index += 1
        while index < len(data) and data[index] == 0xff:
            index += 1
        if index + 2 >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in (0xda, 0xd9):
            break
        length = int.from_bytes(data[index:index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        if marker in SOF_MARKERS and length >= 8:
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            return width, height
        index += length
    raise ValueError("The screenshot JPEG header is unreadable.")


def read_screenshot(payload):
    image = payload.get("image")
    if not isinstance(image, str) or not 0 < len(image) <= 4 * ((MAX_JPEG_BYTES + 2) // 3):
        raise ValueError("Send a base64 JPEG screenshot up to 950 KB.")
    try:
        jpeg = base64.b64decode(image, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Send a bare base64 JPEG screenshot.") from None
    if len(jpeg) > MAX_JPEG_BYTES or not jpeg.endswith(b"\xff\xd9"):
        raise ValueError("Send a complete JPEG screenshot up to 950 KB.")
    width, height = jpeg_size(jpeg)
    if not (240 <= min(width, height) and max(width, height) <= MAX_IMAGE_DIMENSION):
        raise ValueError("Resize the screenshot to at most 1200 pixels with at least 240 pixels on each edge.")
    x, y = payload.get("pixelX"), payload.get("pixelY")
    if not (bounded_number(x, 0, width - 1) and bounded_number(y, 0, height - 1)):
        raise ValueError("Click the player arrow inside the screenshot.")
    return jpeg, width, height, x, y


class ScreenshotLocator:
    def __init__(self, public_dir, asset_dir):
        self.public = public_dir
        self.assets = asset_dir
        self.lock = Lock()
        self.references = {}

    def locate(self, payload):
        jpeg, width, height, x, y = read_screenshot(payload)
        if not self.lock.acquire(blocking=False):
            raise GpsUnavailable("Another screenshot is being checked. Try again in a moment.")
        try:
            try:
                import cv2
                import numpy as np
            except ImportError:
                raise GpsUnavailable("Install opencv-python-headless to enable screenshot positioning.") from None
            cv2.setNumThreads(2)
            try:
                return self._locate(cv2, np, jpeg, width, height, x, y)
            except cv2.error:
                raise ValueError(NO_MATCH) from None
        finally:
            self.lock.release()

    def _reference(self, cv2, np, filename, metafile):
        path = self.assets / filename
        if not path.is_file():
            path = self.public / ("day-map.webp" if filename == "day-map.webp" else "game-map.png")
        meta_path = self.public / metafile
        try:
            stamp = (path.stat().st_mtime_ns, meta_path.stat().st_mtime_ns)
        except OSError:
            self.references.pop(filename, None)
            return None
        cached = self.references.get(filename)
        if cached and cached[0] == stamp:
            return cached[1]
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
            registration = meta["registration"]
            matrix = np.float64(registration["matrix"])
            raw = path.read_bytes()
            if "sha256" in meta and sha256(raw).hexdigest() != meta["sha256"]:
                return None
            gray = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if gray is None or gray.shape != (meta["height"], meta["width"]):
                return None
            if matrix.shape != (2, 3) or not np.isfinite(matrix).all():
                return None
            inverse = cv2.invertAffineTransform(matrix)
            if abs(float(np.linalg.det(matrix[:, :2]))) < 0.01:
                return None
            frame_size = np.float64([registration["inputWidth"], registration["inputHeight"]])
            if np.any(frame_size < 100) or not np.isfinite(frame_size).all():
                return None
            sift = cv2.SIFT_create(nfeatures=18000, contrastThreshold=.012)
            keypoints, descriptors = sift.detectAndCompute(gray, None)
            if descriptors is None or len(descriptors) < 100:
                return None
            index = cv2.FlannBasedMatcher({"algorithm": 1, "trees": 5}, {"checks": 80})
            index.add([descriptors])
            index.train()
            ref = (index, np.float32([point.pt for point in keypoints]), inverse, frame_size)
            self.references[filename] = (stamp, ref)
            return ref
        except (OSError, ValueError, TypeError, KeyError, cv2.error, OverflowError):
            return None

    def _locate(self, cv2, np, jpeg, width, height, x, y):
        gray = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8),
                            cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
        if gray is None or gray.shape != (height, width) or gray.std() < 9:
            raise ValueError(NO_MATCH)
        sift = cv2.SIFT_create(nfeatures=4200, contrastThreshold=.013)
        keypoints, descriptors = sift.detectAndCompute(gray, None)
        if descriptors is None or len(descriptors) < 45:
            raise ValueError(NO_MATCH)
        points = np.float32([point.pt for point in keypoints])
        click = np.float64([x, y])
        results = []
        available = False
        for filename, metafile in REFERENCES:
            reference = self._reference(cv2, np, filename, metafile)
            if reference is None:
                continue
            available = True
            result = match_reference(cv2, np, reference, points, descriptors, click, width, height)
            if result is not None:
                results.append(result)
        if not available:
            raise GpsUnavailable("Install the In-game map or GTADB Day reference for screenshot positioning.")
        if not results:
            raise ValueError(NO_MATCH)
        results.sort(key=lambda result: result["inliers"], reverse=True)
        best = results[0]
        if any(hypot(best["x"] - other["x"], best["y"] - other["y"]) > .004 for other in results[1:]):
            raise ValueError("Map references disagree about this position. Try a wider screenshot.")
        return best


def match_reference(cv2, np, reference, points, descriptors, click, width, height):
    index, target, inverse, frame_size = reference
    unique = {}
    pairs = index.knnMatch(descriptors, k=2)
    acceptable = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < .75 * pair[1].distance]
    for match in sorted(acceptable, key=lambda match: match.distance):
        unique.setdefault(match.trainIdx, match.queryIdx)
    if len(unique) < 42:
        return None
    source = points[list(unique.values())]
    mapped = target[list(unique)]
    permutation = np.random.default_rng(20261121).permutation(len(source))
    train, holdout = np.split(permutation, [len(permutation) * 4 // 5])
    matrix, _ = cv2.estimateAffinePartial2D(source[train], mapped[train], method=cv2.RANSAC,
                                            ransacReprojThreshold=4, maxIters=2500)
    if matrix is None or not np.isfinite(matrix).all():
        return None
    scale = float(np.linalg.norm(matrix[:, 0]))
    if not (.12 <= scale <= 9 and matrix[0, 0] / scale >= .90):
        return None
    errors = np.linalg.norm(source @ matrix[:, :2].T + matrix[:, 2] - mapped, axis=1)
    inliers = errors <= 4
    accepted = source[inliers]
    count = int(inliers.sum())
    checks = errors[holdout][inliers[holdout]]
    if count < 35 or count < len(source) * .19 or len(checks) < 8:
        return None
    if np.any(np.ptp(accepted, axis=0) < [max(42, width * .10), max(42, height * .10)]):
        return None
    hull = cv2.convexHull(accepted)
    if cv2.contourArea(hull) < max(1800, width * height * .015):
        return None
    click_margin = cv2.pointPolygonTest(hull, tuple(click), True)
    distances = np.linalg.norm(accepted - click, axis=1)
    if click_margin < -max(14, min(width, height) * .04) or (distances <= min(width, height) * .27).sum() < 4:
        return None
    # Refuse another independently supported placement of the same scene.
    if len(source) - count >= 35:
        alt_source, alt_target = source[~inliers], mapped[~inliers]
        alternative, flags = cv2.estimateAffinePartial2D(alt_source, alt_target, method=cv2.RANSAC,
                                                         ransacReprojThreshold=4, maxIters=800)
        if alternative is not None and flags is not None and int(flags.sum()) >= max(26, count * .62):
            disagreement = np.linalg.norm((matrix - alternative) @ np.append(click, 1))
            if disagreement > 10:
                return None
    matched_pixel = matrix[:, :2] @ click + matrix[:, 2]
    canonical = (inverse[:, :2] @ matched_pixel + inverse[:, 2]) / frame_size
    if not all(bounded_number(float(axis), 0, 1) for axis in canonical):
        return None
    error = float(np.quantile(checks, .9) * np.linalg.norm(inverse[:, 0]))
    if not isfinite(error) or error > 5.5:
        return None
    return {"x": float(canonical[0]), "y": float(canonical[1]), "matched": len(unique),
            "inliers": count, "errorPixels": round(error, 2)}
