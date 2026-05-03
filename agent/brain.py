# agent/brain.py — Cerebro del agente: conexión con Groq
# Generado por AgentKit (variante Groq)

"""
Lógica de IA del agente. Lee el system prompt de prompts.yaml
y genera respuestas usando la API de Groq (llama-3.3-70b-versatile).
"""

import os
import yaml
import logging
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Cliente de Groq (compatible con formato OpenAI)
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# Modelo por defecto — configurable via .env
MODELO = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def cargar_config_prompts() -> dict:
    """Lee toda la configuración desde config/prompts.yaml."""
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def cargar_system_prompt() -> str:
    """Lee el system prompt desde config/prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("system_prompt", "Eres un asistente útil. Responde en español.")


def obtener_mensaje_error() -> str:
    """Retorna el mensaje de error configurado en prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo en unos minutos.")


def obtener_mensaje_fallback() -> str:
    """Retorna el mensaje de fallback configurado en prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpa, no entendí tu mensaje. ¿Podrías reformularlo?")


async def generar_respuesta(mensaje: str, historial: list[dict]) -> str:
    """
    Genera una respuesta usando Groq.

    Args:
        mensaje: El mensaje nuevo del usuario.
        historial: Lista de mensajes anteriores [{"role": "user/assistant", "content": "..."}].

    Returns:
        La respuesta generada por el modelo.
    """
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = cargar_system_prompt()

    # Groq usa el formato OpenAI: el system prompt va como primer mensaje
    mensajes = [{"role": "system", "content": system_prompt}]

    for msg in historial:
        mensajes.append({
            "role": msg["role"],
            "content": msg["content"],
        })

    mensajes.append({"role": "user", "content": mensaje})

    try:
        response = await client.chat.completions.create(
            model=MODELO,
            messages=mensajes,
            max_tokens=1024,
            temperature=0.7,
        )

        respuesta = response.choices[0].message.content
        usage = response.usage
        logger.info(
            f"Respuesta generada con {MODELO} "
            f"({usage.prompt_tokens} in / {usage.completion_tokens} out)"
        )
        return respuesta

    except Exception as e:
        logger.error(f"Error Groq API: {e}")
        return obtener_mensaje_error()
