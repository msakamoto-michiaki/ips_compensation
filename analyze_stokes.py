# -*- coding: utf-8 -*-
"""
Analyze Stokes parameters from progress CSV and relate them to analyzer axis at off-axis direction.

Arg-driven version of the provided snippet.

Example:
  python analyze_stokes.py --fn out_opt --csv progress_LC_AC_abs.csv --row -1 --theta 30 --phi 45 --basis pol_in --stage el#2_C
"""
import argparse, math
from pathlib import Path
import numpy as np
import pandas as pd

import ips_compensation_run_signedC as ips
import ips_stokes_trace as st

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fn", type=str, default="out_opt", help="output directory that holds the CSV")
    ap.add_argument("--csv", type=str, default="progress_LC_AC_abs.csv", help="CSV filename under --fn (or full path)")
    ap.add_argument("--row", type=int, default=-1, help="row index (default -1 = last)")
    ap.add_argument("--theta", type=float, default=30.0)
    ap.add_argument("--phi", type=float, default=45.0)
    ap.add_argument("--basis", type=str, default="pol_in", help="Stokes transverse basis")
    ap.add_argument("--stage", type=str, default="el#2_C", help='stage key, e.g. "el#1_A", "el#2_C"')
    ap.add_argument("--pol_in", type=float, default=0.0, help="pol_in rotation (deg) for pol_axes")
    ap.add_argument("--pol_out", type=float, default=0.0, help="pol_out rotation (deg) for pol_axes")
    args = ap.parse_args()




    fn = Path(args.fn)
    csv_path = Path(args.csv)
    if not csv_path.exists():
        csv_path = fn / args.csv

    df = pd.read_csv(csv_path)
    r = df.iloc[int(args.row)]

    c1, c2 = ips.pol_axes(float(args.pol_in), float(args.pol_out))

    k = ips.k_hat(float(args.theta), float(args.phi))

    u, v = st.transverse_basis(k, basis=args.basis, c1=c1, c2=c2)

    o2 = ips.o_axis_Otype(k, c2)

    au = float(np.dot(o2, u))
    av = float(np.dot(o2, v))
    alpha_deg = math.degrees(math.atan2(av, au))

    stage = args.stage
    s1_col = f"s1_{stage}"
    s2_col = f"s2_{stage}"
    s3_col = f"s3_{stage}"
    if s1_col not in r.index:
        raise KeyError(f"Column '{s1_col}' not found. Available columns include: {list(df.columns)[:30]} ...")

    s1 = float(r[s1_col]); s2 = float(r[s2_col]); s3 = float(r[s3_col])

    psi_deg = 0.5 * math.degrees(math.atan2(s2, s1))

    delta_deg = (alpha_deg - psi_deg) % 180.0
    ortho_err_deg = abs(delta_deg - 90.0)

    alpha = math.radians(alpha_deg)
    I = 0.5 * (1 + s1 * math.cos(2 * alpha) + s2 * math.sin(2 * alpha))
    Tleak_pred = 0.5 * I
    CR_pred = ips.CR_from_Tleak(Tleak_pred)

    psi = math.radians(psi_deg)
    e_pol = math.cos(psi) * u + math.sin(psi) * v
    e_an  = math.cos(alpha) * u + math.sin(alpha) * v

    dot_pol_an = float(np.dot(e_pol, e_an))
    dot_an_o2  = float(np.dot(e_an, o2))
    dot_pol_o2 = float(np.dot(e_pol, o2))

    print("\n" + "=" * 80)
    print("Off-axis analyzer axis vs. output (near-linear) polarization axis (from progress CSV)")
    print("-" * 80)
    print(f"CSV      : {csv_path}")
    print(f"row      : {args.row}   (update_idx={int(r.get('update_idx', -1)) if 'update_idx' in r.index else 'N/A'})")
    print(f"angle    : theta={float(args.theta):.2f} deg, phi={float(args.phi):.2f} deg")
    print(f"basis    : {args.basis}  (transverse basis u,v)")
    print(f"stage    : {stage}  (reading columns: {s1_col}, {s2_col}, {s3_col})")
    print(f"pol_in/out: {float(args.pol_in):.3f} / {float(args.pol_out):.3f} deg")
    print("-" * 80)

    print("Stokes at stage (normalized):")
    print(f"  s1,s2,s3 = {s1:.12f}, {s2:.12f}, {s3:.12f}")
    print("Interpretation:")
    print("  s3 ~ 0  => close to linear polarization (small ellipticity).")
    print("  (s1,s2) => determines linear-azimuth angle psi in the SAME (u,v) basis.\n")

    print("Axes (angles in the SAME u-v transverse plane):")
    print(f"  analyzer transmission azimuth alpha = {alpha_deg:.12f} deg")
    print(f"  output polarization azimuth   psi   = {psi_deg:.12f} deg  (psi=0.5*atan2(s2,s1))")
    print(f"  delta = (alpha - psi) mod 180       = {delta_deg:.12f} deg")
    print(f"  ideal delta ≈ 90 deg (orthogonal).  orthogonality error = {ortho_err_deg:.12f} deg\n")

    print("Axis vectors (in 3D; both are transverse to k):")
    print(f"  e_pol (from psi): {e_pol}")
    print(f"  e_an  (from alpha): {e_an}")
    print("Dot products (quick sanity):")
    print(f"  e_pol · e_an   = {dot_pol_an:.12f}  (≈0 if orthogonal)")
    print(f"  e_an  · o2     = {dot_an_o2:.12f}  (≈1 if e_an matches analyzer axis o2)")
    print(f"  e_pol · o2     = {dot_pol_o2:.12f}\n")

    print("Leakage consistency check:")
    print(f"  Tleak_pred = {Tleak_pred:.15f}")
    print(f"  CR_pred    = {CR_pred}")
    if "best_CR" in r.index:
        print(f"  best_CR(from CSV) = {float(r['best_CR'])}")
    print("=" * 80)

if __name__ == "__main__":
    main()
