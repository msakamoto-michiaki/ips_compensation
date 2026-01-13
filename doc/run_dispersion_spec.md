# run_dispersion.py 仕様書（波長掃引・分散評価）

対象ファイル: `run_dispersion.py` fileciteturn5file3  
生成日: 2026-01-13

---

## 1. 概要

`run_dispersion.py` は、最適化結果（`progress_*.csv` の任意行）を基準として固定スタック（LC/A/C）を作り、  
波長を掃引して **単色（monochromatic）**での

- `CR00_mono(λ)`（正面）
- `CR_mono(θ,φ; λ)`（指定角度）
- ISO-CR polar map（指定間隔）

を評価するスクリプトです。

> 注意：このスクリプトの “W” は **白色加重平均ではありません**。  
> `ips` モジュールの `Tleak_stack_scalar` が持つ「白色加重W」とは別物で、ここでは単色TleakからCRを計算します（列名に `_mono` が付く）。

---

## 2. 入出力と実行方法

### 2.1 入力（主な引数）

必須:
- `--progress_csv` : 参照する progress CSV
- `--row` : 行番号（`-1`で最終）

出力:
- `--outdir` : 出力ディレクトリ（デフォルト `dispersion`）
- `--tag` : 表示用タグ

固定条件（他の感度スクリプトと整合）:
- `--lc_basis` : `abs` / `tran`
- `--pol_in`, `--pol_out`, `--relLC`, `--relA`

REF上書き:
- `--ref_A_scale`, `--ref_ReC_nm`

波長掃引:
- `--wl_min_nm`, `--wl_max_nm`, `--wl_step_nm`
- `--wl_list_nm` : `"450,500,546,610,650"` のように明示リスト指定も可能

分散モデル:
- `--dispersion` : `flat` / `matched` / `mismatched` / `current`
  - `flat`      : dnスケール = 1（分散なし、Γの 1/λ だけ効く）
  - `matched`   : `ips.DN_SCALE_MATCHED`（B/G/R点のスケールを線形補間）
  - `mismatched`: `ips.DN_SCALE_MISMATCHED`
  - `current`   : `ips.DN_SCALE`（ips側で現在有効な設定）

モニター角:
- `--mon_theta` : 例 30°
- `--mon_phis`  : 例 `"45,135,-45,-135"`

ISO出力:
- `--iso_every` : `>0` で、波長N点ごとに ISOを保存
- `--theta_max`, `--dtheta`, `--dphi` : ISO解像度

### 2.2 実行例

```bash
python run_dispersion.py \
  --progress_csv out_opt/progress_LC_AC_abs.csv \
  --row -1 \
  --outdir dispersion \
  --dispersion matched \
  --wl_min_nm 420 --wl_max_nm 680 --wl_step_nm 10 \
  --iso_every 5
```

### 2.3 出力（outdir配下）

- `ref_stack.json`  
  REFから構成した固定スタック（LC/A/C）の定義。
- `dispersion.csv`  
  波長ごとの単色CR（`CR00_mono` と指定角度 `CR_mono_t.._p..`）を記録。
- `plot_lambda_vs_CR00_mono.png`  
  `CR00_mono(λ)` のプロット。
- `iso_mono_<lambda>nm.png`（`--iso_every` 指定時）  
  指定波長での単色ISO-CR図。
- `summary.json`  
  実行条件（dispersionモード、波長リスト、REFパラメータ等）のメタ情報。

---

## 3. main が利用する主モジュール

- `ips_compensation_run_signedC`（`ips`）
  - `eq3a_Gamma_A`, `eq3b_Gamma_C`, `retarder_matrix`, `plot_isocontrast_polar` など。

---

## 4. 主な関数（役割）

### 4.1 スタック生成（他スクリプトと同系）
- `build_LC_from_azimuth`, `build_A_from_azimuth`, `build_C`
  - progress行から得たA_scale/ReCと、固定角（pol_in/out, relLC/A）からスタックを構築。

### 4.2 分散・波長補間
- `_dn_scale_table(mode)`
  - 分散スケールテーブルを選択（flat/matched/mismatched/current）。
- `_interp_scale(lam_nm, scale_dict_BGR)`
  - B/G/R点（450/546/610nm）で定義されたスケールを線形補間。
- `ne_no_for_lambda(el, lam_nm, disp_mode)`
  - 要素 `el` の `dnG=ne-no` を基準に、波長に応じたスケールを掛けて `(no,ne)` を返す。

### 4.3 単色Tleak/CR
- `Tleak_stack_mono(theta, phi, stack, c1, c2, lam_nm, disp_mode)`
  - 指定波長で `eq3a/eq3b` と `retarder_matrix` で伝搬し、Analyzer軸射影でリーク `T` を計算。
- `CR00_mono(stack, c1, c2, lam_nm, disp_mode)`
- `CR_mono(theta, phi, stack, c1, c2, lam_nm, disp_mode)`
  - `CR_from_Tleak` でCRへ変換。

### 4.4 単色ISO
- `compute_CR_grid_mono(...)`
- `save_iso_mono(...)`
  - 単色で角度グリッドを回してISO-CR図を保存。

---

## 5. 注意点

- `dispersion.csv` の値は単色であり、白色加重（W）の「色混合」を評価したい場合は、元の `ips` の白色計算（`Tleak_stack_scalar`）を使う系と併用してください。
- `--iso_every` を小さくするとISO出力が多くなり計算時間が増えます。まずは粗く試してから絞るのが安全です。

