# Pipeline Handoff: airbnb

- **Run ID**: `20260322-035830-airbnb`
- **Status**: failed
- **Started**: 2026-03-22T03:58:30.795058+00:00
- **Current Phase**: 3
- **Project Dir**: `/Users/masa/Development/web-app-factory/output/airbnb`

## Idea

温泉旅館に特化したAirBnBみたいな旅行予約サイト

## Phase Progress

| Phase | Status | Started | Completed | Artifacts |
|-------|--------|---------|-----------|-----------|
| 1a: Idea Validation | completed | 2026-03-22T03:58:30.841052+00:00 | 2026-03-22T04:05:52.818465+00:00 | /Users/masa/Development/web-app-factory/output/airbnb/docs/pipeline/idea-validation.md, /Users/masa/Development/web-app-factory/output/airbnb/docs/pipeline/tech-feasibility-memo.json |
| 1b: Spec & Design | completed | 2026-03-22T04:05:52.885536+00:00 | 2026-03-22T04:18:12.069390+00:00 | /Users/masa/Development/web-app-factory/output/airbnb/docs/pipeline/prd.md, /Users/masa/Development/web-app-factory/output/airbnb/docs/pipeline/screen-spec.json |
| 2a: Scaffold | completed | 2026-03-22T04:18:12.138227+00:00 | 2026-03-22T04:19:46.164457+00:00 | /Users/masa/Development/web-app-factory/output/airbnb/airbnb |
| 2b: Build | completed | 2026-03-22T04:19:46.230137+00:00 | 2026-03-22T04:41:16.989971+00:00 | /Users/masa/Development/web-app-factory/output/airbnb |
| 3: Ship | failed | 2026-03-22T07:46:33.665069+00:00 | 2026-03-22T05:09:22.588028+00:00 | - |

## Notes

### Phase 3: Ship

FAILED: gate_lighthouse failed after 3 attempt(s). Last issues: Lighthouse performance score 83.0 is below threshold 85
FAILED: gate_lighthouse failed after 3 attempt(s). Last issues: Lighthouse performance score 72.0 is below threshold 85
FAILED: gate_lighthouse failed after 3 attempt(s). Last issues: Lighthouse performance score 72.0 is below threshold 85
FAILED: gate_accessibility failed after 3 attempt(s). Last issues: playwright and axe-playwright-python are required but not installed
FAILED: Security headers gate failed: Missing required security header: Content-Security-Policy; Missing required security header: X-Content-Type-Options; Missing required security header: Referrer-Policy
FAILED: Security headers gate failed: Missing required security header: Content-Security-Policy; Missing required security header: X-Content-Type-Options; Missing required security header: Referrer-Policy

