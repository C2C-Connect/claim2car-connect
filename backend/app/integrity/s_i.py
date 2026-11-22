"""Forensic Integrity Score S_i: weighted sum with fail-closed evidence-chain integrity."""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional
from config import forensic_constants as C

@dataclass
class IntegrityInputs:
    gps_accuracy_m: Optional[float] = None
    master_hash_valid: bool = True
    chain_coverage: float = 1.0
    chain_uniqueness: float = 1.0
    meta_completeness: float = 1.0
    gps_spoof_suspected: bool = False
    hash_tamper_suspected: bool = False

@dataclass
class IntegrityResult:
    s_i: float
    c_gps: float
    c_hash: float
    c_meta: float
    tier: str
    all_or_nothing_collapse: bool
    formula_version: str = C.VERSION
    c_chain: float = 1.0
    c_chain_geometric: float = 1.0
    chain_failure_reason: Optional[str] = None

def _fraction(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"INVALID_INTEGRITY_FRACTION:{name}")
    value=float(value)
    if not math.isfinite(value) or value<0.0 or value>1.0:
        raise ValueError(f"INVALID_INTEGRITY_FRACTION:{name}")
    return value

def c_gps_from_accuracy(accuracy_m: Optional[float], spoof: bool=False) -> float:
    if spoof: return 0.0
    if accuracy_m is None: return 0.5
    if isinstance(accuracy_m,bool) or not isinstance(accuracy_m,(int,float)):
        raise ValueError("INVALID_GPS_ACCURACY")
    accuracy_m=float(accuracy_m)
    if not math.isfinite(accuracy_m) or accuracy_m<0.0: raise ValueError("INVALID_GPS_ACCURACY")
    for limit,coef in C.GPS_TIERS:
        if accuracy_m<=limit: return coef
    return C.GPS_TIER_FLOOR

def _chain_details(coverage:float,uniqueness:float,tamper:bool=False):
    coverage=_fraction(coverage,"chain_coverage")
    uniqueness=_fraction(uniqueness,"chain_uniqueness")
    geometric=math.sqrt(coverage*uniqueness)
    if tamper: return 0.0,geometric,"HASH_TAMPER_SUSPECTED"
    if coverage<1.0: return 0.0,geometric,"CHAIN_COVERAGE_INCOMPLETE"
    if uniqueness<1.0: return 0.0,geometric,"CHAIN_HASH_DUPLICATE"
    return geometric,geometric,None

def c_chain(coverage:float,uniqueness:float,tamper:bool=False):
    effective,_,reason=_chain_details(coverage,uniqueness,tamper)
    return effective,reason

def c_hash(master_valid:bool,coverage:float,uniqueness:float,tamper:bool=False)->float:
    if not master_valid: return 0.0
    effective,_,reason=_chain_details(coverage,uniqueness,tamper)
    return 0.0 if reason else effective

def c_meta(completeness:float)->float:
    return _fraction(completeness,"meta_completeness")

def compute_s_i(inp:IntegrityInputs)->IntegrityResult:
    cg=c_gps_from_accuracy(inp.gps_accuracy_m,inp.gps_spoof_suspected)
    chain,raw_chain,chain_failure=_chain_details(inp.chain_coverage,inp.chain_uniqueness,inp.hash_tamper_suspected)
    ch=0.0 if chain_failure or not inp.master_hash_valid else chain
    cm=c_meta(inp.meta_completeness)
    collapse=bool(chain_failure or not inp.master_hash_valid or inp.gps_spoof_suspected)
    weights=C.S_I_WEIGHTS
    if not math.isclose(sum(weights.values()),1.0,rel_tol=0.0,abs_tol=1e-9): raise ValueError("INVALID_S_I_WEIGHT_SUM")
    score=0.0 if collapse else weights["gps"]*cg+weights["hash"]*ch+weights["meta"]*cm
    if score>=C.S_I_PASS: tier="pass"
    elif score>=C.S_I_REJECT: tier="review"
    else: tier="reject"
    return IntegrityResult(s_i=round(score,4),c_gps=round(cg,4),c_hash=round(ch,4),c_meta=round(cm,4),tier=tier,
        all_or_nothing_collapse=collapse,c_chain=round(chain,4),c_chain_geometric=round(raw_chain,4),
        chain_failure_reason=chain_failure or ("MASTER_HASH_INVALID" if not inp.master_hash_valid else None))
