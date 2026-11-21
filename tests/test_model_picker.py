import json
from pathlib import Path
import sys
import unittest
from datetime import timedelta
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers import CatalogueUnavailable, add_source_steps, check_access, configure, list_models
from server import Atlas, utcnow


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
                         ("gpt-oss:120b", "gpt-oss:20b", "gpt-oss:20b", "gemma4:31b", "audio-only", "hidden", "x<y")],
                "models": [{"slug": "hidden", "supported_in_api": False},
                           {"slug": "audio-only", "input_modalities": ["audio"]}],
            }).encode()

        result = list_models(config, public_inventory)
        self.assertEqual(result["models"], ["gpt-oss:120b", "gemma4:31b", "gpt-oss:20b"])
        self.assertEqual(result["recommended"], "gpt-oss:120b")
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
        settings = {"kind": "ollama-cloud", "model": "gpt-oss:120b", "enabled": True,
                    "key": "fixture-only"}
        with self.assertRaisesRegex(ValueError, "explicit consent"):
            configure(settings)
        self.assertFalse(configure(settings, probe=True).active)
        active = configure({**settings, "allowPaid": True})
        self.assertTrue(active.active)
        self.assertFalse(configure({"kind": "none"}, active).active)
        self.assertTrue(configure({"kind": "openrouter", "key": "fixture-only", "enabled": True}).active)

        def chat(url, headers, payload, **kwargs):
            self.assertEqual(payload["model"], "gpt-oss:120b")
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
        self.assertEqual(result["recommended"], "openrouter/free")
        rows.append({"id": "openai/gpt-oss-120b:free"})
        result = list_models(configure({"kind":"openrouter"}, probe=True),
                             lambda *_args, **_kw: json.dumps({"data":rows}).encode())
        self.assertEqual(result["models"][0], "openai/gpt-oss-120b:free")
        self.assertEqual(result["recommended"], result["models"][0])

    def test_connect_without_model_uses_live_default_and_preserves_an_override(self):
        with TemporaryDirectory() as folder:
            atlas = Atlas(cache=Path(folder) / "state.json")
            options = {"kind":"openrouter", "enabled":True, "key":"fixture-only", "startDiscovery":True}
            models = {"models":["openrouter/free", "other:free"], "recommended":"openrouter/free"}
            with patch("server.list_models", return_value=models) as inventory, patch("server.check_access", return_value="verified"):
                self.assertEqual(atlas.set_provider({"kind":"openrouter", "key":"fixture-only"})["provider"]["model"], "")
                inventory.assert_not_called()
                self.assertEqual(atlas.set_provider(options)["provider"]["model"], "openrouter/free")
                inventory.assert_called_once()
                atlas.set_provider({**options,"startDiscovery":False,"model":"other:free"})
                self.assertEqual(atlas.set_provider(options)["provider"]["model"], "other:free")
                inventory.assert_called_once()

    def test_openrouter_120b_chat_uses_selected_free_id(self):
        config = configure({"kind":"openrouter", "model":"openai/gpt-oss-120b:free", "key":"fixture-only", "enabled":True})
        def chat(url, headers, payload, **kwargs):
            self.assertEqual(payload["model"], "openai/gpt-oss-120b:free")
            self.assertEqual(payload["reasoning"], {"effort":"low"})
            return json.dumps({"choices":[{"message":{"content":'{"steps":[]}'}}]}).encode()
        self.assertEqual(add_source_steps(config, {"_extract":"No directions."}, chat), "No source-backed steps extracted.")

    def test_key_checks_use_one_fixed_service_and_return_only_a_verdict(self):
        for kind, endpoint, body, expected in (
            ("ollama-cloud", "https://ollama.com/api/me", {}, {"Name": "fixture-account"}),
            ("openrouter", "https://openrouter.ai/api/v1/key", None, {"data": {"label": "fixture-label"}}),
        ):
            with self.subTest(kind=kind):
                cfg = configure({"kind": kind, "key": "fixture-only"}, probe=True)
                def account(url, headers, payload, **kwargs):
                    self.assertEqual((url, payload), (endpoint, body))
                    self.assertEqual(headers["Authorization"], "Bearer fixture-only")
                    return json.dumps(expected).encode()
                self.assertEqual(check_access(cfg, account), "verified")
                with self.assertRaisesRegex(RuntimeError, "could not confirm"):
                    check_access(cfg, lambda *_, **__: b"{}")
                def catalogue(url, headers, **kwargs):
                    self.assertNotIn("Authorization", headers)
                    return b'{"data":[]}'
                list_models(cfg, catalogue)
        fake = "sk-or-v1-" + "a" * 64
        for kind in ("ollama-cloud", "custom", "opencode"):
            with self.assertRaisesRegex(ValueError, "Choose OpenRouter"):
                configure({"kind": kind, "base": "https://fixture.example/v1", "key": fake}, probe=True)
        for values, expected in (({"kind": "ollama-local"}, "local"), ({"kind": "ollama-cloud"}, "catalogue-only"),
                                 ({"kind": "custom", "base": "https://fixture.example/v1", "key":"fixture-only"}, "catalogue-only")):
            self.assertEqual(check_access(configure(values, probe=True), self.fail), expected)

    def test_connection_is_atomic_and_queues_a_single_general_scan(self):
        with TemporaryDirectory() as folder:
            app = Atlas(cache=Path(folder) / "state.json")
            app.settings({"interval": 6})
            app.bounty_settings({"interval": 12})
            config = {"kind": "openrouter", "model": "openrouter/free", "key": "fixture-only",
                      "enabled": True, "startDiscovery": True}
            with patch("server.check_access", side_effect=RuntimeError("Fixture rejected")):
                with self.assertRaisesRegex(RuntimeError, "rejected"):
                    app.set_provider(config)
            self.assertFalse(app.provider.active or app.requested)
            with patch("server.check_access", return_value="verified") as access:
                with patch("server.list_models", return_value={"selectedAvailable": False}):
                    with self.assertRaisesRegex(ValueError, "outside"):
                        app.set_provider(config)
                with patch("server.list_models", return_value={"selectedAvailable": True}):
                    result = app.set_provider(config)
                    self.assertTrue(result["initialDiscovery"] and app.requested)
                    self.assertNotIn("fixture-only", json.dumps(result))
                    self.assertNotIn("fixture-only", app.cache.read_text(encoding="utf8"))
                    app.requested = False
                    result = app.set_provider(config)
                    self.assertFalse(result["initialDiscovery"] or app.requested)
                    self.assertEqual(access.call_count, 2)
                    self.assertTrue(app.set_provider({**config, "model": "second:free"})["initialDiscovery"])
                    self.assertFalse(app.bounty_requested)
                    self.assertEqual((app.interval, app.bounty_interval), (6, 12))
                    app.requested = False
                    self.assertFalse(app.set_provider({**config, "enabled": False})["initialDiscovery"] or app.requested)

    def test_initial_worker_processes_at_most_one_new_report(self):
        with TemporaryDirectory() as folder:
            seen = Event()
            runs = []
            def feeds(landmarks):
                runs.append(1)
                return [], [{"id": str(i), "publishedAt": "2030-01-01", "_extract": "sample", "category": "bag",
                             "title": "Fixture bag", "sourceDigest": str(i), "steps": []} for i in range(2)]
            app = Atlas(cache=Path(folder) / "state.json", discovery=feeds)
            app.next_run = utcnow() + timedelta(days=1)
            def enriched(*args, **kwargs):
                seen.set()
                return "Fixture source checked."
            with patch("server.check_access", return_value="local"), patch("server.list_models", return_value={"selectedAvailable": True}), patch("server.add_source_steps", side_effect=enriched) as chat:
                worker = Thread(target=app.worker)
                worker.start()
                try:
                    config = {"kind": "ollama-local", "model": "fixture:3b", "enabled": True, "startDiscovery": True}
                    self.assertTrue(app.set_provider(config)["initialDiscovery"])
                    self.assertTrue(seen.wait(4))
                    self.assertFalse(app.set_provider(config)["initialDiscovery"])
                finally:
                    with app.change:
                        app.stopping = True
                        app.change.notify_all()
                    worker.join(4)
                self.assertFalse(worker.is_alive())
                self.assertEqual(runs, [1])
                chat.assert_called_once()

    def test_manual_model_handles_unsupported_catalogue_but_rejects_bad_access(self):
        with TemporaryDirectory() as folder:
            app = Atlas(cache=Path(folder) / "state.json")
            config = {"kind": "custom", "model": "private-model", "base": "https://fixture.example/v1",
                      "key": "fixture-only", "enabled": True, "allowPaid": True, "startDiscovery": True,
                      "manualModel": True}
            def failure(code):
                return CatalogueUnavailable(HTTPError(config["base"], code, "synthetic error", {}, None))
            with patch("server.list_models", side_effect=failure(401)), self.assertRaises(CatalogueUnavailable):
                app.set_provider(config)
            self.assertFalse(app.provider.active or app.requested)
            with patch("server.list_models", side_effect=failure(404)):
                result = app.set_provider(config)
                self.assertTrue(app.provider.active)
                self.assertFalse(result["initialDiscovery"] or app.requested)
                self.assertIn("next scheduled", result["provider"]["lastStatus"])


if __name__ == "__main__":
    unittest.main()
