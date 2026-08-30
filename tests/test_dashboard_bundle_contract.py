"""Contract tests for the manual dashboard bundle example."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path, PurePosixPath
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "dashboard-bundle.schema.json"
EXAMPLE_PATH = (
    ROOT
    / "examples"
    / "dashboard-bundles"
    / "hi-lab-operations.manual.v1.json"
)
FORBIDDEN_DELIVERY_FIXTURE = (
    ROOT / "tests" / "fixtures" / "dashboard_bundle_forbidden_delivery.json"
)

EXPECTED_DELIVERY = {
    "mode": "manual_raw_yaml",
    "automatic_install": False,
    "browser_automation": False,
    "direct_home_assistant_save": False,
    "direct_storage_write": False,
    "preview_required": True,
    "backup_required_before_replace": True,
    "explicit_admin_confirmation_required": True,
    "readback_required": True,
    "hacs_install_is_separate": True,
}

EXPECTED_ENTITIES = {
    "sensor.hi_lab_controller_feed": "hi_lab_controller_status_feed",
    "sensor.hi_lab_controller_last_contact": "hi_lab_controller_last_contact",
    "sensor.hi_lab_controller_readiness": (
        "hi_lab_controller_controller_readiness"
    ),
    "sensor.hi_lab_controller_active_deployment": (
        "hi_lab_controller_active_deployment"
    ),
    "sensor.hi_lab_controller_pending_deployment": (
        "hi_lab_controller_pending_deployment"
    ),
    "sensor.hi_lab_controller_mutation_lock": "hi_lab_controller_mutation_lock",
    "sensor.hi_lab_controller_accepted_baseline": (
        "hi_lab_controller_accepted_baseline"
    ),
    "sensor.hi_lab_controller_last_validation": "hi_lab_controller_last_validation",
    "sensor.hi_lab_controller_last_outcome": "hi_lab_controller_last_outcome",
    "sensor.hi_lab_controller_prepare_queue": "hi_lab_controller_prepare_queue",
    "binary_sensor.hi_lab_controller_restart_required": (
        "hi_lab_controller_restart_required"
    ),
}

MAX_MANIFEST_BYTES = 65536
MAX_ASSETS = 16
MAX_TITLE_LENGTH = 160
MAX_ARTIFACT_BYTES = 33554432
VALIDATION_AVAILABLE = importlib.util.find_spec("jsonschema") is not None
if VALIDATION_AVAILABLE:
    from jsonschema import Draft202012Validator


def load_json(path: Path) -> dict:
    """Load a checked-in JSON object."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def contract_errors(manifest: dict) -> list[str]:
    """Return errors for safety-critical invariants without a third-party validator."""
    errors: list[str] = []
    if manifest.get("contract") != "hi-lab-controller.dashboard-bundle":
        errors.append("contract identity must be hi-lab-controller.dashboard-bundle")
    if manifest.get("contract_version") != 1:
        errors.append("contract_version must be 1")

    bundle = manifest.get("bundle", {})
    source = bundle.get("source", {})
    title = bundle.get("title")
    if not isinstance(title, str) or not 1 <= len(title) <= MAX_TITLE_LENGTH:
        errors.append("bundle title must contain 1 through 160 characters")
    if source.get("repository") != "senyo888/hi-lab-controller-companion":
        errors.append("bundle source repository is invalid")
    if bundle.get("lifecycle") == "contract_example":
        if source.get("commit") is not None or source.get("tag") is not None:
            errors.append("contract examples must not claim source release identity")
    elif bundle.get("lifecycle") == "released":
        if not re.fullmatch(r"[a-f0-9]{40}", str(source.get("commit", ""))):
            errors.append("released bundle must bind an exact source commit")
        if not re.fullmatch(
            r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?",
            str(source.get("tag", "")),
        ):
            errors.append("released bundle must bind an exact source tag")
    else:
        errors.append("bundle lifecycle is invalid")

    delivery = manifest.get("delivery", {})
    for key, expected in EXPECTED_DELIVERY.items():
        if delivery.get(key) != expected:
            errors.append(f"delivery.{key} must be {expected!r}")

    signed_status = manifest.get("compatibility", {}).get("signed_status", {})
    if signed_status.get("supported_major_versions") != [1, 2]:
        errors.append("signed status compatibility must remain [1, 2]")
    if signed_status.get("capabilities", {}).get("dashboard") is not False:
        errors.append("capabilities.dashboard must remain false")

    companion = manifest.get("compatibility", {}).get("companion", {})
    if not companion.get("maximum_tested_version"):
        errors.append("companion maximum tested version is required")

    if manifest.get("dashboard", {}).get("read_only") is not True:
        errors.append("dashboard must remain read-only")

    assets = manifest.get("assets", [])
    if not isinstance(assets, list) or not 1 <= len(assets) <= MAX_ASSETS:
        errors.append("assets must contain 1 through 16 entries")

    try:
        encoded = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        errors.append("manifest must be canonical JSON serializable")
    else:
        if len(encoded) > MAX_MANIFEST_BYTES:
            errors.append("manifest must not exceed 65536 canonical UTF-8 bytes")

    try:
        descriptors = file_descriptors(manifest)
    except (KeyError, TypeError):
        errors.append("artifact descriptors are incomplete")
    else:
        for descriptor in descriptors:
            byte_count = descriptor.get("bytes")
            if (
                not isinstance(byte_count, int)
                or isinstance(byte_count, bool)
                or not 1 <= byte_count <= MAX_ARTIFACT_BYTES
            ):
                errors.append("artifact bytes must be between 1 and 33554432")

    semantic_set = manifest.get("entity_semantic_set", {})
    entities = semantic_set.get("entities", [])
    if semantic_set.get("count") != 11 or len(entities) != 11:
        errors.append("entity semantic set must contain exactly eleven entities")
    return errors


def file_descriptors(manifest: dict) -> list[dict]:
    """Return every repository artifact descriptor in the example."""
    return [
        manifest["dashboard"]["artifact"],
        *(asset["artifact"] for asset in manifest["assets"]),
    ]


class DashboardBundleContractTests(unittest.TestCase):
    """Keep the contract manual, public-safe, and bound to repository truth."""

    def test_schema_is_versioned_and_forbids_automatic_delivery(self) -> None:
        schema = load_json(SCHEMA_PATH)

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            schema["properties"]["contract"]["const"],
            "hi-lab-controller.dashboard-bundle",
        )
        self.assertEqual(schema["properties"]["contract_version"]["const"], 1)

        delivery = schema["$defs"]["manualDelivery"]["properties"]
        for key, expected in EXPECTED_DELIVERY.items():
            self.assertEqual(delivery[key]["const"], expected)

        dashboard_capability = schema["$defs"]["compatibility"]["properties"][
            "signed_status"
        ]["properties"]["capabilities"]["properties"]["dashboard"]
        self.assertIs(dashboard_capability["const"], False)

    def test_example_matches_companion_and_repository_artifacts(self) -> None:
        manifest = load_json(EXAMPLE_PATH)
        companion_manifest = load_json(
            ROOT / "custom_components" / "hi_lab_controller" / "manifest.json"
        )

        self.assertEqual(contract_errors(manifest), [])
        self.assertEqual(manifest["bundle"]["lifecycle"], "contract_example")
        self.assertLessEqual(
            len(
                json.dumps(
                    manifest,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ),
            MAX_MANIFEST_BYTES,
        )
        self.assertEqual(
            manifest["bundle"]["source"]["repository"],
            "senyo888/hi-lab-controller-companion",
        )
        self.assertIsNone(manifest["bundle"]["source"]["commit"])
        self.assertIsNone(manifest["bundle"]["source"]["tag"])
        self.assertEqual(
            manifest["compatibility"]["companion"]["domain"],
            companion_manifest["domain"],
        )
        self.assertEqual(
            manifest["compatibility"]["companion"]["minimum_version"],
            companion_manifest["version"],
        )
        self.assertEqual(
            manifest["compatibility"]["companion"]["maximum_tested_version"],
            companion_manifest["version"],
        )
        self.assertEqual(
            manifest["compatibility"]["companion"]["installation_owner"],
            "hacs",
        )
        self.assertEqual(
            manifest["compatibility"]["home_assistant"]["minimum_version"],
            "2026.4.0",
        )
        self.assertEqual(
            manifest["compatibility"]["cards"]["profile"],
            "home_assistant_core_only",
        )

        for descriptor in file_descriptors(manifest):
            relative_path = descriptor["path"]
            posix_path = PurePosixPath(relative_path)
            self.assertFalse(posix_path.is_absolute())
            self.assertNotIn("..", posix_path.parts)

            payload = (ROOT / relative_path).read_bytes()
            self.assertEqual(len(payload), descriptor["bytes"])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), descriptor["sha256"])

    def test_entity_semantic_set_matches_dashboard_defaults(self) -> None:
        manifest = load_json(EXAMPLE_PATH)
        semantic_set = manifest["entity_semantic_set"]
        entities = semantic_set["entities"]

        declared = {
            entity["default_entity_id"]: entity["unique_id"] for entity in entities
        }
        self.assertEqual(declared, EXPECTED_ENTITIES)
        self.assertEqual(len({entity["key"] for entity in entities}), 11)
        self.assertEqual(len({entity["semantic_role"] for entity in entities}), 11)
        self.assertEqual(len(set(declared.values())), 11)
        self.assertEqual(semantic_set["id"], manifest["dashboard"]["entity_semantic_set"])

        dashboard = (
            ROOT / manifest["dashboard"]["artifact"]["path"]
        ).read_text(encoding="utf-8")
        dashboard_entities = set(
            re.findall(
                r"(?:sensor|binary_sensor)\.hi_lab_controller_[a-z0-9_]+",
                dashboard,
            )
        )
        self.assertEqual(dashboard_entities, set(EXPECTED_ENTITIES))

    def test_forbidden_delivery_fixture_is_rejected(self) -> None:
        manifest = load_json(EXAMPLE_PATH)
        fixture = load_json(FORBIDDEN_DELIVERY_FIXTURE)
        invalid = copy.deepcopy(manifest)
        invalid["delivery"].update(fixture["delivery_overrides"])

        errors = contract_errors(invalid)
        self.assertIn("delivery.browser_automation must be False", errors)
        self.assertIn("delivery.direct_home_assistant_save must be False", errors)

    def test_released_lifecycle_requires_exact_source_commit_and_tag(self) -> None:
        manifest = load_json(EXAMPLE_PATH)
        manifest["bundle"]["lifecycle"] = "released"
        errors = contract_errors(manifest)
        self.assertIn("released bundle must bind an exact source commit", errors)
        self.assertIn("released bundle must bind an exact source tag", errors)

    def test_resource_bounds_reject_oversized_manifest_fields(self) -> None:
        manifest = load_json(EXAMPLE_PATH)

        oversized_title = copy.deepcopy(manifest)
        oversized_title["bundle"]["title"] = "x" * 100000
        self.assertIn(
            "bundle title must contain 1 through 160 characters",
            contract_errors(oversized_title),
        )

        oversized_assets = copy.deepcopy(manifest)
        oversized_assets["assets"] = oversized_assets["assets"] * 1000
        self.assertIn(
            "assets must contain 1 through 16 entries",
            contract_errors(oversized_assets),
        )

        oversized_artifact = copy.deepcopy(manifest)
        oversized_artifact["dashboard"]["artifact"]["bytes"] = 10**30
        self.assertIn(
            "artifact bytes must be between 1 and 33554432",
            contract_errors(oversized_artifact),
        )

    @unittest.skipUnless(
        VALIDATION_AVAILABLE,
        "jsonschema is available only in the validation environment",
    )
    def test_json_schema_rejects_resource_exhaustion_shapes(self) -> None:
        schema = load_json(SCHEMA_PATH)
        validator = Draft202012Validator(schema)
        manifest = load_json(EXAMPLE_PATH)

        oversized_title = copy.deepcopy(manifest)
        oversized_title["bundle"]["title"] = "x" * 100000
        self.assertTrue(list(validator.iter_errors(oversized_title)))

        oversized_assets = copy.deepcopy(manifest)
        oversized_assets["assets"] = oversized_assets["assets"] * 1000
        self.assertTrue(list(validator.iter_errors(oversized_assets)))

        oversized_artifact = copy.deepcopy(manifest)
        oversized_artifact["dashboard"]["artifact"]["bytes"] = 10**30
        self.assertTrue(list(validator.iter_errors(oversized_artifact)))

    def test_example_and_documentation_are_public_safe_and_manual_first(self) -> None:
        serialized = EXAMPLE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "/" + "Users" + "/",
            "/config/.storage",
            "http://",
            "https://",
        ):
            self.assertNotIn(forbidden, serialized)

        documentation = (
            ROOT / "docs" / "DASHBOARD_BUNDLE_CONTRACT.md"
        ).read_text(encoding="utf-8")
        for required in (
            "HACS owns companion integration installation and update",
            "explicit confirmation",
            "Immediately read the saved raw configuration back",
            "manually restore the private backup",
            "`capabilities.dashboard` remains `false`",
            "direct `.storage` writes",
        ):
            self.assertIn(required, documentation)


if __name__ == "__main__":
    unittest.main()
