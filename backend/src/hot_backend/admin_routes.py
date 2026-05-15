"""Admin panel API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from hot_backend.auth import (
    TokenResponse,
    LoginRequest,
    check_admin_password,
    create_token,
    get_current_admin,
    verify_token,
)
from hot_backend.auth import TokenPayload

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ==================== Authentication ====================


@router.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest) -> TokenResponse:
    """Login with admin password to get JWT token."""
    if not check_admin_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )
    return create_token()


@router.get("/auth/verify")
def verify(
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Verify if the current token is valid."""
    return {"valid": True}


# ==================== Sources Management ====================


@router.get("/sources")
def list_sources(
    _: TokenPayload = Depends(get_current_admin),
) -> list[dict]:
    """List all collector sources."""
    from hot_backend.sqlite_store import get_store

    return get_store().list_sources()


@router.get("/sources/{source_id}")
def get_source(
    source_id: str,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Get a specific source by ID."""
    from hot_backend.sqlite_store import get_store

    source = get_store().get_source(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found",
        )
    return source


@router.post("/sources")
def create_source(
    source: dict,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Create a new source."""
    from hot_backend.sqlite_store import get_store

    return get_store().create_source(source)


@router.put("/sources/{source_id}")
def update_source(
    source_id: str,
    source: dict,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Update an existing source."""
    from hot_backend.sqlite_store import get_store

    store = get_store()
    existing = store.get_source(source_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found",
        )
    return store.update_source(source_id, source)


@router.delete("/sources/{source_id}")
def delete_source(
    source_id: str,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Delete a source."""
    from hot_backend.sqlite_store import get_store

    store = get_store()
    existing = store.get_source(source_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found",
        )
    store.delete_source(source_id)
    return {"deleted": True}


@router.patch("/sources/{source_id}/toggle")
def toggle_source(
    source_id: str,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Toggle source enabled status."""
    from hot_backend.sqlite_store import get_store

    store = get_store()
    existing = store.get_source(source_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found",
        )
    new_enabled = not existing.get("enabled", True)
    return store.update_source(source_id, {"enabled": new_enabled})


# ==================== Navigation Management ====================


@router.get("/navigation")
def list_navigation(
    _: TokenPayload = Depends(get_current_admin),
) -> list[dict]:
    """List all navigation items."""
    from hot_backend.sqlite_store import get_store

    return get_store().list_navigation_items()


@router.post("/navigation")
def create_navigation_item(
    item: dict,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Create a new navigation item."""
    from hot_backend.sqlite_store import get_store

    return get_store().create_navigation_item(item)


@router.put("/navigation/{item_id}")
def update_navigation_item(
    item_id: int,
    item: dict,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Update an existing navigation item."""
    from hot_backend.sqlite_store import get_store

    store = get_store()
    existing = store.get_navigation_item(item_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Navigation item '{item_id}' not found",
        )
    return store.update_navigation_item(item_id, item)


@router.delete("/navigation/{item_id}")
def delete_navigation_item(
    item_id: int,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Delete a navigation item."""
    from hot_backend.sqlite_store import get_store

    store = get_store()
    existing = store.get_navigation_item(item_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Navigation item '{item_id}' not found",
        )
    store.delete_navigation_item(item_id)
    return {"deleted": True}


@router.patch("/navigation/{item_id}/toggle")
def toggle_navigation_item(
    item_id: int,
    _: TokenPayload = Depends(get_current_admin),
) -> dict:
    """Toggle navigation item enabled status."""
    from hot_backend.sqlite_store import get_store

    store = get_store()
    existing = store.get_navigation_item(item_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Navigation item '{item_id}' not found",
        )
    new_enabled = not existing.get("enabled", True)
    return store.update_navigation_item(item_id, {"enabled": new_enabled})


@router.put("/navigation/reorder")
def reorder_navigation(
    items: list[dict],
    _: TokenPayload = Depends(get_current_admin),
) -> list[dict]:
    """Reorder navigation items. Expects [{'id': 1, 'sort_order': 0}, ...]"""
    from hot_backend.sqlite_store import get_store

    store = get_store()
    for item in items:
        store.update_navigation_item(item["id"], {"sort_order": item["sort_order"]})
    return store.list_navigation_items()
