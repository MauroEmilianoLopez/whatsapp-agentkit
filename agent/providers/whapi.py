# agent/providers/whapi.py — Adaptador para Whapi.cloud
# Generado por AgentKit

import os
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


class ProveedorWhapi(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Whapi.cloud (REST API simple)."""

    def __init__(self):
        self.token = os.getenv("WHAPI_TOKEN")
        self.url_envio = "https://gate.whapi.cloud/messages/text"

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload de Whapi.cloud y aplica filtros para que el agente
        sólo procese mensajes válidos. Los mensajes filtrados se loguean en
        DEBUG para no contaminar los logs de producción.

        Filtros aplicados (en orden):
          1. chat_id termina en @g.us  → grupo, ignorar
          2. from_me == true           → mensaje propio del canal, evitar loop
          3. type in {system, notification} → notificación de WhatsApp
        """
        body = await request.json()
        mensajes = []
        for msg in body.get("messages", []):
            mensaje_id = msg.get("id", "")
            chat_id = msg.get("chat_id", "")
            msg_type = msg.get("type", "text")
            from_me = msg.get("from_me", False)

            if chat_id.endswith("@g.us"):
                logger.debug(f"Ignorado (grupo): chat_id={chat_id} id={mensaje_id}")
                continue

            if from_me:
                logger.debug(f"Ignorado (propio): id={mensaje_id}")
                continue

            if msg_type in ("system", "notification"):
                logger.debug(f"Ignorado (tipo {msg_type!r}): id={mensaje_id}")
                continue

            mensajes.append(MensajeEntrante(
                telefono=chat_id,
                texto=msg.get("text", {}).get("body", ""),
                mensaje_id=mensaje_id,
                es_propio=from_me,
            ))
        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envía mensaje via Whapi.cloud."""
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado — mensaje no enviado")
            return False
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    self.url_envio,
                    json={"to": telefono, "body": mensaje},
                    headers=headers,
                )
                if r.status_code != 200:
                    logger.error(f"Error Whapi: {r.status_code} — {r.text}")
                return r.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Whapi exception: {e.__class__.__name__}")
            return False
