# run_Re_LC.py 仕様書（LCリターデーション摂動感度解析）

対象ファイル: `run_Re_LC.py` fileciteturn5file1  
生成日: 2026-01-13

---

## 1. 概要

`run_Re_LC.py` は、最適化結果（`progress_*.csv` の任意行）を基準として読み込み、  
LCの複屈折 `dn_LC` をスケールすることで **LCリターデーション Re_LC を摂動**させたときの性能（CR）の感度を評価します。

評価指標:
- `CR00`（R/G/B 単色 + 白色W）
- `CR(theta=30°, phi=45,135,-45,-135; W)`
- ISO-CR（`--iso_every` 指定時に各スケール点で出力）

---

## 2. 入出力と実行方法

### 2.1 入力（主な引数）

必須:
- `--progress_csv` : 参照する progress CSV

REF行指定:
- `--row` : 行番号（`-1`で最終）

出力:
- `--outdir` : 出力ディレクトリ（デフォルト `sens_ReLC`）
- `--tag` : 表示用タグ

固定条件:
- `--lc_basis` : `abs` / `tran`
- `--pol_in`, `--pol_out`, `--relA`, `--relLC`

ISO設定:
- `--theta_max`, `--dtheta`, `--dphi`

LC摂動スキャン:
- `--scale_min`, `--scale_max`, `--scale_step`
  - `dn_LC_eff = dn_LC * scale`
  - `ReLC_nm = (dn_LC_eff * d_LC) * 1e9` を出力列に記録

ISO出力間隔:
- `--iso_every` : `>0` で、スキャン点 NごとにISOを保存（デフォルト1=全点）

### 2.2 実行例

```bash
python run_Re_LC.py \
  --progress_csv out_opt/progress_LC_AC_abs.csv \
  --outdir sens_ReLC \
  --lc_basis abs \
  --scale_min 0.85 --scale_max 1.15 --scale_step 0.05 \
  --iso_every 1
```

### 2.3 出力（outdir配下）

- `ref_stack.json`  
  REFのスタック定義（LC/A/C）。
- `ref_CR00.json`  
  REFの `CR00`（R/G/B/W）。
- `ref_CR_theta30.json`  
  REFの斜めモニターCR（W）。
- `ref_iso.png`  
  REFのISO-CR（W）。
- `scan_ReLC.csv`  
  `scale` ごとの `ReLC_nm`、CR00、斜めCR、REF比[dB] を記録。
- `plot_ReLC_vs_CR00_W.png`  
  `ReLC_nm` に対する `CR00_W` プロット。
- `iso_ReLC_<ReLC_nm>nm.png`（`--iso_every` 指定時）  
  各スキャン点のISO-CR（W）。

---

## 3. main が利用する主モジュール

- `ips_compensation_run_signedC`（`ips`）
  - `eq3a_Gamma_A`, `eq3b_Gamma_C`, `retarder_matrix`, `Tleak_stack_scalar`, `compute_CR_grid` 等。

---

## 4. 主な関数（役割）

### 4.1 スタック生成
- `build_LC_scaled(lc_basis, pol_in, relLC, dn_scale)`
  - LC軸方位（abs/tran + pol_in + relLC）を決め、`dn_LC` を `dn_scale` 倍して `ne` を生成。
- `build_A(A_scale, A_base_deg, pol_out, relA, A_kind)`
  - progress CSVのAパラメータ（A_scale, A_base_deg, A_kind）からA板要素を生成。
- `build_C(ReC_nm_signed)`
  - progress CSVの `ReC_nm` からC板要素を生成（符号で+/-C切替）。

### 4.2 光学計算
- `Tleak_single_lambda(...)`
  - R/G/B単色のリークを計算（内部は eq3a/eq3b と retarder による電場伝搬）。
- `CR00_per_wavelength(...)`
  - 正面CR00をR/G/B（単色）とW（白色）で返す。
- `CR_at_angles_W(...)`
  - θ=30°, φ=±45°,±135° の白色CRを返す。
- `save_iso(...)`
  - 白色ISO-CR図を保存。

---

## 5. 注意点

- ここでの摂動は「LCの厚み `d_LC` は固定、`dn_LC` をスケール」というモデルです。  
  製造誤差が厚み起因の場合は解釈が変わります（ReLCは dn×d の積なので）。
- `--iso_every 1` で全点ISOを出すと重いので、まず粗く走らせてから絞る運用が安全です。

