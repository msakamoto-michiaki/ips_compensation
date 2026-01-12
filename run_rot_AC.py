# -*- coding: utf-8 -*-
"""
run_rot_AC.py (assembly-misalignment sensitivity + coupled rotation mode)

目的：
  (A) 組み立て誤差（独立オフセット）として、1つの部材だけ azimuth 誤差を掃引
  (B) A-plate と Analyzer(POL_out) を「一緒に」回すモード（coupled）で掃引

モニター：
  - CR00(R/G/B/W)
  - CR(theta=mon_theta, phi in mon_phis; W)

REF（基準）は progress CSV の指定行(--row)。
--ref_A_scale / --ref_ReC_nm で REF(A_scale, ReC_nm)を手動指定可能。

固定条件は以下で設定可能：
  --pol_in 0.0
  --pol_out 0.0
  --relA 0.25
  --relLC 0.25

モード：
  --rot_mode misalign   : 従来の「独立オフセット」モデル（scan_targetで対象を指定）
  --rot_mode A_polout   : A と pol_out を同じ delta で一緒に回す（LCは固定）
  --rot_mode LC_A_polout: LC, A, pol_out を同じ delta で一緒に回す（必要なら）

Scan:
  --delta_min / --delta_max / --delta_step

Optional fixed offsets (deg):
  --d_polout_fixed / --d_LC_fixed / --d_A_fixed

Outputs (outdir):
  - scan_misalign.csv
  - ref_iso.png, (optional) iso_*.png
  - plot_delta_vs_CR00_W.png
  - ref_stack.json, ref_CR00.json, ref_CR_angles.json
"""
import argparse
import math
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import ips_compensation_run_signedC as ips

MON_THETA_DEFAULT = 30.0


def build_LC_from_azimuth(lc_azimuth_deg: float):
    """LC element with axis azimuth specified in lab frame (deg)."""
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
    """A-plate element with axis azimuth specified in lab frame (deg)."""
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
    """C-plate (optical axis = z). Sign is encoded by ne via dn sign."""
    ReC = float(ReC_nm_signed)
    if ReC == 0:
        return None
    sgn = 1.0 if ReC >= 0 else -1.0
    dnC = float(ips.dn_C)

    # d[um] = Re[nm] / (1000*dn)
    dC_um = abs(ReC) / (dnC * 1000.0)

    return {
        "type": "C",
        "axis": [0, 0, 1],
        "d": float(dC_um) * 1e-6,  # um -> m
        "no": ips.NO_BASE,
        "ne": ips.ne_from_dn(ips.NO_BASE, dnC * sgn),
    }


def Tleak_single_lambda(theta_deg: float, phi_deg: float, stack, c1, c2, wl_key: str) -> float:
    """Leakage transmittance at a single wavelength key ('R','G','B') using your internal model."""
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
        E = E - np.dot(E, k) * k  # enforce transverse
    T = abs(np.vdot(o2, E)) ** 2
    return float(T.real)


def CR00_per_wavelength(stack, c1, c2):
    """CR00 for R/G/B (single-lambda) and W (polychromatic) at theta=0,phi=0."""
    out = {}
    for wl in ("R", "G", "B"):
        T = Tleak_single_lambda(0.0, 0.0, stack, c1, c2, wl_key=wl)
        out[wl] = ips.CR_from_Tleak(T)
    Tw = ips.Tleak_stack_scalar(0.0, 0.0, stack, c1=c1, c2=c2)
    out["W"] = ips.CR_from_Tleak(Tw)
    return out


def CR_at_angles_W(stack, c1, c2, theta_deg: float, phis_deg):
    """CR at given theta and multiple phis, for W (polychromatic)."""
    res = {}
    for ph in phis_deg:
        Tw = ips.Tleak_stack_scalar(theta_deg, float(ph), stack, c1=c1, c2=c2)
        res[ph] = ips.CR_from_Tleak(Tw)
    return res


def save_iso(stack, title: str, out_png: Path, c1, c2, theta_max=60.0, dtheta=5.0, dphi=5.0):
    """Save iso-contrast plot for W."""
    thetas, phis, CR = ips.compute_CR_grid(
        stack, c1, c2, theta_max=theta_max, dtheta=dtheta, dphi=dphi
    )
    ips.plot_isocontrast_polar(
        thetas,
        phis,
        CR,
        title=title,
        out_path=str(out_png),
        theta_ticks=[0, 10, 20, 30, 40, 50, 60],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--progress_csv", type=str, required=True)
    ap.add_argument("--row", type=int, default=-1)
    ap.add_argument("--outdir", type=str, default="rot_scan")
    ap.add_argument("--tag", type=str, default="LC_AC_abs")

    # ---- fixed settings (as you requested) ----
    ap.add_argument("--lc_basis", type=str, choices=["abs", "tran"], default="abs")
    ap.add_argument("--pol_in", type=float, default=0.0)
    ap.add_argument("--pol_out", type=float, default=0.0, help="REF pol_out (deg). crossed Nicolなら0")
    ap.add_argument("--relLC", type=float, default=0.25, help="LC azimuth offset from pol_in (deg) at REF")
    ap.add_argument("--relA", type=float, default=0.25, help="A azimuth offset from pol_out (deg) at REF")

    # REF overrides
    ap.add_argument("--ref_A_scale", type=float, default=None, help="override REF A_scale")
    ap.add_argument("--ref_ReC_nm", type=float, default=None, help="override REF ReC_nm")

    # rotation model
    ap.add_argument("--rot_mode", type=str, default="misalign",
                    choices=["misalign", "A_polout", "LC_A_polout"],
                    help=(
                        "misalign: scan one target as independent assembly error (scan_target)\n"
                        "A_polout: rotate A and pol_out together by delta (LC fixed)\n"
                        "LC_A_polout: rotate LC, A, pol_out together by delta"
                    ))

    # assembly misalignment scan target (used in rot_mode=misalign)
    ap.add_argument("--scan_target", type=str, default="polout", choices=["polout", "LC", "A"])

    # scan range
    ap.add_argument("--delta_min", type=float, default=-3.0)
    ap.add_argument("--delta_max", type=float, default=3.0)
    ap.add_argument("--delta_step", type=float, default=0.5)

    # optional fixed offsets (deg)
    ap.add_argument("--d_polout_fixed", type=float, default=0.0)
    ap.add_argument("--d_LC_fixed", type=float, default=0.0)
    ap.add_argument("--d_A_fixed", type=float, default=0.0)

    # monitor angles
    ap.add_argument("--mon_theta", type=float, default=MON_THETA_DEFAULT)
    ap.add_argument("--mon_phis", type=str, default="45,135,-45,-135")

    # ISO
    ap.add_argument("--iso_every", type=int, default=0)
    ap.add_argument("--theta_max", type=float, default=60.0)
    ap.add_argument("--dtheta", type=float, default=5.0)
    ap.add_argument("--dphi", type=float, default=5.0)

    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    mon_phis = [float(x.strip()) for x in args.mon_phis.split(",") if x.strip()]

    df = pd.read_csv(args.progress_csv)
    r = df.iloc[int(args.row)]

    # from progress CSV (must exist in your optimization output)
    A_base = float(r.get("A_base_deg", 0.0))
    A_kind = str(r.get("A_kind", "upper"))

    A_scale_csv = float(r["A_scale"])
    ReC_nm_csv = float(r["ReC_nm"])
    A_scale_ref = float(args.ref_A_scale) if args.ref_A_scale is not None else A_scale_csv
    ReC_nm_ref = float(args.ref_ReC_nm) if args.ref_ReC_nm is not None else ReC_nm_csv

    pol_out_ref = float(args.pol_out)

    # REF absolute azimuths (deg)
    lc_base = 0.0 if args.lc_basis == "abs" else 90.0
    LC_az_ref = lc_base + float(args.pol_in) + float(args.relLC)
    A_az_ref = float(A_base) + pol_out_ref + float(args.relA)

    # REF polarizers
    c1_ref, c2_ref = ips.pol_axes(float(args.pol_in), pol_out_ref)

    # REF stack
    LC_ref = build_LC_from_azimuth(LC_az_ref)
    A_ref = build_A_from_azimuth(A_scale_ref, A_base, A_az_ref, A_kind)
    C_ref = build_C(ReC_nm_ref)
    ref_stack = [LC_ref, A_ref] + ([] if C_ref is None else [C_ref])

    (outdir / "ref_stack.json").write_text(json.dumps(ref_stack, indent=2), encoding="utf-8")
    ref_cr00 = CR00_per_wavelength(ref_stack, c1_ref, c2_ref)
    ref_crang = CR_at_angles_W(ref_stack, c1_ref, c2_ref, float(args.mon_theta), mon_phis)
    (outdir / "ref_CR00.json").write_text(json.dumps(ref_cr00, indent=2), encoding="utf-8")
    (outdir / "ref_CR_angles.json").write_text(json.dumps(ref_crang, indent=2), encoding="utf-8")

    save_iso(ref_stack, f"ISO-CR REF ({args.tag})", outdir / "ref_iso.png", c1_ref, c2_ref,
             theta_max=args.theta_max, dtheta=args.dtheta, dphi=args.dphi)

    deltas = np.arange(args.delta_min, args.delta_max + 1e-12, args.delta_step)

    rows = []
    for idx, d in enumerate(deltas):
        # start from fixed offsets
        d_polout = float(args.d_polout_fixed)
        d_LC = float(args.d_LC_fixed)
        d_A = float(args.d_A_fixed)

        # apply scan depending on rot_mode
        if args.rot_mode == "misalign":
            if args.scan_target == "polout":
                d_polout += float(d)
            elif args.scan_target == "LC":
                d_LC += float(d)
            elif args.scan_target == "A":
                d_A += float(d)

        elif args.rot_mode == "A_polout":
            # rotate A and analyzer together by delta; LC fixed
            d_polout += float(d)
            d_A += float(d)

        elif args.rot_mode == "LC_A_polout":
            # rotate LC, A, analyzer together by delta
            d_polout += float(d)
            d_A += float(d)
            d_LC += float(d)
        else:
            raise ValueError("unknown rot_mode")

        # effective analyzer angle
        pol_out_eff = pol_out_ref + d_polout
        c1, c2 = ips.pol_axes(float(args.pol_in), pol_out_eff)

        # effective azimuths
        LC_az = LC_az_ref + d_LC
        A_az = A_az_ref + d_A

        LC = build_LC_from_azimuth(LC_az)
        A = build_A_from_azimuth(A_scale_ref, A_base, A_az, A_kind)
        C = build_C(ReC_nm_ref)
        stack = [LC, A] + ([] if C is None else [C])

        cr00 = CR00_per_wavelength(stack, c1, c2)
        crang = CR_at_angles_W(stack, c1, c2, float(args.mon_theta), mon_phis)

        row = {
            "delta_deg": float(d),
            "rot_mode": str(args.rot_mode),
            "scan_target": str(args.scan_target),
            "d_polout_deg": float(d_polout),
            "d_LC_deg": float(d_LC),
            "d_A_deg": float(d_A),
            "pol_in_deg": float(args.pol_in),
            "pol_out_ref_deg": float(pol_out_ref),

            "A_scale_ref": float(A_scale_ref),
            "ReC_nm_ref": float(ReC_nm_ref),
            "A_base_deg": float(A_base),
            "A_kind": str(A_kind),

            "CR00_R": float(cr00["R"]),
            "CR00_G": float(cr00["G"]),
            "CR00_B": float(cr00["B"]),
            "CR00_W": float(cr00["W"]),
            "CR00_W_rel_to_ref_dB": 10.0 * math.log10(float(cr00["W"]) / float(ref_cr00["W"])),
        }
        for ph in mon_phis:
            key = f"CR_W_t{int(args.mon_theta):d}_p{int(ph):+d}"
            row[key] = float(crang[ph])
            row[key + "_rel_to_ref_dB"] = 10.0 * math.log10(float(crang[ph]) / float(ref_crang[ph]))
        rows.append(row)

        if int(args.iso_every) > 0 and (idx % int(args.iso_every) == 0):
            save_iso(
                stack,
                f"ISO-CR {args.tag} mode={args.rot_mode} delta={d:+.2f}deg",
                outdir / f"iso_{args.rot_mode}_{d:+.2f}deg.png",
                c1,
                c2,
                theta_max=args.theta_max,
                dtheta=args.dtheta,
                dphi=args.dphi,
            )

    dfo = pd.DataFrame(rows)
    dfo.to_csv(outdir / "scan_misalign.csv", index=False)

    # quick plot
    fig = plt.figure(figsize=(5.6, 3.6), dpi=200)
    ax = fig.add_subplot(111)
    ax.plot(dfo["delta_deg"].values, dfo["CR00_W"].values, marker="o")
    ax.set_xlabel("delta (deg)")
    ax.set_ylabel("CR00 (W)")
    ax.grid(True, ls=":")
    ax.set_title(f"CR00(W) vs delta ({args.tag}, mode={args.rot_mode})")
    fig.tight_layout()
    fig.savefig(outdir / "plot_delta_vs_CR00_W.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
