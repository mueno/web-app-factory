# Phase 17: Supabase Provisioning - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Supabase Management API を使ってプロジェクトを自動プロビジョニングし、RLS デフォルトのマイグレーションを適用し、クレデンシャルを注入し、生成アプリにデュアルクライアントファイルを生成する。加えて、全クレデンシャル管理を banto ベースに統一する。

</domain>

<decisions>
## Implementation Decisions

### クレデンシャル管理 — banto 統一
- `_keychain.py` を banto (`SecureVault`) ベースにリファクタ — 全クレデンシャル（Anthropic, Vercel, Supabase）を banto 経由で取得
- banto は**任意依存**（optional dependency）。インストールされていなければ環境変数フォールバック
- Supabase クレデンシャルは2つのプロバイダーとして banto に保存:
  - `supabase-access-token` — Supabase Management API トークン
  - `supabase-org-id` — Supabase 組織 ID
- 既存の Vercel/Anthropic クレデンシャルも banto プロバイダーにマッピング

### トークン未設定時の動作
- Supabase トークンが未設定のまま `waf_generate_app` を実行した場合は**即座にエラー**
- `waf_check_env` で事前確認を促すメッセージを表示（banto store コマンドまたは環境変数設定のガイダンス付き）

### Claude's Discretion
- 再実行時の Supabase プロジェクトライフサイクル（新規作成 vs 再利用）
- マイグレーション SQL の生成方式（直接 SQL vs Supabase CLI vs Management API）
- `SupabaseProvisioner` の内部アーキテクチャ
- `supabase_gate.py` の検証項目の実装詳細
- デュアルクライアントパターン（`supabase-browser.ts` / `supabase-server.ts`）のテンプレート構造
- RLS ポリシーのデフォルトパターン
- セキュリティゲート（SECG-01, SECG-02）の実装方式

</decisions>

<specifics>
## Specific Ideas

- banto パッケージ: `/Users/masa/Development/mcp/banto` — `SecureVault` クラスで `vault.get_key(provider='supabase-access-token')` の形式で取得
- banto のフォールバック層: banto がなければ `os.environ.get()` で環境変数から取得（既存パターンの維持）
- banto の CLI: `banto store supabase-access-token` でユーザーがキーを保存

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_keychain.py` (151行): keyring + env-var フォールバック。`_ENV_FALLBACKS` dict で論理名→環境変数マッピング。banto ベースにリファクタ対象
- `_env_checker.py` (479行): `check_env(deploy_target)` でプラットフォーム別ガイダンス。Supabase チェック追加先
- `_tool_impls.py` (293行): `impl_check_env()` — waf_check_env のビジネスロジック
- `agents/definitions.py`: SPEC_AGENT が「Postgres via Neon or Supabase」を既に認識

### Established Patterns
- Lazy imports: 循環依存回避のため関数内 import（banto import もこのパターンに従う）
- Optional dependency: keyring パッケージと同じ try/except import パターンを banto にも適用
- ToolStatus dict: `{tool, status, version_found, version_required, install_command, note}` — Supabase チェックもこの形式で追加
- Security contract: credential VALUES は一切ログ出力しない（`_keychain.py` と同じ契約）

### Integration Points
- `_keychain.py` の `_ENV_FALLBACKS` dict: `supabase_access_token` → `SUPABASE_ACCESS_TOKEN` 等のマッピング追加（banto フォールバック用）
- `_env_checker.py` の `check_env()`: `deploy_target` に "supabase" 関連チェック追加
- `pyproject.toml`: banto を optional dependency として追加
- `tests/test_keychain.py`, `tests/test_env_checker.py`: banto 統合テスト追加

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-supabase-provisioning*
*Context gathered: 2026-03-24*
