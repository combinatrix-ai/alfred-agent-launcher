import base64
import importlib.util
import json
from pathlib import Path
import shlex
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


query = load_module("agent_launcher_query", ROOT / "source/query.py")
launch = load_module("agent_launcher_launch", ROOT / "source/launch.py")

MODELS = {
    "codex": [
        {"id": "gpt-5.6-luna", "display_name": "GPT-5.6-Luna", "priority": 3},
        {"id": "gpt-5.6-terra", "display_name": "GPT-5.6-Terra", "priority": 2},
        {"id": "gpt-5.6-sol", "display_name": "GPT-5.6-Sol", "priority": 1},
    ],
    "claude": [
        {"id": "claude-fable-5", "display_name": "Claude Fable 5", "created_at": "2026-06-07"},
        {"id": "claude-opus-5", "display_name": "Claude Opus 5", "created_at": "2026-07-24"},
        {
            "id": "claude-haiku-4-5-20251001",
            "display_name": "Claude Haiku 4.5",
            "created_at": "2025-10-15",
        },
    ],
}


class WorkflowTests(unittest.TestCase):
    def decode(self, encoded):
        padding = "=" * (-len(encoded) % 4)
        return json.loads(base64.urlsafe_b64decode(encoded + padding).decode())

    def test_preset_order(self):
        items = query.build_items("test", "", MODELS)
        self.assertEqual(
            [item["title"] for item in items],
            ["Luna", "Terra", "Sol", "Codex Desktop", "Fable", "Opus", "Haiku", "Claude Desktop"],
        )

    def test_provider_icons(self):
        items = query.build_items("test", "", MODELS)
        for item in items[:4]:
            self.assertEqual(item["icon"]["path"], "icon-codex.png")
        for item in items[4:]:
            self.assertEqual(item["icon"]["path"], "icon-claude.png")

    def test_default_omits_effort(self):
        for item in query.build_items("test", "", MODELS):
            self.assertEqual(self.decode(item["arg"])["effort"], "")

    def test_shared_xhigh_ignores_haiku_and_desktop(self):
        requests = {
            item["title"]: self.decode(item["arg"])
            for item in query.build_items("test", "xhigh", MODELS)
        }
        self.assertEqual(requests["Luna"]["effort"], "xhigh")
        self.assertEqual(requests["Fable"]["effort"], "xhigh")
        self.assertEqual(requests["Haiku"]["effort"], "")
        self.assertEqual(requests["Codex Desktop"]["effort"], "")
        self.assertEqual(requests["Claude Desktop"]["effort"], "")

    def test_provider_only_levels(self):
        max_requests = {
            item["title"]: self.decode(item["arg"])
            for item in query.build_items("test", "max", MODELS)
        }
        self.assertEqual(max_requests["Luna"]["effort"], "")
        self.assertEqual(max_requests["Fable"]["effort"], "max")
        minimal_requests = {
            item["title"]: self.decode(item["arg"])
            for item in query.build_items("test", "minimal", MODELS)
        }
        self.assertEqual(minimal_requests["Luna"]["effort"], "minimal")
        self.assertEqual(minimal_requests["Fable"]["effort"], "")

    def test_modifiers_are_consistent(self):
        for item in query.build_items("safe", "high", MODELS):
            self.assertEqual(self.decode(item["mods"]["cmd"]["arg"])["model"], "claude-fable-5")
            self.assertEqual(item["mods"]["cmd"]["subtitle"], "Claude CLI · claude-fable-5")
            alt = self.decode(item["mods"]["alt"]["arg"])
            self.assertEqual((alt["provider"], alt["surface"]), ("codex", "desktop"))
            self.assertEqual(item["mods"]["alt"]["subtitle"], "Codex Desktop · review & send")

    def test_compact_desktop_and_empty_prompt_copy(self):
        prompted = {item["title"]: item for item in query.build_items("safe", "", MODELS)}
        self.assertEqual(prompted["Codex Desktop"]["subtitle"], "Model in app · review & send")
        self.assertEqual(prompted["Claude Desktop"]["subtitle"], "Model in app · review & send")

        empty = {item["title"]: item for item in query.build_items("", "", MODELS)}
        self.assertEqual(empty["Luna"]["subtitle"], "Codex CLI · gpt-5.6-luna · new session")
        self.assertEqual(empty["Codex Desktop"]["subtitle"], "Model in app · new session")
        self.assertEqual(
            empty["Fable"]["mods"]["cmd"]["subtitle"],
            "Claude CLI · claude-fable-5 · new session",
        )
        self.assertEqual(empty["Fable"]["mods"]["alt"]["subtitle"], "Codex Desktop · new session")

    def test_cli_quoting_round_trip(self):
        prompt = "it's $(safe); café\nsecond line"
        request = self.decode(query.build_items(prompt, "high", MODELS)[0]["arg"])
        argv = shlex.split(launch.build_cli_command(request, "/tmp/codex"))
        self.assertEqual(
            argv,
            ["exec", "/tmp/codex", "--model", "gpt-5.6-luna", "-c", 'model_reasoning_effort="high"', prompt],
        )

    def test_desktop_urls_are_encoded(self):
        prompt = "café & spaces"
        requests = {
            item["title"]: self.decode(item["arg"])
            for item in query.build_items(prompt, "high", MODELS)
        }
        self.assertEqual(
            launch.desktop_url(requests["Codex Desktop"]),
            "codex://threads/new?prompt=caf%C3%A9+%26+spaces",
        )
        self.assertEqual(
            launch.desktop_url(requests["Claude Desktop"]),
            "claude://code/new?q=caf%C3%A9+%26+spaces",
        )

    def test_empty_prompt_is_valid(self):
        self.assertTrue(all(item["valid"] for item in query.build_items("", "", MODELS)))

    def test_normalizes_only_visible_codex_models(self):
        models = query.normalize_codex_catalog(
            {
                "models": [
                    {
                        "slug": "gpt-5.6-luna",
                        "display_name": "GPT-5.6-Luna",
                        "visibility": "list",
                        "priority": 3,
                    },
                    {
                        "slug": "gpt-private-sol",
                        "display_name": "Hidden",
                        "visibility": "hide",
                    },
                    {
                        "slug": "--unsafe",
                        "display_name": "Unsafe",
                        "visibility": "list",
                    },
                ]
            }
        )
        self.assertEqual([model["id"] for model in models], ["gpt-5.6-luna"])

    def test_selects_latest_claude_model_in_each_family(self):
        models = MODELS["claude"] + [
            {"id": "claude-opus-4-8", "display_name": "Claude Opus 4.8", "created_at": "2026-05-28"}
        ]
        selected = query.select_family_models("claude", models)
        self.assertEqual(
            [model["id"] for model in selected],
            ["claude-fable-5", "claude-opus-5", "claude-haiku-4-5-20251001"],
        )

    def test_partial_failure_uses_default_cli_and_keeps_other_provider(self):
        items = query.build_items(
            "test",
            "",
            {"codex": MODELS["codex"]},
            {
                "claude": {
                    "title": "Claude models unavailable",
                    "subtitle": "No internet access — cannot list latest models",
                }
            },
        )
        self.assertEqual(
            [item["title"] for item in items],
            [
                "Luna",
                "Terra",
                "Sol",
                "Codex Desktop",
                "Claude CLI",
                "Claude Desktop",
            ],
        )
        fallback = items[-2]
        self.assertTrue(fallback["valid"])
        self.assertEqual(fallback["subtitle"], "Default model · model list unavailable")
        self.assertEqual(self.decode(fallback["arg"])["model"], "")
        self.assertEqual(self.decode(fallback["arg"])["effort"], "")
        self.assertTrue(items[0]["mods"]["cmd"]["valid"])
        self.assertEqual(self.decode(items[0]["mods"]["cmd"]["arg"])["model"], "")

    def test_loading_catalogs_offer_default_cli_without_effort(self):
        loading = {
            provider: {
                "title": f"Refreshing {provider} models…",
                "subtitle": "Model choices will appear automatically",
                "loading": True,
            }
            for provider in ("codex", "claude")
        }
        items = query.build_items("test", "high", {}, loading)
        self.assertEqual(
            [item["title"] for item in items],
            ["Codex CLI", "Codex Desktop", "Claude CLI", "Claude Desktop"],
        )
        for item in (items[0], items[2]):
            request = self.decode(item["arg"])
            self.assertEqual(request["model"], "")
            self.assertEqual(request["effort"], "")
            self.assertEqual(item["subtitle"], "Default model · refreshing model list…")

    def test_model_cache_expires_after_one_day(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_dir = Path(temporary_directory)
            query._write_json_atomic(
                query._cache_path(cache_dir, "codex"),
                {
                    "version": query.CACHE_VERSION,
                    "provider": "codex",
                    "fetched_at": 100,
                    "models": MODELS["codex"],
                },
            )
            self.assertEqual(query.read_fresh_cache(cache_dir, "codex", 100), MODELS["codex"])
            self.assertIsNone(
                query.read_fresh_cache(cache_dir, "codex", 100 + query.CACHE_TTL_SECONDS)
            )

    def test_dynamic_model_validation_rejects_option_injection(self):
        request = {
            "provider": "claude",
            "surface": "cli",
            "model": "claude-opus-5",
            "effort": "",
            "prompt": "test",
        }
        launch.validate_cli_request(request)
        request["model"] = "--dangerous-opus"
        with self.assertRaises(SystemExit):
            launch.validate_cli_request(request)

    def test_default_cli_command_omits_model_and_effort(self):
        request = {
            "provider": "codex",
            "surface": "cli",
            "model": "",
            "effort": "",
            "prompt": "test",
        }
        self.assertEqual(
            shlex.split(launch.build_cli_command(request, "/tmp/codex")),
            ["exec", "/tmp/codex", "test"],
        )
        request["effort"] = "high"
        with self.assertRaises(SystemExit):
            launch.validate_cli_request(request)


if __name__ == "__main__":
    unittest.main()
