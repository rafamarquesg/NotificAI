"""
api/main.py
===========
Aplicação FastAPI principal — NotificAI.

Para rodar localmente:
    uvicorn api.main:app --reload --port 8000

Documentação automática disponível em:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.analyze import router as analyze_router
from .routes.review import router as review_router
from .routes.feedback import router as feedback_router

app = FastAPI(
    title="NotificAI — Detecção de Agravos de Notificação Compulsória",
    description="""
Sistema de apoio à decisão clínica para identificação e rastreamento de
casos de notificação compulsória em registros médicos.

## Fluxo HitL (Human-in-the-Loop)

| Etapa | Ação | Endpoint |
|-------|------|----------|
| **A** | Análise + Highlighting | `POST /analyze/file` |
| **B** | Validação do técnico | `POST /review/{id}/validate` |
| **C** | Feedback → retreinamento | `GET /feedback/stats`, `POST /feedback/retrain` |
| **D** | Preenchimento SINAN | Automático após Etapa B com `trigger_sinan=true` |
""",
    version="2.0.0",
    contact={
        "name": "NUVE — Núcleo de Vigilância Epidemiológica HCFMUSP",
    },
    license_info={"name": "Uso interno — HCFMUSP"},
)

# CORS — ajustar origens em produção
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra routers
app.include_router(analyze_router)
app.include_router(review_router)
app.include_router(feedback_router)


@app.get("/", tags=["Status"])
def health_check():
    """Verifica se a API está operacional."""
    return {
        "status": "online",
        "service": "NotificAI",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/formats", tags=["Status"])
def list_supported_formats():
    """Lista os formatos de arquivo suportados pela ingestão."""
    from ingestion.router import IngestionRouter
    return {"supported_formats": IngestionRouter.supported_formats()}
