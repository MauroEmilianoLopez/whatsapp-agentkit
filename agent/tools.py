# agent/tools.py — Herramientas del agente
# Generado por AgentKit

"""
Herramientas específicas del Estudio Jurídico Barchilon.
Casos de uso configurados: FAQ + Agendar consultas + Calificar leads.
"""

import os
import yaml
import logging
from datetime import datetime, time
from typing import Optional

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    """Carga la información del negocio desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    """
    Retorna el horario del estudio y si está abierto en este momento.
    Horario: L-V 8-19, Sáb 8-13.
    """
    info = cargar_info_negocio()
    ahora = datetime.now()
    dia = ahora.weekday()  # 0=Lun ... 6=Dom
    hora_actual = ahora.time()

    abierto = False
    if dia <= 4:  # Lunes a Viernes
        abierto = time(8, 0) <= hora_actual <= time(19, 0)
    elif dia == 5:  # Sábado
        abierto = time(8, 0) <= hora_actual <= time(13, 0)

    return {
        "horario": info.get("negocio", {}).get("horario", "No disponible"),
        "esta_abierto": abierto,
    }


def buscar_en_knowledge(consulta: str) -> str:
    """
    Busca información relevante en los archivos de /knowledge.
    Útil para responder preguntas frecuentes con datos del estudio.
    """
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


# ════════════════════════════════════════════════════════════
# AGENDAR CONSULTAS — caso de uso del Estudio Barchilon
# ════════════════════════════════════════════════════════════

def registrar_solicitud_consulta(
    telefono: str,
    nombre: str,
    descripcion_caso: str,
    area: str,
    preferencia_horario: Optional[str] = None,
    urgencia: str = "normal",
) -> dict:
    """
    Registra una solicitud de consulta para que la Dra. Barchilon coordine.
    Por ahora guarda en un archivo JSON local. Migrable a calendario/CRM más adelante.
    """
    import json

    os.makedirs("data", exist_ok=True)
    ruta = "data/consultas_pendientes.json"

    consulta = {
        "telefono": telefono,
        "nombre": nombre,
        "descripcion_caso": descripcion_caso,
        "area": area,
        "preferencia_horario": preferencia_horario,
        "urgencia": urgencia,
        "creada": datetime.utcnow().isoformat(),
        "estado": "pendiente",
    }

    pendientes = []
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                pendientes = json.load(f)
        except (json.JSONDecodeError, IOError):
            pendientes = []

    pendientes.append(consulta)

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(pendientes, f, ensure_ascii=False, indent=2)

    logger.info(f"Consulta registrada: {nombre} ({area}) — {telefono}")
    return consulta


# ════════════════════════════════════════════════════════════
# CALIFICAR LEADS — caso de uso del Estudio Barchilon
# ════════════════════════════════════════════════════════════

AREAS_VALIDAS = {
    "familia": ["divorcio", "alimentos", "tenencia", "adopción", "violencia"],
    "civil": ["contrato", "daños", "perjuicios", "sucesión", "herencia"],
    "laboral": ["despido", "accidente", "trabajo", "indemnización"],
    "penal": ["penal", "denuncia", "defensa", "imputado"],
}


def detectar_area_legal(texto: str) -> Optional[str]:
    """
    Detecta a qué área del derecho pertenece la consulta del cliente.
    Heurística simple por palabras clave (el LLM hace lo grueso, esto es backup).
    """
    texto_lower = texto.lower()
    for area, palabras in AREAS_VALIDAS.items():
        if any(palabra in texto_lower for palabra in palabras):
            return area
    return None


def calificar_lead(telefono: str, datos: dict) -> dict:
    """
    Califica un lead según la información recolectada.
    Útil para que la Dra. Barchilon priorice respuestas.
    """
    score = 0
    razones = []

    if datos.get("area"):
        score += 3
        razones.append(f"Área identificada: {datos['area']}")

    if datos.get("descripcion_caso") and len(datos["descripcion_caso"]) > 30:
        score += 2
        razones.append("Caso descripto en detalle")

    if datos.get("urgencia") == "urgente":
        score += 3
        razones.append("Cliente reporta urgencia")

    if datos.get("preferencia_horario"):
        score += 1
        razones.append("Disponibilidad horaria definida")

    if score >= 7:
        prioridad = "alta"
    elif score >= 4:
        prioridad = "media"
    else:
        prioridad = "baja"

    return {
        "telefono": telefono,
        "score": score,
        "prioridad": prioridad,
        "razones": razones,
    }
