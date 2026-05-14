from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from hot_backend.collectors.models import CollectRequest
from hot_backend.collectors.graph import make_collect_state
from hot_backend.collectors.models import SourceConfig

router = APIRouter()
VISIBLE_COLLECT_ADAPTER_KINDS = ("rss-generic",)


class CollectExecuteRequest(BaseModel):
    source_id: str
    limit: int = Field(default=20, ge=1, le=200)
    dry_run: bool = True
    resume: bool = True


class CollectSourceUpsertRequest(BaseModel):
    source_id: str
    adapter_kind: str
    title: str
    description: str
    enabled: bool = True
    base_url: str | None = None
    seed_urls: list[str] = Field(default_factory=list)
    config_json: dict = Field(default_factory=dict)


class CollectSourceUpdateRequest(BaseModel):
    adapter_kind: str | None = None
    title: str | None = None
    description: str | None = None
    enabled: bool | None = None
    base_url: str | None = None
    seed_urls: list[str] | None = None
    config_json: dict | None = None


def _validate_source_payload(payload: dict, *, adapter_kind: str) -> None:
    seed_urls = payload.get("seed_urls") or []

    if adapter_kind == "rss-generic":
        if not seed_urls:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="rss-generic requires at least one seed_urls entry",
            )

        allowed_schemes = {"http", "https", "file"}
        for url in seed_urls:
            scheme = urlparse(url).scheme.lower()
            if scheme not in allowed_schemes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"unsupported rss-generic URL scheme: {url}",
                )
    elif adapter_kind == "mp-hot-snapshot":
        if not seed_urls:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mp-hot-snapshot requires at least one seed_urls entry",
            )

        allowed_schemes = {"http", "https", "file"}
        for url in seed_urls:
            scheme = urlparse(url).scheme.lower()
            if scheme not in allowed_schemes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"unsupported mp-hot-snapshot URL scheme: {url}",
                )


@router.get("/api/collect/adapter-kinds")
def list_collect_adapter_kinds(request: Request) -> dict:
    registry = request.app.state.collector_registry
    visible = [
        adapter_kind
        for adapter_kind in registry.list_registered()
        if adapter_kind in VISIBLE_COLLECT_ADAPTER_KINDS
    ]
    return {"count": len(visible), "items": visible}


@router.get("/api/collect/sources")
def list_collect_sources(request: Request) -> dict:
    store = request.app.state.hot_store
    sources = [
        source.model_dump(mode="json")
        for source in store.list_collector_sources()
        if source.adapter_kind in VISIBLE_COLLECT_ADAPTER_KINDS
    ]
    return {"count": len(sources), "items": sources}


@router.get("/api/collect/sources/{source_id}")
def get_collect_source(source_id: str, request: Request) -> dict:
    store = request.app.state.hot_store
    try:
        source = store.get_collector_source(source_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return source.model_dump(mode="json")


@router.post("/api/collect/sources", status_code=status.HTTP_201_CREATED)
def create_collect_source(body: CollectSourceUpsertRequest, request: Request) -> dict:
    registry = request.app.state.collector_registry
    store = request.app.state.hot_store

    if body.adapter_kind not in registry.list_registered():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown adapter kind: {body.adapter_kind}",
        )
    _validate_source_payload(body.model_dump(mode="python"), adapter_kind=body.adapter_kind)

    source = SourceConfig.model_validate(body.model_dump(mode="python"))
    store.upsert_collector_source(source)
    return source.model_dump(mode="json")


@router.put("/api/collect/sources/{source_id}")
def update_collect_source(
    source_id: str,
    body: CollectSourceUpdateRequest,
    request: Request,
) -> dict:
    registry = request.app.state.collector_registry
    store = request.app.state.hot_store

    try:
        current = store.get_collector_source(source_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    next_payload = current.model_dump(mode="python")
    for key, value in body.model_dump(exclude_unset=True).items():
        next_payload[key] = value

    if next_payload["adapter_kind"] not in registry.list_registered():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown adapter kind: {next_payload['adapter_kind']}",
        )
    _validate_source_payload(next_payload, adapter_kind=next_payload["adapter_kind"])

    source = SourceConfig.model_validate(next_payload)
    store.upsert_collector_source(source)
    return source.model_dump(mode="json")


@router.delete("/api/collect/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collect_source(source_id: str, request: Request) -> None:
    store = request.app.state.hot_store
    try:
        store.delete_collector_source(source_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/api/collect/execute")
async def execute_collect(request: Request, body: CollectExecuteRequest) -> dict:
    collect_graph = request.app.state.hot_collect_graph
    store = request.app.state.hot_store
    try:
        source = store.get_collector_source(body.source_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if not source.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"collector source is disabled: {body.source_id}",
        )

    collect_request = CollectRequest.model_validate(body.model_dump(mode="python"))
    initial_state = make_collect_state(collect_request)
    snapshot = initial_state["snapshot"]
    store.create_collector_run(snapshot.run_id, snapshot.request)
    result = await collect_graph.ainvoke(initial_state)
    final_snapshot = result["snapshot"]
    store.complete_collector_run(final_snapshot)
    return {
        "workflow": "hot-collect",
        "run_id": final_snapshot.run_id,
        "status": final_snapshot.status,
        "summary": final_snapshot.summary.model_dump(mode="json"),
        "source_id": final_snapshot.source.source_id if final_snapshot.source else body.source_id,
        "events": [event.model_dump(mode="json") for event in final_snapshot.events],
    }


@router.get("/api/collect/runs/{run_id}")
def get_collect_run(run_id: str, request: Request) -> dict:
    store = request.app.state.hot_store
    payload = store.get_collector_run(run_id)
    if payload is None:
        return {"run": None, "events": []}
    return payload


@router.get("/api/collect/runs")
def list_collect_runs(
    request: Request,
    limit: int = 20,
    source_id: str | None = None,
) -> dict:
    store = request.app.state.hot_store
    runs = store.list_collector_runs(limit=limit, source_id=source_id)
    return {"count": len(runs), "items": runs}
