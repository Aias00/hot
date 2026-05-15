---
created: 2026-05-15
status: completed
---

# About Page Admin Design

## Overview

Add an admin-editable "About" page that displays WeChat Official Account information with a full-screen background.

## Requirements

1. About page with full-screen background (keep sidebar navigation)
2. Display WeChat Official Account: title, description, QR code, follow link, contact info
3. Admin page to edit about page content
4. Data persisted in SQLite

## Database

New table `about_config` in SQLite:

```sql
CREATE TABLE about_config (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  qr_code_url TEXT NOT NULL DEFAULT '',
  follow_link TEXT NOT NULL DEFAULT '',
  contact_info TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

- `GET /api/about` - Get about page config (public)
- `PUT /api/admin/about` - Update about page config (admin)

## Frontend

- `AboutPage.jsx` - Full-screen background page, fetches config from API
- `AdminPage.jsx` - Form to edit about page config
- Routes: `/about`, `/admin`

## Implementation Steps

1. Add `about_config` table to SQLite schema
2. Add `get_about_config()` and `update_about_config()` to `sqlite_store.py`
3. Add `/api/about` and `/api/admin/about` routes to `routes.py`
4. Create `AboutPage.jsx` with full-screen background styling
5. Create `AdminPage.jsx` with edit form
6. Add routes to `AppRouter.jsx`
7. Add "About" link to sidebar navigation
8. Add "Admin" link to sidebar (or separate entry point)
