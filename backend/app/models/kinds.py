"""Logical tables (DynamoDB: pk = kind). See docs/ARCHITECTURE.md for the entity map."""
USERS = "users"
ORGS = "organizations"
BUILDINGS = "buildings"
SUBMISSIONS = "waste_submissions"      # one submission = one identified item (+ quantity); waste_items are embedded
PREDICTIONS = "ai_predictions"         # raw AI output + user correction (human-in-the-loop record)
RECYCLERS = "recyclers"
PICKUPS = "pickup_requests"
LEDGER = "points_ledger"               # every point change is a ledger row; balances are derived
IMPACT = "environmental_impact"        # one row per verified item
CHALLENGES = "challenges"
PARTICIPANTS = "challenge_participants"
NOTIFS = "notifications"
FRAUD = "fraud_flags"
AUDIT = "audit_logs"
BIN_SCANS = "bin_scans"
EMAIL_IDX = "email_index"              # email -> user id
IMG_IDX = "image_hashes"               # sha256 -> first submission (duplicate detection)
# Leaderboards and price estimates are computed views (see services/leaderboard.py, services/pricing.py).

ROLES = ("USER", "COLLECTOR", "ADMIN", "ORGANIZATION_ADMIN")
