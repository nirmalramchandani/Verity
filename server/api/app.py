from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router


# ---------------------------------------------------------------------------
# Starlette ≥ 0.40 limits each multipart form part to 1 MB by default
# (max_part_size=1_048_576).  Our bulk-deal CSVs can be 50 MB+, so we
# override the form() call on upload routes to allow up to 200 MB per part.
# ---------------------------------------------------------------------------
MAX_PART_SIZE = 200 * 1024 * 1024   # 200 MB per file part


app = FastAPI(
    title="Verity API",
    description="Verity Financial Data & Intelligence Pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def increase_upload_limit(request: Request, call_next):
    """
    Raise the multipart parser limits for /upload/* endpoints.
    
    Without this, Starlette silently rejects any file part > 1 MB
    with a 400 Bad Request.
    """
    if request.url.path.startswith("/upload/"):
        # Starlette caches the form on first access.  We need to intercept
        # _before_ FastAPI's dependency injection calls request.form().
        # We override receive to mark the request, then patch form.
        _original_form = request.form

        def _patched_form(**kwargs):
            kwargs.setdefault("max_part_size", MAX_PART_SIZE)
            kwargs.setdefault("max_files", 100)
            kwargs.setdefault("max_fields", 200)
            return _original_form(**kwargs)

        request._form = None           # clear any cached result
        request.form = _patched_form    # type: ignore[assignment]

    response = await call_next(request)
    return response


app.include_router(router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Server is awake"}
