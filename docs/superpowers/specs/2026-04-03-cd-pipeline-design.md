# CD Pipeline Design Spec

**Date**: 2026-04-03
**Status**: Approved

---

## Overview

タグ push をトリガーに、Tauri デスクトップアプリの自動ビルド・GitHub Release 公開を行う CD パイプライン。リリーススクリプトでバージョン更新・CHANGELOG 生成・タグ作成を一括実行する。

---

## Release Script (`scripts/release.sh`)

### Usage

```bash
./scripts/release.sh 1.0.0
```

### Steps

1. バージョン引数のバリデーション（semver 形式チェック）
2. `src-tauri/tauri.conf.json` の `"version"` を更新
3. `pyproject.toml` の `version` を更新（存在する場合）
4. 前回タグ〜HEAD の Conventional Commits から CHANGELOG.md を生成・先頭に追記
5. 変更をステージ・コミット: `chore(release): v{VERSION}`
6. `v{VERSION}` タグを作成
7. `git push origin HEAD --tags`

### Validation

- 引数なしで実行 → usage 表示して終了
- semver 形式でなければエラー
- working tree が dirty ならエラー（未コミットの変更がある場合）
- 同名タグが既存ならエラー

---

## CHANGELOG Generation

### Format: Keep a Changelog

```markdown
# Changelog

## [1.0.0] - 2026-04-03

### Added
- 新しいΔV計算エンジン (feat: ...)

### Fixed
- パーサーのクラッシュを修正 (fix: ...)

### Changed
- パフォーマンス改善 (perf: ...)
```

### Conventional Commits → Section Mapping

| Commit prefix | Section | Include |
|---------------|---------|---------|
| `feat` | Added | Yes |
| `fix` | Fixed | Yes |
| `update` | Changed | Yes |
| `refactor` | Changed | Yes |
| `perf` | Changed | Yes |
| `docs` | Documentation | Yes |
| `chore` | — | No |
| `ci` | — | No |
| `test` | — | No |
| `style` | — | No |

### Rules

- scope を括弧内に表示: `feat(parser):` → `**parser**: description`
- 同一セクション内はアルファベット順ソート
- セクションが空なら省略
- 初回リリース（前回タグなし）はすべてのコミットを含む

---

## GitHub Actions (`release.yml`)

### Trigger

```yaml
on:
  push:
    tags:
      - "v*"
```

### Jobs

#### build-windows

1. Checkout
2. Setup pnpm, Node.js, Rust
3. タグからバージョン抽出 (`${GITHUB_REF_NAME#v}`)
4. `tauri.conf.json` のバージョンがタグと一致することを検証（不一致ならfail）
5. Frontend: `pnpm install --frozen-lockfile && pnpm build`
6. `cargo install tauri-cli`
7. `cargo tauri build --bundles nsis`
8. CHANGELOG.md から該当バージョンのセクションを抽出（`## [X.Y.Z]` ブロック）
9. Upload artifact (NSIS exe)
10. GitHub Release 作成: **draft: false**, body = CHANGELOG セクション

### Version Verification Step

```yaml
- name: Verify version matches tag
  run: |
    TAG_VERSION="${GITHUB_REF_NAME#v}"
    CONF_VERSION=$(grep -o '"version": "[^"]*"' src-tauri/tauri.conf.json | head -1 | cut -d'"' -f4)
    if [ "$TAG_VERSION" != "$CONF_VERSION" ]; then
      echo "::error::Tag version ($TAG_VERSION) does not match tauri.conf.json ($CONF_VERSION)"
      exit 1
    fi
  shell: bash
```

### CHANGELOG Extraction Step

```yaml
- name: Extract changelog for this version
  id: changelog
  run: |
    VERSION="${GITHUB_REF_NAME#v}"
    BODY=$(sed -n "/^## \[${VERSION}\]/,/^## \[/{ /^## \[${VERSION}\]/d; /^## \[/d; p; }" CHANGELOG.md)
    echo "body<<EOF" >> "$GITHUB_OUTPUT"
    echo "$BODY" >> "$GITHUB_OUTPUT"
    echo "EOF" >> "$GITHUB_OUTPUT"
  shell: bash
```

---

## File Map

### Create

| File | Responsibility |
|------|---------------|
| `scripts/release.sh` | リリーススクリプト（バージョン更新 + CHANGELOG + タグ + push） |
| `CHANGELOG.md` | 初回はスクリプトが生成 |

### Modify

| File | Changes |
|------|---------|
| `.github/workflows/release.yml` | バージョン検証、CHANGELOG body、draft: false |

---

## Out of Scope

- Linux / macOS ビルド
- 自動 semver bump（major/minor/patch 自動判定）
- npm / PyPI publish
- Pre-release / beta チャンネル
