[English](README.md) | [Bahasa Indonesia](README-id.md)

# KSPDeltaVForMods

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

> KSP1 惑星パックMod向け ΔV 計算ツール（Kopernicus対応）

## 概要

KSPDeltaVForMods は Kopernicus の `.cfg` ファイルを解析し、低軌道投入・ホーマン遷移・脱出速度・質量比などの軌道力学 ΔV を大気モデリング込みで自動計算します。

### なぜ作ったのか

ストック KSP 用の ΔV マップは存在しますが、惑星パックMod用のものはありません。Celestial Harmony のような惑星パックを導入した場合、軌道投入や惑星間遷移に必要な ΔV の参考値がありません。このツールは Mod の Kopernicus 設定ファイルを読み込み、全てを自動計算します。

## 主な機能

- **Kopernicus ConfigNode パーサー** -- 修飾子、コメント、ネストノード、AnimationCurve キーに対応
- **ΔV 計算エンジン** -- 低軌道投入、ホーマン遷移、脱出速度、ツィオルコフスキーのロケット方程式
- **大気モデリング** -- KSP の AnimationCurve 互換の3次エルミート補間
- **対話型 CLI** -- 天体ツリーをナビゲートし、天体間のルート計算が可能
- **GameData スキャナー** -- KSP GameData ディレクトリを再帰的にスキャンし、JSON として保存
- **GUI フロントエンド** -- Vue 3 SPA。8ページ構成、D3.js 地下鉄路線図スタイルの ΔV ルートマップ付き
- **デスクトップアプリ** -- Tauri v2 Windows exe。フロントエンドのツールチェーンは不要

## 技術スタック

| レイヤー | 技術 | 備考 |
|---------|------|------|
| コアライブラリ | Python 3.10+ | 外部依存ゼロ |
| CLI | Python 単体実行 | `python run.py` -- pip 不要 |
| バックエンド API | FastAPI + Uvicorn | `/docs` で Swagger UI |
| フロントエンド | Vue 3 + Vite + TypeScript | PrimeVue Aura Dark、vue-i18n (ja/en/id)、D3.js |
| デスクトップ | Tauri v2 (Rust) | GitHub Releases で Windows exe 配布 |

## はじめ方

### 前提条件

- Python 3.10 以上（デスクトップアプリを含む全モードで必須）

### デスクトップアプリ

最新の Windows `.exe` インストーラーは [GitHub Releases](https://github.com/yuuka-dev/KSPDeltaVForMods/releases) からダウンロードできます。アプリが Python バックエンドを自動起動するため、Python 3.10+ のインストールが必要です。

### CLI の使い方

```bash
git clone https://github.com/yuuka-dev/KSPDeltaVForMods.git
cd KSPDeltaVForMods
python run.py --scan /path/to/KSP/GameData
python run.py --interactive
```

単一の設定ファイルで ΔV を計算することもできます:

```bash
python run.py sample_configs/Sanctar.cfg
```

### フロントエンド開発

```bash
# バックエンド API を起動
pip install -e ".[api,dev]"
uvicorn api:app --reload --port 8000

# フロントエンド開発サーバーを起動
cd frontend && pnpm install && pnpm dev
```

## KSP2 について

このツールは KSP1 + Kopernicus のみを対象としています。KSP2 には対応しておらず、対応する予定もありません。

## ライセンス

[MIT](LICENSE)
