# Phase 16: MCP Infrastructure Hardening - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

既存7つの waf_* ツールを stdio + HTTP のデュアルエントリポイントアーキテクチャに整備し、全ツールにアノテーションを付与し、セキュリティ不変条件を CI でロックする。新しいツールの追加はスコープ外。

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

ユーザーは全領域を Claude の裁量に委ねた。以下の判断は研究・計画フェーズで最適解を選択する。

**ツール安全分類:**
- 7つの waf_* ツールそれぞれの readOnlyHint / destructiveHint / openWorldHint の値
- OpenAI Apps SDK の仕様に準拠した適切な分類を選択

**HTTP 認証方針:**
- 外部クライアント（ChatGPT等）がHTTPエンドポイントにアクセスする際の認証方式
- OpenAI が推奨する認証パターンに従う

**共有ロジック分離の粒度:**
- mcp_server.py (406行) からのロジック抽出方法
- 既存ヘルパーモジュール（_pipeline_bridge.py, _progress_store.py 等）との整合性を維持

**エラーハンドリング方針:**
- stdio と HTTP で異なるエラー表現の統一方法
- ビジネスロジック層では統一エラー、トランスポート層で変換するパターンを想定

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `mcp_server.py` (406行): 7ツール全て async, FastMCP >=3.1.0 使用
- `_input_validator.py`: 入力バリデーション（null byte, shell injection, path traversal 防止）
- `_pipeline_bridge.py`: 非同期ラッパー（ThreadPoolExecutor, run ID 生成）
- `_progress_store.py`: スレッドセーフなイベントストア（シングルトン）
- `_status_formatter.py`: Markdown フォーマッター（GSD シンボル対応）
- `_dev_server.py`: dev server ライフサイクル管理
- `_env_checker.py`: 環境チェック（Node, npm, Python, deploy CLI）
- `_keychain.py`: macOS Keychain 統合

### Established Patterns
- Lazy imports: 循環依存回避のため関数内 import
- モジュールレベルシングルトン: _STORE, _REGISTRY, _EXECUTOR
- Async wrapping: `run_in_executor()` で同期コードをラップ
- Markdown 出力: 全ツール出力はステータス表・プログレスバー付き Markdown

### Integration Points
- `tests/test_mcp_server_tool_names.py`: waf_ プレフィックス CI 検証（stdio のみ — HTTP 拡張が必要）
- `tools/factory_mcp_server.py`: 内部 MCP サーバー（別名前空間, waf_ なし）
- `pyproject.toml`: console_scripts エントリポイント定義

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-mcp-infrastructure-hardening*
*Context gathered: 2026-03-24*
