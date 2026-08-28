from __future__ import annotations

import json
import re
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "hi_lab_controller"


class RepositoryContractTests(unittest.TestCase):
    def test_hacs_layout_and_release_only_updates(self) -> None:
        integrations = sorted(
            path.name for path in (ROOT / "custom_components").iterdir() if path.is_dir()
        )
        self.assertEqual(integrations, ["hi_lab_controller"])
        self.assertFalse((ROOT / "manifest.json").exists())
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        self.assertEqual(hacs, {"name": "HI Lab Controller", "hide_default_branch": True})

    def test_manifest_identity_and_public_routes(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["domain"], "hi_lab_controller")
        self.assertEqual(manifest["name"], "HI Lab Controller")
        self.assertEqual(manifest["version"], "0.4.1")
        self.assertEqual(manifest["iot_class"], "local_polling")
        self.assertEqual(manifest["requirements"], [])
        self.assertEqual(
            manifest["documentation"],
            "https://github.com/senyo888/hi-lab-controller-companion",
        )
        self.assertEqual(
            manifest["issue_tracker"],
            "https://github.com/senyo888/hi-lab-controller-companion/issues",
        )

    def test_fixed_actions_and_no_arbitrary_provider_inputs(self) -> None:
        services = (COMPONENT / "services.yaml").read_text(encoding="utf-8")
        names = set(re.findall(r"^([a-z][a-z0-9_]+):$", services, re.MULTILINE))
        self.assertEqual(
            names,
            {
                "prepare_version",
                "activate_prepared_version",
                "discard_prepared_version",
                "deployment_status",
                "controller_health",
                "rollback_deployment",
                "queue_prepare_version",
                "cancel_queued_prepare",
            },
        )
        for forbidden in ("repository:", "ref:", "url:", "target:", "credential:"):
            self.assertNotIn(forbidden, services.lower())

    def test_eleven_truth_entities_and_dual_status_compatibility(self) -> None:
        sensors = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        binary = (COMPONENT / "binary_sensor.py").read_text(encoding="utf-8")
        reader = (COMPONENT / "status_reader.py").read_text(encoding="utf-8")
        described = len(re.findall(r"^\s+HILabSensorDescription\($", sensors, re.MULTILINE))
        self.assertEqual(described + 2 + 1, 11)
        self.assertIn("HILabFeedSensor", sensors)
        self.assertIn("HILabLastContactSensor", sensors)
        self.assertIn("HILabRestartRequiredSensor", binary)
        self.assertIn("SUPPORTED_SCHEMA_MAJORS = {1, 2}", reader)

    def test_translation_sources_match(self) -> None:
        strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
        english = json.loads(
            (COMPONENT / "translations" / "en.json").read_text(encoding="utf-8")
        )
        self.assertEqual(strings, english)
        self.assertNotIn("state", strings["entity"]["sensor"]["controller_readiness"])
        self.assertNotIn("state", strings["entity"]["sensor"]["last_outcome"])

    def test_config_entry_only_schema_is_declared(self) -> None:
        source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)", source)

    def test_brand_assets_are_identical_valid_pngs(self) -> None:
        root_icon = ROOT / "brand" / "icon.png"
        component_icon = COMPONENT / "brand" / "icon.png"
        self.assertEqual(root_icon.read_bytes(), component_icon.read_bytes())
        payload = root_icon.read_bytes()
        self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", payload[16:24])
        self.assertEqual((width, height), (256, 256))

    def test_public_text_contains_no_local_identity_or_secret_value(self) -> None:
        forbidden = (
            "/" + "Users" + "/",
            "homeassistant" + ".local",
            "github" + "_pat_",
            "gh" + "p_",
            "gh" + "o_",
            "BEGIN " + "OPENSSH PRIVATE KEY",
        )
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or ".git" in path.parts
                or "__pycache__" in path.parts
                or path.suffix in {".png", ".pyc"}
            ):
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, path.as_posix())


if __name__ == "__main__":
    unittest.main()
