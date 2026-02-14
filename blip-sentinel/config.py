"""
Blip Sentinel v2.3 — Configuration
All constants, user IDs, model config, DND hours, meeting prep cap.
"""

import os
from datetime import timezone, timedelta

# ── Sam's Identity ──
SAM_CHAT_USER_ID = "users/115141803777443372092"
SAM_CHAT_MENTION = f"<{SAM_CHAT_USER_ID}>"
SAM_EMAIL = "sam@bebang.ph"

# ── Google API Scopes ──
# DWD scopes for reading Sam's data (sweepers)
SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
]

# Bot scope for sending messages as Blip (notifier only, no DWD)
BOT_SCOPES = [
    "https://www.googleapis.com/auth/chat.bot",
]

# ── Google API Config ──
SERVICE_ACCOUNT_FILE = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "/app/blip-sentinel/credentials/task-manager-service.json",
)
DELEGATED_USER = SAM_EMAIL

# ── Anthropic AI Models ──
HAIKU_MODEL = "claude-haiku-4-5-20251001"
OPUS_MODEL = "claude-opus-4-6"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Sweep Intervals (seconds) ──
CHAT_SWEEP_INTERVAL = 300       # 5 minutes
GMAIL_SWEEP_INTERVAL = 1800     # 30 minutes
CALENDAR_SWEEP_INTERVAL = 1800  # 30 minutes

# ── Classification ──
CLASSIFIER_BATCH_SIZE = 50
HAIKU_MAX_RETRIES = 3
HAIKU_MAX_TOKENS = 1000

# ── Briefing ──
MAX_MEETING_PREPS_PER_DAY = 3
BRIEFING_MAX_WORDS = 500
CHAT_MESSAGE_CHAR_LIMIT = 4000  # Google Chat limit

# ── DND Window (PHT = UTC+8) ──
PHT = timezone(timedelta(hours=8))
DND_START_HOUR = 23  # 11 PM PHT
DND_END_HOUR = 7     # 7 AM PHT

# ── Blip Bot Identity ──
BLIP_BOT_USER_ID = os.environ.get("BLIP_BOT_USER_ID", "")

# The DM space where Blip sends notifications to Sam
BLIP_NOTIFICATION_SPACE = os.environ.get(
    "BLIP_NOTIFICATION_SPACE",
    "",  # Set in .env — the space ID for "! Blip Notifications"
)

# Bot circuit breaker: max messages per window
BOT_MAX_MESSAGES_PER_WINDOW = 3
BOT_WINDOW_SECONDS = 300  # 5 minutes

# ── Data Paths ──
DB_PATH = os.environ.get(
    "SENTINEL_DB_PATH",
    "/app/blip-sentinel/data/sentinel.db",
)
LOG_PATH = os.environ.get(
    "SENTINEL_LOG_PATH",
    "/app/blip-sentinel/logs/sentinel.log",
)

# ── Retention ──
DATA_RETENTION_DAYS = 90

# ── Lock Files ──
CHAT_SWEEP_LOCK = "/tmp/blip-sentinel-chat.lock"
GMAIL_SWEEP_LOCK = "/tmp/blip-sentinel-gmail.lock"
CALENDAR_SWEEP_LOCK = "/tmp/blip-sentinel-calendar.lock"

# ── Healthchecks.io Ping URLs ──
HC_CHAT_SWEEP = os.environ.get("HC_CHAT_SWEEP", "")
HC_GMAIL_SWEEP = os.environ.get("HC_GMAIL_SWEEP", "")
HC_CALENDAR_SWEEP = os.environ.get("HC_CALENDAR_SWEEP", "")
HC_CLASSIFY = os.environ.get("HC_CLASSIFY", "")
HC_MORNING_BRIEFING = os.environ.get("HC_MORNING_BRIEFING", "")
HC_EVENING_BRIEFING = os.environ.get("HC_EVENING_BRIEFING", "")

# ── Logging ──
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# ── Key People (for classifier context) ──
KEY_PEOPLE = {
    "Ana": "COO",
    "Mae": "CFO",
    "Herdie": "Ops",
    "Alessandro": "Finance",
    "Chimes": "EA",
    "Chimes Marco": "EA",
}

# ── Org Context for Briefing Prompt ──
ORG_CONTEXT = """Sam is CEO of Bebang Enterprise Inc. (BEI), a QSR chain with 30+ stores.
His direct reports: Mae (CFO), Ana (COO), Chimes (EA), Herdie (Ops), Alessandro (Finance).
He oversees: ERP migration, store operations, biometric attendance, procurement automation."""

# ── Rate Limiting ──
CHAT_API_RATE_LIMIT = 1400  # calls per minute
CHAT_API_RATE_WINDOW = 60   # seconds

# ── Circuit Breaker ──
HAIKU_FAILURE_THRESHOLD = 5
HAIKU_RECOVERY_TIMEOUT = 300  # 5 minutes
GOOGLE_API_FAILURE_THRESHOLD = 3
GOOGLE_API_RECOVERY_TIMEOUT = 300

# ── Backups ──
BACKUP_S3_BUCKET = os.environ.get("BACKUP_S3_BUCKET", "bei-backups")
BACKUP_S3_PREFIX = os.environ.get("BACKUP_S3_PREFIX", "blip-sentinel")

# ── Health Check ──
HEALTH_CHECK_PORT = int(os.environ.get("HEALTH_CHECK_PORT", "8080"))

# ── Content Guard ──
SENSITIVE_DM_REDACTION = "[Sensitive — check DM directly]"
