"""Offline YAML/Jinja and schema fixtures, not installed dashboard rendering."""
import json
from pathlib import Path
import unittest

import jsonschema
from jinja2 import Environment, StrictUndefined
import yaml

from observation_fixtures import p, payload

ROOT = Path(__file__).resolve().parents[1]


class ObservationPresentationTests(unittest.TestCase):
    def test_schema_accepts_all_states_and_rejects_extra_privilege_fields(self):
        schema = json.loads((ROOT / "schemas/integration-observation-companion-v2.schema.json").read_text())
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        validator.check_schema(schema)
        for state in (None, *p.STATES):
            value = payload(state=state)
            validator.validate(value)
            value["command"] = "start"
            with self.assertRaises(jsonschema.ValidationError):
                validator.validate(value)

    def test_native_panel_preserves_observation_only_entity_and_action_boundary(self):
        panel = yaml.safe_load((ROOT / "dashboards/integration-observation.yaml").read_text())
        entities = set()
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & {"tap_action", "hold_action", "double_tap_action", "service", "action"})
                self.assertFalse(str(value.get("type", "")).startswith("custom:"))
                if "entity" in value: entities.add(value["entity"])
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(panel)
        self.assertEqual(entities, {"sensor.hi_lab_controller_observation_" + name
                                  for name in ("feed", "integration", "campaign", "last_result")})
        self.assertEqual(panel["cards"][2]["conditions"][0]["state"], "fresh")
        self.assertEqual(panel["cards"][3]["conditions"][0]["state_not"], "fresh")

    def test_templates_distinguish_idle_active_unavailable_and_retained_result(self):
        panel = yaml.safe_load((ROOT / "dashboards/integration-observation.yaml").read_text())
        attributes = {"integration": {"reference_label": "Expected fixture"},
                      "campaign": {"campaign": None, "background_state": "PAUSED"},
                      "feed": {"error_code": "STATUS_EXPIRED"}, "last_result": {"campaign": None}}
        def attr(entity, name):
            return attributes[entity.removeprefix("sensor.hi_lab_controller_observation_")].get(name)
        env = Environment(undefined=StrictUndefined)
        env.globals["state_attr"] = attr
        fresh = env.from_string(panel["cards"][2]["card"]["content"])
        self.assertIn("Idle.", fresh.render())
        self.assertIn("PAUSED", fresh.render())
        attributes["campaign"]["campaign"] = payload(state="RUNNING")["campaign"]
        self.assertIn("1 / 9", fresh.render())
        self.assertIn("PENDING", fresh.render())
        self.assertIn("does not prove continuous", fresh.render())
        stale = env.from_string(panel["cards"][3]["card"]["content"]).render()
        self.assertIn("STATUS_EXPIRED", stale)
        self.assertIn("Current campaign values are withheld", stale)
        history = env.from_string(panel["cards"][4]["content"])
        self.assertIn("No authenticated terminal result", history.render())
        for state, result in (("COMPLETED", "PASS"), ("STOPPED", "INCOMPLETE"), ("FAILED", "FAIL")):
            attributes["last_result"]["campaign"] = payload(state=state)["campaign"]
            rendered = history.render()
            self.assertIn(result, rendered)
            self.assertIn("Historical only; not current health", rendered)


if __name__ == "__main__": unittest.main()
