import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers import add_source_steps, configure, list_models


class ModelPickerTests(unittest.TestCase):
    def test_cloud_catalogue_is_anonymous_and_filters_api_ineligible_models(self):
        config = configure({"kind": "ollama-cloud", "model": "gpt-oss:20b",
                            "key": "fixture-only"}, probe=True)

        def public_inventory(url, headers, payload, **kwargs):
            self.assertEqual(url, "https://ollama.com/v1/models")
            self.assertNotIn("Authorization", headers)
            self.assertIsNone(payload)
            return json.dumps({
                "data": [{"id": name} for name in
                         ("gpt-oss:20b", "gpt-oss:20b", "gemma4:31b", "audio-only", "hidden", "x<y")],
                "models": [{"slug": "hidden", "supported_in_api": False},
                           {"slug": "audio-only", "input_modalities": ["audio"]}],
            }).encode()

        result = list_models(config, public_inventory)
        self.assertEqual(result["models"], ["gemma4:31b", "gpt-oss:20b"])
        self.assertEqual(result["recommended"], "gpt-oss:20b")
        self.assertEqual(result["billing"], "metered")
        self.assertTrue(result["selectedAvailable"])

    def test_cloud_catalogue_does_not_substitute_a_metered_model(self):
        config = configure({"kind": "ollama-cloud", "model": "gpt-oss:20b"}, probe=True)
        result = list_models(config, lambda *_args, **_kw: b'{"data":[{"id":"different"}]}')
        self.assertEqual(result["models"], ["different"])
        self.assertFalse(result["selectedAvailable"])
        self.assertIsNone(result["recommended"])
        with self.assertRaisesRegex(RuntimeError, "unreadable"):
            list_models(config, lambda *_args, **_kw: b"invalid")

    def test_metered_cloud_requires_consent_and_never_runs_on_probe(self):
        settings = {"kind": "ollama-cloud", "model": "gpt-oss:20b", "enabled": True,
                    "key": "fixture-only"}
        with self.assertRaisesRegex(ValueError, "explicit consent"):
            configure(settings)
        self.assertFalse(configure(settings, probe=True).active)
        active = configure({**settings, "allowPaid": True})
        self.assertTrue(active.active)
        self.assertFalse(configure({"kind": "none"}, active).active)
        self.assertTrue(configure({"kind": "openrouter", "key": "fixture-only", "enabled": True}).active)

        def chat(url, headers, payload, **kwargs):
            self.assertEqual(payload["think"], "low")
            self.assertEqual(payload["options"]["num_predict"], 220)
            return b'{"message":{"content":"{\\"steps\\":[]}"}}'

        self.assertEqual(add_source_steps(active, {"_extract": "No directions."}, chat),
                         "No source-backed steps extracted.")

    def test_openrouter_retains_free_models_in_large_catalogue(self):
        rows = [{"id": f"paid-{i:03}"} for i in range(260)]
        rows += [{"id": "openrouter/free"}, {"id": "zzz/atlas:free"},
                 {"id": "image-only:free", "architecture": {"output_modalities": ["image"]}}]
        result = list_models(configure({"kind": "openrouter"}, probe=True),
                             lambda *_args, **_kw: json.dumps({"data": rows}).encode())
        self.assertEqual(result["models"][:2], ["openrouter/free", "zzz/atlas:free"])
        self.assertNotIn("image-only:free", result["models"])


if __name__ == "__main__":
    unittest.main()
