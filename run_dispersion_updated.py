# -*- coding: utf-8 -*-
"""run_dispersion.py

Wavelength sweep (dispersion) analysis for a fixed best/ref stack.

You can evaluate:
  - CR00 at each wavelength
  - CR(theta,phi) at each wavelength (user-specified angles)
  - ISO-CR polar map at selected wavelengths

The interface is aligned with run_rot_AC.py / run_Re_LC.py:
  --pol_in --pol_out --relA --relLC (fixed settings)
  --ref_A_scale --ref_ReC_nm (override REF A_scale/ReC)

Dispersion model:
  - 'flat'      : dn is constant (no wavelength dependence except 1/lambda in Gamma)
  - 'matched'   : use ips.DN_SCALE_MATCHED for LC/A/C and linearly interpolate vs wavelength
  - 'mismatched': use ips.DN_SCALE_MISMATCHED and interpolate
  - 'current'   : use ips.DN_SCALE (active in ips module) and interpolate

Outputs (outdir):
  - dispersion.csv
  - ref_stack.json
  - iso_ref_<lambda>.png (and more if iso_every>0)
  - plot_lambda_vs_CR00_W.png  (single-wavelength CR00 at each lambda)

Notes:
  - This script computes *monochromatic* CR from Tleak(lambda).
  - It does NOT compute the white-averaged 'W' definition from ips.
    Column names use suffix '_mono'.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import ips_compensation_run_signedC as ips


# ------------------------
# Stack builders (same idea as other scripts)
# ------------------------

def build_LC_from_azimuth(lc_azimuth_deg: float):
    axis_LC = ips.axis_from_azimuth_deg(float(lc_azimuth_deg))
    dn = float(ips.dn_LC)
    return {
        "type": "LC",
        "axis": axis_LC.tolist(),
        "d": float(ips.d_LC),
        "no": ips.NO_BASE,
        "ne": ips.ne_from_dn(ips.NO_BASE, dn),
    }


def build_A_from_azimuth(A_scale: float, A_base_deg: float, A_azimuth_deg: float, A_kind: str):
    axis_A = ips.axis_from_azimuth_deg(float(A_azimuth_deg))
    # Re_each = RE_A_EACH_BASE_NM * A_scale (nm) -> (m)
    Re_each_m = (ips.RE_A_EACH_BASE_NM * 1e-9) * float(A_scale)
    dnA = float(ips.dn_upperA) if str(A_kind) == "upper" else float(ips.dn_lowerA)
    dA = Re_each_m / dnA if float(A_scale) != 0 else 0.0
    return {
        "type": "A",
        "axis": axis_A.tolist(),
        "d": float(dA),
        "no": ips.NO_BASE,
        "ne": ips.ne_from_dn(ips.NO_BASE, dnA),
        "meta": {"A_base_deg": float(A_base_deg), "A_kind": str(A_kind)},
    }


def build_C(ReC_nm_signed: float):
    ReC = float(ReC_nm_signed)
    if ReC == 0:
        return None
    sgn = 1.0 if ReC >= 0 else -1.0
    dnC = float(ips.dn_C)
    dC_um = abs(ReC) / (dnC * 1000.0)  # d[um]=Re[nm]/(1000*dn)
    return {
        "type": "C",
        "axis": [0, 0, 1],
        "d": float(dC_um) * 1e-6,  # um -> m
        "no": ips.NO_BASE,
        "ne": ips.ne_from_dn(ips.NO_BASE, dnC * sgn),
    }


# ------------------------
# Dispersion / wavelength helpers
# ------------------------

BGR_WL = np.array([450.0, 546.0, 610.0], dtype=float)


def _interp_scale(lam_nm: float, scale_dict_BGR: dict) -> float:
    """Linear interpolation of scale factors defined at B/G/R points."""
    # default is 1.0
    sb = float(scale_dict_BGR.get("B", 1.0))
    sg = float(scale_dict_BGR.get("G", 1.0))
    sr = float(scale_dict_BGR.get("R", 1.0))
    y = np.array([sb, sg, sr], dtype=float)
    return float(np.interp(float(lam_nm), BGR_WL, y, left=y[0], right=y[-1]))


def _dn_scale_table(mode: str):
    if mode == "flat":
        # all = 1
        return {"LC": {"B": 1.0, "G": 1.0, "R": 1.0},
                "A":  {"B": 1.0, "G": 1.0, "R": 1.0},
                "C":  {"B": 1.0, "G": 1.0, "R": 1.0},
                "TAC": {"B": 1.0, "G": 1.0, "R": 1.0}}
    if mode == "matched":
        return ips.DN_SCALE_MATCHED
    if mode == "mismatched":
        return ips.DN_SCALE_MISMATCHED
    if mode == "current":
        return ips.DN_SCALE
    raise ValueError(f"Unknown dispersion mode: {mode}")


def ne_no_for_lambda(el: dict, lam_nm: float, disp_mode: str) -> tuple[float, float]:
    """Return (no, ne) at lam_nm.

    In ips, el['no'], el['ne'] are treated as G-values. We follow the same rule and apply
    a dn scale factor vs wavelength (interpolated from B/G/R) when disp_mode != 'flat'.
    """
    no = float(el["no"])
    neG = float(el["ne"])
    dnG = neG - no

    if disp_mode == "flat":
        return no, no + dnG

    tab = _dn_scale_table(disp_mode)
    t = str(el["type"])
    scale_BGR = tab.get(t, {"B": 1.0, "G": 1.0, "R": 1.0})
    s = _interp_scale(float(lam_nm), scale_BGR)
    return no, no + dnG * float(s)


# ------------------------
# Optical computation at single wavelength
# ------------------------


def Tleak_stack_mono(theta_deg: float, phi_deg: float, stack, c1, c2, lam_nm: float, disp_mode: str) -> float:
    """Monochromatic leakage Tleak at a given wavelength (nm)."""
    k = ips.k_hat(theta_deg, phi_deg)
    o1 = ips.o_axis_Otype(k, c1)
    o2 = ips.o_axis_Otype(k, c2)
    E = o1.astype(complex)

    lam = float(lam_nm) * 1e-9

    for el in stack:
        no, ne = ne_no_for_lambda(el, lam_nm, disp_mode)
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

    T = abs(np.vdot(o2, E)) ** 2
    return float(np.real(T))


def CR00_mono(stack, c1, c2, lam_nm: float, disp_mode: str) -> float:
    T = Tleak_stack_mono(0.0, 0.0, stack, c1, c2, lam_nm=lam_nm, disp_mode=disp_mode)
    return float(ips.CR_from_Tleak(T))


def CR_mono(theta_deg: float, phi_deg: float, stack, c1, c2, lam_nm: float, disp_mode: str) -> float:
    T = Tleak_stack_mono(theta_deg, phi_deg, stack, c1, c2, lam_nm=lam_nm, disp_mode=disp_mode)
    return float(ips.CR_from_Tleak(T))



def Tleak_stack_W(theta_deg: float, phi_deg: float, stack, c1, c2, disp_mode: str,
                  wl_keys=ips.WL_KEYS, wl_nm_map=ips.WL_NM, wl_weights=ips.WL_WEIGHTS) -> float:
    """White-evaluated leakage Tleak using B/G/R weighted average.

    Notes
    -----
    - This is NOT an average of CR. We average monochromatic Tleak(lambda) and then
      convert to CR via ips.CR_from_Tleak(), consistent with ips.Tleak_stack_scalar().
    - The wavelength-dependent (dn) scaling is controlled by disp_mode and applied
      inside Tleak_stack_mono() through ne_no_for_lambda().
    """
    Tsum = 0.0
    wsum = 0.0
    for k in wl_keys:
        lam_nm = float(wl_nm_map[k])
        w = float(wl_weights.get(k, 1.0))
        Tsum += w * Tleak_stack_mono(theta_deg, phi_deg, stack, c1, c2, lam_nm=lam_nm, disp_mode=disp_mode)
        wsum += w
    return float(Tsum / max(wsum, 1e-30))


def CR_W(theta_deg: float, phi_deg: float, stack, c1, c2, disp_mode: str) -> float:
    """White-evaluated CR (W) at (theta,phi)."""
    T = Tleak_stack_W(theta_deg, phi_deg, stack, c1, c2, disp_mode=disp_mode)
    return float(ips.CR_from_Tleak(T))


def compute_CR_grid_W(stack, c1, c2, disp_mode: str, theta_max=60.0, dtheta=5.0, dphi=5.0):
    """Compute ISO-CR polar grid for white evaluation (W)."""
    thetas = np.arange(0.0, float(theta_max) + 1e-12, float(dtheta))
    phis = np.arange(0.0, 360.0 + 1e-12, float(dphi))

    CR = np.zeros((len(thetas), len(phis)), dtype=float)
    for i, th in enumerate(thetas):
        for j, ph in enumerate(phis):
            CR[i, j] = CR_W(float(th), float(ph), stack, c1, c2, disp_mode=disp_mode)
    return thetas, phis, CR


def save_iso_W(stack, title: str, out_png: Path, c1, c2, disp_mode: str,
               theta_max=60.0, dtheta=5.0, dphi=5.0):
    """Save ISO-contrast plot for white evaluation (W)."""
    thetas, phis, CR = compute_CR_grid_W(
        stack, c1, c2, disp_mode=disp_mode, theta_max=theta_max, dtheta=dtheta, dphi=dphi
    )
    ips.plot_isocontrast_polar(
        thetas,
        phis,
        CR,
        title=title,
        out_path=str(out_png),
        theta_ticks=[0, 10, 20, 30, 40, 50, 60],
    )

def compute_CR_grid_mono(stack, c1, c2, lam_nm: float, disp_mode: str,
                         theta_max=60.0, dtheta=5.0, dphi=5.0):
    thetas = np.arange(0.0, float(theta_max) + 1e-12, float(dtheta))
    phis = np.arange(0.0, 360.0 + 1e-12, float(dphi))

    CR = np.zeros((len(thetas), len(phis)), dtype=float)
    for i, th in enumerate(thetas):
        for j, ph in enumerate(phis):
            CR[i, j] = CR_mono(float(th), float(ph), stack, c1, c2, lam_nm=lam_nm, disp_mode=disp_mode)
    return thetas, phis, CR


def save_iso_mono(stack, title: str, out_png: Path, c1, c2, lam_nm: float, disp_mode: str,
                  theta_max=60.0, dtheta=5.0, dphi=5.0):
    thetas, phis, CR = compute_CR_grid_mono(
        stack, c1, c2, lam_nm=lam_nm, disp_mode=disp_mode,
        theta_max=theta_max, dtheta=dtheta, dphi=dphi
    )
    ips.plot_isocontrast_polar(
        thetas, phis, CR,
        title=title,
        out_path=str(out_png),
        theta_ticks=[0, 10, 20, 30, 40, 50, 60]
    )


# ------------------------
# Main
# ------------------------

def parse_wavelengths(args) -> np.ndarray:
    if args.wl_list_nm is not None and len(args.wl_list_nm.strip()) > 0:
        vals = [float(x.strip()) for x in args.wl_list_nm.split(",") if x.strip()]
        return np.array(vals, dtype=float)
    return np.arange(args.wl_min_nm, args.wl_max_nm + 1e-12, args.wl_step_nm, dtype=float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--progress_csv", type=str, required=True)
    ap.add_argument("--row", type=int, default=-1)
    ap.add_argument("--outdir", type=str, default="dispersion")
    ap.add_argument("--tag", type=str, default="LC_AC_abs")

    # fixed settings (aligned)
    ap.add_argument("--lc_basis", type=str, choices=["abs", "tran"], default="abs")
    ap.add_argument("--pol_in", type=float, default=0.0)
    ap.add_argument("--pol_out", type=float, default=0.0)
    ap.add_argument("--relLC", type=float, default=0.25)
    ap.add_argument("--relA", type=float, default=0.25)

    # REF overrides
    ap.add_argument("--ref_A_scale", type=float, default=None)
    ap.add_argument("--ref_ReC_nm", type=float, default=None)

    # wavelength sweep
    ap.add_argument("--wl_min_nm", type=float, default=420.0)
    ap.add_argument("--wl_max_nm", type=float, default=680.0)
    ap.add_argument("--wl_step_nm", type=float, default=10.0)
    ap.add_argument("--wl_list_nm", type=str, default=None,
                    help="comma-separated list, e.g. '450,500,546,610,650'")

    ap.add_argument("--dispersion", type=str, default="matched",
                    choices=["flat", "matched", "mismatched", "current"],
                    help="dn dispersion model")

    # monitor angles
    ap.add_argument("--mon_theta", type=float, default=30.0)
    ap.add_argument("--mon_phis", type=str, default="45,135,-45,-135")

    # ISO output control
    ap.add_argument("--iso_every", type=int, default=0,
                    help="if >0, output ISO png every N wavelengths")
    ap.add_argument("--theta_max", type=float, default=60.0)
    ap.add_argument("--dtheta", type=float, default=5.0)
    ap.add_argument("--dphi", type=float, default=5.0)

    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    mon_phis = [float(x.strip()) for x in args.mon_phis.split(",") if x.strip()]

    df = pd.read_csv(args.progress_csv)
    r = df.iloc[int(args.row)]

    A_base = float(r.get("A_base_deg", 0.0))
    A_kind = str(r.get("A_kind", "upper"))

    A_scale_csv = float(r["A_scale"])
    ReC_nm_csv = float(r["ReC_nm"])
    A_scale_ref = float(args.ref_A_scale) if args.ref_A_scale is not None else A_scale_csv
    ReC_nm_ref = float(args.ref_ReC_nm) if args.ref_ReC_nm is not None else ReC_nm_csv

    pol_out_ref = float(args.pol_out)

    # REF absolute azimuths
    lc_base = 0.0 if args.lc_basis == "abs" else 90.0
    LC_az_ref = lc_base + float(args.pol_in) + float(args.relLC)
    A_az_ref = float(A_base) + pol_out_ref + float(args.relA)

    # polarizers
    c1, c2 = ips.pol_axes(float(args.pol_in), pol_out_ref)

    # stack
    LC = build_LC_from_azimuth(LC_az_ref)
    A = build_A_from_azimuth(A_scale_ref, A_base, A_az_ref, A_kind)
    C = build_C(ReC_nm_ref)
    stack = [LC, A] + ([] if C is None else [C])

    (outdir / "ref_stack.json").write_text(json.dumps(stack, indent=2), encoding="utf-8")

    # wavelengths
    wls = parse_wavelengths(args)

    rows = []
    for i, lam_nm in enumerate(wls):
        cr00 = CR00_mono(stack, c1, c2, lam_nm=lam_nm, disp_mode=args.dispersion)
        row = {
            "lambda_nm": float(lam_nm),
            "CR00_mono": float(cr00),
        }
        for ph in mon_phis:
            key = f"CR_mono_t{int(args.mon_theta):d}_p{int(ph):+d}"
            row[key] = CR_mono(float(args.mon_theta), float(ph), stack, c1, c2, lam_nm=float(lam_nm), disp_mode=args.dispersion)
        rows.append(row)

        if int(args.iso_every) > 0 and (i % int(args.iso_every) == 0):
            out_png = outdir / f"iso_mono_{lam_nm:.1f}nm.png"
            save_iso_mono(
                stack,
                title=f"ISO-CR mono {lam_nm:.1f} nm  ({args.tag}, disp={args.dispersion})",
                out_png=out_png,
                c1=c1,
                c2=c2,
                lam_nm=float(lam_nm),
                disp_mode=args.dispersion,
                theta_max=args.theta_max,
                dtheta=args.dtheta,
                dphi=args.dphi,
            )

    # ---- export canonical ISO maps for R/G/B (mono) and W ----
    # These are useful for direct comparison with optimization-side (W) iso plots.
    try:
        # RGB mono ISO maps at representative wavelengths
        for k in ips.WL_KEYS:
            lam_nm = float(ips.WL_NM[k])
            out_png = outdir / f"iso_{k}_mono_{int(lam_nm):d}nm.png"
            title = f"ISO-CR ({k}, mono {lam_nm:.0f} nm)  ({args.tag}, disp={args.dispersion})"
            save_iso_mono(
                stack=stack,
                title=title,
                out_png=out_png,
                c1=c1,
                c2=c2,
                lam_nm=lam_nm,
                disp_mode=args.dispersion,
                theta_max=args.theta_max,
                dtheta=args.dtheta,
                dphi=args.dphi,
            )

        # White-evaluated ISO map (W): B/G/R weighted average of Tleak
        out_png = outdir / "iso_W.png"
        title = f"ISO-CR (W: B/G/R Tleak-average)  ({args.tag}, disp={args.dispersion})"
        save_iso_W(
            stack=stack,
            title=title,
            out_png=out_png,
            c1=c1,
            c2=c2,
            disp_mode=args.dispersion,
            theta_max=args.theta_max,
            dtheta=args.dtheta,
            dphi=args.dphi,
        )
    except Exception as e:
        print(f"[WARN] Failed to export canonical RGB/W ISO maps: {e}")

    dfo = pd.DataFrame(rows)
    dfo.to_csv(outdir / "dispersion.csv", index=False)
    # ---- additional summary: CRavg4 at mon_theta over mon_phis (default: ±45, ±135) ----
    mon_keys = [f"CR_mono_t{int(args.mon_theta):d}_p{int(ph):+d}" for ph in mon_phis]
    mon_keys = [k for k in mon_keys if k in dfo.columns]
    if len(mon_keys) > 0:
        dfo["CRavg4_mono_t30"] = dfo[mon_keys].mean(axis=1)

        cols_out = ["lambda_nm", "CR00_mono", "CRavg4_mono_t30"] + mon_keys
        dfo[cols_out].to_csv(outdir / "dispersion_summary_CRavg4.csv", index=False)

        fig = plt.figure(figsize=(5.8, 3.8), dpi=200)
        ax = fig.add_subplot(111)
        ax.plot(dfo["lambda_nm"].values, dfo["CR00_mono"].values, marker="o", label="CR00 (mono)")
        ax.plot(dfo["lambda_nm"].values, dfo["CRavg4_mono_t30"].values, marker="s",
                label=f"avg CR(theta={args.mon_theta:g}, phis={args.mon_phis}) (mono)")
        ax.set_xlabel("wavelength (nm)")
        ax.set_ylabel("CR (mono)")
        ax.set_yscale("log")
        ax.grid(True, ls=":")
        #ax.legend()
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2)
        ax.set_title(f"CR00 & CRavg4(mono) vs wavelength ({args.tag}, disp={args.dispersion})")
        fig.tight_layout()
        #fig.subplots_adjust(bottom=0.22)  # 余白を増やす（tight_layoutだけだと足りない時）
        fig.savefig(outdir / "plot_lambda_vs_CR00_and_CRavg4_mono.png", bbox_inches="tight")
        plt.close(fig)

    # plot CR00 vs wavelength
    fig = plt.figure(figsize=(5.6, 3.6), dpi=200)
    ax = fig.add_subplot(111)
    ax.plot(dfo["lambda_nm"].values, dfo["CR00_mono"].values, marker="o")
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("CR00 (mono)")
    ax.grid(True, ls=":")
    ax.set_title(f"CR00(mono) vs wavelength ({args.tag}, disp={args.dispersion})")
    fig.tight_layout()
    fig.savefig(outdir / "plot_lambda_vs_CR00_mono.png", bbox_inches="tight")
    plt.close(fig)

    # also dump a small summary json
    summary = {
        "tag": args.tag,
        "dispersion": args.dispersion,
        "wavelengths_nm": [float(x) for x in wls.tolist()],
        "pol_in": float(args.pol_in),
        "pol_out": float(args.pol_out),
        "relLC": float(args.relLC),
        "relA": float(args.relA),
        "A_scale_ref": float(A_scale_ref),
        "ReC_nm_ref": float(ReC_nm_ref),
        "A_base_deg": float(A_base),
        "A_kind": str(A_kind),
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
