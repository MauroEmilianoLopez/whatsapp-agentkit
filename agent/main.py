# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

"""
Servidor principal del agente de WhatsApp.
Funciona con cualquier proveedor (Whapi, Meta, Twilio) gracias a la capa de providers.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta, validar_configuracion
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor

load_dotenv()

# Configuración de logging según entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

# Proveedor de WhatsApp (se configura en .env con WHATSAPP_PROVIDER)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


def _diagnostico_arranque():
    """Loguea el estado de las variables de entorno al arrancar.
    No expone valores de secretos — sólo presencia, longitud y prefijo."""
    logger.info("=" * 60)
    logger.info("AgentKit — Diagnóstico de arranque")
    logger.info("=" * 60)

    # LLM (Groq)
    config_llm = validar_configuracion()
    for k, v in config_llm.items():
        logger.info(f"  {k}: {v}")

    # WhatsApp provider
    logger.info(f"  WHATSAPP_PROVIDER: {os.getenv('WHATSAPP_PROVIDER', '(missing)')}")
    whapi_token = os.getenv("WHAPI_TOKEN")
    logger.info(f"  WHAPI_TOKEN_present: {bool(whapi_token)}")
    if whapi_token:
        logger.info(f"  WHAPI_TOKEN_length: {len(whapi_token)}")
        logger.info(f"  WHAPI_TOKEN_prefix: {whapi_token[:4]}...")

    # Otras
    logger.info(f"  PORT: {os.getenv('PORT', '(missing)')}")
    logger.info(f"  ENVIRONMENT: {os.getenv('ENVIRONMENT', '(missing)')}")
    db_url = os.getenv("DATABASE_URL", "")
    if "postgres" in db_url:
        db_type = "postgres"
    elif "sqlite" in db_url:
        db_type = "sqlite"
    else:
        db_type = "(missing)"
    logger.info(f"  DATABASE_TYPE: {db_type}")

    logger.info(f"  Total env vars in container: {len(os.environ)}")
    logger.info("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar el servidor."""
    _diagnostico_arranque()
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="AgentKit — WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway/monitoreo."""
    return {"status": "ok", "service": "agentkit"}


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    """Verificación GET del webhook (requerido por Meta Cloud API, no-op para otros)."""
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Recibe mensajes de WhatsApp via el proveedor configurado.
    Procesa el mensaje, genera respuesta con el LLM y la envía de vuelta.
    """
    try:
        # Parsear webhook — el proveedor normaliza el formato
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            # Ignorar mensajes propios o vacíos
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            # Obtener historial ANTES de guardar el mensaje actual
            # (brain.py agrega el mensaje actual, evitando duplicados)
            historial = await obtener_historial(msg.telefono)

            # Generar respuesta con el LLM
            respuesta = await generar_respuesta(msg.texto, historial)

            # Guardar mensaje del usuario Y respuesta del agente en memoria
            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            # Enviar respuesta por WhatsApp via el proveedor
            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"Respuesta a {msg.telefono}: {respuesta}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
