#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stokes-parameter helper for ips_compensation_run_signedC.py

- Computes Stokes (S0,S1,S2,S3) and normalized (s1,s2,s3) from the complex E-field
  in a transverse (⊥ k) basis.
- Can return the polarization state after every element in the stack.

This is meant to complement the existing CR/leakage calculation.
"""

from __future__ import annotations
import argparse
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np

import ips_compensation_run_signedC as ips


# -----------------------------
# Stokes math
# -----------------------------
def _normalize(v: np.ndarray, eps: float = 1e-15) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / max(n, eps)


def transverse_basis(
    k: np.ndarray,
    basis: str = "lab",            # "lab" or "pol_in" or "pol_out"
    c1: Optional[np.ndarray] = None,
    c2: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build an orthonormal transverse basis (u, v) such that:
      - u ⟂ k, v ⟂ k, u·v = 0
      - (u, v, k) is right-handed (v = k × u)

    basis:
      - "lab":    u is the projection of x-hat onto the plane ⟂ k (fallback to y-hat)
      - "pol_in": u is the input POL pass axis o1 = o_axis_Otype(k, c1)
      - "pol_out":u is the analyzer pass axis o2 = o_axis_Otype(k, c2)

    Note:
      Using "lab" is closest to a fixed S1 axis definition in the lab frame.
      Using "pol_in"/"pol_out" is useful if you want S1 aligned with the POL pass axis.
    """
    k = _normalize(k)

    if basis == "lab":
        ref = np.array([1.0, 0.0, 0.0], dtype=float)
        # If x-hat is almost parallel to k, use y-hat
        if abs(float(np.dot(ref, k))) > 0.95:
            ref = np.array([0.0, 1.0, 0.0], dtype=float)

        u = ref - np.dot(ref, k) * k

    elif basis == "pol_in":
        if c1 is None:
            raise ValueError("basis='pol_in' requires c1")
        u = ips.o_axis_Otype(k, c1)

    elif basis == "pol_out":
        if c2 is None:
            raise ValueError("basis='pol_out' requires c2")
        u = ips.o_axis_Otype(k, c2)

    else:
        raise ValueError("basis must be one of: lab, pol_in, pol_out")

    u = _normalize(u)
    v = _normalize(np.cross(k, u))
    return u, v


def stokes_from_E(
    E: np.ndarray,
    k: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
) -> Tuple[float, float, float, float]:
    """
    Compute Stokes parameters from the complex E vector.

    We first form complex transverse Jones components:
      Eu = u · E
      Ev = v · E

    Then (one common convention):
      S0 = |Eu|^2 + |Ev|^2
      S1 = |Eu|^2 - |Ev|^2
      S2 = 2 Re(Eu Ev*)
      S3 = 2 Im(Eu Ev*)

    NOTE on sign:
      The sign of S3 depends on handedness / time convention.
      With (u, v, k) right-handed and exp(+iωt) convention, this is standard.
      If you compare against another convention and S3 appears flipped,
      multiply S3 by -1.

    Returns (S0,S1,S2,S3) as floats.
    """
    E = np.asarray(E, dtype=complex)
    k = _normalize(k)

    # Enforce transverse component (safety)
    E = E - np.dot(E, k) * k

    Eu = complex(np.dot(u, E))
    Ev = complex(np.dot(v, E))

    S0 = (abs(Eu) ** 2 + abs(Ev) ** 2)
    S1 = (abs(Eu) ** 2 - abs(Ev) ** 2)
    S2 = 2.0 * np.real(Eu * np.conj(Ev))
    S3 = 2.0 * np.imag(Eu * np.conj(Ev))
    return float(np.real(S0)), float(np.real(S1)), float(np.real(S2)), float(np.real(S3))


@dataclass
class StokesPoint:
    label: str
    wl_key: str
    S0: float
    S1: float
    S2: float
    S3: float

    @property
    def s1(self) -> float:
        return self.S1 / max(self.S0, 1e-30)

    @property
    def s2(self) -> float:
        return self.S2 / max(self.S0, 1e-30)

    @property
    def s3(self) -> float:
        return self.S3 / max(self.S0, 1e-30)

    def as_dict(self) -> Dict[str, float]:
        return {
            "label": self.label,
            "wl_key": self.wl_key,
            "S0": self.S0, "S1": self.S1, "S2": self.S2, "S3": self.S3,
            "s1": self.s1, "s2": self.s2, "s3": self.s3,
        }


def trace_stokes_per_wavelength(
    theta_deg: float,
    phi_deg: float,
    stack: List[Dict],
    c1: np.ndarray,
    c2: np.ndarray,
    basis: str = "lab",
    wl_keys: Tuple[str, ...] = ips.WL_KEYS,
) -> List[StokesPoint]:
    """
    Return a flat list of StokesPoint for:
      - after input polarizer ("POL_in")
      - after each element in stack ("el#i_type")
    for each wavelength key in wl_keys.
    """
    k = ips.k_hat(theta_deg, phi_deg)
    u, v = transverse_basis(k, basis=basis, c1=c1, c2=c2)

    out: List[StokesPoint] = []

    o1 = ips.o_axis_Otype(k, c1)
    E0 = o1.astype(complex)

    # After input POL
    for wl_key in wl_keys:
        S0, S1, S2, S3 = stokes_from_E(E0, k, u, v)
        out.append(StokesPoint(label="POL_in", wl_key=wl_key, S0=S0, S1=S1, S2=S2, S3=S3))

    # After each element
    for wl_key in wl_keys:
        lam = ips.wl_m(wl_key)
        E = E0.copy()

        for i, el in enumerate(stack):
            no, ne = ips._ne_no_for_wl(el, wl_key)

            if el["type"] in ("A", "LC"):
                alpha = ips.axis_azimuth_deg(el["axis"])
                phi_rel = float(phi_deg) - float(alpha)
                Gamma = float(ips.eq3a_Gamma_A(theta_deg, phi_rel, lam, el["d"], no, ne))
            elif el["type"] == "C":
                Gamma = float(ips.eq3b_Gamma_C(theta_deg, lam, el["d"], no, ne))
            else:
                raise ValueError(f"Unknown element type: {el['type']}")

            M = ips.retarder_matrix(k, np.array(el["axis"], dtype=float), Gamma)
            E = M @ E
            E = E - np.dot(E, k) * k

            S0, S1, S2, S3 = stokes_from_E(E, k, u, v)
            out.append(StokesPoint(label=f"el#{i}_{el['type']}", wl_key=wl_key, S0=S0, S1=S1, S2=S2, S3=S3))

    return out


def trace_stokes_white(
    theta_deg: float,
    phi_deg: float,
    stack: List[Dict],
    c1: np.ndarray,
    c2: np.ndarray,
    basis: str = "lab",
    wl_keys: Tuple[str, ...] = ips.WL_KEYS,
    wl_weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, float]]:
    """
    White-averaged (intensity-weighted) normalized Stokes after each stage.

    Returns list of dict per stage:
      {label, s1, s2, s3, S0_sum}

    Averaging rule:
      - For each stage and each wavelength: compute (S0,S1,S2,S3)
      - Weight by w * S0 (so dim wavelengths or attenuated states contribute less)
      - Return normalized (S1/S0, S2/S0, S3/S0) from summed Stokes.
    """
    if wl_weights is None:
        wl_weights = dict(ips.WL_WEIGHTS)

    pts = trace_stokes_per_wavelength(theta_deg, phi_deg, stack, c1, c2, basis=basis, wl_keys=wl_keys)

    # Group by label
    labels = []
    for p in pts:
        if p.label not in labels:
            labels.append(p.label)

    out_rows = []
    for lab in labels:
        S0t = S1t = S2t = S3t = 0.0
        for p in pts:
            if p.label != lab:
                continue
            w = float(wl_weights.get(p.wl_key, 1.0))
            # intensity-weighted Stokes sum
            S0t += w * p.S0
            S1t += w * p.S1
            S2t += w * p.S2
            S3t += w * p.S3

        denom = max(S0t, 1e-30)
        out_rows.append({
            "label": lab,
            "S0_sum": float(S0t),
            "s1": float(S1t / denom),
            "s2": float(S2t / denom),
            "s3": float(S3t / denom),
        })

    return out_rows


# -----------------------------
# CLI demo (optional)
# -----------------------------
def _build_demo_stack(mode: str, A_scale: float, dC_um: Optional[float]) -> List[Dict]:
    """
    Convenience builder for quick checks:
      mode="ex2": uses build_stack_realistic with TAC etc as defined in ips_compensation_run_signedC.py
      mode="LAC": user-simple LC/A/C stack (no TAC), in the same order you used in recent runs.
    """
    if mode == "ex2":
        # Uses your existing builder & parameters in ips module
        return ips.build_stack_realistic(
            dC_um=dC_um,
            A_scale=A_scale,
            tac_repeat=int(ips.TAC_REPEATS[0]),
            tac_um=float(ips.TAC_UM_CASES[0]),
            dn_tac=float(ips.DN_TAC_CASES[0]),
            pol_pair_rot_in_deg=float(ips.POL_PAIR_ROT_IN_DEGS[0]),
            pol_pair_rot_out_deg=float(ips.POL_PAIR_ROT_OUT_DEGS[0]),
            rel_rot_LA_deg=float(ips.REL_ROT_LA_DEGS[0]),
            rel_rot_UA_deg=float(ips.REL_ROT_UA_DEGS[0]),
            lc_rel_to_inpol_deg=float(ips.LC_REL_TO_INPOL_DEG),
        )

    if mode == "LAC":
        # Minimal example: LC / A / C
        # (Assumes axis conventions from the existing code base.)
        # You should replace axes/parameters to your actual optimized condition.
        k_dummy = np.array([0, 0, 1], dtype=float)

        # Reuse parameters from ips module:
        Re_each_m = (ips.RE_A_EACH_BASE_NM * 1e-9) * float(A_scale)
        d_A = Re_each_m / float(ips.dn_lowerA)  # choose lowerA dn as proxy

        axis_LC = ips.axis_from_azimuth_deg(0.0)
        axis_A  = ips.axis_from_azimuth_deg(0.0)
        # C is along z in this model

        stack = [
            {"type": "LC", "axis": axis_LC.tolist(), "d": float(ips.d_LC), "no": ips.NO_BASE, "ne": ips.ne_from_dn(ips.NO_BASE, float(ips.dn_LC))},
            {"type": "A",  "axis": axis_A.tolist(),  "d": float(d_A),      "no": ips.NO_BASE, "ne": ips.ne_from_dn(ips.NO_BASE, float(ips.dn_lowerA))},
        ]
        if dC_um is not None and abs(float(dC_um)) > 0:
            sgn = 1.0 if float(dC_um) >= 0 else -1.0
            dnC_eff = float(ips.dn_C) * sgn
            stack.append({"type": "C", "axis": [0, 0, 1], "d": abs(float(dC_um)) * 1e-6, "no": ips.NO_BASE, "ne": ips.ne_from_dn(ips.NO_BASE, dnC_eff)})
        return stack

    raise ValueError("mode must be 'ex2' or 'LAC'")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--theta", type=float, default=30.0)
    p.add_argument("--phi", type=float, default=45.0)
    p.add_argument("--basis", type=str, default="lab", choices=["lab", "pol_in", "pol_out"])
    p.add_argument("--mode", type=str, default="ex2", choices=["ex2", "LAC"])
    p.add_argument("--A_scale", type=float, default=1.0)
    p.add_argument("--dC_um", type=float, default=0.5)
    p.add_argument("--out_json", type=str, default="stokes_trace.json")
    p.add_argument("--white", action="store_true", help="Output white-averaged trace (default is per-wavelength list)")
    args, _unknown = p.parse_known_args()  # ignore -f from notebooks, etc.

    # POL axes (absorption axes)
    c1, c2 = ips.pol_axes(
        float(ips.POL_PAIR_ROT_IN_DEGS[0]) if hasattr(ips, "POL_PAIR_ROT_IN_DEGS") else 0.0,
        float(ips.POL_PAIR_ROT_OUT_DEGS[0]) if hasattr(ips, "POL_PAIR_ROT_OUT_DEGS") else 0.0,
    )

    stack = _build_demo_stack(args.mode, args.A_scale, args.dC_um)

    if args.white:
        rows = trace_stokes_white(args.theta, args.phi, stack, c1=c1, c2=c2, basis=args.basis)
        Path(args.out_json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    else:
        pts = trace_stokes_per_wavelength(args.theta, args.phi, stack, c1=c1, c2=c2, basis=args.basis)
        Path(args.out_json).write_text(json.dumps([p.as_dict() for p in pts], indent=2), encoding="utf-8")

    print(f"Saved: {args.out_json}")


if __name__ == "__main__":
    main()
