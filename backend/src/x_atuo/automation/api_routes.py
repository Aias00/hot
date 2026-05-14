from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, status

from x_atuo.automation.api_execution_services import (
    _dispatch_scheduled_request,
    _execute_author_alpha_job,
    _execute_job,
    _workflow_binding,
)
from x_atuo.automation.api_read_services import (
    _build_runtime_twitter_client,
    _get_account_analytics_snapshot,
    _get_account_content_snapshot,
    _get_device_follow_feed_snapshot,
    _get_notifications_snapshot,
    _handle_twitter_read_error,
    _normalize_tweet_record,
)
from x_atuo.automation.api_sync_services import (
    _backfill_author_alpha_shared_engagements,
    _restore_db_file,
    _snapshot_db_file,
    get_author_alpha_storage,
    get_author_alpha_sync_manager,
    get_storage,
)
from x_atuo.automation.author_alpha_sync import AuthorAlphaSyncActiveError
from x_atuo.automation.runtime_contract import enrich_runtime_contract
from x_atuo.automation.schemas import (
    AccountAnalyticsResponse,
    AccountContentAnalyticsResponse,
    AuthorAlphaBootstrapRequest,
    AuthorAlphaExecuteRequest,
    AuthorAlphaExecuteResponse,
    AuthorAlphaResetResponse,
    AuthorAlphaReconcileRequest,
    AuthorAlphaRunLookupResponse,
    AuthorAlphaScoreImportResponse,
    AuthorAlphaScoreSnapshotResponse,
    AuthorAlphaSyncAcceptedResponse,
    AuthorAlphaSyncHistoryResponse,
    AuthorAlphaSyncRunRecord,
    AuthorAlphaSyncStatusResponse,
    AuthorAlphaSyncStopResponse,
    DeviceFollowFeedResponse,
    FeedEngageExecuteRequest,
    FeedEngageExecuteResponse,
    HealthResponse,
    NotificationsResponse,
    RunLookupResponse,
    TwitterBookmarkFoldersResponse,
    TwitterTweetResponse,
    TwitterTweetsResponse,
    TwitterUsersResponse,
)
from x_atuo.automation.state import AutomationRequest, FeedOptions, WorkflowKind
from x_atuo.automation.state import workflow_contract_kind_for
from x_atuo.core.twitter_client import TwitterClientError
from x_atuo.core.x_web_analytics import (
    AnalyticsGranularity,
    ContentSortField,
    ContentType,
    SortDirection,
    XWebClientConfigError,
    XWebClientError,
)
from x_atuo.core.x_web_notifications import (
    NotificationsTimelineType,
    XWebNotificationsConfigError,
    XWebNotificationsError,
)

router = APIRouter()


def register_routes(app: FastAPI) -> FastAPI:
    app.include_router(router)
    return app


@router.get("/healthz", response_model=HealthResponse)
async def healthz(request: Request) -> HealthResponse:
    status_payload = get_storage(request).healthcheck()
    return HealthResponse(**status_payload)


@router.get("/runs/{run_id}", response_model=RunLookupResponse)
async def get_run(run_id: str, request: Request) -> RunLookupResponse:
    run_payload = get_storage(request).get_run(run_id)
    if run_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return RunLookupResponse(**run_payload)


@router.get("/analytics/account", response_model=AccountAnalyticsResponse)
async def get_account_analytics(
    request: Request,
    days: int = Query(default=28, ge=1, le=365),
    post_limit: int = Query(default=10, ge=1, le=100),
    granularity: AnalyticsGranularity = Query(default="total"),
) -> AccountAnalyticsResponse:
    try:
        payload = _get_account_analytics_snapshot(
            request=request,
            days=days,
            post_limit=post_limit,
            granularity=granularity,
        )
    except XWebClientConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except XWebClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return AccountAnalyticsResponse(**payload)


@router.get("/analytics/account/content", response_model=AccountContentAnalyticsResponse)
async def get_account_analytics_content(
    request: Request,
    content_type: ContentType = Query(default="all", alias="type"),
    sort_field: ContentSortField = Query(default="date", alias="sort"),
    sort_direction: SortDirection = Query(default="desc", alias="dir"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=500),
) -> AccountContentAnalyticsResponse:
    try:
        payload = _get_account_content_snapshot(
            request=request,
            from_date=from_date,
            to_date=to_date,
            content_type=content_type,
            sort_field=sort_field,
            sort_direction=sort_direction,
            limit=limit,
        )
    except XWebClientConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except XWebClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return AccountContentAnalyticsResponse(**payload)


@router.get("/notifications", response_model=NotificationsResponse)
async def get_notifications(
    request: Request,
    timeline_type: NotificationsTimelineType = Query(default="All"),
    count: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> NotificationsResponse:
    try:
        payload = _get_notifications_snapshot(
            request=request,
            timeline_type=timeline_type,
            count=count,
            cursor=cursor,
        )
    except XWebNotificationsConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except XWebNotificationsError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return NotificationsResponse(**payload)


@router.get("/notifications/device-follow-feed", response_model=DeviceFollowFeedResponse)
async def get_device_follow_feed(
    request: Request,
    count: int = Query(default=20, ge=1, le=100),
) -> DeviceFollowFeedResponse:
    try:
        payload = _get_device_follow_feed_snapshot(
            request=request,
            count=count,
        )
    except XWebNotificationsConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except XWebNotificationsError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return DeviceFollowFeedResponse(**payload)


@router.get("/twitter/search", response_model=TwitterTweetsResponse)
async def get_twitter_search(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    product: str = Query(default="Top"),
) -> TwitterTweetsResponse:
    client = _build_runtime_twitter_client(request.app.state.settings)
    try:
        items = [_normalize_tweet_record(tweet) for tweet in client.fetch_search(q, max_items=limit, product=product)]
    except TwitterClientError as exc:
        raise _handle_twitter_read_error(exc) from exc
    return TwitterTweetsResponse(count=len(items), items=items)


@router.get("/twitter/bookmarks", response_model=TwitterTweetsResponse)
async def get_twitter_bookmarks(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> TwitterTweetsResponse:
    client = _build_runtime_twitter_client(request.app.state.settings)
    try:
        items = [_normalize_tweet_record(tweet) for tweet in client.fetch_bookmarks(max_items=limit)]
    except TwitterClientError as exc:
        raise _handle_twitter_read_error(exc) from exc
    return TwitterTweetsResponse(count=len(items), items=items)


@router.get("/twitter/bookmarks/folders", response_model=TwitterBookmarkFoldersResponse)
async def get_twitter_bookmark_folders(request: Request) -> TwitterBookmarkFoldersResponse:
    client = _build_runtime_twitter_client(request.app.state.settings)
    try:
        items = client.fetch_bookmark_folders()
    except TwitterClientError as exc:
        raise _handle_twitter_read_error(exc) from exc
    return TwitterBookmarkFoldersResponse(count=len(items), items=items)


@router.get("/twitter/bookmarks/folders/{folder_id}", response_model=TwitterTweetsResponse)
async def get_twitter_bookmark_folder_posts(
    request: Request,
    folder_id: str,
    limit: int = Query(default=50, ge=1, le=100),
) -> TwitterTweetsResponse:
    client = _build_runtime_twitter_client(request.app.state.settings)
    try:
        items = [_normalize_tweet_record(tweet) for tweet in client.fetch_bookmark_folder_posts(folder_id, max_items=limit)]
    except TwitterClientError as exc:
        raise _handle_twitter_read_error(exc) from exc
    return TwitterTweetsResponse(count=len(items), items=items)


@router.get("/twitter/users/{screen_name}/likes", response_model=TwitterTweetsResponse)
async def get_twitter_user_likes(
    request: Request,
    screen_name: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> TwitterTweetsResponse:
    client = _build_runtime_twitter_client(request.app.state.settings)
    try:
        items = [_normalize_tweet_record(tweet) for tweet in client.fetch_user_likes(screen_name, max_items=limit)]
    except TwitterClientError as exc:
        raise _handle_twitter_read_error(exc) from exc
    return TwitterTweetsResponse(count=len(items), items=items)


@router.get("/twitter/users/{screen_name}/followers", response_model=TwitterUsersResponse)
async def get_twitter_followers(
    request: Request,
    screen_name: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> TwitterUsersResponse:
    client = _build_runtime_twitter_client(request.app.state.settings)
    try:
        items = client.fetch_followers(screen_name, max_items=limit)
    except TwitterClientError as exc:
        raise _handle_twitter_read_error(exc) from exc
    return TwitterUsersResponse(count=len(items), items=items)


@router.get("/twitter/users/{screen_name}/following", response_model=TwitterUsersResponse)
async def get_twitter_following(
    request: Request,
    screen_name: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> TwitterUsersResponse:
    client = _build_runtime_twitter_client(request.app.state.settings)
    try:
        items = client.fetch_following(screen_name, max_items=limit)
    except TwitterClientError as exc:
        raise _handle_twitter_read_error(exc) from exc
    return TwitterUsersResponse(count=len(items), items=items)


@router.get("/twitter/articles/{tweet_id}", response_model=TwitterTweetResponse)
async def get_twitter_article(request: Request, tweet_id: str) -> TwitterTweetResponse:
    client = _build_runtime_twitter_client(request.app.state.settings)
    try:
        tweet = _normalize_tweet_record(client.fetch_article(tweet_id))
    except TwitterClientError as exc:
        raise _handle_twitter_read_error(exc) from exc
    return TwitterTweetResponse(tweet=tweet)


@router.post("/feed-engage/execute", response_model=FeedEngageExecuteResponse)
async def post_feed_engage_execute(
    request: Request,
    body: FeedEngageExecuteRequest,
) -> FeedEngageExecuteResponse:
    settings = request.app.state.settings
    storage = get_storage(request)
    request_obj = AutomationRequest.for_feed_engage(
        job_name="manual-feed-engage",
        dry_run=body.dry_run,
        reply_text=body.reply_text,
        feed_options=FeedOptions(feed_count=body.feed_count, feed_type=body.feed_type),
        approval_mode="ai_auto",
        metadata={
            "proxy": settings.twitter.proxy_url,
            "trigger": "manual",
        },
    )
    job_type, function_name, payload, _endpoint = _workflow_binding(request_obj)
    result = await _execute_job(
        storage=storage,
        endpoint="manual:feed-engage",
        job_type=job_type,
        function_name=function_name,
        payload=payload,
        requested_job_id=request_obj.job_name,
        request_obj=request_obj,
        observability_runtime=request.app.state.observability_runtime,
        config=settings,
    )
    return FeedEngageExecuteResponse(**result)


@router.post("/author-alpha/sync/bootstrap", response_model=AuthorAlphaSyncAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def post_author_alpha_sync_bootstrap(
    request: Request,
    body: AuthorAlphaBootstrapRequest,
) -> AuthorAlphaSyncAcceptedResponse:
    manager = get_author_alpha_sync_manager(request)
    try:
        payload = manager.start_bootstrap(
            from_date=body.from_date,
            to_date=body.to_date,
            resume=body.resume,
            max_days=body.max_days,
        )
    except AuthorAlphaSyncActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    payload = enrich_runtime_contract(
        payload,
        workflow="author-alpha-sync",
        trigger="manual",
        input_payload={
            "from_date": body.from_date,
            "to_date": body.to_date,
            "resume": body.resume,
            "max_days": body.max_days,
        },
        retry_attempted=False,
        max_attempts=2,
        terminal=False,
        outcome=str(payload["status"]),
    )
    payload["workflow"] = "author-alpha-sync"
    return AuthorAlphaSyncAcceptedResponse(**payload)


@router.post("/author-alpha/sync/reconcile", response_model=AuthorAlphaSyncAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def post_author_alpha_sync_reconcile(
    request: Request,
    body: AuthorAlphaReconcileRequest,
) -> AuthorAlphaSyncAcceptedResponse:
    manager = get_author_alpha_sync_manager(request)
    try:
        payload = manager.start_reconcile(target_date=body.target_date)
    except AuthorAlphaSyncActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    payload = enrich_runtime_contract(
        payload,
        workflow="author-alpha-sync",
        trigger="manual",
        input_payload={"target_date": body.target_date},
        retry_attempted=False,
        max_attempts=2,
        terminal=False,
        outcome=str(payload["status"]),
    )
    payload["workflow"] = "author-alpha-sync"
    return AuthorAlphaSyncAcceptedResponse(**payload)


@router.post("/author-alpha/sync/stop", response_model=AuthorAlphaSyncStopResponse, status_code=status.HTTP_202_ACCEPTED)
async def post_author_alpha_sync_stop(request: Request) -> AuthorAlphaSyncStopResponse:
    manager = get_author_alpha_sync_manager(request)
    try:
        payload = manager.stop_active_run()
    except AuthorAlphaSyncActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    payload = enrich_runtime_contract(
        payload,
        workflow="author-alpha-sync",
        trigger="manual",
        input_payload={},
        retry_attempted=False,
        max_attempts=1,
        terminal=False,
        outcome=str(payload["status"]),
    )
    payload["workflow"] = "author-alpha-sync"
    return AuthorAlphaSyncStopResponse(**payload)


@router.get("/author-alpha/sync/status", response_model=AuthorAlphaSyncStatusResponse)
async def get_author_alpha_sync_status(request: Request) -> AuthorAlphaSyncStatusResponse:
    payload = get_author_alpha_sync_manager(request).get_status()
    return AuthorAlphaSyncStatusResponse(**payload)


@router.get("/author-alpha/sync/history", response_model=AuthorAlphaSyncHistoryResponse)
async def get_author_alpha_sync_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
) -> AuthorAlphaSyncHistoryResponse:
    runs = get_author_alpha_sync_manager(request).list_history(limit=limit)
    return AuthorAlphaSyncHistoryResponse(runs=[AuthorAlphaSyncRunRecord(**run) for run in runs])


@router.get("/author-alpha/runs/{run_id}", response_model=AuthorAlphaRunLookupResponse)
async def get_author_alpha_run(run_id: str, request: Request) -> AuthorAlphaRunLookupResponse:
    author_alpha_storage = get_author_alpha_storage(request)
    execution_payload = author_alpha_storage.get_execution_run(run_id)
    if execution_payload is not None:
        return AuthorAlphaRunLookupResponse(**execution_payload)
    sync_payload = get_author_alpha_sync_manager(request).get_run(run_id)
    if sync_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return AuthorAlphaRunLookupResponse(
        run=sync_payload,
        audit_events=author_alpha_storage.get_execution_audit_events_for_run(run_id),
    )


@router.get("/author-alpha/scores/export", response_model=AuthorAlphaScoreSnapshotResponse)
async def get_author_alpha_scores_export(request: Request) -> AuthorAlphaScoreSnapshotResponse:
    author_alpha_storage = get_author_alpha_storage(request)
    storage = get_storage(request)
    _backfill_author_alpha_shared_engagements(author_alpha_storage=author_alpha_storage, storage=storage)
    payload = author_alpha_storage.export_score_snapshot()
    shared_engagements = storage.list_shared_engagements(workflow=WorkflowKind.AUTHOR_ALPHA_ENGAGE.value)
    payload["shared_engagement_count"] = len(shared_engagements)
    payload["shared_engagements"] = shared_engagements
    return AuthorAlphaScoreSnapshotResponse(**payload)


@router.post("/author-alpha/scores/import", response_model=AuthorAlphaScoreImportResponse)
async def post_author_alpha_scores_import(
    request: Request,
    body: AuthorAlphaScoreSnapshotResponse,
    replace_existing: bool = Query(default=False),
) -> AuthorAlphaScoreImportResponse:
    author_alpha_storage = get_author_alpha_storage(request)
    storage = get_storage(request)
    author_alpha_snapshot = _snapshot_db_file(author_alpha_storage.db_path)
    shared_snapshot = _snapshot_db_file(storage.db_path)

    def _rollback() -> None:
        _restore_db_file(author_alpha_storage.db_path, author_alpha_snapshot)
        _restore_db_file(storage.db_path, shared_snapshot)

    try:
        raw_payload = body.model_dump(mode="python")
        shared_engagements = raw_payload.pop("shared_engagements", [])
        payload = author_alpha_storage.import_score_snapshot(
            raw_payload,
            replace_existing=replace_existing,
        )
        imported_shared_engagement_count = storage.import_shared_engagements(
            workflow=WorkflowKind.AUTHOR_ALPHA_ENGAGE.value,
            rows=shared_engagements,
            replace_existing=replace_existing,
        )
        imported_shared_engagement_count += _backfill_author_alpha_shared_engagements(
            author_alpha_storage=author_alpha_storage,
            storage=storage,
        )
        payload["imported_shared_engagement_count"] = imported_shared_engagement_count
    except ValueError as exc:
        _rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        _rollback()
        raise
    return AuthorAlphaScoreImportResponse(**payload)


@router.post("/author-alpha/reset", response_model=AuthorAlphaResetResponse)
async def post_author_alpha_reset(request: Request) -> AuthorAlphaResetResponse:
    manager = get_author_alpha_sync_manager(request)
    if manager.get_status().get("active"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="author-alpha sync run already active")
    get_author_alpha_storage(request).reset_all()
    get_storage(request).delete_shared_engagements(workflow=WorkflowKind.AUTHOR_ALPHA_ENGAGE.value)
    return AuthorAlphaResetResponse(status="cleared")


@router.post("/author-alpha/execute", response_model=AuthorAlphaExecuteResponse)
async def post_author_alpha_execute(
    request: Request,
    body: AuthorAlphaExecuteRequest,
) -> AuthorAlphaExecuteResponse:
    settings = request.app.state.settings
    storage = get_author_alpha_storage(request)
    request_obj = AutomationRequest.for_author_alpha_engage(
        job_name="manual-author-alpha-engage",
        dry_run=body.dry_run,
        metadata={
            "proxy": settings.twitter.proxy_url,
            "trigger": "manual",
        },
    )
    job_type, _function_name, payload, _endpoint = _workflow_binding(request_obj)
    result = await _execute_author_alpha_job(
        settings=settings,
        storage=storage,
        shared_storage=get_storage(request),
        endpoint="manual:author-alpha-engage",
        job_type=job_type,
        payload=payload,
        requested_job_id=request_obj.job_name,
        request_obj=request_obj,
    )
    return AuthorAlphaExecuteResponse(**result)
