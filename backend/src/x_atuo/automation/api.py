from __future__ import annotations

from x_atuo.automation import api_bootstrap as _bootstrap
from x_atuo.automation import api_execution_services as _execution
from x_atuo.automation import api_read_services as _read
from x_atuo.automation import api_routes as _routes
from x_atuo.automation import api_sync_services as _sync

app = _bootstrap.build_app()
build_app = _bootstrap.build_app
lifespan = _bootstrap.lifespan
router = _routes.router
register_routes = _routes.register_routes


def __getattr__(name: str):
    for module in (_bootstrap, _routes, _execution, _sync, _read):
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
