"""
Claim2Car Connect — versioned forensic constants.
Single source of truth for weights, thresholds, and commercial parameters.
"""

VERSION = "2026.11.06.1"  # Owner fee decision 2026-11-06: flat dealer $375, shop $275

# --- Commercial ---
OPERATOR_PAYOUT_USD = 110.0
# OWNER payout intentionally absent — permanently excluded per legal counsel.
# Operator payout trigger (owner decision 2026-11-06): paid upon the accepting
# repair shop's acceptance of the vehicle; the tow driver is then routed to
# deliver the vehicle to that shop. See docs/acceptance/product-contract.md.

DEALER_ACQUISITION_FEE_USD = 375.0  # flat rate — supersedes $375–$425 range and $175 figure (D-01)
SHOP_FEE_USD = 275.0  # flat repair-shop fee — supersedes $250 auction floor
FEE_FACTOR_CAP_USD = 500.0

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

# --- VIN ---
CURB_MASS_KG_MIN = 500
CURB_MASS_KG_MAX = 5000

# --- Physics / Layer 2 ---
LOW_IMPACT_EK_KJ = 20.0
RTV_REVIEW_LOW = 0.70   # inclusive lower bound of review band
RTV_TOTAL_LOSS = 1.0
ENSEMBLE_PHYSICS_WEIGHT = 0.55
ENSEMBLE_AI_WEIGHT = 0.45

# Severe impact guard
SEVERE_IMPACT_EK_KJ = 400.0
SEVERE_IMPACT_DEPTH_CM = 40.0

# Entropy / yield overrides
ENTROPY_COLLAPSE_BITS = 2.0
YIELD_RATIO_OVERRIDE = 1.0

# --- Valuation ---
ACV_BLEND = {"black_book": 0.40, "manheim": 0.40, "market_db": 0.20}  # internal analogs
P_S_CAP = 0.45
P_S_SCALE = 0.6

# --- Commercial routing (constants consolidated above; no duplicates) ---
