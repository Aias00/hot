# Cloudflare R2 Image Pipeline Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-ready media asset foundation backed by Cloudflare R2 and `static.cloudbase.eu.org`, then use it for admin-side image uploads so uploaded images already follow the final public URL contract.

**Architecture:** Phase 1 creates a new `media_assets` backend slice with three responsibilities: persist media metadata in SQLite, upload originals plus generated renditions to R2, and expose a simple admin upload API. The first UI integration is the existing “关于页面” admin screen, which will upload an image and save the returned CDN URL into `about_config.qr_code_url` without changing the public about page contract.

**Tech Stack:** FastAPI, SQLite, existing `curl_cffi` runtime dependency for HTTPS requests, standard-library image metadata helpers, React admin form, Cloudflare R2, `static.cloudbase.eu.org`

---

## File Structure

### New files

- `backend/src/hot_backend/media_assets.py`
  - Runtime service for media asset ID generation, R2 key generation, public CDN URL construction, and upload orchestration.
- `backend/src/hot_backend/media_variants.py`
  - Image validation and rendition planning helpers (`original`, `cover`, `thumb`), with deterministic size/format rules.
- `backend/tests/test_media_assets.py`
  - Backend-focused tests for SQLite persistence, CDN URL generation, upload endpoint behavior, and about-page integration helpers.
- `src/pages/admin/AboutPageAdmin.test.jsx`
  - UI regression test for the new upload interaction on the about admin screen.
- `docs/superpowers/specs/2026-05-18-r2-image-pipeline-design.md`
  - Existing spec reference, not modified by this plan unless the implementation exposes a real mismatch.

### Modified files

- `backend/src/hot_backend/sqlite_store.py`
  - Add `media_assets` table creation and CRUD helpers.
- `backend/src/hot_backend/admin_routes.py`
  - Add authenticated media upload endpoint and wire uploaded asset URLs into the about admin flow.
- `backend/src/hot_backend/routes.py`
  - Keep public about response shape stable, but ensure it can surface uploaded CDN-backed URLs.
- `backend/pyproject.toml`
  - Only modify if a runtime dependency is absolutely unavoidable. Current plan assumes **no new runtime dependencies**.
- `backend/.env.example`
  - Add R2/CDN configuration placeholders.
- `src/pages/admin/AboutPageAdmin.jsx`
  - Add upload button/input, upload state, and “use uploaded image” flow.
- `README.md`
  - Document new required R2 env vars and the admin upload flow.

## Implementation Constraints

- No new runtime dependency unless absolutely necessary. Prefer existing production deps plus standard library.
- Uploaded images and future mirrored collector images must share one URL contract from day one.
- Phase 1 must not block later collector mirroring design; it should add the asset foundation without entangling collector ingestion logic.
- Public about page should continue consuming `qr_code_url`; Phase 1 should route uploads into that existing field rather than redesigning the public API.

## URL and Storage Contract

- Original: `https://static.cloudbase.eu.org/original/<asset-id>.<ext>`
- Cover: `https://static.cloudbase.eu.org/cover/<asset-id>.webp`
- Thumb: `https://static.cloudbase.eu.org/thumb/<asset-id>.webp`

Suggested env vars:

- `MEDIA_CDN_BASE_URL=https://static.cloudbase.eu.org`
- `R2_ACCOUNT_ID=...`
- `R2_BUCKET=...`
- `R2_ACCESS_KEY_ID=...`
- `R2_SECRET_ACCESS_KEY=...`

## Task 1: Add Media Asset Schema and Service Skeleton

**Files:**
- Create: `backend/src/hot_backend/media_assets.py`
- Create: `backend/src/hot_backend/media_variants.py`
- Modify: `backend/src/hot_backend/sqlite_store.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_media_assets.py`

- [ ] **Step 1: Write the failing backend schema/service tests**

Add tests that assert:

```python
def test_media_asset_urls_follow_static_cloudbase_contract():
    asset = build_asset_descriptor(asset_id="abc123", original_ext="png")
    assert asset["original_url"] == "https://static.cloudbase.eu.org/original/abc123.png"
    assert asset["cover_url"] == "https://static.cloudbase.eu.org/cover/abc123.webp"
    assert asset["thumb_url"] == "https://static.cloudbase.eu.org/thumb/abc123.webp"

def test_media_asset_row_can_be_persisted_and_loaded(store):
    payload = {
        "asset_id": "abc123",
        "source_kind": "uploaded",
        "source_origin_url": None,
        "storage_key_original": "original/abc123.png",
        "storage_key_cover": "cover/abc123.webp",
        "storage_key_thumb": "thumb/abc123.webp",
    }
    created = store.create_media_asset(payload)
    assert created["asset_id"] == "abc123"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest -q backend/tests/test_media_assets.py
```

Expected:
- fail because `media_assets.py` and new store methods do not exist yet

- [ ] **Step 3: Add the schema and minimal storage/service implementation**

Implement:

- `media_assets` table in `sqlite_store.py`
- `create_media_asset()`
- `get_media_asset()`
- `list_media_assets()` if useful for admin debugging
- `build_asset_descriptor()` / `build_public_urls()` in `media_assets.py`

Keep the initial implementation narrow:

```python
def build_public_urls(asset_id: str, original_ext: str, base_url: str) -> dict[str, str]:
    base = base_url.rstrip("/")
    return {
        "original_url": f"{base}/original/{asset_id}.{original_ext}",
        "cover_url": f"{base}/cover/{asset_id}.webp",
        "thumb_url": f"{base}/thumb/{asset_id}.webp",
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run --project backend pytest -q backend/tests/test_media_assets.py
```

Expected:
- schema and URL contract tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/src/hot_backend/media_assets.py backend/src/hot_backend/media_variants.py backend/src/hot_backend/sqlite_store.py backend/.env.example backend/tests/test_media_assets.py
git commit -m "feat: add media asset schema and URL contract"
```

## Task 2: Add Admin Upload Endpoint Backed by R2

**Files:**
- Modify: `backend/src/hot_backend/admin_routes.py`
- Modify: `backend/src/hot_backend/media_assets.py`
- Modify: `backend/src/hot_backend/media_variants.py`
- Test: `backend/tests/test_media_assets.py`
- Docs: `README.md`

- [ ] **Step 1: Write the failing upload API tests**

Add tests for an authenticated upload endpoint:

```python
def test_admin_media_upload_returns_asset_payload(client, auth_headers, monkeypatch):
    monkeypatch.setattr("hot_backend.media_assets.upload_to_r2", fake_upload)
    response = client.post(
        "/api/admin/media-assets/upload",
        headers=auth_headers,
        files={"file": ("qr.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["asset_id"]
    assert body["original_url"].startswith("https://static.cloudbase.eu.org/")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest -q backend/tests/test_media_assets.py::test_admin_media_upload_returns_asset_payload
```

Expected:
- fail because the endpoint and upload service do not exist yet

- [ ] **Step 3: Implement upload orchestration**

Implementation target:

- `POST /api/admin/media-assets/upload`
- validate mime type and size
- derive `asset_id`
- upload original to R2
- produce `cover` and `thumb` renditions
- persist `media_assets` row
- return payload:

```json
{
  "asset_id": "abc123",
  "source_kind": "uploaded",
  "original_url": "...",
  "cover_url": "...",
  "thumb_url": "...",
  "width": 512,
  "height": 512,
  "mime_type": "image/png",
  "status": "ready"
}
```

Use an internal service boundary so R2 PUT logic and SQLite persistence stay testable independently.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run --project backend pytest -q backend/tests/test_media_assets.py
```

Expected:
- upload endpoint tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/src/hot_backend/admin_routes.py backend/src/hot_backend/media_assets.py backend/src/hot_backend/media_variants.py backend/tests/test_media_assets.py README.md
git commit -m "feat: add admin R2 media upload endpoint"
```

## Task 3: Connect About Admin to Uploaded Asset URLs

**Files:**
- Modify: `src/pages/admin/AboutPageAdmin.jsx`
- Create: `src/pages/admin/AboutPageAdmin.test.jsx`
- Modify: `backend/src/hot_backend/routes.py`
- Modify: `backend/src/hot_backend/admin_routes.py`
- Test: `src/pages/admin/AboutPageAdmin.test.jsx`

- [ ] **Step 1: Write the failing About admin UI test**

Test the intended flow:

```jsx
it("uploads an image and stores returned CDN URL into qr_code_url", async () => {
  render(<AboutPageAdmin />);
  await user.upload(screen.getByLabelText("上传二维码图片"), file);
  expect(await screen.findByDisplayValue("https://static.cloudbase.eu.org/original/")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
npm test -- src/pages/admin/AboutPageAdmin.test.jsx
```

Expected:
- fail because there is no upload control or upload flow yet

- [ ] **Step 3: Implement the minimal admin UI integration**

Add to `AboutPageAdmin.jsx`:

- file input
- upload button/state
- success message
- on success, write returned `original_url` (or chosen rendition URL) into `config.qr_code_url`

Recommended first-pass behavior:

- use the uploaded asset’s `original_url` for QR fidelity
- keep existing manual URL field available
- show the current uploaded preview if `qr_code_url` is present

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
npm test -- src/pages/admin/AboutPageAdmin.test.jsx
npm run build
```

Expected:
- UI upload test passes
- app still builds cleanly

- [ ] **Step 5: Commit**

```bash
git add src/pages/admin/AboutPageAdmin.jsx src/pages/admin/AboutPageAdmin.test.jsx backend/src/hot_backend/routes.py backend/src/hot_backend/admin_routes.py
git commit -m "feat: connect about admin to uploaded media assets"
```

## Task 4: Verify Phase 1 End-to-End and Leave Collector Path Prepared

**Files:**
- Modify: `README.md`
- Modify: `progress.md`
- Test: existing backend/frontend suites

- [ ] **Step 1: Add env/config documentation**

Document:

- required R2 env vars
- expected public CDN domain
- admin upload usage
- which URL (`original`, `cover`, `thumb`) should be used for QR vs future list cards

- [ ] **Step 2: Run full verification**

Run:

```bash
npm test
npm run build
```

Expected:
- frontend tests pass
- backend tests pass
- production build passes

- [ ] **Step 3: Manual local verification**

Check locally:

1. admin login works
2. upload image in `/admin/about`
3. returned URL is under `https://static.cloudbase.eu.org/...`
4. save succeeds
5. public `/about` renders the uploaded QR image

- [ ] **Step 4: Record rollout notes**

Add a short `progress.md` note describing:

- R2/CDN env vars added
- admin uploads now use the unified asset contract
- collector mirroring intentionally deferred to the next phase

- [ ] **Step 5: Commit**

```bash
git add README.md progress.md
git commit -m "docs: record phase 1 R2 image pipeline rollout"
```

## Phase 2 Follow-up (Separate Plan)

Do **not** implement collector mirroring in this plan. The next plan should cover:

- extractor support for remote image candidate URLs
- async mirror worker
- content-to-asset linkage in collected APIs
- list/detail UI consumption of `thumb_url` / `cover_url`

