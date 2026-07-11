# AI Development Pipeline

AIエージェントが要件整理・計画立案・設計・設計監査・実装・テスト・レビュー・PR作成・定期レビューを役割分担して実施する、MVP優先の自律開発パイプライン。

Design Freeze v1.0 完了済み。詳細は `docs/DESIGN_FREEZE_v1.0.md` / `docs/CHANGELOG.md` を参照。

## ディレクトリ構成

```text
docs/                 引継ぎ資料・CHANGELOG・Design Freeze宣言
design/               モジュール詳細設計書(M00〜M21)
implementation_spec/  実装仕様書(IS00〜IS21)
src/                  実装コード(モジュール単位のパッケージ)
tests/                Unit Test(モジュール単位、srcと対称構成)
config/               実行時設定ファイル
```

## モジュール構成

21モジュール(M00 Foundation 〜 M21 Slack/Discord Connector、M18はM03へ統合し欠番)。各モジュールの責務は `design/` 配下の詳細設計書を正とする。

## 開発規約

- Python 3.13
- 型ヒント必須、dataclass積極利用、pathlib使用、標準`logging`使用、`unittest`使用
- UTF-8、Ruff、Black
- 設計書に無い機能を推測で追加しない(MVP First / Design Before Code)

## テスト実行

```bash
python -m unittest discover -s tests
```

## Lint / Format

```bash
ruff check src tests
black --check src tests
```
