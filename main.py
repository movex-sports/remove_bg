import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from rembg import new_session, remove


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("remove_bg")

MODEL_NAME = os.getenv("REMBG_MODEL", "u2net")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_CONCURRENT_JOBS = max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "1")))
API_KEY = os.getenv("API_KEY", "").strip()

rembg_session = None
processing_slots = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


def parse_cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ORIGINS", "").strip()
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def process_image(image_bytes: bytes) -> bytes:
    try:
        with Image.open(BytesIO(image_bytes)) as source_image:
            source_image.load()
            input_image = source_image.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Arquivo de imagem inválido.") from error

    output_image = remove(input_image, session=rembg_session)
    output_buffer = BytesIO()
    output_image.save(output_buffer, format="PNG", optimize=True)
    return output_buffer.getvalue()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global rembg_session
    logger.info("Carregando modelo rembg: %s", MODEL_NAME)
    rembg_session = await run_in_threadpool(new_session, MODEL_NAME)
    logger.info("Modelo rembg carregado")
    yield
    rembg_session = None


app = FastAPI(
    title="Remove BG API",
    description="API para remoção de fundo de imagens usando rembg.",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = parse_cors_origins()
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )


def validate_api_key(x_api_key: str | None) -> None:
    if API_KEY and (not x_api_key or not secrets.compare_digest(x_api_key, API_KEY)):
        raise HTTPException(status_code=401, detail="API key inválida ou ausente.")


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "remove_bg",
        "model": MODEL_NAME,
    }


@app.get("/health")
def health():
    return {
        "status": "ok" if rembg_session is not None else "starting",
        "model_loaded": rembg_session is not None,
    }


@app.post("/remove-background")
async def remove_background(
    file: UploadFile = File(...),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    validate_api_key(x_api_key)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="O arquivo enviado não é uma imagem.")

    image_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="A imagem enviada está vazia.")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"A imagem excede o limite de {MAX_UPLOAD_MB} MB.",
        )
    if rembg_session is None:
        raise HTTPException(status_code=503, detail="O modelo ainda está inicializando.")

    started_at = time.perf_counter()
    try:
        async with processing_slots:
            output_bytes = await run_in_threadpool(process_image, image_bytes)
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Falha ao remover fundo")
        raise HTTPException(status_code=500, detail="Erro ao remover o fundo da imagem.") from error

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    return Response(
        content=output_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": 'inline; filename="imagem-sem-fundo.png"',
            "X-Processing-Time-Ms": str(elapsed_ms),
        },
    )
