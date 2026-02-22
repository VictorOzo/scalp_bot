from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from api.auth import bootstrap_admin_from_env, router as auth_router
from api.routes.audit import router as audit_router
from api.routes.commands import router as commands_router
from api.routes.exports import router as exports_router
from api.routes.gates import router as gates_router
from api.routes.positions import router as positions_router
from api.routes.settings import router as settings_router
from api.routes.status import router as status_router
from api.routes.trades import router as trades_router
from storage.db import connect, init_db

app = FastAPI(title="Scalp Bot API", version="phase-d4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(status_router)
app.include_router(gates_router)
app.include_router(positions_router)
app.include_router(trades_router)
app.include_router(commands_router)
app.include_router(exports_router)
app.include_router(settings_router)
app.include_router(audit_router)


@app.on_event("startup")
def _startup() -> None:
    conn = connect()
    try:
        init_db(conn)
    finally:
        conn.close()

    bootstrap_admin_from_env()


def main() -> None:
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()