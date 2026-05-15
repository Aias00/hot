from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from hot_backend.sqlite_store import get_store

router = APIRouter()


class AboutConfigUpdate(BaseModel):
    title: str = ""
    description: str = ""
    qr_code_url: str = ""
    follow_link: str = ""
    contact_info: str = ""


@router.get("/api/navigation")
def get_navigation() -> list[dict]:
    """Get navigation items for frontend."""
    return get_store().list_navigation_items()


@router.get("/api/nav-hub")
def get_nav_hub() -> list[dict]:
    """Get nav hub categories with links for frontend."""
    categories = get_store().list_nav_hub_categories()
    # Filter enabled categories and links
    return [
        {
            "id": cat["id"],
            "name": cat["name"],
            "icon": cat["icon"],
            "color": cat["color"],
            "links": [link for link in cat["links"] if link["enabled"]],
        }
        for cat in categories
        if cat["enabled"]
    ]


@router.get("/api/feed")
def get_feed(
    q: str = Query(default=""),
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> dict:
    return get_store().get_feed_items(query=q, page=page, limit=limit)


@router.get("/api/collected")
def get_collected(
    q: str = Query(default=""),
    source_id: str | None = Query(default=None),
    source_ids: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    sort: str = Query(default="date"),
    dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    payload = get_store().get_collected_items(
        query=q,
        source_id=source_id,
        source_ids=source_ids.split(",") if source_ids else None,
        tag=tag,
        from_date=from_date,
        to_date=to_date,
        sort=sort,
        direction=dir,
        page=page,
        limit=limit,
    )
    return payload


@router.get("/api/daily")
def get_daily(
    view: str = Query(default="issue"),
    date: str = Query(default="2026-05-08"),
) -> dict:
    return get_store().get_daily_snapshot(view=view, date=date)


@router.get("/api/mp")
def get_mp(
    q: str = Query(default=""),
    since: str = Query(default="30d"),
    page: int = Query(default=1, ge=1),
) -> dict:
    return get_store().get_mp_snapshot(query=q, since=since, page=page)


@router.get("/api/about")
def get_about() -> dict:
    return get_store().get_about_config()


@router.put("/api/admin/about")
def update_about(config: AboutConfigUpdate) -> dict:
    return get_store().update_about_config(
        title=config.title,
        description=config.description,
        qr_code_url=config.qr_code_url,
        follow_link=config.follow_link,
        contact_info=config.contact_info,
    )
