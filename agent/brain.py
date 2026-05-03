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

# override=False explícito: no pisar variables que ya estén en el entorno del proceso
# (las que inyecta Railway, Docker -e, systemd, etc.). Es el default de la librería,
# pero lo hacemos explícito para que nadie lo cambie por accidente.
load_dotenv(override=False)
logger = logging.getLogger("agentkit")

# Modelo por defecto — configurable via env
MODELO = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Cliente Groq con inicialización lazy.
# NO se construye al importar el módulo: si GROQ_API_KEY no está presente,
# el import seguiría funcionando y los logs de startup pueden ejecutarse
# antes de que falle la primera llamada al LLM (con un error informativo).
_client: AsyncGroq | None = None


def validar_configuracion() -> dict:
    """
    Devuelve un diagnóstico seguro del estado de las env vars del LLM.
    Pensado para loguear al startup. NUNCA devuelve la API key completa.
    """
    api_key = os.getenv("GROQ_API_KEY")
    return {
        "GROQ_API_KEY_present": bool(api_key),
        "GROQ_API_KEY_length": len(api_key) if api_key else 0,
        "GROQ_API_KEY_prefix": (api_key[:4] + "...") if api_key else "(missing)",
        "GROQ_MODEL": MODELO,
    }


def _get_client() -> AsyncGroq:
    """
    Construye el cliente Groq la primera vez que se usa.
    Si GROQ_API_KEY no está, levanta RuntimeError con mensaje DIAGNÓSTICO claro.
    """
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Lista los nombres de env vars visibles, sin valores, para diagnóstico.
        # Filtra ruido del SO para que el mensaje quede legible en logs de Railway.
        ruido = ("PATH", "PYTHON", "LANG", "LC_", "HOME", "PWD", "SHLVL",
                "TERM", "USER", "HOSTNAME", "OLDPWD", "_=")
        visibles = sorted(
            k for k in os.environ
            if not any(k.startswith(p) for p in ruido)
        )
        raise RuntimeError(
            "GROQ_API_KEY no está disponible en el entorno del contenedor.\n"
            f"Variables de entorno presentes (sin valores): {visibles}\n"
            f"Total de env vars: {len(os.environ)}\n"
            "Verificá en Railway:\n"
            "  1. Variables están en el SERVICIO, no a nivel de proyecto\n"
            "  2. El nombre es exactamente GROQ_API_KEY (case-sensitive)\n"
            "  3. El valor empieza con gsk_ y no tiene comillas ni espacios\n"
            "  4. Hiciste 'Redeploy' después de guardar las variables"
        )

    _client = AsyncGroq(api_key=api_key)
    logger.info(f"Cliente Groq inicializado (key prefix: {api_key[:4]}..., longitud: {len(api_key)})")
    return _client


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
        client = _get_client()
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
