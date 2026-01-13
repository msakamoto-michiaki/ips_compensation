# IPS液晶のJones伝搬行列ベース光学補償シミュレーション（A-plate/C-plate最適化）ドキュメント

対象プログラム:
- `ips_compensation4_stacks_envelope.py`（最適化・出力生成のメイン）
- `ips_compensation4_stacks_envelope_AstepIso.py`（拡張版: A膜厚ステップごとの最適点をCSV記録し、各ステップでISO-CRを出力）
- `ips_compensation_run_signedC.py`（物理モデル：O-type偏光子、Eq.(3)の有効リターデーション、Jones/ベクトル伝搬、CR計算、等コントラスト描画）
- `ips_stokes_trace.py`（Stokes追跡：各層通過後の偏光状態をJSON/CSVに出力）

関連論文:
- *Optical configuration of a horizontal-switching liquid-crystal cell for improvement of the viewing angle* (Applied Optics, 2006)

---

## 1. プログラムの概要

本コード群は、IPS（横電界スイッチング）液晶セルの**斜め視野角での暗状態リーク（light leakage）低減**を目的として、  
(POLARIZER) / LC / A-plate / (+/-C-plate) / (ANALYZER) あるいはそれを拡張した多層スタックを対象に、

- 視線方向（入射角）に依存した各層の**有効位相差（有効リターデーション）**
- 各層のJones（ここでは 3D電場ベクトルを用いた等価Jones）伝搬
- 検光子通過後の強度（リーク）とコントラスト比（CR）

を数値計算し、**A-plateのスケール係数 `A_scale` と C-plateの有効リターデーション `ReC_nm` を総当たり（グリッド）探索**して、
指定視角（デフォルト: `theta=30°`, `phi=45°`）でCRを最大化する組み合わせを探索します。

### 論文との対応（式(2),(3),(5)）
- **式(3a)(3b)**（斜入射時のA板/LC・C板の有効リターデーション）  
  → `ips_compensation_run_signedC.py` の  
  `eq3a_Gamma_A()`（A/LC用）と `eq3b_Gamma_C()`（C用）で実装されています。

- **式(2)**（理想O-type直交偏光子の斜入射リーク）  
  → 本実装では、式(2)をそのまま代入するのではなく、  
  **O-type偏光子の通過状態**を「吸収軸 `c` と波数ベクトル `k` から `o = normalize(k×c)` を作る」ことで表現し、  
  入射電場 `E0=o1` をスタックに伝搬後、出射側 `o2` への射影 `amp=o2·E` からリーク強度 `T` を計算します  
  （式(2)で扱う「斜入射で有効吸収軸がずれる」効果を、ベクトル幾何で直接取り込む実装です）。

- **式(5)**（Poincaré球上の幾何設計におけるC板の最適化関係）  
  → 本コードは球面三角法による閉形式最適化（式(5)の導出）ではなく、  
  **膜厚/有効リターデーションを直接スキャンし、CR最大化で最適点を求める**方針です。  
  ただし「C板の符号（+C/-C）」や「波長分散を加味した白色評価」は、論文の設計思想と整合するように実装されています。

---

## 2. 座標系と角度定義（重要）

本実装の視線方向は、標準的な球座標で

- `theta` : **極角（polar angle）** … +z軸からの角度（0°が正面）
- `phi`   : **方位角（azimuth）** … x軸基準でxy平面内を回る角度（0–360°）

として定義されています（`ips_compensation_run_signedC.py` の `k_hat()` 参照）。

> もし「theta=方位角、phi=極角」として入力したい場合は、ユーザ側で値を入れ替えて指定してください。

---

## 3. 実行方法（mainプログラムの入出力を含む動作説明）

### 3.1 `ips_compensation4_stacks_envelope.py`（最適化のメイン）

#### 入力（コマンドライン引数）

主要引数（デフォルト値付き）:

- 出力:
  - `--outdir out_opt` : 出力ディレクトリ
- 最適化ターゲット視角:
  - `--theta 30.0` : 極角（deg）
  - `--phi 45.0`   : 方位角（deg）
- 偏光子/検光子と相対角:
  - `--pol_in 0.0` , `--pol_out 0.0` : 入射側/出射側偏光子の面内回転（deg）
  - `--relA 0.25` : A-plateの偏光子基準の相対回転（deg）
  - `--relLC 0.25`: LC directorの偏光子基準の相対回転（deg）
- 探索レンジ（グリッド）:
  - `--Amin 0.60 --Amax 1.40 --Ad 0.05` : `A_scale` の範囲/刻み
  - `--ReCmin -280 --ReCmax 280 --ReCd 20` : `ReC_nm` の範囲/刻み（nm）
- スタック選択:
  - `--stack all`（または `LC_AC_abs`, `LC_AC_tran`, `CA_LC_tran`, `CA_LC_AC_abs`, `CA_LC_AC_tran`）
  - 互換エイリアス: `case1`, `case2`, `case3`
- 出力制御:
  - `--skip_iso` : 等コントラスト（ISO-CR）描画を省略
  - `--skip_stokes` : Stokesトレース出力を省略
  - `--skip_summary` : `summary.csv` を省略
  - `--export_envelope` : A-scaleごとの包絡線（envelope）CSV/PNGを追加出力
  - `--export_Astep_iso` : **A膜厚ステップごと**に、そのステップで最適なReC等（envelopeで得た最適点）に対してISO-CR図を必ず出力（best更新に依存しない）
  - `--Astep_iso_stride N` : AステップISO出力をN行ごとに間引き（重い場合の負荷軽減。デフォルト1=全行）
  - `--Astep_iso_theta_max` / `--Astep_iso_dtheta` / `--Astep_iso_dphi` : AステップISO出力の角度範囲と解像度（粗くすると高速）
  - `--load_best_from DIR` : 最適化をスキップし、既存の `best_stack_*.json` を読み込んで可視化/出力のみ実行
- 進捗（best更新ログ）:
  - `--track_progress` : ベスト更新時のログを保存
  - `--progress_stride N` : N回の更新ごとに1行保存
  - `--progress_limit M` : 進捗ログ最大行数（0で無制限）
  - `--progress_plot` : CR推移プロットPNGを出力
  - `--progress_iso_stride N` : 進捗ログのN行ごとにISO図も保存（重い）
- Stokesトレース視角:
  - `--stokes_theta` / `--stokes_phi` : 未指定なら `--theta/--phi` を使用
  - `--stokes_basis` : `lab` / `pol_in` / `pol_out`（推奨: `pol_in`）

#### 実行例

```bash
python ips_compensation4_stacks_envelope_AstepIso.py \
  --outdir out_opt \
  --stack LC_AC_abs \
  --Amin 0.60 --Amax 2.40 --Ad 0.05 \
  --ReCmin -280 --ReCmax 280 --ReCd 20 \
  --track_progress --progress_plot \
  --progress_iso_stride 5 \
  --export_envelope \
  --export_Astep_iso
```

#### 出力（生成ファイル）

`--outdir` 配下に、主に以下が生成されます（スタックごとに作られるものは `<tag>` で表記）:

- 最適解:
  - `best_stack_<tag>.json` : 最適スタックの層パラメータ（type/axis/d/no/ne等）
- 進捗（`--track_progress`）:
  - `progress_<tag>.csv` / `progress_<tag>.json` : ベスト更新ログ（CR、A_scale、ReC_nm、Stokes要約など）
  - `progress_<tag>_CR.png` : 更新インデックスに対するCR推移
  - `iso_progress_<tag>/index.csv` と `iso_progress_<tag>/iso_<tag>_uXXX.png` : 進捗ISO図（`--progress_iso_stride`。**best更新が無いと増えない**）
- Aステップ最適点のISO-CR出力（`--export_Astep_iso`）:
  - `A_envelope_<tag>.csv` : A-scale（膜厚ステップ）ごとの最適点（best_ReC_nm/best_CR等）
  - `iso_Astep_<tag>/index.csv` と `iso_Astep_<tag>/iso_<tag>_A###.png` : **各Aステップ最適点で必ず出る**ISO-CR図（best更新に依存しない）
- ISO-CR可視化（`--skip_iso` で抑制）:
  - `iso_<tag>_best.png` : 最適スタックの等コントラスト極座標図
- Stokesトレース（`--skip_stokes` で抑制）:
  - `stokes_per_wavelength_<tag>.json/.csv`
  - `stokes_white_<tag>.json/.csv`
- サマリ（`--skip_summary` で抑制）:
  - `summary.csv` : 各スタックでのベストCR、全方位min/5%点、基準（LCのみ）との比較

---

---

### 出力ファイルの意味（outdir配下）

以下は `--outdir out_opt --stack LC_AC_abs` のように実行した場合を例に、`out_opt/` 配下に生成される代表ファイルが「何を意味するか」「何に使うか」をまとめたものです（`<tag>` はスタックタグ）。

#### 最終最適解（best）
- `best_stack_<tag>.json`  
  **意味**: 探索した全パラメータの中で、ターゲット視角（例: `theta=30°, phi=45°`）のCRが最大だった「スタックの完全レシピ」。  
  **用途**: 後から同じ条件の再計算・再描画をするための保存設計（再現性の根拠）。
- `iso_<tag>_best.png`  
  **意味**: `best_stack_<tag>.json` のスタックについて、角度グリッド上で計算した **等コントラスト（ISO-CR）極座標プロット**。  
  **用途**: 最終最適解の視野角特性を一目で確認する代表図。

#### Stokesトレース（偏光状態の層別追跡）
- `stokes_white_<tag>.json/.csv`  
  **意味**: 層ごとの Stokes（S0..S3）を **白色（波長加重平均）**でまとめたトレース。  
  **用途**: どの層で偏光がどう回り、暗状態リークがどう抑制されているかを解析（Poincaré球的挙動の確認）。
- `stokes_per_wavelength_<tag>.json/.csv`  
  **意味**: 層ごとの Stokes を **波長ごと**に列挙したトレース。  
  **用途**: 色依存で補償が崩れていないか（特定波長でリークが増えないか）を確認。

#### progress（探索中の「best更新」ログ）
- `progress_<tag>.csv/.json`（`--track_progress`）  
  **意味**: 探索中に **best（最高CR）が更新された瞬間だけ**を記録するログ。  
  **用途**: 探索がどこで収束したか、改善が起きたパラメータ領域はどこか、次の探索レンジの当たりを付ける。
- `progress_<tag>_CR.png`（`--progress_plot`）  
  **意味**: best更新回数（`update_idx`）に対する `best_CR` の推移プロット。  
  **用途**: 収束状況の可視化。

#### progress由来のISO（best更新履歴のスナップショット）
- `iso_progress_<tag>/index.csv`（`--progress_iso_stride`）  
  **意味**: progressのどの記録点（更新回）をISO化したかと、PNGの対応表。  
  **用途**: ISO図がどの時点のbestを表しているか追跡する。
- `iso_progress_<tag>/iso_<tag>_uXXX.png`  
  **意味**: progressの記録点のうち、指定間隔（例: 5更新ごと）で保存したISO-CR図。  
  **注意**: **best更新が止まると progress が増えず、ISOも増えません**。  
  **用途**: bestが改善するにつれて視野角特性がどう変わったかを時系列で観察。

#### A膜厚ステップごとの最適点（envelope）
- `A_envelope_<tag>.csv`（`--export_envelope`）  
  **意味**: A_scale（A膜厚ステップ）を固定したときに、そのAで最適となる ReC（等）を探索し、**Aステップごとの最適点**を1行にまとめた表。  
  **用途**: A膜厚の設計余裕・許容差（AずれでCRがどれだけ落ちるか）を評価する基礎データ。
- `A_envelope_<tag>_CR.png` / `A_envelope_<tag>_rel_to_best.png`  
  **意味**: envelope（Aごとの到達best_CR）をプロットした図（後者は全体bestで正規化した相対図）。  
  **用途**: ピークの鋭さ/鈍さ（製造許容差の観点）を直感的に把握する。
- `A_envelope_<tag>_best.json`  
  **意味**: envelope上で得られた最良点（全Aの中でもベスト）をまとめたJSON。  
  **用途**: envelope観点の最良点を再参照する。

#### Aステップ最適点ごとのISO（拡張：best更新に依存しないISO群）
- `iso_Astep_<tag>/index.csv`（`--export_Astep_iso`）  
  **意味**: `A_envelope_<tag>.csv` の各行（各Aステップ最適点）に対して作成したISO PNGの対応表。  
  **用途**: Aと最適ReCに対応するISO図を機械的に追跡する。
- `iso_Astep_<tag>/iso_<tag>_A###.png`  
  **意味**: **各Aステップで最適なReC点**（envelopeの各行）に対して必ず保存されるISO-CR図。  
  **用途**: A膜厚のずれに対する視野角特性の変化を、ISO図で一括比較（ばらつき評価・ターゲット選定）。

#### サマリ
- `summary.csv`  
  **意味**: 実行したスタックの代表指標を1行にまとめた総括表。  
  **用途**: 複数スタックを回したときの比較・選定に使用。


### 3.2 `ips_stokes_trace.py`（Stokes追跡の単体実行）

最適化で選ばれたスタックを、層ごとに通過後のStokesパラメータ（S0..S3）として出力し、Poincaré球的な挙動の確認に使います。

#### 入力

- `--theta`, `--phi` : 視線方向（極角/方位角）
- `--basis` : Stokes計算の基底
  - `lab` : 実験室座標に近い固定基底（kに直交なu,vを自動生成）
  - `pol_in` / `pol_out` : S1軸を偏光子（または検光子）通過軸に合わせる
- `--mode` : デモ用スタック生成モード
  - `ex2` : `ips_compensation_run_signedC.build_stack_realistic()` を使ったTAC付き例
  - `LAC` : `LC/A/C` 簡易例
- `--A_scale`, `--dC_um` : デモスタックのパラメータ
- `--white` : 指定すると波長加重平均（白色）を出力。指定しない場合は波長ごとのリスト。

#### 実行例

```bash
python ips_stokes_trace.py --theta 30 --phi 45 --basis pol_in --mode ex2 --A_scale 1.0 --dC_um 0.5 --white
```

#### 出力
- `--out_json`（デフォルト `stokes_trace.json`）にJSON出力。

---

### 3.3 `ips_compensation_run_signedC.py`（モデル単体実行）

このファイルは **主に「モデル関数を提供するライブラリ」**として使われますが、`__main__` ブロックが複数あり、
実行すると検証用のプロット生成・再現実験ルーチンが走ります（出力ディレクトリにISO図やmanifestが生成されます）。

> 日常運用では `ips_compensation4_stacks_envelope.py` から import して使うのが基本です。

---

## 4. mainから呼び出される主なモジュール

### 4.1 `ips_compensation4_stacks_envelope.py` → `ips_compensation_run_signedC.py`（`import ... as ips`）
主に以下を利用します:
- `ips.pol_axes()` : 偏光子/検光子の吸収軸ベクトル `c1, c2` を生成
- `ips.Tleak_stack_scalar()` : 指定視角でのリーク強度（白色加重）計算
- `ips.compute_CR_grid()` / `ips.plot_isocontrast_polar()` : ISO-CR計算と描画
- 物性定数: `ips.NO_BASE`, `ips.dn_LC`, `ips.dn_upperA`, `ips.dn_lowerA`, `ips.dn_C`, `ips.d_LC`, `ips.RE_A_EACH_BASE_NM` など

### 4.2 `ips_compensation4_stacks_envelope.py` → `ips_stokes_trace.py`
- `trace_stokes_per_wavelength()` : 波長ごとに層通過後Stokesを列挙
- `trace_stokes_white()` : 波長加重平均（白色）Stokesトレース

---

## 5. 主なモジュール関数の説明

### 5.1 `ips_compensation_run_signedC.py`（物理モデル）

#### `k_hat(theta_deg, phi_deg) -> ndarray(3,)`
球座標から単位波数ベクトル `k` を生成します。

#### `o_axis_Otype(k, c) -> ndarray(3,)`
O-type偏光子の通過状態（ordinary）を
`o = normalize(k × c)` で与えます（`c` は吸収軸）。

#### `eq3a_Gamma_A(theta_deg, phi_deg_rel, lam, d, no, ne)`
論文式(3a)に対応。A-plate/LC（面内軸を持つ一軸性近似）の斜入射有効位相差 `Γ` を返します。  
`phi_deg_rel` は「視線方位角 `phi` と素子軸方位 `alpha` の相対角 `phi-alpha`」です。

#### `eq3b_Gamma_C(theta_deg, lam, d, no, ne)`
論文式(3b)に対応。C-plate（光軸z）の斜入射有効位相差 `Γ` を返します。

#### `retarder_matrix(k, axis_vec, Gamma) -> (3x3 complex)`
`k` に直交する2次元偏光空間で位相差 `±Γ/2` を与える「3D電場ベクトル版レターダ」を構成します。  
内部では
- `u` : 軸 `axis_vec` を `k` に垂直な面へ射影して正規化
- `v = k × u`
を基底として、`u,v` 成分に位相を付与します。

#### `build_stack_realistic(dC_um, A_scale, tac_repeat=..., ...) -> List[Dict]`
TACフィルム（±C相当）、A-plate、LC、（符号付き）C-plate を含む実用的なスタック辞書列を生成します。  
`dC_um` は**符号付き**で解釈され、符号がC板の複屈折符号（+C/-C）を切り替えます。

スタック要素（dict）は概ね以下:
- `type`: `"A" | "LC" | "C"`
- `axis`: 光軸ベクトル（3要素）
- `d`: 厚み [m]
- `no`, `ne`: 屈折率（波長分散が有効な場合は内部で補正）

#### `Tleak_stack_scalar(theta_deg, phi_deg, stack, c1, c2) -> float`
白色加重平均リーク `Tleak` を返します。

計算フロー（概念）:
1. `k = k_hat(theta, phi)`
2. 入射偏光状態 `E0 = o_axis_Otype(k, c1)` を生成
3. 各層 `el` について
   - A/LC: `Γ = eq3a_Gamma_A(theta, phi-alpha, ...)`
   - C:    `Γ = eq3b_Gamma_C(theta, ...)`
   - `M = retarder_matrix(k, axis, Γ)` で `E ← M E`
   - `E` から縦成分を除去（横波条件）: `E ← E - (E·k)k`
4. 出射側の通過状態 `o2` へ射影 `amp=o2·E` → `T ∝ |amp|^2`

#### `compute_CR_grid(stack, c1, c2, theta_max=..., dtheta=..., dphi=...)`
角度グリッド上でCRを計算します（ISO-CR図生成に使用）。

---


---

#### 5.1.x 詳細解説（仕様書PDFの Section 5.3 / 5.4 相当）

この節では、`ips_compensation_run_signedC.py` の **主要4関数**（`eq3a_Gamma_A`, `eq3b_Gamma_C`, `build_stack_realistic`, `Tleak_stack_scalar`）と、
それらを支える補助関数（`k_hat`, `o_axis_Otype`, `retarder_matrix`, `pol_axes`, `CR_from_Tleak` ほか）について、
数式・座標・数値安定化の観点から整理します。

##### `eq3a_Gamma_A(theta_deg, phi_deg_rel, lam, d, no, ne)`（Eq. 3a：A-plate / LC 用の斜入射見かけ遅相）

- **役割**  
  面内に光学軸をもつ一軸性レターダ（A-plate/LC）について、斜入射角 `(θ, φ)` での **見かけ位相差** `ΓA` [rad] を返します。  
  ここで `phi_deg_rel` は **素子軸方位 `α` に対する相対方位角** `φrel = φ − α` を与えます。

- **なぜ `φrel` を使うか（重要）**  
  `φ`（ラボ座標の方位角）をそのまま使うと、素子軸の回転（`α`）と整合しない角度依存が混入し、
  ISO-CR の極座標パターンが不自然になるため、必ず `φrel` を用います（実装では `phi_rel = phi_deg - axis_azimuth_deg(axis)`）。

- **実装されている数式の形**  
  実装は、`term_e`, `term_o`（平方根の中身）を計算し、
  `ΓA = (2π/λ) d ( ne·sqrt(term_e) − no·sqrt(term_o) )` の形で評価します。

- **数値安定化**  
  `term_e`, `term_o` は数値誤差で負になり得るため、`max(…, 0)` でクリップしてから平方根を取っています。

##### `eq3b_Gamma_C(theta_deg, lam, d, no, ne)`（Eq. 3b：C-plate 用の斜入射見かけ遅相）

- **役割**  
  光学軸が面法線（z軸）方向の C-plate について、斜入射角 `θ` における見かけ位相差 `ΓC` [rad] を返します。  
  理想 C-plate は **方位角 `φ` に依存しない**ため、本関数は `φ` を引数に取りません。

- **数値安定化（θ→90°の発散回避）**  
  `d / cosθ` を含むため、`cosθ` が 0 に近づくと発散します。実装では `cosθ` に下限を設けています。  
  また、有効屈折率を作る式の分母・平方根内部にも下限を設け、`inside >= 1e-18` のようにクリップしています。

##### `retarder_matrix(k, axis_vec, Gamma)`（3D電場ベクトル版レターダ演算子）

- **狙い**  
  偏光は本質的に `k` に直交する2次元空間ですが、斜入射では「透過状態」「射影」を扱うために 3D ベクトルとして持つと実装が簡潔になります。  
  本関数は、`k` に直交する面上に定義される直交基底 `(u, v)` を作り、その2次元部分空間に位相差 `±Γ/2` を与えます。

- **内部の幾何**  
  1. `axis_vec` を `k` に直交する平面へ射影し `a_perp` を得る  
  2. `u = normalize(a_perp)`  
  3. `v = normalize(k × u)`  
  4. 射影演算子 `uu = u u^T`, `vv = v v^T`, `kk = k k^T` を用意し  
     `M = e^{+iΓ/2} uu + e^{-iΓ/2} vv + kk` として返します。  
     （`kk` は縦成分をそのまま通す項ですが、後段で横波条件を強制するので、結果として偏光は横成分に保たれます。）

- **例外処理**  
  `axis_vec` が `k` とほぼ平行な場合、射影 `a_perp` がゼロに近づき基底が作れないため、
  `k` と十分直交する仮ベクトルを選んで回避しています。

##### `build_stack_realistic(dC_um, A_scale, tac_repeat=..., ..., pol_pair_rot_in_deg=..., ...)`

- **役割**  
  評価対象の **retarder-only スタック**（TAC繰返し、対称 C-plate、A/LC/A）を、層辞書のリストとして構築します。  
  偏光子/検光子はここには入れず、`Tleak_stack_scalar` 側で `c1/c2` として与えます。

- **スタックの基本順序（概念）**  
  `TAC(-C)×N / (L-C) / L-A(rot) / LC / U-A(rot) / (U-C) / TAC(-C)×N`  
  ※ 実際に入る層は `dC_um` の有無や TAC 繰り返し数で変化します。

- **軸回転ロジック（実務上重要）**  
  基準軸：Lower A は azimuth 0°, Upper A は azimuth 90° とし、以下のように回転を与えます。

  - 入射側：`axis_LA = Rz(POL_IN + REL_LA) axis_LA_base`
  - 出射側：`axis_UA = Rz(POL_OUT + REL_UA) axis_UA_base`
  - LC：`axis_LC = Rz(POL_IN + LC_REL) axis_0deg`

  `REL_*` は「偏光子とA板が完全に一体回転しない」ミスアライメントを表し、
  `POL_PAIR_ROT_*` は「偏光子と（基準の）A板が一緒に回る」ペア回転を表します。

- **厚み（d）の決定（Re→d の逆算）**  
  A-plate は基準遅相 `Re_each`（nm）を `A_scale` でスケールし、`d = Re_each / Δn` で厚みを決めます（実装は SI 単位に換算して計算）。

##### `Tleak_stack_scalar(theta_deg, phi_deg, stack, c1, c2)`（リーク計算：Eq.(2) / Eq.(5) と等価な実装）

- **役割**  
  指定視野角 `(θ, φ)` における暗状態リーク透過率 `Tleak`（スカラー）を返します。  
  白色評価では、B/G/R の `Tleak(λ)` を **重み付き平均**して 1 つの `Tleak` を作ります。

- **Eq.(2) の扱い（偏光子/検光子は“行列”にしない）**  
  実装上の要点は、偏光子/検光子を損失行列として積層に入れず、
  1) 入射偏光を偏光子透過状態 `o1(k)` に固定し、  
  2) 出射側で検光子透過状態 `o2(k)` へ射影する  
  ことで Eq.(2) 相当の効果を取り込むことです（簡略モデルでは Fresnel 項は省略）。

- **Eq.(5)（積層演算子）の等価表現**  
  全体は概念的に  
  `a(θ, φ) = o2(k)^T  ( Π_n  M_n(k, a_n, Γ_n) )  o1(k)`、`Tleak ∝ |a|^2`  
  という形で書けます（`M_n` が `retarder_matrix` に相当）。

- **処理フロー（実装の骨格）**  
  1. `k = k_hat(θ, φ)`  
  2. `o1 = o_axis_Otype(k, c1)`, `o2 = o_axis_Otype(k, c2)`  
  3. `E0 ← o1` としてスタックに入射  
  4. 波長ループ（B/G/R）  
     - 層ループ：A/LC は `Γ=eq3a_Gamma_A(θ, φ−α, ...)`、C は `Γ=eq3b_Gamma_C(θ, ...)`  
     - `E ← retarder_matrix(k, axis, Γ) E`  
     - **横波条件の強制**：`E ← E − (E·k)k`（層更新ごとに縦成分を除去）  
     - 出射で `amp = o2·E`, `T ∝ |amp|^2`  
  5. 波長加重平均（`WL_KEYS`, `WL_WEIGHTS`）で白色 `Tleak` を返す

- **出力値の意味**  
  ここで得る `Tleak` は Fresnel 係数等を省略した簡略値で、CR の **相対比較**（最適化・等コントラスト図）に用います。

##### 補助関数（Section 5.4 相当）：何をどの数式に対応させているか

- `k_hat(theta, phi)`：球座標から単位波数ベクトル `k` を構成します。  
- `o_axis_Otype(k, c)`：O-type 偏光子の ordinary 透過状態 `o = normalize(k×c)` を与えます。  
- `pol_axes(pol_pair_rot_in_deg, pol_pair_rot_out_deg)`：偏光子/検光子の吸収軸 `c1, c2` を、基準（x, y）から面内回転で生成します。  
- `CR_from_Tleak(Tleak)`：`CR = 1 / (Tleak + 1/CR0_TARGET)` の形で有限CR0を考慮してCRに変換します。  
- `_ne_no_for_wl(el, wl_key)`：層の `(no, ne)` を波長キーに応じて与えます（分散を使わない場合は `Δn` 一定で `Γ ∝ 1/λ` のみを反映）。

---
### 5.2 `ips_compensation4_stacks_envelope.py`（最適化・出力）

#### `setup_model()`
`ips_compensation_run_signedC.py` 側の分散設定や定数を、この探索用に整える初期化関数です。

#### `build_LC(lc_basis, pol_in_deg, relLC_deg) -> dict`
LC層のスタック要素を生成します。`lc_basis`:
- `"abs"` : LC軸ベース方位 0°
- `"tran"`: LC軸ベース方位 90°
を採用します。

#### `build_A(A_scale, A_base_deg, pol_out_deg, relA_deg, A_kind) -> dict`
A-plate要素を生成します。`A_scale` は基準リターデーション `RE_A_EACH_BASE_NM` をスケールし、
`dn_upperA/dn_lowerA` から厚み `dA = Re/dn` を算出します。

#### `build_C(ReC_nm_signed) -> dict | None`
C-plate（光軸z）を生成します。`ReC_nm_signed` の符号で +C/-C を切り替え、
絶対値から厚み `dC` を求めます。0なら `None`（C板なし）。

#### スタックビルダ
- `stack_LC_A_C(...)` : `LC / A / C`
- `stack_C_A_LC_trans(...)` : `C / A / LC`（LCは"tran"固定）
- `stack_C_A_LC_A_C(...)` : `C / A(bot) / LC / A(top) / C`（対称5層）

#### `CR_from_stack(theta, phi, stack, c1, c2) -> float`
`ips.Tleak_stack_scalar()` を呼び出してリークを得て、`CR = 1/(Tleak + 1/CR0_TARGET)` でCRを返します。

#### `grid_optimize(...) -> (best_dict, progress_rows)`
`A_scale × ReC_nm × (A_base) × (A_kind)` を総当たりし、指定視角でCR最大の条件を探索します。  
`--track_progress` 指定時はベスト更新のたびに、CR・パラメータ・Stokes要約を記録します。

#### `save_iso(stack, title, out_path, c1, c2, ...)`
`ips.compute_CR_grid()` で角度依存CRを計算し、`ips.plot_isocontrast_polar()` で極座標ISO図を保存します。

#### `save_stokes_traces(case_tag, theta, phi, stack, c1, c2, basis, outdir)`
`ips_stokes_trace` を用いて Stokes追跡をJSON/CSVとして保存します。

#### `envelope_over_A(...)` / `export_progress_iso(...)` / `export_Astep_iso_from_envelope(...)`
オプションで、A-scaleを走査した際の最良CR包絡線（`A_envelope_<tag>.csv`）、進捗途中のISO図（`iso_progress_<tag>/...`）などを出力します。

- `export_Astep_iso_from_envelope(...)`（拡張）:
  - `A_envelope_<tag>.csv` に記録された **Aステップごとの最適ReC** を読み出し、
    その最適点スタックを再構成して `save_iso()` を呼び出し、`iso_Astep_<tag>/` にISO-CR図を保存します。
  - これにより「best更新が止まったらISOが増えない」という進捗ログ由来の制約から独立に、AステップごとのISOを取得できます。

---

### 5.3 `ips_stokes_trace.py`（Stokes追跡）

#### `transverse_basis(k, c1, c2, basis="lab") -> (u,v)`
Stokes計算用の直交基底 `u,v`（kに直交）を構成します。`basis` で基準軸を切替可能です。

#### `stokes_from_E(E,k,u,v) -> (S0,S1,S2,S3)`
複素電場 `E` を `u,v` 成分へ射影して Stokes を計算します。

#### `trace_stokes_per_wavelength(theta, phi, stack, c1, c2, basis, wl_keys)`
- 入射偏光子直後（`POL_in`）
- スタック各層通過後（`el#i_type`）
について、**波長ごとの StokesPoint リスト**を返します。

#### `trace_stokes_white(...)`
波長ごとのStokesを重み付き平均し、白色のトレースを返します。

---

## 6. 典型的な解析フロー（おすすめ）

1. `ips_compensation4_stacks_envelope.py`（または拡張版 `ips_compensation4_stacks_envelope_AstepIso.py`）を実行して `best_stack_<tag>.json` を得る  
2. `iso_<tag>_best.png` で視野角等コントラストを確認  
3. （任意）`--export_Astep_iso` を有効にして `iso_Astep_<tag>/` を出力し、A膜厚ステップごとの最適点の視野角特性を一括で確認  
4. `stokes_*_<tag>.json/.csv` を見て、どの層で偏光状態がどう動いているか（Poincaré球的挙動）を確認  
5. 探索レンジを絞り（`--Amin/--Amax/--Ad`, `--ReCmin/--ReCmax/--ReCd`）、より高精度に再探索

---

## 7. 依存関係

- Python 3.x
- NumPy
- Pandas
- Matplotlib（ISO図、進捗プロット）

---

*Generated on 2026-01-13*
