# hot backend

Python `FastAPI` backend for `hot`, composed with vendored `x_atuo`.

## Run

```bash
cd backend
uv sync --extra dev
uv run uvicorn hot_backend.app:app --host 127.0.0.1 --port 18000
```
