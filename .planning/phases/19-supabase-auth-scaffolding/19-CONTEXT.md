# Phase 19: Supabase Auth Scaffolding - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

生成アプリに完全なパスキー認証 + Google/Apple OAuth を統合する。@supabase/ssr を使った Cookie ベースセッション管理、middleware.ts による自動セッションリフレッシュ、保護ルートパターン、サインイン/サインアップ/サインアウトページを生成する。Supabase Management API で OAuth プロバイダーを自動有効化し、手動設定は Google Cloud Console / Apple Developer Portal 側のみ。

**要件変更:** 元の AUTH-01〜06 はメール/パスワード前提だったが、パスキー + OAuth に変更。AUTH-03（サインイン/サインアップページ）とAUTH-05（Google OAuthのみ→Google + Apple）が大幅に変わる。

</domain>

<decisions>
## Implementation Decisions

### 認証方式
- **パスキー認証を主要方式**として採用 — メール/パスワードは使用しない
- **Google OAuth + Apple Sign-In** を代替手段として提供
- @supabase/auth-ui-react を使用してパスキー登録/認証 + OAuth ボタンを表示
- Supabase の WebAuthn/Passkeys サポートの調査が必要（リサーチャーに委託）

### Auth UI ページ
- @supabase/auth-ui-react で UI を構築（カスタムフォームではなく公式コンポーネント）
- テーマは生成アプリの Tailwind カラーで ThemeSupa をオーバーライド — アプリごとにブランド一貫
- ページ構成: /auth/login, /auth/signup, /auth/signout を app/auth/ 配下に生成

### 保護ルート戦略
- **デフォルト保護** — 全ルートがデフォルトで認証必須。auth_required: false のエンドポイント（/api/health 等）のみ公開
- 未認証アクセス → /auth/login にリダイレクト（returnTo パラメータで元ページに復帰）
- middleware.ts は**全リクエスト**で updateSession() を呼び出し — セッショントークンを自動リフレッシュ
- 保護チェックの実施箇所（Server Component のみ vs Client Component も含む）は Claude の裁量

### Google OAuth / Apple Sign-In スキャフォールド
- **コード生成 + 環境変数チェック + README 手順** の3点セット
- Supabase クライアントの OAuth 呼び出しコード、コールバックハンドラ、UI ボタンを生成
- Supabase **Management API** で Google/Apple プロバイダーを自動有効化（ダッシュボード手動設定不要）
- Google Cloud Console / Apple Developer Portal の設定は README に手順記載（.p8 キー取得等）
- waf_check_env で Google/Apple OAuth の環境変数が設定されているか検証 — 未設定ならガイダンス表示
- **Apple Sign-In は Google と同等のスキャフォールド深度** — Developer Portal 自動化は v4.0 に据え置き

### セッションエッジケース
- リフレッシュ失敗 → **サイレントにログインページへリダイレクト**（エラーメッセージなし）
- マルチタブ/マルチデバイス → **Cookie ベースの Supabase SSR 標準動作**に任せる（特別な実装不要）
- サインアウト → **signOut({ scope: 'global' })** で全デバイスのセッション無効化 + / にリダイレクト

### Claude's Discretion
- パスキー + @supabase/auth-ui-react の統合パターン（WebAuthn サポート状況次第で最適化）
- 保護ルートのチェック箇所（Server Component のみ vs Client Component 併用）
- OAuth コールバックの実装パターン（/auth/callback ルートの構造）
- Management API でのプロバイダー設定の具体的なペイロード
- SPEC_AGENT / BUILD_AGENT プロンプトへの認証指示の追加方法
- **全ての技術的決定において、2026年3月時点のベストプラクティスを調査して最良の方式を適用すること**

</decisions>

<specifics>
## Specific Ideas

- パスキー認証は Supabase の WebAuthn サポートに依存 — リサーチャーが 2026年3月時点の対応状況を徹底調査すること
- @supabase/auth-ui-react がパスキーをサポートしていない場合、カスタムコンポーネントが必要になる可能性 — リサーチ結果に基づいて判断
- Phase 17 で生成済みの supabase-server.ts テンプレートは service_role キー使用 — Auth 用にはanon キーの supabase-browser.ts を使う認識を明確にすること
- waf_check_env の OAuth 環境変数チェックは Phase 17 の Supabase チェックパターン（_env_checker.py）を踏襲

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web_app_factory/templates/supabase-server.ts.tmpl`: createServerClient + Cookie ハンドリング済み — middleware.ts と保護ルートで再利用可能
- `web_app_factory/templates/supabase-browser.ts.tmpl`: createBrowserClient — クライアントサイド認証で使用
- `web_app_factory/templates/backend/with-validation.ts.tmpl`: Zod バリデーション HOF — auth ミドルウェアと統合可能
- `_env_checker.py` (479行): check_env() — OAuth 環境変数チェック追加先
- `_supabase_provisioner.py`: Management API 呼び出しパターン — OAuth プロバイダー自動設定に再利用可能
- `agents/definitions.py`: SPEC_AGENT / BUILD_AGENT — 認証関連指示の追加先（AUTH-06）

### Established Patterns
- Phase 17 の SupabaseProvisioner: Management API + httpx.AsyncClient → OAuth プロバイダー設定にも同じパターン
- Phase 18 の optional sub-step: backend-spec.json 不在時のスキップ → OAuth 設定不在時のスキップにも適用可能
- Phase 2b のサブステップ構成: 認証ページ生成を新サブステップとして追加
- backend-spec.json の auth_required フィールド: 保護ルート判定のデータソース

### Integration Points
- `phase_2b_executor.py`: 認証ページ生成サブステップを追加（generate_api_routes の後）
- `phase_3_executor.py`: Supabase プロビジョニング時に OAuth プロバイダー自動設定を追加
- `_env_checker.py`: Google/Apple OAuth の環境変数チェック追加
- `agents/definitions.py`: SPEC_AGENT に「Supabase DB 使用時は Supabase Auth を優先」指示追加
- `middleware.ts` テンプレート: 新規作成（templates/ 配下）
- `app/auth/*` テンプレート: 新規作成（login, signup, signout, callback ページ）

</code_context>

<deferred>
## Deferred Ideas

- Apple Developer Portal の完全自動化（.p8 キー取得等）→ v4.0 ADV-01
- Apple Sign-In の p8 キー自動プロビジョニング → v4.0 ADV-01
- メール/パスワード認証 → 現時点では不採用（パスキー + OAuth で十分）

</deferred>

---

*Phase: 19-supabase-auth-scaffolding*
*Context gathered: 2026-03-25*
