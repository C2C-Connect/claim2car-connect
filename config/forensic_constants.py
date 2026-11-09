"""
Claim2Car Connect — versioned forensic constants.
Single source of truth for weights, thresholds, and commercial parameters.
"""

VERSION = "2026.11.06.1"  # Owner fee decision 2026-11-06: flat dealer $375, shop $275

# --- Commercial ---
OPERATOR_PAYOUT_USD = 110.0
# OWNER payout intentionally absent — permanently excluded per legal counsel.
# Operator payout trigger: OPEN (plan v1.3 D-04) — amount carried forward only;
# eligibility, trigger, split, reversals, and ledger treatment not yet decided.
# Shop acceptance of the vehicle authorizes tow dispatch to that shop (confirmed
# in plan v1.3), independent of payout. See docs/acceptance/product-contract.md.

DEALER_ACQUISITION_FEE_USD = 375.0  # flat, due on qualified-acquisition close (plan v1.3 D-01); supersedes $375–$425 range and $175 figure
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
ENSEMBLE_TOTAL_LOSS_THRESHOLD = 0.55  # p_ensemble >= 0.55 -> total_loss_dealer (test-pinned)
MODEL_VOTE_THRESHOLD = 2.0 / 3.0     # two-thirds agreement rule (test-pinned)
INFERENCE_TIMEOUT_S = 30.0            # LMM inference budget; timeout -> physics fallback
YOLO_CONF_MIN = 0.55                  # detection confidence floor

# DARCI structural model (formulas documented in backend/app/physics/darci.py)
KE_FACTOR_DIVISOR_KJ = 500.0   # ke_factor = min(E_k/500, cap) (test-pinned)
KE_FACTOR_CAP = 1.0            # test-pinned
SIGMA_YIELD_MPA = {
    "mild_steel": 250.0,       # test-pinned (r_y = sigma/250)
    "ahss": 600.0,             # typical advanced high-strength steel yield
    "aluminum": 200.0,         # typical aluminum alloy yield
}
A_ZONE_M2 = {                  # zone structural cross-sections (Physics Engine deck)
    "front": 0.55,
    "rear": 0.50,
    "side": 0.35,
    "roof": 0.85,
    "underbody": 0.65,
}
P_BRITTLE_BETA = 0.6           # provisional — owner review pending
P_BRITTLE_CAP = 0.99           # docstring-pinned
P_STRUCT_RY_THRESHOLD = 0.6    # docstring-pinned
P_STRUCT_RY_SCALE = 0.45       # docstring-pinned
P_STRUCT_BRITTLE_SCALE = 0.4   # docstring-pinned
P_STRUCT_CAP = 0.99            # docstring-pinned
R_STRUCT_W_RY = 0.48           # Option B weights (SPEC_DECISIONS 2026-11-03)
R_STRUCT_W_BRITTLE = 0.28
R_STRUCT_W_ENTROPY = 0.14
R_STRUCT_W_ZONE = 0.10
R_STRUCT_RY_DIVISOR = 2.2

# Severe impact guard
SEVERE_EK_KJ = 400.0            # (was SEVERE_IMPACT_EK_KJ; same value, new name)
SEVERE_DEPTH_CM = 40.0
SEVERE_P_PHYSICS_FLOOR = 0.75   # docstring-pinned: p_physics >= 0.75
SEVERE_IMPACT_EK_KJ = SEVERE_EK_KJ        # legacy alias
SEVERE_IMPACT_DEPTH_CM = SEVERE_DEPTH_CM  # legacy alias

# Low-impact guard (v1 physics: E_k < 20kJ & r_y low & v < 25 -> P_TL <= 0.15)
LOW_IMPACT_RY = 0.30            # provisional — owner review pending
LOW_IMPACT_V_KPH = 25.0         # docstring-pinned
LOW_IMPACT_P_PHYSICS_CEIL = 0.15

# Entropy / yield overrides
ENTROPY_COLLAPSE_BITS = 2.0
ENTROPY_AI_OVERRIDE_BITS = 2.0  # H > 2 bits -> physics overrides AI
YIELD_RATIO_OVERRIDE = 1.0

# --- Valuation ---
ACV_BLEND = {"black_book": 0.40, "manheim": 0.40, "market_db": 0.20}  # internal analogs
ACV_BLEND_WEIGHTS = (0.40, 0.40, 0.20)  # tri-source blend (docstring-pinned)
ACV_FALLBACK_BASE = 32000.0   # fallback_acv = max(4000, 32000 * 0.86^age) (docstring-pinned)
ACV_FALLBACK_DECAY = 0.86
ACV_FALLBACK_FLOOR = 4000.0
P_S_CAP = 0.45
P_S_SCALE = 0.6
P_S_R_STRUCT_SCALE = 0.6      # P_s = min(0.45, R_struct * 0.6) (docstring-pinned)
CLAIM2CAR_PRICE_MULTIPLIER = 1.08  # derived from M4 dispatch fixture (19440/18000)

# --- Repair catalog / estimating ---
RTV_BORDERLINE_MARGIN = 0.02  # |rtv - threshold| <= 0.02 -> borderline flag
DEFAULT_LABOR_RATE_USD = 65.0   # provisional — owner review pending
DEFAULT_PAINT_RATE_USD = 55.0   # provisional — owner review pending
DEFAULT_TAX_RATE = 0.0825       # default parts tax (TX); regional overrides in catalog
HIDDEN_DAMAGE_STRUCTURAL_ALLOWANCE = 0.15  # provisional — owner review pending
PDR_MAX_AREA_CM2 = 400.0        # provisional — owner review pending
PDR_MAX_DEPTH_CM = 1.5          # provisional — owner review pending
REPAIR_MAX_AREA_CM2 = 2500.0    # provisional — owner review pending
REPAIR_MAX_DEPTH_CM = 8.0       # provisional — owner review pending
SECTION_MAX_DEPTH_CM = 30.0     # provisional — owner review pending

# --- Commercial routing (constants consolidated above; no duplicates) ---
