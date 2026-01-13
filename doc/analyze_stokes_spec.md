# analyze_stokes.py 仕様書（progress CSVのStokes列を用いたオフ軸解析）

対象ファイル: `analyze_stokes.py` fileciteturn5file2  
生成日: 2026-01-13

---

## 1. 概要

`analyze_stokes.py` は、最適化の `progress_*.csv` に保存された **Stokes成分（s1,s2,s3）**を読み取り、  
指定視角（θ,φ）における

- Analyzer通過軸（オフ軸での実効軸）の方位角 `alpha`
- 出射偏光（近似的に線偏光とみなす）の方位角 `psi`
- 両者の直交ズレ（理想は 90°）  
- Stokesから予測したリーク `Tleak_pred` と `CR_pred`

を計算して、ターミナルにレポート表示する診断ツールです。

> 目的は「progressに記録された Stokes が、暗状態リークの説明変数として整合しているか」を素早く確認することです。

---

## 2. 入出力と実行方法

### 2.1 入力（主な引数）

- `--fn` : 出力ディレクトリ（デフォルト `out_opt`）
- `--csv` : progress CSV名（デフォルト `progress_LC_AC_abs.csv`）。フルパス指定も可。
- `--row` : 行番号（デフォルト `-1`）
- `--theta`, `--phi` : 評価する視角（デフォルト 30°, 45°）
- `--basis` : Stokes基底（`pol_in` 推奨）
- `--stage` : progress CSV内の段（列プレフィクス）指定  
  例: `"el#1_A"`, `"el#2_C"` など。列名 `s1_<stage>, s2_<stage>, s3_<stage>` を読む。
- `--pol_in`, `--pol_out` : Analyzer軸計算用（`ips.pol_axes` に渡す）

### 2.2 実行例

```bash
python analyze_stokes.py \
  --fn out_opt \
  --csv progress_LC_AC_abs.csv \
  --row -1 \
  --theta 30 --phi 45 \
  --basis pol_in \
  --stage el#2_C
```

### 2.3 出力

- ファイルは生成せず、標準出力に解析結果を表示します。
- もし指定した `s1_<stage>` 列が存在しない場合は例外で停止します。

---

## 3. main が利用する主モジュール

- `ips_compensation_run_signedC`（`ips`）
  - `pol_axes`, `k_hat`, `o_axis_Otype`, `CR_from_Tleak` など
- `ips_stokes_trace`（`st`）
  - `transverse_basis`（指定basisでu,vを作る）

---

## 4. 計算内容（重要式の意味づけ）

### 4.1 Analyzer通過軸のオフ軸方位角 `alpha`
- `k = k_hat(theta, phi)`
- `u,v = transverse_basis(k, basis=..., c1,c2)`
- `o2 = o_axis_Otype(k, c2)`（Analyzer側の通過状態）
- `alpha = atan2(o2·v, o2·u)` をdeg化  
  → `u,v` 平面上での Analyzer通過軸の方位角。

### 4.2 出射偏光の方位角 `psi`（Stokesから）
progress CSVの `s1,s2,s3`（正規化）から
- `psi = 0.5 * atan2(s2, s1)`（deg）

`|s3| ≪ 1` なら線偏光に近く、`psi` が「偏光方位角」を表します。

### 4.3 直交ズレ
- `delta = (alpha - psi) mod 180`
- 理想は `delta ≈ 90°`（Analyzer軸と出射偏光が直交）
- `orthogonality error = |delta - 90°|`

### 4.4 Stokesからのリーク予測（簡易）
`I = 0.5*(1 + s1 cos2α + s2 sin2α)` を用い、
- `Tleak_pred = 0.5 * I`
- `CR_pred = CR_from_Tleak(Tleak_pred)`

※これは「出射がほぼ線偏光」「吸収モデル簡略化」などの近似に基づくチェック用推定です。

---

## 5. 注意点

- `--stage` は progress CSVの列名に完全一致する必要があります（例: `s1_el#2_C` が存在すること）。
- `basis` を変えると `psi` の解釈が変わります。設計解析では `pol_in` 基底が扱いやすいことが多いです。
- このスクリプトは “診断・整合性チェック用” で、Tleakの厳密計算（白色加重や多層伝搬）そのものは行いません。

