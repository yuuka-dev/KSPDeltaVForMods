# Python Core Library Design — KSPDeltaVForMods

## Overview

KSP1 の惑星パック Mod 向け ΔV 計算ツールのコアライブラリ設計。
Kopernicus の `.cfg` ファイルを GameData フォルダから再帰スキャンし、
軌道力学（低軌道投入ΔV、ホーマン遷移、脱出バーン、質量比）を大気モデリング込みで計算する。

## Scope

本ドキュメントは `kopdeltav/` パッケージ（Python コアライブラリ）と `run.py`（CLI）のみを対象とする。
FastAPI (`api.py`)、フロントエンド、Tauri はスコープ外。

## Constraints

- **外部依存ゼロ**: `kopdeltav/` は Python 標準ライブラリのみ
- **Python 3.10+**: `from __future__ import annotations` 必須
- **型安全**: `mypy --strict` を通すこと
- **KSP1 専用**: KSP2 は対象外

---

## Module Design

### 1. `kopdeltav/models.py` — Data Models

天体・大気・軌道を表現するデータ構造と Hermite 補間関数。

#### Data Classes

```python
@dataclass
class CurveKey:
    """AnimationCurve の単一キーポイント。"""
    position: float    # x 値（高度 [m] など）
    value: float       # y 値（圧力 [kPa]、温度 [K] など）
    in_tangent: float  # 入力タンジェント
    out_tangent: float # 出力タンジェント（省略時は in_tangent をコピー）

@dataclass
class Atmosphere:
    """天体の大気パラメータ。

    大気なしの天体は CelestialBody.atmosphere = None で表現する。
    このクラスのインスタンスが存在する ＝ 大気がある。
    """
    atmosphere_depth: float              # 大気圏高度 [m]
    pressure_curve: list[CurveKey]       # 圧力カーブ [kPa]
    temperature_curve: list[CurveKey]    # 温度カーブ [K]
    molar_mass: float                    # モル質量 [kg/mol]
    adiabatic_index: float               # 比熱比
    pressure_at_sea_level: float         # 海面気圧 [kPa]
    temperature_at_sea_level: float      # 海面温度 [K]

@dataclass
class OrbitalElements:
    """天体の軌道要素。"""
    semi_major_axis: float    # 軌道長半径 [m]
    eccentricity: float       # 離心率
    inclination: float        # 軌道傾斜角 [deg]
    argument_of_periapsis: float  # 近点引数 [deg]
    longitude_of_ascending_node: float  # 昇交点経度 [deg]
    mean_anomaly_at_epoch: float  # 元期平均近点角 [deg]
    epoch: float              # 元期 [s]

@dataclass(repr=False, eq=False)
class CelestialBody:
    """天体の物理・軌道パラメータ。

    Note:
        repr=False, eq=False: parent/children の循環参照による RecursionError を防止。
        __repr__ は name ベース、__eq__ は name + radius で比較。
        mu は __post_init__ で gee_asl × G0 × radius² から自動導出（init=False）。
        soi は config に明示値があればそれを使用。なければ
        soi = a × (m/M)^(2/5) で計算。ルート天体は inf。
    """
    name: str
    radius: float             # 赤道半径 [m]
    gee_asl: float            # 海面重力加速度 [g]
    has_ocean: bool
    atmosphere: Atmosphere | None  # 大気なし = None（Atmosphere.has_atmosphere は使わない）
    orbit: OrbitalElements | None  # ルート天体（恒星）は None
    rotational_period: float  # 自転周期 [s]
    display_name: str         # 表示名（#LOC_ 解決済みまたは name フォールバック）
    soi: float = 0.0          # 影響圏半径 [m]（0 の場合、親子関係構築時にパーサーが計算）
    mu: float = field(init=False)   # 重力パラメータ [m³/s²] — __post_init__ で導出
    parent: CelestialBody | None = field(default=None, init=False, repr=False)
    children: list[CelestialBody] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.mu = compute_mu(self.gee_asl, self.radius)

    def __repr__(self) -> str:
        return f"CelestialBody(name={self.name!r}, radius={self.radius}, gee_asl={self.gee_asl})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CelestialBody):
            return NotImplemented
        return self.name == other.name and self.radius == other.radius
```

#### Functions

```python
G0: float = 9.80665  # 標準重力加速度 [m/s²]

def hermite_interp(keys: list[CurveKey], x: float) -> float:
    """Cubic Hermite Spline 補間（KSP AnimationCurve 互換）。

    隣接する 2 キー間を三次エルミートスプラインで補間する。
    x が範囲外の場合、端のキー値でクランプ。

    Args:
        keys: position 昇順にソートされた CurveKey リスト。
              空リストの場合は ValueError を送出。
        x: 補間対象の position 値。

    Returns:
        補間された value。

    Raises:
        ValueError: keys が空の場合。
    """

def compute_mu(gee_asl: float, radius: float) -> float:
    """μ = gee_asl × G0 × radius² を計算する。"""
```

---

### 2. `kopdeltav/stock.py` — Stock Kerbal System Data

KSP1 の Stock 天体データを内蔵。Kopernicus `.cfg` にはストック天体の元データがないため、
ゲームソースから値を取得し Python コード内に定義する。

#### Content

- 全 17 天体: Kerbol, Moho, Eve, Gilly, Kerbin, Mun, Minmus, Duna, Ike, Dres, Jool, Laythe, Vall, Tylo, Bop, Pol, Eeloo
- 大気カーブ含む: Eve, Kerbin, Duna, Jool, Laythe
- 親子関係（ツリー構造）構築済み

#### Interface

```python
def get_stock_system() -> CelestialBody:
    """Stock Kerbal 星系のルート天体（Kerbol）を返す。

    子天体は children に再帰的に格納済み。
    各天体の mu は gee_asl × G0 × radius² から導出。

    Returns:
        Kerbol を root とする天体ツリー。
    """

def get_stock_body(name: str) -> CelestialBody | None:
    """名前で Stock 天体を検索する。大文字小文字を区別しない。"""
```

---

### 3. `kopdeltav/parser.py` — Kopernicus ConfigNode Parser

Kopernicus の `.cfg` ファイルをパースし、`CelestialBody` オブジェクトを生成する。

#### ConfigNode Parsing

1. ファイル内容を読み込み
2. `//` コメントを除去
3. トークナイズ: `key = value`、`{`、`}`、ブロック名
4. 再帰的にネスト構造をパース → `ConfigNode` 中間表現（dict of lists）
5. 修飾子 (`@`, `!`, `+`, `-`, `%`) をキー名から除去

#### Body Extraction

1. `Kopernicus {}` ブロック内の `Body {}` を探索
2. 各 Body から `Properties {}`, `Orbit {}`, `Atmosphere {}` を抽出
3. カーブキー解析: `key = pos val [inTan [outTan]]` — outTangent 省略時 inTangent コピー
4. `#LOC_...` 表示名は `name` にフォールバック
5. `!Body[Name]{}` 削除指令はスキップ（警告出力）

#### Patch Application

Stock 天体への変更パッチを処理する。

**処理順序**（Kopernicus のロード順に準拠）:
1. Stock 天体データ (`stock.py`) をベースとしてロード
2. 全 `.cfg` ファイルから新規 `Body {}` 定義を先に処理 → 天体を追加
3. 次に `@Body[Name] {}` パッチを処理 → 該当天体のプロパティを上書き
4. 最後に `!Body[Name] {}` 削除指令を処理 → 該当天体を削除

この順序により、パッチ適用時にはターゲット天体が必ず存在する。

#### Interface

```python
@dataclass
class ParseResult:
    """パース結果。"""
    bodies: list[CelestialBody]   # パースされた天体リスト（親子関係構築済み）
    warnings: list[str]           # パース中の警告メッセージ

def parse_config(text: str, stock_bodies: list[CelestialBody] | None = None) -> ParseResult:
    """Kopernicus config テキストをパースする。

    Stock 天体をベースにパッチ（@Body[Name]）を適用する。
    stock_bodies が None の場合、stock.get_stock_system() から自動ロードする。
    単一 .cfg のアップロード時も Stock ベースで動作するため、
    @Body[Kerbin]{} 等のパッチが正しく適用される。

    Args:
        text: .cfg ファイルの内容。
        stock_bodies: ベースとなる Stock 天体リスト（省略時は自動ロード）。

    Returns:
        パース結果（天体リスト + 警告）。
    """

def parse_gamedata(gamedata_path: Path) -> ParseResult:
    """GameData フォルダを再帰スキャンし、全 Kopernicus config をパースする。

    Stock 天体をベースとし、Kopernicus パッチを適用した完全な天体ツリーを返す。

    Args:
        gamedata_path: GameData ディレクトリのパス。

    Returns:
        統合されたパース結果。
    """
```

#### Error Handling

- 不正な構文: 該当行をスキップし warning に追加。クラッシュしない
- 不正なカーブキー: スキップ + warning
- 存在しない天体へのパッチ: warning（Stock にも新規天体にもない場合）

---

### 4. `kopdeltav/discovery.py` — GameData Path Discovery

GameData フォルダのパス解決と Kopernicus config ファイルの検出。

#### Path Resolution

```python
def find_gamedata(user_path: Path | None = None) -> Path:
    """GameData ディレクトリのパスを解決する。

    解決順:
    1. user_path が指定されていればそれを使用
       - GameData ディレクトリ自体、または KSP インストールディレクトリを受け付ける
    2. 未指定の場合、一般的な Steam インストールパスをフォールバック:
       - Windows: C:/Program Files (x86)/Steam/steamapps/common/Kerbal Space Program/GameData
       - Linux:   ~/.steam/steam/steamapps/common/Kerbal Space Program/GameData
                  ~/.local/share/Steam/steamapps/common/Kerbal Space Program/GameData
       - macOS:   ~/Library/Application Support/Steam/steamapps/common/Kerbal Space Program/GameData

    Args:
        user_path: ユーザー指定のパス（省略可）。

    Returns:
        GameData ディレクトリの Path。

    Raises:
        FileNotFoundError: GameData ディレクトリが見つからない場合。
    """
```

#### Config Scanning

```python
def scan_kopernicus_configs(gamedata_path: Path) -> list[Path]:
    """GameData 以下を再帰スキャンし、Kopernicus ボディ定義を含む .cfg を返す。

    フィルタリング: ファイル内容に 'Kopernicus' ブロック（@Kopernicus または Kopernicus）
    が含まれるもののみ。GameData には大量の .cfg（パーツ Mod 等）があるため、
    ファイルサイズが極端に大きいもの（>1MB）はスキップするなどの
    軽量なヒューリスティックを適用してもよい。

    Args:
        gamedata_path: GameData ディレクトリのパス。

    Returns:
        Kopernicus config ファイルのパスリスト。
    """
```

---

### 5. `kopdeltav/calculator.py` — ΔV Calculation Engine

軌道力学の計算を行うエンジン。

#### Core Functions

```python
def circular_velocity(body: CelestialBody, altitude: float) -> float:
    """指定高度での円軌道速度 [m/s]。v = √(μ/r)"""

def escape_velocity(body: CelestialBody, altitude: float) -> float:
    """指定高度での脱出速度 [m/s]。v = √(2μ/r)"""

R_UNIVERSAL: float = 8.314462  # 普遍気体定数 [J/(mol·K)]

def atmospheric_density(atmosphere: Atmosphere, altitude: float) -> float:
    """指定高度での大気密度 [kg/m³]。

    Hermite 補間で圧力 [kPa] と温度 [K] を取得し、
    理想気体の式 ρ = (P×1000) × M / (R_UNIVERSAL × T) で密度を算出。
    注意: 圧力は kPa → Pa 変換（×1000）が必要。
    R = 8.314462 J/(mol·K)（普遍気体定数）。
    """
```

#### Launch ΔV

```python
@dataclass
class LaunchResult:
    """低軌道投入 ΔV の計算結果。"""
    orbital_velocity: float        # 目標軌道速度 [m/s]
    surface_velocity: float        # 地表自転速度 [m/s]
    theoretical_dv: float          # 理論ΔV [m/s]（orbital - surface rotation）
    gravity_loss: float            # 重力損失推定 [m/s]
    drag_loss: float               # 大気抵抗損失推定 [m/s]
    total_rocket_dv: float         # ロケット必要ΔV [m/s]（理論 + losses）
    jet_saving: float              # ジェット節約推定 [m/s]
    total_jet_dv: float            # ジェット併用時ΔV [m/s]

def launch_to_orbit(
    body: CelestialBody,
    target_altitude: float,
) -> LaunchResult:
    """低軌道投入 ΔV を計算する。

    前提:
        - 赤道上（緯度 0°）からの打ち上げを想定（自転速度最大）
        - surface_velocity = 2π × radius / rotational_period

    経験的推定モデル:
        - gravity_loss ≈ surface_gravity × burn_time_estimate
          burn_time_estimate は TWR=1.5 仮定で orbital_velocity / (TWR × g0)
        - drag_loss ≈ 0.1 × orbital_velocity（大気がある場合）。大気なしは 0
        - jet_saving ≈ 0.36 × orbital_velocity（大気密度が十分な場合）。大気なしは 0

    注意: これらは Kerbin での経験則をスケーリングした推定値であり、
    実際のゲーム内値とは 5-15% 程度の誤差が生じうる。
    """
```

#### Hohmann Transfer

```python
@dataclass
class HohmannResult:
    """ホーマン遷移の計算結果。"""
    departure_dv: float    # 出発バーン [m/s]
    arrival_dv: float      # 到着バーン [m/s]
    total_dv: float        # 合計 [m/s]
    transfer_time: float   # 遷移時間 [s]
    ejection_dv: float     # 脱出バーン（低軌道から） [m/s]

def hohmann_transfer(
    body_from: CelestialBody,
    body_to: CelestialBody,
    parking_altitude_from: float,
    parking_altitude_to: float,
) -> HohmannResult:
    """2 天体間のホーマン遷移 ΔV を計算する。

    同一親天体を周回する 2 天体間の遷移を想定。
    親天体が異なる場合は ValueError を送出する。

    Raises:
        ValueError: body_from と body_to の親天体が異なる場合。
    """
```

#### Tsiolkovsky

```python
@dataclass
class TsiolkovskyResult:
    """ツィオルコフスキーの公式の計算結果。"""
    mass_ratio: float      # 質量比 (m0/mf)
    fuel_fraction: float   # 燃料比率
    wet_mass: float        # 湿重量 [kg]（dry_mass 指定時）
    fuel_mass: float       # 燃料質量 [kg]

def tsiolkovsky(
    delta_v: float,
    isp: float,
    dry_mass: float,
) -> TsiolkovskyResult:
    """ツィオルコフスキーの公式で質量比を計算する。"""
```

#### Reference Values (Regression Test)

```
天体: Sanctar (Kopernicus config)
  半径:               670,000 m
  geeASL:             1.1 g
  μ:                  4.8424e12 m³/s²
  脱出速度:           3,802.0 m/s
  海面大気密度:       1.4096 kg/m³
  低軌道速度 (80km):  2,541.1 m/s
  低軌道ΔV (ロケット): ≈3,110 m/s
  低軌道ΔV (ジェット): ≈1,982 m/s
```

---

### 6. `kopdeltav/i18n.py` — Internationalization

dict ベースの日本語/英語翻訳。

```python
def t(key: str, lang: str = "ja") -> str:
    """翻訳文字列を取得する。

    Args:
        key: ドット区切りのキー（例: "launch.title"）。
        lang: 言語コード ("ja" or "en")。

    Returns:
        翻訳文字列。キーが見つからない場合はキー自体を返す。
    """
```

---

### 7. `run.py` — CLI Entry Point

```
Usage: python run.py [path]

Arguments:
  path    GameData ディレクトリ、KSP インストールディレクトリ、
          または単一の .cfg ファイル（省略時: Steam デフォルトパスを自動検出）

Output:
  - パースされた天体ツリーの表示
  - 各天体の物理パラメータ
  - 低軌道投入 ΔV（大気がある天体）
  - 天体間ホーマン遷移 ΔV マップ
```

---

## Testing Strategy

### `tests/test_models.py`
- `hermite_interp`: 2 点間の補間精度、端値クランプ、単一キー
- `compute_mu`: Kerbin リファレンス値との一致

### `tests/test_parser.py`
- Sanctar.cfg の正常パース: 天体名、半径、geeASL、大気パラメータ
- カーブキー: outTangent 省略時の inTangent コピー
- `!Body[Name]{}` 削除指令のスキップ
- `#LOC_...` タグの name フォールバック
- `@Body[Name]{}` パッチ適用
- 壊れた構文: クラッシュせず warning 生成
- コメント除去、修飾子除去
- 空ファイル、空ブロック

### `tests/test_calculator.py`
- Sanctar リファレンス値との回帰テスト（μ, 脱出速度, 低軌道速度, 低軌道ΔV）
- `atmospheric_density`: kPa→Pa 変換の正確性
- Hohmann 遷移: Kerbin→Duna 等の既知値との比較
- Tsiolkovsky: 既知の mass ratio との一致

### `tests/test_discovery.py`
- `find_gamedata`: 明示パス指定、存在しないパス → `FileNotFoundError`
- `scan_kopernicus_configs`: Kopernicus 含む/含まない .cfg のフィルタリング

### `tests/test_stock.py`
- Stock 天体数の確認（17 天体）
- Kerbin リファレンス値（radius=600000, geeASL=1.0）
- 親子関係の整合性

---

## CLAUDE.md Updates Required

本設計で追加されたモジュール・テストファイルを CLAUDE.md のリポジトリ構成に反映する:
- `kopdeltav/stock.py` — Stock Kerbal 星系データ
- `kopdeltav/discovery.py` — GameData パス探索
- `tests/test_models.py`, `tests/test_discovery.py`, `tests/test_stock.py`

---

## Implementation Order

1. `models.py` — データ構造 + hermite_interp
2. `stock.py` — Stock 天体データ
3. `parser.py` — ConfigNode パーサー + パッチ適用
4. `discovery.py` — GameData 探索
5. `calculator.py` — ΔV 計算エンジン
6. `i18n.py` — 翻訳
7. `run.py` — CLI
8. テスト（各モジュールと並行して TDD で進行）
