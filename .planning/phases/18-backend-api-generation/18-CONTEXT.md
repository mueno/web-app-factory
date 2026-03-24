# Phase 18: Backend API Generation - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1b を拡張して `backend-spec.json`（エンティティ、リレーション、エンドポイント）を `screen-spec.json` と並行して生成し、Phase 2b に新サブステップを追加して Next.js Route Handlers を `backend-spec.json` から自動生成する。全ルートに Zod バリデーション、標準化エラーレスポンス、ヘルスエンドポイントを含む。BackendSpecValidator ゲートが Zod 欠落・SQL インジェクションパターン・生シークレットを検出してビルドを拒否する。

</domain>

<decisions>
## Implementation Decisions

### backend-spec.json の設計
- エンティティ定義の詳細度は Claude の裁量 — アプリの複雑さに応じてテーブル+カラム+型レベルまたはエンティティ+フィールド名のみを使い分ける
- エンドポイント定義は **CRUD 自動展開** — エンティティごとに CRUD エンドポイントを自動生成し、カスタムエンドポイントを追加定義可能
- `screen-spec.json` と `backend-spec.json` は **相互参照** — 画面が使う API エンドポイントを参照し、エンドポイントがどの画面から呼ばれるかを記録。Phase 1b Gate で整合性検証を行う
- backend-spec.json の生成対象（全アプリ vs バックエンド必要なアプリのみ）は Claude の裁量

### ルート生成戦略
- Claude の裁量 — Phase 2b への新サブステップの位置づけ、Supabase クライアントの Route Handler 内での使い方、Zod スキーマの導出方法は全て Claude が 2026 年 3 月時点のベストプラクティスを調査して決定
- **方針: 最短ルートではなく最良の方式を選択すること。コストより品質を優先**

### エラーレスポンスとヘルスエンドポイント
- **ベストプラクティス優先** — allnew-baas の既存パターンとの互換性より、Next.js + Supabase の 2026 年時点のベストプラクティスを採用
- allnew-baas との共通化は Phase 20（iOS Backend Generation）で対応
- エラー形式 `{ error: string, code: string }`、HTTP ステータスコード規約、`/api/health` の挙動は Claude が最新プラクティスを調査して決定

### BackendSpecValidator ゲート
- **全項目 blocking** — Zod インポート欠落、SQL インジェクションパターン（文字列連結によるクエリ構築）、生シークレット、未検証入力は全てビルド失敗
- 品質を妥協しない — advisory は使わず、全検出項目を blocking として扱う

### Claude's Discretion
- backend-spec.json の JSON スキーマ構造（フィールド名、ネスト構造）
- Phase 2b サブステップの分割方式と実行順序
- Zod スキーマの自動生成パターン（エンティティ定義からの導出方法）
- Route Handler のファイル構成（`app/api/[entity]/route.ts` 等）
- ヘルスエンドポイントのレスポンス形式
- `templates/backend/` ディレクトリの構成（BGEN-07）
- SPEC_AGENT / BUILD_AGENT システムプロンプトへのバックエンド関連指示の追加方法
- Phase 1b Gate の backend-spec ↔ screen-spec 整合性検証の実装方式
- **全ての技術的決定において、2026年3月時点の最新ベストプラクティスを調査し、最良の方式を適用すること**

</decisions>

<specifics>
## Specific Ideas

- **ベストプラクティス調査必須**: リサーチャーは Next.js Route Handlers、Zod バリデーション、Supabase クライアント統合について 2026 年 3 月時点の最新ドキュメントとベストプラクティスを徹底調査すること
- **最良の方式を選択**: 実装の簡易さやコストより品質を優先。最短ルートではなく最良のアプローチを採用する
- BGEN-05: `/api/health` は allnew-baas パターンを参考にしつつ、Next.js のベストプラクティスに合わせる
- BGEN-07: `templates/backend/` は allnew-baas の既存パターン（CORS、レート制限、認証ヘルパー）を参考に抽出
- SECG-03: BackendSpecValidator は `static_analysis_gate.py` と同じ regex ベーススキャンパターンを踏襲可能（既存パターン）

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `phase_1b_executor.py`: `screen-spec.json` + `prd.md` 生成。`backend-spec.json` 生成を追加する拡張先
- `phase_2b_executor.py`: 5ステップ生成プロセス（load_spec → shared_components → pages → integration → validate_packages）。API ルート生成サブステップを追加
- `agents/definitions.py`: SPEC_AGENT（Web spec）+ BUILD_AGENT（Next.js コード生成）。バックエンド関連のシステムプロンプト拡張が必要
- `static_analysis_gate.py`: regex ベースのファイルスキャン（GATE-05, GATE-06, SECG-01）。BackendSpecValidator も同パターンで実装可能
- `supabase_gate.py`: RLS 検証、プロジェクトヘルス確認。バックエンドゲートの参考パターン
- `web_app_factory/templates/`: `supabase-browser.ts.tmpl`, `supabase-server.ts.tmpl` — バックエンドテンプレートもここに配置
- `build_agent_runner.py`: `run_build_agent()` — バックエンド生成サブステップから呼び出し可能

### Established Patterns
- Phase 1b: PRD を先に生成し、そこから screen-spec.json を導出（整合性担保）→ backend-spec.json も同じフローで PRD から導出すべき
- Phase 2b: サブステップごとにフォーカスしたプロンプトを構築（Pitfall 2 回避 — 再生成防止のため前ステップの PRD/spec を含めない）
- Gate: `GateResult(passed=True/False)` + `issues` リスト + `advisories` リスト
- Lazy imports: Phase 3 executor の Supabase 依存と同パターン
- Content injection: 前フェーズの成果物を全文テキストとしてエージェントプロンプトに埋め込み

### Integration Points
- `phase_1b_executor.py`: `_SCREEN_SPEC_PATH` と並列に `_BACKEND_SPEC_PATH` を追加
- `phase_2b_executor.py`: Step 2-3 の間または Step 3 の後に API ルート生成サブステップを挿入
- `contract_pipeline_runner.py`: BackendSpecValidator ゲートタイプの登録/ディスパッチ追加
- `pipeline-contract.web.v1.yaml`: Phase 1b の deliverables に `backend-spec.json` 追加、新ゲート定義追加
- `agents/definitions.py`: SPEC_AGENT と BUILD_AGENT のシステムプロンプトにバックエンド関連指示を追加

</code_context>

<deferred>
## Deferred Ideas

- allnew-baas との API パターン共通化 — Phase 20（iOS Backend Generation）で対応
- OpenAPI スペック自動生成 — Phase 20（IOSB-05）で対応

</deferred>

---

*Phase: 18-backend-api-generation*
*Context gathered: 2026-03-25*
