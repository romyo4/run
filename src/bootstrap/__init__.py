"""AI Development Pipeline 配線層(Phase 0)。

外部サービス(GitHub/Slack/Discord/Codex/Fable)に接続せずとも、21モジュール
(M00〜M21、M18はM03への統合により欠番)の実装コード同士を接続し、1つの
Workflowが最後まで流れることを実証する。うちFoundation(M00)は全モジュールが
依存する共通基盤であり、それ自体は実行時にインスタンス化されるコンポーネントでは
ないため、`bootstrap.wiring.Application`が実行時に構築するのはFoundationを
除く20モジュールとなる(詳細は`bootstrap.wiring`参照)。
"""
