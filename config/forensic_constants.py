"""
Claim2Car Connect — versioned forensic constants.
Single source of truth for weights, thresholds, and commercial parameters.
"""

VERSION = "2026.11.05.1"  # DARCI constants complete + API auth harden

# --- Commercial ---
OPERATOR_PAYOUT_USD = 110.0
# OWNER payout intentionally absent — permanently excluded per legal counsel.

DEALER_ACQUISITION_FEE_MIN_USD = 375.0
DEALER_ACQUISITION_FEE_MAX_USD = 425.0
SHOP_AUCTION_FLOOR_USD = 250.0
FEE_FACTOR_CAP_USD = 500.0
DEFAULT_TAX_RATE = 0.0825  # TX-ish default; jurisdiction module may override

# --- Integrity (S_i weighted geometric) ---
S_I_PASS = 0.65
S_I_REVIEW = 0.65
S_I_REJECT = 0.30
S_I_WEIGHTS = {"gps": 0.30, "hash": 0.45, "meta": 0.25}

# GPS accuracy tiers (meters → coefficient)
GPS_TIERS = (
    (20.0, 1.0),
    (50.0, 0.9),
    (100.0, 0.8),
    (200.0, 0.6),
    (500.0, 0.4),
)
GPS_TIER_FLOOR = 0.2

# --- Capture ---
DEFAULT_SHOT_LIST = "16-v1"
SELECTABLE_SHOT_LISTS = ("16-v1", "12-v1")
LAPLACIAN_SHARPNESS_MIN = 160.0
LUMINANCE_MIN = 40.0
LUMINANCE_MAX = 220.0
GYRO_STABILITY_MAX_MS2 = 0.6
ACOUSTIC_QUIET_DBFS = -40.0

# --- VIN / mass bounds ---
CURB_MASS_KG_MIN = 500
CURB_MASS_KG_MAX = 5000

# --- Ensemble / Layer 2 ---
ENSEMBLE_PHYSICS_WEIGHT = 0.55
ENSEMBLE_AI_WEIGHT = 0.45
ENSEMBLE_TOTAL_LOSS_THRESHOLD = 0.55
MODEL_VOTE_THRESHOLD = 2.0 / 3.0

# --- DARCI physics (source of truth for Python + future WASM) ---
KE_FACTOR_DIVISOR_KJ = 500.0
KE_FACTOR_CAP = 0.85

# Material yield strengths (MPa)
SIGMA_YIELD_MPA = {
    "mild_steel": 250.0,
    "ahss": 550.0,
    "uhss": 900.0,
    "aluminum": 150.0,
    "composite": 200.0,
}

# Default contact area by zone (m²) when measured area absent
A_ZONE_M2 = {
    "front": 0.50,
    "rear": 0.45,
    "side": 0.35,
    "roof": 0.60,
    "underbody": 0.80,
}

P_BRITTLE_BETA = 0.55
P_BRITTLE_CAP = 0.99

P_STRUCT_RY_THRESHOLD = 0.6
P_STRUCT_RY_SCALE = 0.45
P_STRUCT_BRITTLE_SCALE = 0.40
P_STRUCT_CAP = 0.99

R_STRUCT_W_RY = 0.48
R_STRUCT_W_BRITTLE = 0.28
R_STRUCT_W_ENTROPY = 0.14
R_STRUCT_W_ZONE = 0.10
R_STRUCT_RY_DIVISOR = 2.2

ENTROPY_AI_OVERRIDE_BITS = 2.0
ENTROPY_COLLAPSE_BITS = 2.0
YIELD_RATIO_OVERRIDE = 1.0

# Severe impact guard (aliases used by darci.run_darci)
SEVERE_EK_KJ = 400.0
SEVERE_DEPTH_CM = 40.0
SEVERE_P_PHYSICS_FLOOR = 0.75
SEVERE_IMPACT_EK_KJ = SEVERE_EK_KJ
SEVERE_IMPACT_DEPTH_CM = SEVERE_DEPTH_CM

# Low-impact guard
LOW_IMPACT_EK_KJ = 20.0
LOW_IMPACT_RY = 0.35
LOW_IMPACT_V_KPH = 25.0
LOW_IMPACT_P_PHYSICS_CEIL = 0.15

# RTV bands
RTV_REVIEW_LOW = 0.70
RTV_TOTAL_LOSS = 1.0

# --- Valuation ---
ACV_BLEND = {"black_book": 0.40, "manheim": 0.40, "market_db": 0.20}
P_S_CAP = 0.45
P_S_SCALE = 0.6
