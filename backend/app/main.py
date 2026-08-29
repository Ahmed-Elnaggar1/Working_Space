# ruff: noqa: E402
from dotenv import load_dotenv
load_dotenv()


import uuid
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.routes import router as auth_router
from app.channels.routes import router as channels_router
from app.files.routes import router as files_router
from app.workspaces.routes import router as workspaces_router
from app.files.routes import router as files_router

app = FastAPI(title="Vault API", version="0.1.0")

# Register routers
app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(channels_router)
app.include_router(files_router)

# Global Exception Handlers to match API.md contract
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_SERVER_ERROR",
    }
    code = code_map.get(exc.status_code, "ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": exc.detail,
                "request_id": str(uuid.uuid4()),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "details": exc.errors(),
                "request_id": str(uuid.uuid4()),
            }
        },
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}

