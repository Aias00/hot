# Hot Collect Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new graph-based hot-content collection workflow in the Python backend, designed to support multiple source websites over time.

**Architecture:** Reuse vendored `x_atuo` as the backend host and orchestration substrate, but keep collection logic in a separate `hot_backend.collectors` package. Add a source-adapter registry, a LangGraph collection workflow, and SQLite-backed source/run/checkpoint/item tables. Expose collection APIs without yet wiring concrete live website collectors.

**Tech Stack:** Python FastAPI, LangGraph, SQLite, vendored x_atuo

---
