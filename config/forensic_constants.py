"""
Claim2Car Connect — versioned forensic constants.
Single source of truth for weights, thresholds, and commercial parameters.
Do not hard-code these values elsewhere.
"""

VERSION = "2026.11.02.1"

# --- Commercial (owner directive 2026-11-02) ---
OPERATOR_PAYOUT_USD = 110.0
# OWNER payout intentionally absent — permanently excluded per legal counsel.

DEALER_ACQUISITION_FEE_MIN_USD = 375.0
DEALER_ACQUISITION_FEE_MAX_USD = 425.0
SHOP_AUCTION_FLOOR_USD = 250.0
FEE_FACTOR_CAP_USD = 500.0  # fee_factor = min(fee / FEE_FACTOR_CAP_USD, 1.0)

# --- Integrity ---
S_I_PASS = 0.65
S_I_REVIEW = 0.65  # < this → review
S_I_REJECT = 0.30  # < this → reject/fraud
S_I_WEIGHTS = {"gps": 0.30, "hash": 0.45, "meta": 0.25}  # geometric form required

# --- Capture protocol ---
DEFAULT_SHOT_LIST = "16-v1"
SELECTABLE_SHOT_LISTS = ("16-v1", "12-v1")

# Quality gates (16-v1 / walkaround)
LAPLACIAN_SHARPNESS_MIN = 160.0
LUMINANCE_MIN = 40.0
LUMINANCE_MAX = 220.0
GYRO_STABILITY_MAX_MS2 = 0.6
ACOUSTIC_QUIET_DBFS = -40.0

# --- VIN ---
CURB_MASS_KG_MIN = 500
CURB_MASS_KG_MAX = 5000

# --- Physics / triage (targets; formulas locked in Layer 2/3) ---
LOW_IMPACT_EK_KJ = 20.0
RTV_REVIEW_LOW = 0.70   # inclusive
RTV_TOTAL_LOSS = 1.0
ENSEMBLE_PHYSICS_WEIGHT = 0.55
ENSEMBLE_AI_WEIGHT = 0.45
ENSEMBLE_TOTAL_LOSS_THRESHOLD = 0.55

# --- Zones (m²) for stress ---
A_ZONE = {
    "front": 0.55,
    "rear": 0.50,
    "side": 0.35,
    "roof": 0.85,
    "underbody": 0.65,
}

# Yield strengths (MPa) — representative
SIGMA_YIELD_MPA = {
    "boron": 1500,
    "ahss": 780,
    "composite": 400,
    "aluminum": 275,
    "mild_steel": 250,
}
