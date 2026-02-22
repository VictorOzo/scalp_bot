from __future__ import annotations

from fastapi import FastAPI

from api.auth import bootstrap_admin_from_env, router as auth_router
from api.routes.commands import router as commands_router
from api.routes.exports import router as exports_router
from api.routes.gates import router as gates_router
from api.routes.positions import router as positions_router
from api.routes.settings import router as settings_router
from api.routes.status import router as status_router
from api.routes.trades import router as trades_router

app = FastAPI(title="Scalp Bot API", version="phase-d4")

app.include_router(auth_router)
app.include_router(status_router)
app.include_router(gates_router)
app.include_router(positions_router)
app.include_router(trades_router)
app.include_router(commands_router)
app.include_router(exports_router)
app.include_router(settings_router)


@app.on_event("startup")
def _startup() -> None:
    bootstrap_admin_from_env()


def main() -> None:
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
