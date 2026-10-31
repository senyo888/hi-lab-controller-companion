"""Synthetic observation fixtures; no production enrollment or target is opened."""
from pathlib import Path
import importlib
import sys
import types

PACKAGE = "_hilc_observation_tests"
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/hi_lab_controller")]
    sys.modules[PACKAGE] = package
p = importlib.import_module(PACKAGE + ".observation_protocol")
r = importlib.import_module(PACKAGE + ".observation_receiver")
SECRET = "a" * 64
INSTANCE = "11111111-1111-4111-8111-111111111111"
EPOCH = "22222222-2222-4222-8222-222222222222"
CAMPAIGN = "33333333-3333-4333-8333-333333333333"
NOW = 1791130000.0


class Clock:
    def __init__(self):
        self.now = NOW
        self.mono = 1000.0
    def advance(self, seconds):
        self.now += seconds; self.mono += seconds


def selected(domain="example_integration"):
    return {"profile_id": "observe_" + domain, "integration_label": "Example integration",
            "domain": domain, "reference_label": "Expected synthetic beta",
            "evidence_scope": "reported_health", "source_identity": "EXPECTED_REFERENCE_NOT_LOADED_PROOF",
            "baseline": "NOT_ACCEPTED"}


def payload(sequence=1, now=NOW, *, state=None, result=None, domain="example_integration"):
    profile = selected(domain)
    campaign = None
    if state is not None:
        terminal = state in p.TERMINAL
        count = 9 if state in {"COMPLETED", "FAILED"} else 1
        started = now - (count - 1) * 21600 - 30
        samples = [{"slot": i, "state": "HEALTHY", "due_at": p.iso(started + i * 21600),
                    "observed_at": p.iso(started + i * 21600 + 1), "reasons": []} for i in range(count)]
        if state == "FAILED": samples[0].update(state="UNHEALTHY", reasons=["CHECK_FAILED"])
        campaign = {**profile, "id": CAMPAIGN, "report_id": CAMPAIGN, "state": state,
            "result": result or ("PASS" if state == "COMPLETED" else "FAIL" if state == "FAILED" else
                                 "INCOMPLETE" if terminal or state == "STOPPING" else "PENDING"),
            "completed_slots": count, "total_slots": 9, "started_at": p.iso(started),
            "finished_at": p.iso(now - 2) if terminal else None,
            "next_checkpoint_at": p.iso(started + count * 21600) if state == "RUNNING" else None,
            "reasons": [], "checkpoints": samples}
    return {"schema_version": p.SCHEMA, "controller_instance_id": INSTANCE, "stream_epoch": EPOCH,
            "sequence": sequence, "generated_at": p.iso(now), "expires_at": p.iso(now + 60),
            "background_state": "RUNNING", "selected_profile": profile, "campaign": campaign}
