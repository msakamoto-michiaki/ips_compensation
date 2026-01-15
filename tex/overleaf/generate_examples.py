#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate figures/CSVs for Examples 1-3.

This script uses ips_compensation_run.py (a local-run friendly copy).
Outputs are written under ./examples/.

Note: For runtime, it sets DTHETA=DPHI=10deg (coarser grid than default 5deg).
"""

import numpy as np
import pandas as pd
from pathlib import Path

import ips_compensation_run as m

def compute_bestA_green(pol_in, pol_out, rel_LA, rel_UA, lc_rel, Agrid):
    old_WL_KEYS = m.WL_KEYS
    old_DN_SCALE = m.DN_SCALE
    m.WL_KEYS = ("G",)
    m.DN_SCALE = dict(m.DN_SCALE_MATCHED)

    bestA = None
    bestCR = -1.0
    c1, c2 = m.pol_axes(pol_in, pol_out)
    phis = np.arange(0, 361, 10)

    for A_scale in Agrid:
        stack = m.build_stack_realistic(
            dC_um=None, A_scale=float(A_scale),
            tac_repeat=int(m.TAC_REPEATS[0]), tac_um=float(m.TAC_UM_CASES[0]), dn_tac=float(m.DN_TAC_CASES[0]),
            pol_pair_rot_in_deg=pol_in, pol_pair_rot_out_deg=pol_out,
            rel_rot_LA_deg=rel_LA, rel_rot_UA_deg=rel_UA,
            lc_rel_to_inpol_deg=lc_rel,
        )
        CRs = []
        for ph in phis:
            T = m.Tleak_stack_scalar(0.0, float(ph), stack, c1=c1, c2=c2)
            CRs.append(m.CR_from_Tleak(float(T)))
        CRmean = float(np.mean(CRs))
        if CRmean > bestCR:
            bestCR = CRmean
            bestA = float(A_scale)

    m.WL_KEYS = old_WL_KEYS
    m.DN_SCALE = old_DN_SCALE
    return bestA, bestCR

def CR0_white(bestA, case, pol_in, pol_out, rel_LA, rel_UA, lc_rel):
    old_keys = m.WL_KEYS
    old_scale = m.DN_SCALE
    m.WL_KEYS = ("B", "G", "R")
    m.DN_SCALE = dict(m.DN_SCALE_MATCHED if case == "matched" else m.DN_SCALE_MISMATCHED)

    c1, c2 = m.pol_axes(pol_in, pol_out)
    phis = np.arange(0, 361, 10)

    stack = m.build_stack_realistic(
        dC_um=None, A_scale=float(bestA),
        tac_repeat=int(m.TAC_REPEATS[0]), tac_um=float(m.TAC_UM_CASES[0]), dn_tac=float(m.DN_TAC_CASES[0]),
        pol_pair_rot_in_deg=pol_in, pol_pair_rot_out_deg=pol_out,
        rel_rot_LA_deg=rel_LA, rel_rot_UA_deg=rel_UA,
        lc_rel_to_inpol_deg=lc_rel,
    )

    CRs = []
    for ph in phis:
        T = m.Tleak_stack_scalar(0.0, float(ph), stack, c1=c1, c2=c2)
        CRs.append(m.CR_from_Tleak(float(T)))

    m.WL_KEYS = old_keys
    m.DN_SCALE = old_scale
    return float(np.mean(CRs)), float(np.min(CRs)), float(np.max(CRs)), stack

def main():
    out_root = Path("examples")
    out_root.mkdir(exist_ok=True)

    # Coarser grid for runtime
    m.DTHETA = 10.0
    m.DPHI = 10.0
    m.THETA_MAX = 60.0

    # Example 1
    pol_in = float(m.POL_PAIR_ROT_IN_DEGS[0])
    pol_out = float(m.POL_PAIR_ROT_OUT_DEGS[0])
    rel_LA = float(m.REL_ROT_LA_DEGS[0])
    rel_UA = float(m.REL_ROT_UA_DEGS[0])
    lc_rel = float(m.LC_REL_TO_INPOL_DEG)

    Agrid = np.linspace(0.2, 3.0, 57)
    bestA, bestCRg = compute_bestA_green(pol_in, pol_out, rel_LA, rel_UA, lc_rel, Agrid)

    CRm_mean, CRm_min, CRm_max, stack_match = CR0_white(bestA, "matched", pol_in, pol_out, rel_LA, rel_UA, lc_rel)
    CRmm_mean, CRmm_min, CRmm_max, stack_mismatch = CR0_white(bestA, "mismatched", pol_in, pol_out, rel_LA, rel_UA, lc_rel)

    ex1 = out_root / "ex1_dispersion"
    ex1.mkdir(exist_ok=True)
    df = pd.DataFrame([
        {"case": "matched", "A_scale(best@G)": bestA, "CR0_G_best": bestCRg,
         "CR0_white_mean": CRm_mean, "CR0_white_min": CRm_min, "CR0_white_max": CRm_max},
        {"case": "mismatched", "A_scale(best@G)": bestA, "CR0_G_best": bestCRg,
         "CR0_white_mean": CRmm_mean, "CR0_white_min": CRmm_min, "CR0_white_max": CRmm_max},
    ])
    df.to_csv(ex1 / "ex1_cr0_summary.csv", index=False)

    c1, c2 = m.pol_axes(pol_in, pol_out)
    old_keys = m.WL_KEYS
    old_scale = m.DN_SCALE
    m.WL_KEYS = ("B", "G", "R")

    m.DN_SCALE = dict(m.DN_SCALE_MATCHED)
    thetas, phis, CR = m.compute_CR_grid(stack_match, c1, c2, theta_max=m.THETA_MAX, dtheta=m.DTHETA, dphi=m.DPHI)
    m.plot_isocontrast_polar(thetas, phis, CR, title=f"Example1 Matched (A_scale={bestA:.2f})",
                             out_path=str(ex1 / "ex1_iso_matched.png"))

    m.DN_SCALE = dict(m.DN_SCALE_MISMATCHED)
    thetas, phis, CR = m.compute_CR_grid(stack_mismatch, c1, c2, theta_max=m.THETA_MAX, dtheta=m.DTHETA, dphi=m.DPHI)
    m.plot_isocontrast_polar(thetas, phis, CR, title=f"Example1 Mismatched (A_scale={bestA:.2f})",
                             out_path=str(ex1 / "ex1_iso_mismatched.png"))

    m.WL_KEYS = old_keys
    m.DN_SCALE = old_scale

    # Example 2
    m.run_Ascale_C_grid_check(
        out_dir=str(out_root / "ex2_Ascale_C_grid_check"),
        A_scales=(0.5, 1.0, 1.5, 2.0),
        C_list=(-0.5, 0.0, 0.5),
        pol_in=0.0, pol_out=0.0,
        relA=0.5, lc_rel=1.0,
        case_name="matched",
        wl_keys=("B", "G", "R"),
        thr=100.0,
        cr_cap=None
    )

    # Example 3
    m.run_pol_in_distortion_check(
        out_dir=str(out_root / "ex3_pol_in_distortion_check"),
        pol_in_list=(0.0, 0.2, 0.5, 1.0, 2.0),
        A_scale=2.0,
        C_um=-0.5,
        pol_out=0.0,
        relA=0.5,
        lc_rel=1.0,
        case_name="matched",
        wl_keys=("B", "G", "R"),
        thr=100.0,
        cr_cap=None
    )

    print("Done. Outputs are under ./examples/")

if __name__ == "__main__":
    main()
