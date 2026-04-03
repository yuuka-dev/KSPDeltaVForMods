# CLAUDE.md — KSPDeltaVForMods

## プロジェクト概要

KSPDeltaVForMods は、Kerbal Space Program 1（KSP1）の惑星パックMod向け ΔV 計算ツール。
Kopernicus の `.cfg` ファイルをパースし、軌道力学（低軌道投入ΔV、ホーマン遷移、脱出バーン、質量比）を大気モデリング込みで自動計算する。

- **対象**: KSP1 + Kopernicus Modユーザー（KSP2は対象外）
- **ライセンス**: MIT
- **多言語**: 日本語（主）/ 英語
- **リポジトリ構成**: モノレポ（バックエンド + フロントエンド + デスクトップ）

---

## 禁止事項（Contraindications）

**以下の行為は絶対に行ってはならない。**
Claude Code がこのプロジェクトで作業する際、最優先で守るべきルール。

### コアライブラリ (`kopdeltav/`) に関する禁止

- **外部依存を絶対に追加するな。** `kopdeltav/` パッケージは Python 標準ライブラリのみで動作しなければならない。FastAPI, Pydantic, requests 等のimportは `api.py` 等の外部レイヤーでのみ許可。
- **JSON / YAML / TOML パーサーを Kopernicus config の解析に使うな。** KSP ConfigNode は独自フォーマットであり、既存パーサーでは正しく処理できない。
- **大気カーブの補間に線形補間を使うな。** KSP の AnimationCurve は Cubic Hermite Spline であり、`models.py:hermite_interp()` を必ず使用すること。
- **計算ロジックの変更後、リファレンス値の検証を省略するな。** `calculator.py` または `models.py` を変更した場合、必ずリファレンス値で回帰テストを行うこと。

### フロントエンド (`frontend/`) に関する禁止

- **Vueテンプレートに日本語・英語を直接書くな。** 全てのユーザー向け文字列は `vue-i18n` の `$t('key')` を使用すること。
- **`any` 型を使うな。** 型が不明な場合は `unknown` + 型ガードを使用。
- **コンポーネントから直接APIを叩くな。** API呼び出しは `src/composables/` 内の関数を経由すること。

### API (`api.py`) に関する禁止

- **Python内部エラーをそのままレスポンスに返すな。** `HTTPException` で適切なメッセージに変換すること。
- **ユーザーがアップロードした .cfg ファイルをディスクに永続保存するな。** メモリ上で処理し、セッション単位で保持。

### Tauri (`src-tauri/`) に関する禁止

- **Rust側にビジネスロジックを書くな。** Tauri はシェルに徹する。計算は全て Python バックエンドが行う。

### パーサー (`parser.py`) に関する禁止

- **不正な入力でクラッシュさせるな。** パーサーは壊れた config を受け取っても、該当箇所をスキップして警告を出すだけにすること。
- **AnimationCurve の outTangent が省略されている場合に 0 にするな。** inTangent の値をデフォルトとしてコピーすること。

### 全般

- **`ruff format` を実行せずにコミットするな。**
- **Conventional Commits 形式以外のコミットメッセージを使うな。**
- **KSP2 対応のための変更を行うな。** スコープ外。

---

## 技術スタック

| レイヤー | 技術 | 備考 |
|---------|------|------|
| コアライブラリ | Python 3.10+ | 外部依存ゼロ。`kopdeltav/` パッケージ |
| CLI | Python 単体実行 | `python run.py config.cfg` — pip不要。ユーザー向けツール |
| バックエンドAPI | FastAPI + Uvicorn | REST API。`/docs` でSwagger UI |
| フロントエンド | Vue 3 + Vite + TypeScript | SPA。FastAPI バックエンドを消費 |
| デスクトップ | Tauri v2 (Rust) | Vue フロントエンドをラップ。ネイティブバイナリ配布 |
| パッケージ管理 | uv or pip (Python), pnpm (frontend), cargo (Tauri) | |

---

## リポジトリ構成

```
KSPDeltaVForMods/
├── CLAUDE.md
├── README.md
├── LICENSE                     # MIT
├── pyproject.toml              # Python設定（ruff, mypy, pytest）
├── .github/
│   └── workflows/
│       ├── ci.yml              # Lint → 型チェック → テスト → ビルド
│       └── release.yml         # Tauri ビルド & GitHub Releases（将来）
│
├── kopdeltav/                  # コアライブラリ（外部依存ゼロ）
│   ├── __init__.py
│   ├── models.py               # CelestialBody, Atmosphere, OrbitalElements, CurveKey
│   ├── parser.py               # Kopernicus ConfigNode パーサー
│   ├── calculator.py           # ΔV 計算エンジン
│   └── i18n.py                 # 翻訳文字列（ja / en）
│
├── run.py                      # スタンドアロン CLI（ユーザー向け）
├── api.py                      # FastAPI アプリケーション
│
├── frontend/                   # Vue 3 + Vite SPA
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── components/         # UIコンポーネント
│   │   ├── composables/        # API呼び出し等の共通ロジック
│   │   ├── stores/             # Pinia ストア
│   │   ├── types/              # 型定義（APIレスポンス型等）
│   │   ├── i18n/               # vue-i18n ロケールファイル (ja.json, en.json)
│   │   └── assets/
│   └── public/
│
├── src-tauri/                  # Tauri v2（Rust シェル）
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── src/
│       └── main.rs
│
├── sample_configs/             # テスト用 Kopernicus .cfg
│   └── Sanctar.cfg
│
└── tests/                      # pytest テストスイート
    ├── test_parser.py
    ├── test_calculator.py
    └── test_api.py
```

---

## コーディング規約

### 全体
- コメントは英語 docstriongは英語は詳しく、日本語は簡潔に


### Python（バックエンド / コアライブラリ）

- **フォーマッター**: `ruff format`（black互換、行長100）
- **リンター**: `ruff check`（ルール: `["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]`）
- **型チェック**: `mypy --strict` — 公開関数・メソッドは全て完全な型注釈が必須
- **Docstring**: Google スタイル。公開クラス・関数・メソッド全てに必須
- **インポート**: 全ファイル先頭に `from __future__ import annotations`。`kopdeltav` 内は絶対インポート
- **命名**: 関数/変数は `snake_case`、クラスは `PascalCase`、定数は `UPPER_SNAKE`
- **エラー処理**: 型付き例外を送出。素の `except:` は禁止
- **データ構造**: 公開APIには `dataclass` または Pydantic `BaseModel`。生の dict を返さない
- **パス操作**: `os.path` ではなく `pathlib.Path`
- **設計方針**: 継承より合成

```python
# 模範例
from __future__ import annotations

import math

from .models import CelestialBody


def calculate_orbital_velocity(body: CelestialBody, altitude: float) -> float:
    """指定高度での円軌道速度を計算する。

    Args:
        body: 対象天体。
        altitude: 表面からの高度 [m]。

    Returns:
        軌道速度 [m/s]。

    Raises:
        ValueError: altitude が負の場合。
    """
    if altitude < 0:
        raise ValueError(f"高度は非負でなければならない: {altitude}")
    r = body.radius + altitude
    return math.sqrt(body.mu / r)
```

### TypeScript / Vue（フロントエンド）

- **言語**: TypeScript（tsconfig で strict モード）
- **スタイル**: `<script setup lang="ts">` + Composition API
- **状態管理**: Pinia
- **フォーマット**: Prettier（ESLintプラグイン経由）
- **コンポーネント命名**: ファイル名 PascalCase、テンプレート内 kebab-case
- **i18n**: vue-i18n。ユーザー向け文字列は全てロケール JSON に定義
- **API呼び出し**: `src/composables/` 経由のみ

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { LaunchResult } from '@/types'

const { t } = useI18n()
const props = defineProps<{ result: LaunchResult }>()
const totalDv = computed(() => props.result.total_rocket_ms)
</script>

<template>
  <div class="dv-result">
    <h3>{{ t('launch.totalRocket') }}</h3>
    <span>{{ totalDv.toFixed(1) }} m/s</span>
  </div>
</template>
```

### Rust（Tauri）

- `cargo fmt` + `cargo clippy` デフォルト設定
- Tauri層は極力薄く。ビジネスロジック禁止
- `tauri-plugin-shell` で Python API プロセスを起動・管理

---

## 計算エンジンのルール

### 物理法則の不変条件

```
μ = geeASL × 9.80665 × radius²
v_escape = √(2μ/R)
v_circular = √(μ/r)
v_escape = √2 × v_circular  （同一高度）
```

### リファレンス値（回帰テスト用）

`calculator.py` または `models.py` 変更後、以下との整合性を必ず確認:

```
天体: Sanctar (Kopernicus config)
  半径:               670,000 m
  geeASL:             1.1 g
  μ:                  4.8424e12 m³/s²
  脱出速度:           3,802.0 m/s        ← この値が変わったらバグ
  海面大気密度:       1.4096 kg/m³
  低軌道速度 (80km):  2,541.1 m/s
  低軌道ΔV (ロケット): ≈3,891 m/s
  低軌道ΔV (ジェット): ≈2,899 m/s
```

### 大気モデリング

- 圧力/温度カーブは **Cubic Hermite Spline** で補間（KSP AnimationCurve 互換）
- 大気密度: `ρ = PM/(RT)` （P: kPa→Pa変換必要。×1000を忘れるな）
- config にカーブデータがある場合、簡易指数減衰モデルで代替禁止

### 経験的推定値

- 重力損失・大気抵抗損失・ジェット節約は推定値
- 理論値と実用値の両方を常に表示
- 推定モデルの前提条件と誤差範囲を docstring に記述

---

## Kopernicus パーサーのルール

- KSP ConfigNode形式: `key = value` + ネスト `{ }`
- 修飾子 `@`, `!`, `+`, `-`, `%` はパース時に除去
- `//` コメント除去
- `!Body[Name]{}` 削除指令はスキップ
- カーブキー: `key = position value [inTangent [outTangent]]` — outTangent省略時は inTangent をコピー
- `#LOC_...` で始まる displayName は `name` にフォールバック
- 不正入力でクラッシュ禁止。スキップして警告

---

## i18n 方針

| 対象 | 方式 | 備考 |
|------|------|------|
| バックエンド | `kopdeltav/i18n.py`（dict） | Accept-Language or `?lang=` |
| フロントエンド | vue-i18n + JSON | `src/i18n/ja.json`, `en.json` |
| CLI (`run.py`) | 日本語ハードコード可 | ユーザー向けクイックツール |

キー命名規則:
```json
{
  "nav": { "title": "KSPDeltaVForMods", "bodies": "天体一覧" },
  "launch": { "title": "低軌道投入ΔV", "orbitalVelocity": "軌道速度" },
  "hohmann": { "title": "ホーマン遷移" },
  "common": { "calculate": "計算", "reset": "リセット" }
}
```

---

## API 設計

RESTful JSON API。スキーマは Pydantic モデル。CORS有効。

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/bodies` | 登録済み天体一覧 |
| GET | `/bodies/{name}` | 天体詳細 |
| POST | `/bodies/manual` | 手動で天体追加 |
| POST | `/upload-config` | .cfg アップロード＆パース |
| POST | `/calc/launch` | 低軌道投入 ΔV |
| POST | `/calc/hohmann` | ホーマン遷移 ΔV |
| POST | `/calc/tsiolkovsky` | 質量比計算 |
| GET | `/atmo-profile/{name}` | 大気プロファイル |

---

## CI（GitHub Actions）

```yaml
# Python
- ruff check kopdeltav/ api.py run.py tests/
- ruff format --check kopdeltav/ api.py run.py tests/
- mypy --strict kopdeltav/
- pytest tests/ -v

# フロントエンド
- cd frontend && pnpm install && pnpm type-check && pnpm lint && pnpm build
```

---

## Git 規約

- **ブランチ**: `feature/xxx`, `fix/xxx`, `docs/xxx`
- **コミット**: Conventional Commits（`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `chore:`）
- **main**: PR必須
- Co-Authored-By を追記してはならない

---

## 開発ワークフロー

```bash
# CLI（依存なし）
python run.py sample_configs/Sanctar.cfg

# バックエンド
pip install -e ".[api,dev]"
uvicorn api:app --reload --port 8000

# フロントエンド
cd frontend && pnpm install && pnpm dev

# Tauri
cd src-tauri && cargo tauri dev

# チェック一括
ruff check . && ruff format --check . && mypy --strict kopdeltav/ && pytest tests/ -v
```

---

## よくある落とし穴

1. **geeASL は g単位。** μ = geeASL × g₀ × R²。密度から質量を導出するな。
2. **圧力カーブは kPa。** 理想気体の式は Pa。×1000 忘れるな。
3. **タンジェントは x軸あたりの傾き。** 正規化値ではない。
4. **`!Body[Kerbin]{}` は削除指令。** パーサーをクラッシュさせるな。
5. **`#LOC_...` タグはパーサーで解決しない。** `name` にフォールバック。
6. **KSP の軌道SMAは実世界より桁違いに小さい。** 実世界基準でバリデーションするな。

---

## プロパティ追加時の更新順序

1. `kopdeltav/models.py` → 2. `parser.py` → 3. `calculator.py` → 4. `api.py` → 5. `frontend/src/types/` → 6. `frontend/src/i18n/` → 7. `tests/`

順序を飛ばすとレイヤー間で型の不整合が発生する。

## 開発時の注意事項
- ライブラリを導入する際は必ず仮想環境を用いる

---

## スコープ外

- KSP2 対応
- リアルタイム KSP 連携（kRPC 等）
- N体軌道最適化
- ポークチョッププロット（将来検討）
- モバイルアプリ
