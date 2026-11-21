import json
from collections import Counter
from hashlib import sha256
import math
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from tools import import_gtadb

PROJECT = Path(__file__).resolve().parents[1]
PUBLIC = PROJECT / "public"
CACHE = PROJECT / ".gtadb-import"
RUNTIME = PROJECT / ".atlas"


class MapDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = json.loads((PUBLIC / "map-meta.json").read_text(encoding="utf-8"))
        cls.landmarks = json.loads((PUBLIC / "landmarks.json").read_text(encoding="utf-8"))

    def test_raster_matches_declared_frame(self):
        meta = self.metadata
        frame = meta["coordinateFrame"]
        with Image.open(PUBLIC / "map.webp") as image:
            self.assertEqual(image.size, (meta["width"], meta["height"]))
            self.assertEqual(image.format, "WEBP")
            image.verify()
        self.assertEqual(meta["revision"], import_gtadb.REVISION)
        self.assertEqual((meta["width"], meta["height"]), (3456, 4864))
        self.assertEqual((frame["minX"], frame["maxX"]), (-10240, 3584))
        self.assertEqual((frame["minY"], frame["maxY"]), (-8960, 10496))
        scale = frame["gameUnitsPerPixel"]
        self.assertEqual(frame["maxX"] - frame["minX"], scale * meta["width"])
        self.assertEqual(frame["maxY"] - frame["minY"], scale * meta["height"])

    def test_landmark_identity_metadata_and_bounds(self):
        ids = {entry["id"] for entry in self.landmarks}
        self.assertEqual(len(ids), len(self.landmarks), "duplicate landmark ID")
        self.assertEqual(len(ids), self.metadata["landmarkCount"])
        self.assertEqual(len(ids), 3663)
        self.assertEqual(Counter(entry["nameOrigin"] for entry in self.landmarks),
                         {"game": 983, "counterpart": 1350, "placeholder": 1330})
        for entry in self.landmarks:
            self.assertRegex(entry["id"], r"^gtadb-L\d+$")
            self.assertTrue(entry["title"].strip())
            self.assertTrue(entry["region"].strip())
            self.assertEqual(entry["category"], "landmark")
            self.assertEqual(entry["confidence"], "community")
            self.assertEqual(entry["steps"], [])
            self.assertEqual(entry["source"], f"https://map.gtadb.org/#VI,{entry['id'][6:]}")
            if entry["nameOrigin"] == "placeholder":
                self.assertTrue(entry["title"].startswith("Unnamed "))
                self.assertTrue(entry["title"].endswith(entry["id"][6:]))
            for axis in ("x", "y"):
                self.assertTrue(math.isfinite(entry[axis]))
                self.assertLessEqual(0, entry[axis])
                self.assertLessEqual(entry[axis], 1)

    def test_landmarks_reconstruct_source_position(self):
        frame = self.metadata["coordinateFrame"]
        by_id = {entry["id"]: entry for entry in self.landmarks}
        # Reference positions independently read from the pinned landmark JSON.
        positions = {
            "gtadb-L1": (1409.40126306379, 2803.2135475894142),
            "gtadb-L224": (-393.402, -494.7085),
            "gtadb-L266": (-2353.531, -5532.255),
            "gtadb-L304": (-5354.67, 3461.862),
            "gtadb-L1869": (1420.182, 1766.116),
        }
        for landmark_id, (source_x, source_y) in positions.items():
            entry = by_id[landmark_id]
            with self.subTest(landmark_id=landmark_id):
                x = frame["minX"] + entry["x"] * (frame["maxX"] - frame["minX"])
                y = frame["maxY"] - entry["y"] * (frame["maxY"] - frame["minY"])
                self.assertAlmostEqual(x, source_x, places=3)
                self.assertAlmostEqual(y, source_y, places=3)

    def test_optional_map_registration(self):
        layer_files = {
            "day": "day-map.webp",
            "game": "powerpyx-map-original.png",
            "official": "rockstar-map-original.jpg",
        }
        for layer, filename in layer_files.items():
            with self.subTest(layer=layer):
                meta = json.loads((PUBLIC / f"{layer}-map-meta.json").read_text(encoding="utf-8"))
                registration = meta["registration"]
                self.assertEqual(registration["inputWidth"], self.metadata["width"])
                self.assertEqual(registration["inputHeight"], self.metadata["height"])
                (a, b, tx), (c, d, ty) = registration["matrix"]
                self.assertGreater(a * d - b * c, 0)
                for entry in self.landmarks:
                    x, y = entry["x"] * self.metadata["width"], entry["y"] * self.metadata["height"]
                    self.assertTrue(0 <= a * x + b * y + tx < meta["width"])
                    self.assertTrue(0 <= c * x + d * y + ty < meta["height"])
                path = RUNTIME / filename
                if path.exists():
                    if "sha256" in meta:
                        self.assertEqual(sha256(path.read_bytes()).hexdigest(), meta["sha256"])
                    with Image.open(path) as image:
                        self.assertEqual(image.size, (meta["width"], meta["height"]))
                        image.verify()

    @unittest.skipUnless((CACHE / "map/data/6/landmarks.json").is_file(), "source cache is optional")
    def test_import_matches_pinned_cache(self):
        source_path = CACHE / "map/data/6/landmarks.json"
        source_rows = json.loads(source_path.read_text(encoding="utf-8"))
        self.assertEqual(len(source_rows), self.metadata["sourceLandmarkCount"])
        self.assertEqual(list(import_gtadb.build_landmarks(source_rows)), self.landmarks)
        self.assertEqual({entry["id"] for entry in self.landmarks},
                         {f"gtadb-{source_id}" for source_id, row in source_rows.items() if row[1]})
        for entry in self.landmarks:
            self.assertEqual(entry["sourceTags"], source_rows[entry["id"][6:]][6])
        with tempfile.TemporaryDirectory() as directory:
            raster = Path(directory) / "map.webp"
            import_gtadb.build_map(CACHE, raster)
            with Image.open(raster) as rebuilt, Image.open(PUBLIC / "map.webp") as actual:
                self.assertEqual(rebuilt.tobytes(), actual.tobytes())


if __name__ == "__main__":
    unittest.main()
