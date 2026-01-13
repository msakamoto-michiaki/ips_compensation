# run_rot_AC.py 仕様書（組み立て回転誤差・連動回転モード感度解析）

対象ファイル: `run_rot_AC.py` fileciteturn5file0  
生成日: 2026-01-13

---

## 1. 概要

`run_rot_AC.py` は、最適化結果（`progress_*.csv` の任意行）を**基準（REF）**として読み込み、  
偏光子/検光子/LC/A板の**方位角（azimuth）回転誤差**を掃引したときの

- 正面コントラスト `CR00`（R/G/B 単色 + 白色W）
- 斜め視角のコントラスト `CR(theta=mon_theta, phi in mon_phis; W)`
- ISO-CR（必要に応じて）

の変化を出力する **感度解析スクリプト**です。

本スクリプトは 3つの回転モデルを持ちます：

- **misalign**: 1要素だけを独立にオフセット（組み立て誤差の想定）
- **A_polout**: A板とAnalyzer（pol_out）を同じΔで連動回転（カップリング）
- **LC_A_polout**: LC・A・Analyzerを同じΔで連動回転（必要時）

---

## 2. 入出力と実行方法

### 2.1 入力（主なコマンドライン引数）

必須:
- `--progress_csv` : 参照する progress CSV（例: `out_opt/progress_LC_AC_abs.csv`）

REF行指定:
- `--row` : progress CSVの行番号（`-1`で最終行）

出力:
- `--outdir` : 出力ディレクトリ（デフォルト `rot_scan`）
- `--tag` : 表示用タグ（デフォルト `LC_AC_abs`）

固定条件（REFの定義）:
- `--lc_basis` : `abs` / `tran`（LC軸の基準方位。abs=0°, tran=90°）
- `--pol_in`, `--pol_out` : 入射側/出射側偏光子の回転（deg）
- `--relLC` : `pol_in` に対するLC azimuthオフセット（deg）
- `--relA` : `pol_out` に対するA azimuthオフセット（deg）

REF上書き（progress CSVの値を使わず手で指定）:
- `--ref_A_scale`
- `--ref_ReC_nm`

回転モデル:
- `--rot_mode` : `misalign` / `A_polout` / `LC_A_polout`
- `--scan_target` : `polout` / `LC` / `A`（`rot_mode=misalign` のとき有効）

掃引レンジ:
- `--delta_min`, `--delta_max`, `--delta_step` : Δ[deg] の範囲と刻み

固定オフセット（掃引に加算するオフセット）:
- `--d_polout_fixed`, `--d_LC_fixed`, `--d_A_fixed`

モニター角:
- `--mon_theta` : 斜めモニターのθ（デフォルト 30°）
- `--mon_phis` : 斜めモニターのφリスト（例: `"45,135,-45,-135"`）

ISO出力:
- `--iso_every` : `>0` で、Δの N点ごとに ISO-CR を保存
- `--theta_max`, `--dtheta`, `--dphi` : ISOの角度範囲と解像度

### 2.2 実行例

```bash
python run_rot_AC.py \
  --progress_csv out_opt/progress_LC_AC_abs.csv \
  --row -1 \
  --outdir rot_scan \
  --rot_mode misalign --scan_target polout \
  --delta_min -3 --delta_max 3 --delta_step 0.5 \
  --iso_every 2
```

### 2.3 出力（outdir配下）

- `scan_misalign.csv`  
  Δ掃引の結果（CR00や斜めCR、REF比[dB]）を1行ずつ保存。
- `ref_stack.json`  
  REF行から構築したスタック（LC/A/C）定義。
- `ref_CR00.json`  
  REFの `CR00`（R/G/B/W）。
- `ref_CR_angles.json`  
  REFの `CR(theta=mon_theta, phi in mon_phis; W)`。
- `ref_iso.png`  
  REFの ISO-CR（白色W）。
- `plot_delta_vs_CR00_W.png`  
  Δに対する `CR00_W` の簡易プロット。
- `iso_<rot_mode>_<delta>.png`（`--iso_every` 指定時）  
  ΔのスナップショットISO-CR。

---

## 3. main が利用する主モジュール

- `ips_compensation_run_signedC`（`import ... as ips`）  
  物理モデル（eq3a/eq3b、retarder、Tleak、CR変換、ISO計算）を提供。

---

## 4. 主な関数（役割）

### 4.1 スタック生成
- `build_LC_from_azimuth(lc_azimuth_deg)`
  - 指定 azimuth（lab座標）でLC層要素(dict)を生成。
- `build_A_from_azimuth(A_scale, A_base_deg, A_azimuth_deg, A_kind)`
  - A板の `Re_each = RE_A_EACH_BASE_NM * A_scale` から厚み `dA=Re/dn` を決め、指定 azimuthで要素を生成。
- `build_C(ReC_nm_signed)`
  - `ReC[nm]` から厚み `dC_um = |ReC|/(1000*dnC)` を決定。符号は `ne` 側の dn符号に埋め込む（+C/-Cを切替）。

### 4.2 光学計算
- `Tleak_single_lambda(theta, phi, stack, c1, c2, wl_key)`
  - 単一波長（R/G/B）で、`eq3a_Gamma_A` / `eq3b_Gamma_C` と `retarder_matrix` を用いて電場を伝搬し、Analyzer側 `o2` への射影でリーク `T` を計算。
- `CR00_per_wavelength(stack, c1, c2)`
  - `theta=phi=0` の `CR00` を R/G/B（単色）と W（白色: `Tleak_stack_scalar`）で返す。
- `CR_at_angles_W(stack, c1, c2, theta, phis)`
  - 指定θで複数φの白色CRを計算。

### 4.3 可視化
- `save_iso(stack, title, out_png, c1, c2, ...)`
  - `ips.compute_CR_grid` + `ips.plot_isocontrast_polar` によりISO-CR図を保存。

---

## 5. 注意点（実務上の落とし穴）

- `--progress_csv` の行に `A_base_deg`, `A_kind` 列が無い場合、A方位の再構成が期待とずれる可能性があります。
- `--pol_out` は「REFのAnalyzer角度」を意味します。`rot_mode` によって実効pol_outが変わる点に注意してください。
- ISO出力は角度グリッド計算を含むため重いです（`--iso_every` と `dtheta/dphi` で調整推奨）。

