from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from importlib import import_module
from types import ModuleType
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from x_atuo.automation.author_alpha_graph import run_author_alpha_engage
from x_atuo.automation.author_alpha_storage import AuthorAlphaStorage
from x_atuo.automation.config import AutomationConfig
from x_atuo.automation.observability import LangfuseRuntime
from x_atuo.automation.runtime_contract import build_runtime_contract_fields
from x_atuo.automation.state import AutomationRequest, FeedOptions, WorkflowKind, workflow_contract_kind_for
from x_atuo.automation.storage import AutomationStorage, utcnow
from x_atuo.automation.utils import is_transient_ai_error, is_transient_network_error
from x_atuo.core.ai_client import AIProviderError, build_ai_provider
from x_atuo.core.twitter_client import TwitterClient, TwitterClientError
from x_atuo.core.x_web_notifications import XWebNotificationsClient


def _workflow_binding(request_obj: AutomationRequest) -> tuple[str, str, dict[str, Any], str]:
    if request_obj.workflow is WorkflowKind.FEED_ENGAGE:
        feed_options = request_obj.feed_options or FeedOptions()
        payload = {
            "feed_count": feed_options.feed_count,
            "feed_type": feed_options.feed_type,
            "mode": request_obj.approval_mode,
            "dry_run": request_obj.dry_run,
            "reply_text": request_obj.reply_text,
            "metadata": request_obj.metadata,
            "idempotency_key": request_obj.idempotency_key,
            "proxy": request_obj.metadata.get("proxy"),
        }
        return "feed_engage", "run_feed_engage", payload, "scheduler:feed-engage"
    if request_obj.workflow is WorkflowKind.AUTHOR_ALPHA_ENGAGE:
        metadata = request_obj.metadata if isinstance(request_obj.metadata, dict) else {}
        payload = {
            "mode": request_obj.approval_mode,
            "dry_run": request_obj.dry_run,
            "metadata": metadata,
            "idempotency_key": request_obj.idempotency_key,
            "proxy": metadata.get("proxy"),
        }
        return "author_alpha_engage", "run_author_alpha_engage", payload, "scheduler:author-alpha-engage"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported scheduled workflow")


def _execution_trigger(request_obj: AutomationRequest) -> str:
    metadata = request_obj.metadata if isinstance(request_obj.metadata, dict) else {}
    trigger = metadata.get("trigger")
    return str(trigger) if isinstance(trigger, str) and trigger else "manual"


def _execution_input_payload(request_obj: AutomationRequest) -> dict[str, Any]:
    if request_obj.workflow is WorkflowKind.FEED_ENGAGE:
        feed_options = request_obj.feed_options or FeedOptions()
        return {
            "dry_run": request_obj.dry_run,
            "feed_count": feed_options.feed_count,
            "feed_type": feed_options.feed_type,
            "reply_text": request_obj.reply_text,
        }
    if request_obj.workflow is WorkflowKind.AUTHOR_ALPHA_ENGAGE:
        return {"dry_run": request_obj.dry_run}
    return {"dry_run": request_obj.dry_run}


def _execution_contract_fields(
    request_obj: AutomationRequest,
    *,
    run_status: str,
    retry_attempted: bool,
    max_attempts: int,
) -> dict[str, Any]:
    return build_runtime_contract_fields(
        workflow=workflow_contract_kind_for(request_obj.workflow).value,
        trigger=_execution_trigger(request_obj),
        input_payload=_execution_input_payload(request_obj),
        retry_attempted=retry_attempted,
        max_attempts=max_attempts,
        terminal=True,
        outcome=run_status,
    )


def _persistable_runtime_result(result_payload: Any, *, contract_fields: dict[str, Any] | None) -> Any:
    if not isinstance(result_payload, dict) or contract_fields is None:
        return result_payload
    enriched = dict(result_payload)
    enriched.update(contract_fields)
    return enriched


def _load_graph_module() -> ModuleType:
    try:
        return import_module("x_atuo.automation.graph")
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="automation.graph is not available",
        ) from exc


def _build_invoke_kwargs(function: Any, **candidates: Any) -> dict[str, Any]:
    signature = inspect.signature(function)
    supports_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if supports_kwargs:
        return candidates
    return {name: value for name, value in candidates.items() if name in signature.parameters}


def _build_runtime_graph(config: AutomationConfig, storage: Any, *, proxy: str | None = None) -> Any:
    module = _load_graph_module()
    builder = getattr(module, "build_runtime_graph", None) or getattr(module, "_build_runtime_graph", None)
    if builder is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="automation.graph.build_runtime_graph is not available",
        )
    return builder(config, storage, proxy=proxy)


def _persist_snapshot(storage: Any, snapshot: Any) -> None:
    module = _load_graph_module()
    persist = getattr(module, "persist_snapshot", None) or getattr(module, "_persist_snapshot", None)
    if persist is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="automation.graph.persist_snapshot is not available",
        )
    persist(storage, snapshot)


def _workflow_observation_metadata(
    request_obj: AutomationRequest,
    config: AutomationConfig,
    *,
    endpoint: str,
) -> dict[str, Any]:
    return {
        "run_id": request_obj.run_id,
        "job_id": request_obj.job_name,
        "workflow": request_obj.workflow.value,
        "endpoint": endpoint,
        "dry_run": request_obj.dry_run,
        "approval_mode": request_obj.approval_mode,
        "environment": config.environment,
    }


def _snapshot_response(snapshot: Any) -> dict[str, Any]:
    return {
        "status": snapshot.status.value,
        "run_id": snapshot.run_id,
        "result": snapshot.result.model_dump(mode="json") if snapshot.result else None,
        "candidate_refresh_count": snapshot.candidate_refresh_count,
        "selected_candidate": snapshot.selected_candidate.model_dump(mode="json") if snapshot.selected_candidate else None,
        "rendered_text": snapshot.rendered_text,
        "selection_source": snapshot.selection_source,
        "selection_reason": snapshot.selection_reason,
        "drafted_by": snapshot.drafting_source,
        "errors": snapshot.errors,
        "events": [event.model_dump(mode="json") for event in snapshot.events],
    }


def _workflow_failure_marker(snapshot: Any) -> Exception | None:
    status_value = getattr(getattr(snapshot, "status", None), "value", None)
    if status_value != "failed":
        return None
    errors = getattr(snapshot, "errors", None)
    if isinstance(errors, list):
        messages = [str(item).strip() for item in errors if str(item).strip()]
        if messages:
            return RuntimeError("; ".join(messages))
    return RuntimeError("workflow ended with failed status")


async def _run_request(
    request: AutomationRequest,
    *,
    storage: Any,
    endpoint: str,
    proxy: str | None = None,
    observability_runtime: Any | None = None,
    config: AutomationConfig | None = None,
) -> dict[str, Any]:
    config = config or AutomationConfig()
    runtime = observability_runtime if observability_runtime is not None else LangfuseRuntime()
    graph = _build_runtime_graph(config, storage, proxy=proxy)
    run_name = f"x-atuo.{request.workflow.value}"
    observation = runtime.start_workflow_observation(
        run_name=run_name,
        metadata=_workflow_observation_metadata(request, config, endpoint=endpoint),
    )
    graph_config = runtime.build_graph_config(run_name=run_name, observation=observation)

    snapshot: Any | None = None
    error: Exception | None = None
    try:
        snapshot = await graph.invoke(request, graph_config=graph_config)
        error = _workflow_failure_marker(snapshot)
        _persist_snapshot(storage, snapshot)
        return _snapshot_response(snapshot)
    except Exception as exc:
        error = exc
        raise
    finally:
        runtime.finish_workflow_observation(
            observation,
            output=None if snapshot is None else {"status": snapshot.status.value, "run_id": snapshot.run_id},
            error=error,
        )


async def _call_graph(function_name: str, **kwargs: Any) -> Any:
    module = _load_graph_module()
    bind_request = getattr(module, "build_request_binding", None)
    request_binding = None
    if callable(bind_request):
        request_binding = bind_request(
            function_name,
            run_id=kwargs["run_id"],
            job_id=kwargs["job_id"],
            payload=kwargs["payload"],
        )
    if request_binding is not None:
        request_obj, proxy = request_binding
        return await _run_request(
            request_obj,
            storage=kwargs["storage"],
            endpoint=kwargs["endpoint"],
            proxy=proxy,
            observability_runtime=kwargs.get("observability_runtime"),
            config=kwargs.get("config"),
        )

    function = getattr(module, function_name, None)
    if function is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"automation.graph.{function_name} is not available",
        )
    result = function(**_build_invoke_kwargs(function, **kwargs))
    if inspect.isawaitable(result):
        return await result
    return result


def _normalize_result(result: Any) -> Any:
    if result is None:
        return None
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return result
    if isinstance(result, (list, str, int, float, bool)):
        return result
    return str(result)


def _derive_status(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("status") == "completed_with_errors":
            return "completed"
        if result.get("status") in {"queued", "running", "completed", "failed", "blocked", "skipped"}:
            return str(result["status"])
        if result.get("ok") is False:
            return "failed"
    return "completed"


def _derive_error_message(result: Any, *, run_status: str, current_error: str | None) -> str | None:
    if current_error is not None:
        return current_error
    if run_status not in {"blocked", "skipped"} or not isinstance(result, dict):
        return None
    errors = result.get("errors")
    if not isinstance(errors, list):
        return None
    messages = [str(item).strip() for item in errors if str(item).strip()]
    return messages[0] if messages else None


def _is_retryable_author_alpha_failure(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError, TwitterClientError)):
        return True
    message = str(exc)
    if isinstance(exc, AIProviderError):
        return is_transient_ai_error(message)
    return is_transient_network_error(message)


def _record_author_alpha_retry(
    storage: AuthorAlphaStorage,
    *,
    request: AutomationRequest,
    attempt: int,
    max_attempts: int,
    error: str,
) -> None:
    if not request.run_id:
        return
    storage.add_execution_audit_event(
        run_id=request.run_id,
        event_type="workflow_retry_scheduled",
        node="service",
        payload={
            "attempt": attempt,
            "max_attempts": max_attempts,
            "error": error,
            "workflow": request.workflow.value,
        },
    )


async def _run_author_alpha_request(
    request: AutomationRequest,
    *,
    settings: AutomationConfig,
    storage: AuthorAlphaStorage,
    shared_storage: AutomationStorage,
    endpoint: str,
    proxy: str | None = None,
    retry_tracker: dict[str, bool] | None = None,
) -> dict[str, Any]:
    max_attempts = 2
    attempt = 1
    while True:
        try:
            twitter_client = TwitterClient.from_config(
                settings.agent_reach_config_path,
                proxy=proxy or settings.twitter.proxy_url,
                twitter_bin=settings.twitter.cli_bin,
                timeout=120,
            )
            notifications_client = XWebNotificationsClient.from_settings(settings)
            ai_provider = build_ai_provider(settings.ai)
            if ai_provider is None:
                raise AIProviderError("author-alpha-engage requires an AI provider")
            snapshot = await run_author_alpha_engage(
                request,
                config=settings,
                storage=storage,
                shared_storage=shared_storage,
                candidate_source=notifications_client,
                drafter=ai_provider,
                reply_client=twitter_client,
                sleep=asyncio.sleep,
            )
            response = _snapshot_response(snapshot)
            failure = _workflow_failure_marker(snapshot)
            if failure is None or attempt >= max_attempts or not _is_retryable_author_alpha_failure(failure):
                return response
            _record_author_alpha_retry(
                storage,
                request=request,
                attempt=attempt,
                max_attempts=max_attempts,
                error=str(failure),
            )
            if retry_tracker is not None:
                retry_tracker["attempted"] = True
        except Exception as exc:
            if attempt >= max_attempts or not _is_retryable_author_alpha_failure(exc):
                raise
            _record_author_alpha_retry(
                storage,
                request=request,
                attempt=attempt,
                max_attempts=max_attempts,
                error=str(exc),
            )
            if retry_tracker is not None:
                retry_tracker["attempted"] = True
        attempt += 1
        await asyncio.sleep(float(attempt))


async def _execute_job(
    *,
    storage: AutomationStorage,
    endpoint: str,
    job_type: str,
    function_name: str,
    payload: dict[str, Any],
    requested_job_id: str | None,
    request_obj: AutomationRequest | None = None,
    observability_runtime: Any | None = None,
    config: AutomationConfig | None = None,
) -> dict[str, Any]:
    run_id = str(uuid4())
    job_id = requested_job_id or f"{job_type}-{run_id}"
    normalized_result: Any = None
    run_status = "failed"
    error_message: str | None = None
    request_for_run: AutomationRequest | None = None

    storage.upsert_job(job_id, job_type, config=payload)
    storage.create_run(
        run_id=run_id,
        job_id=job_id,
        job_type=job_type,
        endpoint=endpoint,
        request_payload=payload,
    )
    storage.add_audit_event(
        run_id=run_id,
        event_type="trigger_received",
        node="service",
        payload={"endpoint": endpoint, "job_id": job_id},
    )
    storage.update_run(run_id, status="running", started_at=utcnow())

    try:
        if request_obj is not None:
            request_for_run = request_obj.model_copy(update={"run_id": run_id, "job_name": job_id})
            proxy = request_for_run.metadata.get("proxy") if isinstance(request_for_run.metadata, dict) else None
            result = await _run_request(
                request_for_run,
                storage=storage,
                endpoint=endpoint,
                proxy=proxy,
                observability_runtime=observability_runtime,
                config=config,
            )
        else:
            result = await _call_graph(
                function_name,
                run_id=run_id,
                job_id=job_id,
                endpoint=endpoint,
                payload=payload,
                storage=storage,
                observability_runtime=observability_runtime,
                config=config,
            )
        normalized_result = _normalize_result(result)
        run_status = _derive_status(normalized_result)
        error_message = _derive_error_message(
            normalized_result,
            run_status=run_status,
            current_error=error_message,
        )
    except Exception as exc:
        error_message = str(exc)
        normalized_result = {"status": "failed", "error": error_message}

    contract_fields = (
        _execution_contract_fields(
            request_for_run,
            run_status=run_status,
            retry_attempted=False,
            max_attempts=1,
        )
        if request_for_run is not None
        else None
    )
    persisted_result = _persistable_runtime_result(normalized_result, contract_fields=contract_fields)

    storage.update_run(
        run_id,
        status=run_status,
        response_payload=persisted_result,
        error=error_message,
        finished_at=utcnow(),
    )
    storage.add_audit_event(
        run_id=run_id,
        event_type="orchestration_finished",
        node="service",
        payload={"status": run_status, "error": error_message},
    )
    return {
        "run_id": run_id,
        "job_id": job_id,
        "job_type": job_type,
        "endpoint": endpoint,
        "status": run_status,
        "result": normalized_result,
        "workflow": workflow_contract_kind_for(request_for_run.workflow).value if request_for_run is not None else None,
        **(contract_fields or {}),
    }


async def _execute_author_alpha_job(
    *,
    settings: AutomationConfig,
    storage: AuthorAlphaStorage,
    shared_storage: AutomationStorage,
    endpoint: str,
    job_type: str,
    payload: dict[str, Any],
    requested_job_id: str | None,
    request_obj: AutomationRequest,
) -> dict[str, Any]:
    run_id = str(uuid4())
    job_id = requested_job_id or f"{job_type}-{run_id}"
    normalized_result: Any = None
    run_status = "failed"
    error_message: str | None = None
    retry_tracker = {"attempted": False}
    request_for_run = request_obj.model_copy(update={"run_id": run_id, "job_name": job_id})

    storage.create_execution_run(
        run_id=run_id,
        job_id=job_id,
        job_type=job_type,
        endpoint=endpoint,
        request_payload=payload,
    )
    storage.add_execution_audit_event(
        run_id=run_id,
        event_type="trigger_received",
        node="service",
        payload={"endpoint": endpoint, "job_id": job_id},
    )
    storage.update_execution_run(run_id, status="running", started_at=utcnow())

    try:
        proxy = request_for_run.metadata.get("proxy") if isinstance(request_for_run.metadata, dict) else None
        normalized_result = await _run_author_alpha_request(
            request_for_run,
            settings=settings,
            storage=storage,
            shared_storage=shared_storage,
            endpoint=endpoint,
            proxy=proxy,
            retry_tracker=retry_tracker,
        )
        run_status = _derive_status(normalized_result)
        error_message = _derive_error_message(
            normalized_result,
            run_status=run_status,
            current_error=error_message,
        )
    except Exception as exc:
        error_message = str(exc)
        normalized_result = {"status": "failed", "error": error_message}

    contract_fields = _execution_contract_fields(
        request_for_run,
        run_status=run_status,
        retry_attempted=retry_tracker["attempted"],
        max_attempts=2,
    )
    persisted_result = _persistable_runtime_result(normalized_result, contract_fields=contract_fields)

    storage.update_execution_run(
        run_id,
        status=run_status,
        response_payload=persisted_result,
        error=error_message,
        finished_at=utcnow(),
    )
    storage.add_execution_audit_event(
        run_id=run_id,
        event_type="orchestration_finished",
        node="service",
        payload={"status": run_status, "error": error_message},
    )
    return {
        "run_id": run_id,
        "job_id": job_id,
        "job_type": job_type,
        "endpoint": endpoint,
        "status": run_status,
        "result": normalized_result,
        "workflow": workflow_contract_kind_for(request_for_run.workflow).value,
        **contract_fields,
    }


async def _dispatch_scheduled_request(
    request_obj: AutomationRequest,
    storage: AutomationStorage,
    author_alpha_storage: AuthorAlphaStorage | None = None,
    *,
    settings: AutomationConfig | None = None,
    observability_runtime: Any | None = None,
) -> dict[str, Any]:
    from x_atuo.automation.api_sync_services import _resolve_author_alpha_db_path

    resolved_settings = settings or AutomationConfig()
    job_type, function_name, payload, endpoint = _workflow_binding(request_obj)
    if request_obj.workflow is WorkflowKind.AUTHOR_ALPHA_ENGAGE:
        if author_alpha_storage is None:
            author_alpha_storage = AuthorAlphaStorage(_resolve_author_alpha_db_path(resolved_settings))
            author_alpha_storage.initialize()
        return await _execute_author_alpha_job(
            settings=resolved_settings,
            storage=author_alpha_storage,
            shared_storage=storage,
            endpoint=endpoint,
            job_type=job_type,
            payload=payload,
            requested_job_id=request_obj.job_name,
            request_obj=request_obj,
        )
    return await _execute_job(
        storage=storage,
        endpoint=endpoint,
        job_type=job_type,
        function_name=function_name,
        payload=payload,
        requested_job_id=request_obj.job_name,
        request_obj=request_obj,
        observability_runtime=observability_runtime,
        config=resolved_settings,
    )


def _make_run_job_ids(request_obj: AutomationRequest, job_type: str) -> tuple[str, str]:
    """Return a fresh (run_id, job_id) pair derived from the request."""
    run_id = str(uuid4())
    job_id = request_obj.job_name or f"{job_type}-{run_id}"
    return run_id, job_id


def _record_dropped_scheduled_request(
    request_obj: AutomationRequest,
    storage: AutomationStorage,
    *,
    author_alpha_storage: AuthorAlphaStorage | None = None,
    reason: str,
) -> str:
    job_type, _function_name, payload, endpoint = _workflow_binding(request_obj)
    if request_obj.workflow is WorkflowKind.AUTHOR_ALPHA_ENGAGE:
        if author_alpha_storage is None:
            raise RuntimeError("author-alpha storage is required to record dropped author-alpha requests")
        run_id, job_id = _make_run_job_ids(request_obj, job_type)
        author_alpha_storage.create_execution_run(
            run_id=run_id,
            job_id=job_id,
            job_type=job_type,
            endpoint=endpoint,
            request_payload=payload,
            status="blocked",
        )
        author_alpha_storage.add_execution_audit_event(
            run_id=run_id,
            event_type="scheduler_queue_dropped",
            node="service",
            payload={"endpoint": endpoint, "job_id": job_id, "reason": reason},
        )
        author_alpha_storage.update_execution_run(
            run_id,
            status="blocked",
            response_payload={"status": "blocked", "error": reason},
            error=reason,
            finished_at=utcnow(),
        )
        return run_id
    run_id, job_id = _make_run_job_ids(request_obj, job_type)
    storage.upsert_job(job_id, job_type, config=payload)
    storage.create_run(
        run_id=run_id,
        job_id=job_id,
        job_type=job_type,
        endpoint=endpoint,
        request_payload=payload,
        status="blocked",
    )
    storage.add_audit_event(
        run_id=run_id,
        event_type="scheduler_queue_dropped",
        node="service",
        payload={"endpoint": endpoint, "job_id": job_id, "reason": reason},
    )
    storage.update_run(
        run_id,
        status="blocked",
        response_payload={"status": "blocked", "error": reason},
        error=reason,
        finished_at=utcnow(),
    )
    return run_id


