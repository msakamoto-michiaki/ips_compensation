# ips_compensation4_stacks_envelope_AstepIso_v2.py 仕様書（A-envelope＋A-step ISO＋ReA–ReC 2Dマップ）

対象ファイル: `ips_compensation4_stacks_envelope_AstepIso_v2.py` fileciteturn7file0  
生成日: 2026-01-13

---

## 1. 概要

本スクリプトは、論文の式(2),(3),(5)に基づくIPS液晶セルの光学補償シミュレーション（Jones/ベクトル伝搬）を用いて、

- スタック（例: `LC / A / C`）に対する **ターゲット視角**（デフォルト: `theta=30°, phi=45°`）でのコントラスト比 `CR(theta,phi)` を最大化する探索
- 探索の進捗（best更新）ログ出力と、ログの間引きスナップショット ISO-CR 出力
- **A膜厚ステップごと**に ReC を最適化した包絡線 `A_envelope_<tag>.csv` と、その最適点で **必ず** ISO-CR を出力する `iso_Astep_<tag>/...`
- 追加仕様として、**ReA–ReC の2次元格子**に対する `CR(theta,phi)` を計算し、等高線プロット（PNG）とCSV（ロング/格子）を出力する

を一括で実行する「探索＋可視化＋データ出力」ドライバです。

---

## 2. 入力と実行方法

### 2.1 代表的な実行例（LC_AC_abs）

```bash
python ips_compensation4_stacks_envelope_AstepIso_v2.py \
  --outdir out_opt \
  --stack LC_AC_abs \
  --Amin 0.60 --Amax 2.40 --Ad 0.05 \
  --ReCmin -280 --ReCmax 280 --ReCd 20 \
  --track_progress --progress_plot \
  --progress_iso_stride 5 \
  --export_envelope \
  --export_Astep_iso \
  --export_ReA_ReC_map
```

### 2.2 コマンドライン引数（要点）

#### 出力先
- `--outdir DIR` : 出力ディレクトリ（既定 `out_opt`）

#### ターゲット視角（最適化対象）
- `--theta` : 極角θ（deg, 既定 30）
- `--phi`   : 方位角φ（deg, 既定 45）

#### 探索レンジ（A/ C）
- `--Amin --Amax --Ad` : `A_scale` の範囲と刻み
- `--ReCmin --ReCmax --ReCd` : `ReC_nm` の範囲と刻み（nm）

#### スタック種別
- `--stack` : `LC_AC_abs`, `LC_AC_tran`, `CA_LC_tran`, `CA_LC_AC_abs`, `CA_LC_AC_tran`, `all`

#### progress（best更新ログ）
- `--track_progress` : best更新時のみ progress を記録
- `--progress_stride N` : best更新ログの間引き（N更新に1回記録）
- `--progress_plot` : `progress_<tag>_CR.png` を出力
- `--progress_iso_stride N` : progressログN行ごとに ISO-CR を保存（`iso_progress_<tag>/`）

#### A-envelope（AステップごとのReC最適化）
- `--export_envelope` : `A_envelope_<tag>.csv` と包絡線プロットを出力

#### A-step ISO（Aステップ最適点のISOを必ず出力）
- `--export_Astep_iso` : `A_envelope_<tag>.csv` の各行（Aステップ最適点）で ISO-CR を保存（best更新に依存しない）
- `--Astep_iso_stride N` : AステップISOの間引き（既定1）

#### ReA–ReC 2Dマップ（追加仕様）
- `--export_ReA_ReC_map` : `CR(theta,phi)` の ReA–ReC 2D等高線（PNG）とCSVを出力
- `--map_linear_cr` : 等高線を `CR`（線形）で描く（未指定時は `log10(CR)`）

#### ISO計算の解像度（全系共通の調整に使用）
- `--theta_max`, `--dtheta`, `--dphi` : ISO-CRの角度範囲と刻み

---

## 3. 出力ファイル（outdir配下）

以下は `--stack LC_AC_abs` を例に、生成される代表成果物です（`<tag>=LC_AC_abs`）。

### 3.1 最終最適解（best）
- `best_stack_<tag>.json` : ターゲット視角でCR最大のスタック定義（再現用）
- `iso_<tag>_best.png` : bestスタックのISO-CR極座標図

### 3.2 Stokesトレース（bestスタック）
- `stokes_white_<tag>.json/.csv` : 白色（波長加重平均）Stokesトレース
- `stokes_per_wavelength_<tag>.json/.csv` : 波長別Stokesトレース

### 3.3 progress（best更新ログ）
- `progress_<tag>.csv/.json` : best更新の履歴（更新時のみ）
- `progress_<tag>_CR.png` : best_CR推移プロット（`--progress_plot`）
- `iso_progress_<tag>/index.csv` : progress→ISOの対応表
- `iso_progress_<tag>/iso_<tag>_uXXX.png` : progressスナップショットISO（`--progress_iso_stride`）

### 3.4 A-envelope（Aステップ最適点）
- `A_envelope_<tag>.csv` : A_scaleごとの最適点（best_ReC_nm, best_CR等）
- `A_envelope_<tag>_CR.png` : ReAに対するmax CR（ReC最適化済）のプロット
- `A_envelope_<tag>_rel_to_best.png` : 全体bestで正規化した相対プロット
- `A_envelope_<tag>_best.json` : envelope観点での最良点まとめ

### 3.5 A-step ISO（Aステップ最適点のISO群）
- `iso_Astep_<tag>/index.csv` : Aステップ最適点→ISOの対応表
- `iso_Astep_<tag>/iso_<tag>_A###.png` : Aステップ最適点のISO-CR（best更新に依存しない）

### 3.6 ReA–ReC 2Dマップ（追加仕様）
- `ReA_ReC_map_<tag>.csv` : ロング形式（行=1格子点、列に ReA,ReC,CR 等）
- `ReA_ReC_grid_<tag>.csv` : 格子（pivot）形式（行=ReA、列=ReC、値=CR）
- `ReA_ReC_map_<tag>.png` : 等高線図（既定は `log10(CR)`、`--map_linear_cr` で線形CR）

---

## 4. 計算ロジック（本スクリプトがしていること）

### 4.1 ターゲット視角でのCR評価
1. `A_scale` と `ReC_nm` からスタック（LC/A/C等）を構築  
2. `ips.Tleak_stack_scalar(theta, phi, stack, c1, c2)` で白色リーク `Tleak` を計算  
3. `CR = ips.CR_from_Tleak(Tleak)`（または等価式）でCRへ変換  
4. 探索・比較し、最大の点を best として保持

### 4.2 envelope（AごとにReC最適化）
- 各 `A_scale` について `ReC_nm`（および必要なら A_base/A_kind）を走査して `CR(theta,phi)` を最大化  
- 最大点を `A_envelope_<tag>.csv` の1行として保存  
- ReA（=基準ReA×A_scale）に対するプロットを出力

### 4.3 A-step ISO（envelopeの各行でISO）
- `A_envelope_<tag>.csv` の各行（Aステップ最適点）を読み出し  
- その点のスタックを再構成して ISO-CR を保存  
- これにより progress（best更新）に依存せず、AステップごとのISOを一括取得可能

### 4.4 ReA–ReC 2Dマップ（等高線）
- 探索レンジの `A_scale` と `ReC_nm` の直積格子を作成  
- 各格子点で `CR(theta,phi)` を計算  
- 2D配列として保存（grid CSV）＋ロング形式CSVを出力  
- `log10(CR)`（既定）もしくは `CR`（線形）で等高線PNGを出力

> マルチモードのスタック（A_base/A_kindが複数あるケース）では、各格子点でそれらを内部で評価し、最大CR（best）をマップに採用します。

---

## 5. main から呼び出される主モジュール

- `ips_compensation_run_signedC.py`（`import ... as ips`）  
  - 式(3a)(3b)の有効リターデーション: `eq3a_Gamma_A`, `eq3b_Gamma_C`  
  - 3Dレターダ: `retarder_matrix`  
  - 透過リーク: `Tleak_stack_scalar`  
  - ISO: `compute_CR_grid`, `plot_isocontrast_polar`  
  - 偏光子軸: `pol_axes` など

- `ips_stokes_trace.py`  
  - Stokes追跡: `trace_stokes_per_wavelength`, `trace_stokes_white`

---

## 6. 追加仕様（ReA–ReC 2Dマップ）を使うときの注意

- 2Dマップは格子点数が `N_A × N_ReC` となるため、計算量が増えます。  
  まずは粗い刻み（例: `Ad=0.1`, `ReCd=40`）で傾向を掴み、その後に絞り込む運用を推奨します。
- 等高線はデフォルトで `log10(CR)` 表示です（レンジが広く読みやすい）。線形表示は `--map_linear_cr` を使用してください。

