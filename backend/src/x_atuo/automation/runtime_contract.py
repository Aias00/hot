from __future__ import annotations

from typing import Any


def build_runtime_contract_fields(
    *,
    workflow: str,
    trigger: str,
    input_payload: dict[str, Any],
    retry_attempted: bool,
    max_attempts: int,
    terminal: bool,
    outcome: str,
) -> dict[str, Any]:
    return {
        "request": build_request_contract(
            workflow=workflow,
            trigger=trigger,
            input_payload=input_payload,
        ),
        "audit": build_audit_contract(),
        "retry": build_retry_contract(
            attempted=retry_attempted,
            max_attempts=max_attempts,
        ),
        "completion": build_completion_contract(
            terminal=terminal,
            outcome=outcome,
        ),
    }


def build_request_contract(*, workflow: str, trigger: str, input_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow": workflow,
        "trigger": trigger,
        "input": input_payload,
    }


def build_audit_contract(*, trigger_event: str = "trigger_received") -> dict[str, str]:
    return {"trigger_event": trigger_event}


def build_retry_contract(*, attempted: bool, max_attempts: int) -> dict[str, Any]:
    return {
        "attempted": attempted,
        "max_attempts": max_attempts,
    }


def build_completion_contract(*, terminal: bool, outcome: str) -> dict[str, Any]:
    return {
        "terminal": terminal,
        "outcome": outcome,
    }


def enrich_runtime_contract(
    payload: dict[str, Any],
    *,
    workflow: str,
    trigger: str,
    input_payload: dict[str, Any],
    retry_attempted: bool,
    max_attempts: int,
    terminal: bool,
    outcome: str,
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched.update(
        build_runtime_contract_fields(
            workflow=workflow,
            trigger=trigger,
            input_payload=input_payload,
            retry_attempted=retry_attempted,
            max_attempts=max_attempts,
            terminal=terminal,
            outcome=outcome,
        )
    )
    return enriched
