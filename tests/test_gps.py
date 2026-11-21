"""Deterministic synthetic registration and coordinate-frame fixtures."""

import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gps import GpsUnavailable, ScreenshotLocator, frame_coordinates, jpeg_size

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = np = None


def payload(image, x, y):
    jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]
    return {"image": base64.b64encode(jpeg).decode(), "pixelX": x, "pixelY": y}


class CoordinateTests(unittest.TestCase):
    def test_explicit_signed_normalized_and_clear(self):
        with TemporaryDirectory() as folder:
            public = Path(folder)
            (public / "map-meta.json").write_text(json.dumps({"coordinateFrame": {
                "minX": -10240, "maxX": 3584, "minY": -8960, "maxY": 10496,
            }}), encoding="utf-8")
            values = frame_coordinates({"gameX": -6784, "gameY": -4096}, public)
            self.assertEqual((values["x"], values["y"]), (0.25, 0.75))
            self.assertTrue(values["updatedAt"].endswith("+00:00"))
            self.assertEqual(frame_coordinates({"x": 0.9, "y": 0}, public)["x"], 0.9)
            self.assertIsNone(frame_coordinates({"clear": True}, public))
            for value in ({"clear": 1}, {"x": True, "y": 0}, {"gameX": 4000, "gameY": 0},
                          {"x": float("nan"), "y": 0}, {"x": 0.1, "y": 0.1, "gameX": 0}):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    frame_coordinates(value, public)

    def test_reject_nonjpeg_headers(self):
        with self.assertRaisesRegex(ValueError, "JPEG"):
            jpeg_size(b"not a jpeg")
        with self.assertRaisesRegex(ValueError, "header"):
            jpeg_size(b"\xff\xd8\xff\xc0\xff\xff")


@unittest.skipIf(cv2 is None, "Optional OpenCV and NumPy are unavailable")
class RegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cv2.setNumThreads(2)
        cls.temp = TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.public = Path(cls.temp.name)
        cls.width, cls.height = 1400, 1800
        cls.map = np.full((cls.height, cls.width), 205, dtype=np.uint8)
        rng = np.random.default_rng(487)
        for i in range(500):
            x, y = (int(v) for v in rng.integers([4, 4], [cls.width - 54, cls.height - 52]))
            color, radius = (int(v) for v in rng.integers([35, 3], [175, 20]))
            cv2.circle(cls.map, (x, y), radius, color, rng.choice([1, 2, 3]).item())
            cv2.putText(cls.map, str(i), (x, y), cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1, cv2.LINE_AA)
        self = cls
        cv2.imwrite(str(self.public / "powerpyx-map-original.png"), self.map)
        (self.public / "game-map-meta.json").write_text(json.dumps({
            "width": self.width, "height": self.height,
            "registration": {
                "inputWidth": self.width, "inputHeight": self.height, "matrix": [[1, 0, 0], [0, 1, 0]],
            },
        }), encoding="utf-8")
        cls.locator = ScreenshotLocator(cls.public, cls.public)

    def test_scaled_rotated_jpeg_crop(self):
        left, top = 380, 730
        crop = self.map[top:top + 720, left:left + 580]
        affine = cv2.getRotationMatrix2D((290, 360), 4, 1.15)
        scene = cv2.warpAffine(crop, affine, (580, 720), borderValue=90)
        local_x, local_y = 214, 361
        x, y = (float(v) for v in affine @ [local_x, local_y, 1])
        result = self.locator.locate(payload(scene, x, y))
        self.assertAlmostEqual(result["x"] * self.width, local_x + left, delta=2)
        self.assertAlmostEqual(result["y"] * self.height, local_y + top, delta=2)
        self.assertGreaterEqual(result["inliers"], 35)
        self.assertLess(result["errorPixels"], 4)

    def test_bad_nonmatching_and_unanchored_images(self):
        flat = np.full((460, 600), 120, dtype=np.uint8)
        noise = np.random.default_rng(42).integers(0, 255, flat.shape, dtype=np.uint8)
        for image in (flat, noise):
            with self.assertRaisesRegex(ValueError, "align"):
                self.locator.locate(payload(image, 300, 200))
        large = np.full((600, 1400), 120, dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, "Resize"):
            self.locator.locate(payload(large, 300, 200))
        mostly_ui = flat.copy()
        mostly_ui[40:400, 220:590] = self.map[300:660, 360:730]
        with self.assertRaisesRegex(ValueError, "align"):
            self.locator.locate(payload(mostly_ui, 23, 19))

    def test_competing_placements_refused(self):
        scene = np.concatenate([self.map[50:600, 75:625], self.map[880:1430, 770:1320]], axis=1)
        with self.assertRaisesRegex(ValueError, "align"):
            self.locator.locate(payload(scene, 235, 170))

    def test_missing_data_returns_specific_error(self):
        with TemporaryDirectory() as absent:
            locator = ScreenshotLocator(Path(absent), Path(absent))
            with self.assertRaises(GpsUnavailable):
                locator.locate(payload(self.map[:460, :600], 300, 200))


if __name__ == "__main__":
    unittest.main()
