# Cloudflare R2 Image Pipeline Design

## Goal

Introduce a unified image asset path for two future image sources:

1. manually uploaded images from the admin side
2. remote article cover/thumbnail images discovered by collectors

The storage backend will be Cloudflare R2, and the public delivery domain will be:

- `https://static.cloudbase.eu.org`

The design goal is to make all image consumers use the same CDN-style URL contract, regardless of where the image originally came from.

## Scope

This design covers:

- canonical public image URL structure
- backend data model for image assets
- how uploaded images and mirrored remote images converge into one model
- phased rollout for admin uploads first, collector mirroring second

This design does not cover:

- image editing UI
- signed/private image access
- video assets

## Recommended URL Contract

Use deterministic public paths under `static.cloudbase.eu.org`:

- original asset:
  - `https://static.cloudbase.eu.org/original/<asset-id>.<ext>`
- cover rendition:
  - `https://static.cloudbase.eu.org/cover/<asset-id>.webp`
- thumbnail rendition:
  - `https://static.cloudbase.eu.org/thumb/<asset-id>.webp`

Rationale:

- frontends can choose by intent instead of guessing dimensions
- uploaded and mirrored images share one URL model
- storage backend can change later without changing application-facing URLs

## Asset Model

Use a dedicated `media_assets` table instead of storing only a single `image_url`.

Suggested fields:

- `asset_id`
- `source_kind`
  - `uploaded`
  - `mirrored`
- `source_origin_url`
- `storage_key_original`
- `storage_key_cover`
- `storage_key_thumb`
- `original_url`
- `cover_url`
- `thumb_url`
- `mime_type`
- `width`
- `height`
- `status`
  - `pending`
  - `ready`
  - `failed`
- `content_hash`
- `created_at`
- `updated_at`

Why this model:

- list pages can default to `thumb_url`
- larger cards/details can use `cover_url`
- operators can still inspect `original_url`
- collector-origin images keep provenance via `source_origin_url`

## Integration Points

### Admin Uploads

Admin-uploaded images should become the first supported producer.

Flow:

1. upload image to backend
2. backend stores original in R2
3. backend creates `cover` and `thumb` renditions
4. backend writes `media_assets` row
5. UI receives stable CDN URLs

This is the safest first rollout because it does not depend on collector refactors.

### Collector Mirroring

Collector-discovered article images should be onboarded second.

Flow:

1. collector extracts remote cover/thumbnail candidate URL
2. backend records `source_origin_url`
3. mirror worker fetches and stores asset into R2
4. renditions are generated
5. content rows link to `asset_id`

Do not block the main collector ingestion path on image success for phase one. Text content should still persist if image mirroring fails.

## Content Model Changes

Current collected content does not yet carry first-class cover/thumbnail fields. The recommended direction is:

- content rows point to `asset_id`
- API responses expose:
  - `original_url`
  - `cover_url`
  - `thumb_url`

This keeps rendering logic simple and avoids mixing asset lifecycle into each content table.

## Delivery and Caching

Public delivery is intentionally anonymous and cache-friendly.

Recommendations:

- use `static.cloudbase.eu.org` as the only public asset host
- serve immutable rendition paths
- use long cache headers on renditions
- prefer `webp` for `cover` and `thumb`
- preserve original format only for `original`

This gives good repeat-visit performance and keeps frontend rendering predictable.

## Rollout Plan

### Phase 1

- add `media_assets` table
- add backend support for R2 upload + `original/cover/thumb`
- add admin upload flow
- render uploaded images via CDN URLs

### Phase 2

- extend collectors to extract remote image candidates
- persist `source_origin_url`
- add asynchronous mirroring into R2
- expose mirrored asset URLs in collected APIs

### Phase 3

- switch feed/card/detail UIs to consume `thumb_url` / `cover_url`
- add retries, failure states, and operator diagnostics

## Recommendation

Start with admin uploads first, then add collector mirroring.

Reason:

- lower operational risk
- easier to validate the R2 path contract
- avoids entangling image infrastructure rollout with collector ingestion reliability

Once the upload path is stable, collector-side mirroring can reuse the same asset model and public URL scheme without introducing a second image system.
