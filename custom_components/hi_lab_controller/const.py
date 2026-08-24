"""Constants for the HA Lab Controller companion."""

from pathlib import Path

DOMAIN = "hi_lab_controller"
CONF_SHARED_SECRET = "shared_secret"
NOTIFICATION_ID = "hi_lab_controller_status"
MAILBOX_ROOT = "/config/.hi_lab_controller/mailbox"
STATUS_PATH = Path("/config/.hi_lab_controller/status/current.json")
STATUS_SCAN_SECONDS = 15
STATUS_MAX_BYTES = 32 * 1024
STATUS_TTL_SECONDS = 150
PLATFORMS = ("sensor", "binary_sensor")
RUNTIME_DATA = f"{DOMAIN}_runtime"
