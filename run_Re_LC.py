# -*- coding: utf-8 -*-
"""
Sensitivity study: LC retardation perturbation around the best stack.

Monitors:
  - CR00 at R/G/B/W
  - CR at (theta=30deg, phi=45, 135, -45, -135) for WHITE (W)

Usage example:
  python run_Re_LC.py --progress_csv out_opt/progress_LC_AC_abs.csv --outdir sens_ReLC \
      --lc_basis abs --scale_min 0.85 --scale_max 1.15 --scale_step 0.05 --iso_every 1
"""
import argparse, math, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import ips_compensation_run_signedC as ips

MON_THETA = 30.0
MON_PHIS = [45.0, 135.0, -45.0, -135.0]

def build_LC_scaled(lc_basis: str, pol_in_deg: float, relLC_deg: float, dn_scale: float):
    az = 0.0 if lc_basis == "abs" else 90.0
    axis_LC = ips.rotz_deg(ips.axis_from_azimuth_deg(az), pol_in_deg + relLC_deg)
    dn = float(ips.dn_LC) * float(dn_scale)
    return {
        "type": "LC",
        "axis": axis_LC.tolist(),
        "d": float(ips.d_LC),
        "no": ips.NO_BASE,
        "ne": ips.ne_from_dn(ips.NO_BASE, dn),
    }

def build_A(A_scale: float, A_base_deg: float, pol_out_deg: float, relA_deg: float, A_kind: str):
    axis_A = ips.rotz_deg(ips.axis_from_azimuth_deg(float(A_base_deg)), pol_out_deg + relA_deg)
    Re_each_m = (ips.RE_A_EACH_BASE_NM * 1e-9) * float(A_scale)
    dnA = float(ips.dn_upperA) if A_kind == "upper" else float(ips.dn_lowerA)
    dA = Re_each_m / dnA if float(A_scale) != 0 else 0.0
    return {
        "type": "A",
        "axis": axis_A.tolist(),
        "d": float(dA),
        "no": ips.NO_BASE,
        "ne": ips.ne_from_dn(ips.NO_BASE, dnA),
    }

def build_C(ReC_nm_signed: float):
    ReC = float(ReC_nm_signed)
    if ReC == 0:
        return None
    sgn = 1.0 if ReC >= 0 else -1.0
    dnC = float(ips.dn_C)
    dC_um = abs(ReC) / (dnC * 1000.0)
    return {
        "type": "C",
        "axis": [0, 0, 1],
        "d": float(dC_um) * 1e-6,
        "no": ips.NO_BASE,
        "ne": ips.ne_from_dn(ips.NO_BASE, dnC * sgn),
    }

def Tleak_single_lambda(theta_deg: float, phi_deg: float, stack, c1, c2, wl_key: str) -> float:
    k = ips.k_hat(theta_deg, phi_deg)
    o1 = ips.o_axis_Otype(k, c1)
    o2 = ips.o_axis_Otype(k, c2)
    E = o1.astype(complex)

    lam = ips.wl_m(wl_key)
    for el in stack:
        no, ne = ips._ne_no_for_wl(el, wl_key)
        if el["type"] in ("A", "LC"):
            alpha = ips.axis_azimuth_deg(el["axis"])
            phi_rel = phi_deg - alpha
            Gamma = float(ips.eq3a_Gamma_A(theta_deg, phi_rel, lam, el["d"], no, ne))
        elif el["type"] == "C":
            Gamma = float(ips.eq3b_Gamma_C(theta_deg, lam, el["d"], no, ne))
        else:
            raise ValueError(f"Unknown element type: {el.get('type')}")
        M = ips.retarder_matrix(k, np.array(el["axis"], dtype=float), Gamma)
        E = M @ E
        E = E - np.dot(E, k) * k
    T = abs(np.vdot(o2, E))**2
    return float(T.real)

def CR00_per_wavelength(stack, c1, c2):
    out = {}
    for wl in ("R","G","B"):
        T = Tleak_single_lambda(0.0, 0.0, stack, c1, c2, wl_key=wl)
        out[wl] = ips.CR_from_Tleak(T)
    Tw = ips.Tleak_stack_scalar(0.0, 0.0, stack, c1=c1, c2=c2)
    out["W"] = ips.CR_from_Tleak(Tw)
    return out

def CR_at_angles_W(stack, c1, c2, theta_deg: float, phis_deg):
    res = {}
    for ph in phis_deg:
        Tw = ips.Tleak_stack_scalar(theta_deg, float(ph), stack, c1=c1, c2=c2)
        res[ph] = ips.CR_from_Tleak(Tw)
    return res

def save_iso(stack, title: str, out_png: Path, c1, c2, theta_max=60.0, dtheta=5.0, dphi=5.0):
    thetas, phis, CR = ips.compute_CR_grid(stack, c1, c2, theta_max=theta_max, dtheta=dtheta, dphi=dphi)
    ips.plot_isocontrast_polar(
        thetas, phis, CR,
        title=title,
        out_path=str(out_png),
        theta_ticks=[0,10,20,30,40,50,60]
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--progress_csv", type=str, required=True)
    ap.add_argument("--row", type=int, default=-1)
    ap.add_argument("--outdir", type=str, default="sens_ReLC")
    ap.add_argument("--tag", type=str, default="LC_AC_abs")
    ap.add_argument("--lc_basis", type=str, choices=["abs","tran"], default="abs")
    ap.add_argument("--pol_in", type=float, default=0.0)
    ap.add_argument("--pol_out", type=float, default=0.0)
    ap.add_argument("--relA", type=float, default=0.25)
    ap.add_argument("--relLC", type=float, default=0.25)
    ap.add_argument("--theta_max", type=float, default=60.0)
    ap.add_argument("--dtheta", type=float, default=5.0)
    ap.add_argument("--dphi", type=float, default=5.0)

    ap.add_argument("--scale_min", type=float, default=0.85)
    ap.add_argument("--scale_max", type=float, default=1.15)
    ap.add_argument("--scale_step", type=float, default=0.05)
    ap.add_argument("--iso_every", type=int, default=1)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.progress_csv)
    r = df.iloc[int(args.row)]
    A_scale = float(r["A_scale"])
    ReC_nm = float(r["ReC_nm"])
    A_base = float(r["A_base_deg"])
    A_kind = str(r["A_kind"])

    c1, c2 = ips.pol_axes(float(args.pol_in), float(args.pol_out))

    # Reference (scale=1)
    LC_ref = build_LC_scaled(args.lc_basis, args.pol_in, args.relLC, dn_scale=1.0)
    A_ref  = build_A(A_scale, A_base, args.pol_out, args.relA, A_kind)
    C_ref  = build_C(ReC_nm)
    ref_stack = [LC_ref, A_ref] + ([] if C_ref is None else [C_ref])

    (outdir / "ref_stack.json").write_text(json.dumps(ref_stack, indent=2), encoding="utf-8")
    ref_cr00 = CR00_per_wavelength(ref_stack, c1, c2)
    ref_crang = CR_at_angles_W(ref_stack, c1, c2, MON_THETA, MON_PHIS)
    (outdir / "ref_CR00.json").write_text(json.dumps(ref_cr00, indent=2), encoding="utf-8")
    (outdir / "ref_CR_theta30.json").write_text(json.dumps(ref_crang, indent=2), encoding="utf-8")

    save_iso(ref_stack, f"ISO-CR REF ({args.tag})", outdir / "ref_iso.png", c1, c2,
             theta_max=args.theta_max, dtheta=args.dtheta, dphi=args.dphi)

    base_ReLC_nm = float(ips.dn_LC) * float(ips.d_LC) * 1e9  # dn * d (m) -> nm
    scales = np.arange(args.scale_min, args.scale_max + 1e-12, args.scale_step)

    rows = []
    for idx, s in enumerate(scales):
        LC = build_LC_scaled(args.lc_basis, args.pol_in, args.relLC, dn_scale=float(s))
        A  = build_A(A_scale, A_base, args.pol_out, args.relA, A_kind)
        C  = build_C(ReC_nm)
        stack = [LC, A] + ([] if C is None else [C])

        cr00 = CR00_per_wavelength(stack, c1, c2)
        crang = CR_at_angles_W(stack, c1, c2, MON_THETA, MON_PHIS)

        ReLC_nm = base_ReLC_nm * float(s)

        row = {
            "scale": float(s),
            "ReLC_nm": float(ReLC_nm),

            "CR00_R": float(cr00["R"]),
            "CR00_G": float(cr00["G"]),
            "CR00_B": float(cr00["B"]),
            "CR00_W": float(cr00["W"]),
            "CR00_W_rel_to_ref_dB": 10.0 * math.log10(float(cr00["W"]) / float(ref_cr00["W"])),
        }
        for ph in MON_PHIS:
            key = f"CR_W_t30_p{int(ph):+d}"
            row[key] = float(crang[ph])
            row[key + "_rel_to_ref_dB"] = 10.0 * math.log10(float(crang[ph]) / float(ref_crang[ph]))
        rows.append(row)

        if int(args.iso_every) > 0 and (idx % int(args.iso_every) == 0):
            save_iso(stack,
                     f"ISO-CR {args.tag} ReLC={ReLC_nm:.1f}nm (scale={s:.3f})",
                     outdir / f"iso_ReLC_{ReLC_nm:.1f}nm.png",
                     c1, c2, theta_max=args.theta_max, dtheta=args.dtheta, dphi=args.dphi)

    dfo = pd.DataFrame(rows)
    dfo.to_csv(outdir / "scan_ReLC.csv", index=False)

    fig = plt.figure(figsize=(5.6, 3.6), dpi=200)
    ax = fig.add_subplot(111)
    ax.plot(dfo["ReLC_nm"].values, dfo["CR00_W"].values, marker="o")
    ax.set_xlabel("Re_LC (nm)")
    ax.set_ylabel("CR00 (W)")
    ax.grid(True, ls=":")
    ax.set_title(f"CR00(W) vs Re_LC ({args.tag})")
    fig.tight_layout()
    fig.savefig(outdir / "plot_ReLC_vs_CR00_W.png", bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    main()
