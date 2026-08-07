import base64
import importlib.util
import json
from pathlib import Path
import shlex
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


query = load_module("agent_launcher_query", ROOT / "source/query.py")
launch = load_module("agent_launcher_launch", ROOT / "source/launch.py")


class WorkflowTests(unittest.TestCase):
    def decode(self, encoded):
        padding = "=" * (-len(encoded) % 4)
        return json.loads(base64.urlsafe_b64decode(encoded + padding).decode())

    def test_preset_order(self):
        items = query.build_items("test", "")
        self.assertEqual(
            [item["title"] for item in items],
            ["Luna", "Terra", "Sol", "Codex Desktop", "Fable", "Opus", "Haiku", "Claude Desktop"],
        )

    def test_provider_icons(self):
        items = query.build_items("test", "")
        for item in items[:4]:
            self.assertEqual(item["icon"]["path"], "icon-codex.png")
        for item in items[4:]:
            self.assertEqual(item["icon"]["path"], "icon-claude.png")

    def test_default_omits_effort(self):
        for item in query.build_items("test", ""):
            self.assertEqual(self.decode(item["arg"])["effort"], "")

    def test_shared_xhigh_ignores_haiku_and_desktop(self):
        requests = {item["title"]: self.decode(item["arg"]) for item in query.build_items("test", "xhigh")}
        self.assertEqual(requests["Luna"]["effort"], "xhigh")
        self.assertEqual(requests["Fable"]["effort"], "xhigh")
        self.assertEqual(requests["Haiku"]["effort"], "")
        self.assertEqual(requests["Codex Desktop"]["effort"], "")
        self.assertEqual(requests["Claude Desktop"]["effort"], "")

    def test_provider_only_levels(self):
        max_requests = {item["title"]: self.decode(item["arg"]) for item in query.build_items("test", "max")}
        self.assertEqual(max_requests["Luna"]["effort"], "")
        self.assertEqual(max_requests["Fable"]["effort"], "max")
        minimal_requests = {item["title"]: self.decode(item["arg"]) for item in query.build_items("test", "minimal")}
        self.assertEqual(minimal_requests["Luna"]["effort"], "minimal")
        self.assertEqual(minimal_requests["Fable"]["effort"], "")

    def test_modifiers_are_consistent(self):
        for item in query.build_items("safe", "high"):
            self.assertEqual(self.decode(item["mods"]["cmd"]["arg"])["model"], "fable")
            self.assertEqual(item["mods"]["cmd"]["subtitle"], "Claude CLI · fable")
            alt = self.decode(item["mods"]["alt"]["arg"])
            self.assertEqual((alt["provider"], alt["surface"]), ("codex", "desktop"))
            self.assertEqual(item["mods"]["alt"]["subtitle"], "Codex Desktop · review & send")

    def test_compact_desktop_and_empty_prompt_copy(self):
        prompted = {item["title"]: item for item in query.build_items("safe", "")}
        self.assertEqual(prompted["Codex Desktop"]["subtitle"], "Model in app · review & send")
        self.assertEqual(prompted["Claude Desktop"]["subtitle"], "Model in app · review & send")

        empty = {item["title"]: item for item in query.build_items("", "")}
        self.assertEqual(empty["Luna"]["subtitle"], "Codex CLI · gpt-5.6-luna · new session")
        self.assertEqual(empty["Codex Desktop"]["subtitle"], "Model in app · new session")
        self.assertEqual(empty["Fable"]["mods"]["cmd"]["subtitle"], "Claude CLI · fable · new session")
        self.assertEqual(empty["Fable"]["mods"]["alt"]["subtitle"], "Codex Desktop · new session")

    def test_cli_quoting_round_trip(self):
        prompt = "it's $(safe); café\nsecond line"
        request = self.decode(query.build_items(prompt, "high")[0]["arg"])
        argv = shlex.split(launch.build_cli_command(request, "/tmp/codex"))
        self.assertEqual(
            argv,
            ["exec", "/tmp/codex", "--model", "gpt-5.6-luna", "-c", 'model_reasoning_effort="high"', prompt],
        )

    def test_desktop_urls_are_encoded(self):
        prompt = "café & spaces"
        requests = {item["title"]: self.decode(item["arg"]) for item in query.build_items(prompt, "high")}
        self.assertEqual(
            launch.desktop_url(requests["Codex Desktop"]),
            "codex://threads/new?prompt=caf%C3%A9+%26+spaces",
        )
        self.assertEqual(
            launch.desktop_url(requests["Claude Desktop"]),
            "claude://code/new?q=caf%C3%A9+%26+spaces",
        )

    def test_empty_prompt_is_valid(self):
        self.assertTrue(all(item["valid"] for item in query.build_items("", "")))


if __name__ == "__main__":
    unittest.main()
