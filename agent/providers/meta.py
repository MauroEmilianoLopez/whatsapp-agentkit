# agent/providers/meta.py — Adaptador para Meta Cloud API
# Implementado para VendIA (T-09)

"""
Proveedor de WhatsApp usando Meta Cloud API (Graph API v25.0).
Implementa la interfaz ProveedorWhatsApp definida en base.py.

Requiere en .env:
  WHATSAPP_PROVIDER=meta
  META_ACCESS_TOKEN=<token>
  META_PHONE_NUMBER_ID=<id>
  META_VERIFY_TOKEN=<string_elegido_por_el_dueño>
  META_APP_SECRET=<opcional>

Documentación:
  https://developers.facebook.com/docs/whatsapp/cloud-api
"""

import os
import hashlib
import hmac
import logging
from fastapi import Request
from fastapi.responses import PlainTextResponse
import httpx

from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")

# Versión de la Graph API
GRAPH_API_VERSION = "v25.0"
# Entrada de mensajes que identifican broadcasts
TIPOS_BROADCAST = {"broadcast", "template_button_send"}


def _normalizar_telefono_ar(telefono: str) -> str:
    """
    Normaliza números argentinos para Meta Cloud API.

    Meta Cloud API recibe webhooks con formato 5492664195054
    (54 + 9 + código área sin 0 + número), pero al enviar
    respuestas exige el formato sin el 9: 542664195054.

    Solo aplica a Argentina (prefijo 549 + 10 dígitos = 13 total).
    Otros países se devuelven sin cambios.
    """
    if telefono.startswith("549") and len(telefono) == 13:
        return "54" + telefono[3:]
    return telefono


class ProveedorMeta(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Meta Cloud API (Graph API)."""

    def __init__(self):
        self.token = os.getenv("META_ACCESS_TOKEN")
        self.phone_number_id = os.getenv("META_PHONE_NUMBER_ID")
        self.verify_token = os.getenv("META_VERIFY_TOKEN", "")
        self.app_secret = os.getenv("META_APP_SECRET", "")
        self.url_envio = (
            f"https://graph.facebook.com/{GRAPH_API_VERSION}"
            f"/{self.phone_number_id}/messages"
        )

    # ────────────────────────────────────────────────────────────
    # validar_webhook (GET) — Meta Challenge
    # ────────────────────────────────────────────────────────────

    async def validar_webhook(self, request: Request) -> PlainTextResponse | None:
        """
        Responde al GET de verificación de Meta Cloud API.

        Meta envía:
          ?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>

        Si hub.verify_token coincide con META_VERIFY_TOKEN, responde
        con el challenge en texto plano. Si no, retorna 403.
        """
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == self.verify_token and challenge:
            logger.info("Webhook verificado con Meta Cloud API")
            return PlainTextResponse(challenge)

        logger.warning(
            f"Intento de verificación fallido: mode={mode!r}, "
            f"token_match={token == self.verify_token}"
        )
        # Retornar None para que main.py mantenga el comportamiento por defecto
        return None

    # ────────────────────────────────────────────────────────────
    # parsear_webhook (POST) — Mensajes entrantes
    # ────────────────────────────────────────────────────────────

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload de Meta Cloud API y aplica filtros.

        Estructura del payload de Meta:
        {
          "object": "whatsapp_business_account",
          "entry": [{
            "id": "...",
            "changes": [{
              "field": "messages",
              "value": {
                "messaging_product": "whatsapp",
                "metadata": { "phone_number_id": "...", "display_phone_number": "..." },
                "contacts": [...],
                "messages": [{
                  "from": "5491112345678",
                  "id": "wamid.xxx",
                  "timestamp": "...",
                  "type": "text",
                  "text": { "body": "Hola" }
                }],
                "errors": [...]
              }
            }]
          }]
        }

        Filtros aplicados (en orden):
          1. Tipo broadcast/template_button_send → descartar
          2. Tipo system/notification → descartar
          3. from_me == true → descartar (mensaje propio, evitar loop)
          4. chat_id termina en @g.us → descartar (grupo)
          5. Tipo status → descartar (status updates)
          6. Mensaje sin texto → descartar
        """
        body = await request.json()

        # Validar que sea un webhook de WhatsApp Business
        if body.get("object") != "whatsapp_business_account":
            logger.debug("Ignorado: object no es whatsapp_business_account")
            return []

        mensajes = []

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "messages":
                    continue

                value = change.get("value", {})
                raw_messages = value.get("messages", [])

                for msg in raw_messages:
                    mensaje_id = msg.get("id", "")
                    from_number = msg.get("from", "")
                    msg_type = msg.get("type", "text")

                    # ── Filtro 1: broadcasts / template_button_send ──
                    if msg_type in TIPOS_BROADCAST:
                        logger.debug(
                            f"Ignorado (broadcast): tipo={msg_type!r} id={mensaje_id}"
                        )
                        continue

                    # ── Filtro 2: system / notification ──
                    if msg_type in ("system", "notification"):
                        logger.debug(
                            f"Ignorado (tipo {msg_type!r}): id={mensaje_id}"
                        )
                        continue

                    # ── Filtro 3: mensajes propios ──
                    # Meta no manda from_me explícito; en Cloud API
                    # los mensajes enviados por el bot no llegan al webhook
                    # (el webhook recibe sólo mensajes entrantes).
                    # Pero si por configuración llegan, se filtran por
                    # el número de origen (el propio negocio).
                    # Por ahora no hay from_me en Meta, este filtro es
                    # placeholder para consistencia con whapi.py.
                    # (el filtro real está en S-08 con override humano)

                    # ── Filtro 4: grupos ──
                    # Meta no marca grupos en el número de origen.
                    # Los mensajes de grupo se identifican porque el
                    # payload incluye contexto.group_id o porque se
                    # pueden detectar via metadata. Por ahora se filtra
                    # chequeando errores o ausencia de contacto.
                    # TODO: implementar detección de grupos cuando se
                    # active el webhook de grupos en Meta.

                    # ── Filtro 5: status updates ──
                    # Los status updates (sent/delivered/read) llegan
                    # como entries separados sin "messages", pero si
                    # por algún caso llegan como mensajes, los filtramos.
                    if msg_type in ("status", "message_status"):
                        logger.debug(
                            f"Ignorado (status): tipo={msg_type!r} id={mensaje_id}"
                        )
                        continue

                    # ── Extraer texto según tipo ──
                    texto = self._extraer_texto(msg, msg_type)

                    # ── Filtro 6: sin texto ──
                    if not texto:
                        logger.debug(
                            f"Ignorado (sin texto): tipo={msg_type!r} id={mensaje_id}"
                        )
                        continue

                    mensajes.append(MensajeEntrante(
                        telefono=from_number,
                        texto=texto,
                        mensaje_id=mensaje_id,
                        es_propio=False,
                    ))

        return mensajes

    def _extraer_texto(self, msg: dict, msg_type: str) -> str:
        """
        Extrae el texto del mensaje según su tipo.
        Meta envía distintos formatos según el tipo de mensaje.
        """
        if msg_type == "text":
            return msg.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            # Botones o listas: reply button
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                return interactive.get("button_reply", {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                return interactive.get("list_reply", {}).get("title", "")
        elif msg_type == "button":
            return msg.get("button", {}).get("text", "")
        elif msg_type == "location":
            location = msg.get("location", {})
            return (
                f"Ubicación: {location.get('latitude', '?')}, "
                f"{location.get('longitude', '?')}"
            )
        # Para tipos de mensaje no soportados (image, audio, document, etc.)
        # devolvemos string vacío para que el filtro lo descarte
        logger.debug(f"Tipo de mensaje no soportado para extracción: {msg_type!r}")
        return ""

    # ────────────────────────────────────────────────────────────
    # enviar_mensaje (POST a Graph API)
    # ────────────────────────────────────────────────────────────

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """
        Envía un mensaje de texto via Meta Cloud API.

        POST a /{GRAPH_API_VERSION}/{phone_number_id}/messages
        Body:
          {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": "<telefono>",
            "type": "text",
            "text": { "body": "<mensaje>" }
          }
        """
        if not self.token or not self.phone_number_id:
            logger.warning(
                "META_ACCESS_TOKEN o META_PHONE_NUMBER_ID no configurados "
                "— mensaje no enviado"
            )
            return False

        # Normalizar número argentino (Meta rechaza el 9 intermedio)
        telefono = _normalizar_telefono_ar(telefono)

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "text",
            "text": {"body": mensaje},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    self.url_envio,
                    json=payload,
                    headers=headers,
                )
                if r.status_code == 200:
                    return True
                else:
                    logger.error(
                        f"Error Meta API: {r.status_code} — {r.text}"
                    )
                    return False
        except httpx.HTTPError as e:
            logger.error(f"Meta API exception: {e.__class__.__name__}")
            return False
