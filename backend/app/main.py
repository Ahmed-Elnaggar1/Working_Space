"""
Application entrypoint.

For now this just exposes a health check so Story 2.2 (local dev environment)
has something concrete to verify against. As each module (auth, channels,
files, chat, bot...) gets built out, its router gets included here.
"""

from fastapi import FastAPI

from app.workspaces.routes import router as workspaces_router

app = FastAPI(title="Vault API", version="0.1.0")

app.include_router(workspaces_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Example of how routers get wired in as modules are built, e.g.:
# from app.auth.routes import router as auth_router
# app.include_router(auth_router, prefix="/auth", tags=["auth"])
