# Diagnóstico T-01 — Estado actual del repo

**Proyecto:** VendIA (fork de whatsapp-agentkit, actualmente configurado como "Valeria" para Estudio Jurídico Barchilon)
**Fecha:** 2026-06-02
**Estado:** Pre-MVP, bloqueado para migrar a VendIA

---

## Estructura del repo

```
vendia/
├── agent/
│   ├── __init__.py               (vacío)
│   ├── main.py                   Servidor FastAPI + webhook
│   ├── brain.py                  Cerebro LLM (Groq → llama-3.3-70b-versatile)
│   ├── memory.py                 Persistencia SQLite/PostgreSQL
│   ├── tools.py                  Herramientas específicas de Valeria
│   └── providers/
│       ├── __init__.py           Factory de proveedores
│       ├── base.py               Interfaz abstracta ProveedorWhatsApp
│       └── whapi.py              Adaptador Whapi.cloud
├── config/
│   ├── business.yaml             Config del negocio (Estudio Barchilon)
│   └── prompts.yaml              System prompt de Valeria
├── knowledge/
│   ├── .gitkeep
│   └── estudio_barchilon.md      Base de conocimiento del estudio
├── tests/
│   ├── __init__.py
│   └── test_local.py             Simulador de chat en terminal
├── .env                          Config local
├── .env.example                  Template de variables
├── requirements.txt              Dependencias Python
├── Dockerfile                    Build para Railway
├── start.sh                      Script de setup interactivo
├── docker-compose.yml            Orquestación local
├── CLAUDE.md                     Config de Claude (proyecto heredado)
├── AGENTS.md                     Plan de tareas (VendIA)
├── SOUL.md                       Documento de visión (VendIA)
├── README.md                     README original del fork
├── LICENSE                       MIT
└── agentkit.db                   Base SQLite de Valeria en producción
```

---

## Análisis por archivo

### 1. `agent/main.py` — Framework + adaptación mínima

**Qué hace:** Servidor FastAPI con tres endpoints:
- `GET /` → health check
- `GET /webhook` → verificación (para Meta Cloud API)
- `POST /webhook` → recibe mensajes, llama a brain, guarda en memory, envía respuesta
- `POST /notify` → endpoint protegido para notificaciones automáticas desde CRM

**Framework vs modificación:** ~95% framework. Las únicas adiciones sobre el template base son:
- El endpoint `/notify` (para Valeria, notificaciones del CRM del estudio)
- El log de diagnóstico de arranque (`_diagnostico_arranque`)

**Dificultad de adaptación a VendIA:** FÁCIL (1-2 hs). El webhook handler actual no tiene filtro de canal (S-01) — procesa todo lo que llega. Hay que agregar un `if` al inicio que descarte grupos, broadcasts, status. El resto de la estructura (FastAPI, lifespan, proveedores) sirve igual.

### 2. `agent/brain.py` — Framework + conexión a Groq

**Qué hace:** Carga el system prompt de `prompts.yaml`, construye el mensaje con historial, llama a Groq (llama-3.3-70b-versatile) y devuelve la respuesta.

**Framework vs modificación:** 100% framework. Cero modificaciones sobre el template AgentKit. Usa Groq, el modelo llama-3.3-70b-versatile.

**Dificultad de adaptación a VendIA:** MEDIA (3-4 hs). Hay que:
- Cambiar de Groq a DeepSeek (`deepseek/deepseek-chat`) — cambiar cliente HTTP y API
- El `_get_client()` y `validar_configuracion()` están atados a Groq, hay que refactorizar a un provider pattern de LLM o reemplazar la implementación
- El system prompt se carga de YAML (ok, eso sirve), pero la función de fallback y error también necesitan revisión

### 3. `agent/memory.py` — Framework con ajuste para PostgreSQL

**Qué hace:** Modelo SQLAlchemy para mensajes (`telefono`, `role`, `content`, `timestamp`). CRUD básico: guardar, obtener historial (últimos 20), limpiar. Soporta SQLite local y PostgreSQL en producción.

**Framework vs modificación:** ~98% framework. La única línea modificada es el reemplazo de `postgresql://` a `postgresql+asyncpg://` (el bug conocido). El fix está presente.

**Dificultad de adaptación a VendIA:** MEDIA (4-5 hs). memory.py actual guarda solo mensajes crudos. VendIA necesita:
- Agregar tabla/campos para leads: nivel de calificación (frío/tibio/caliente), vehículo de interés, forma de compra, permuta, urgencia, mejor horario
- Agregar lógica de actualización de metadata por lead
- Agregar consultas para reportes diarios y seguimiento
- Posible migración de esquema SQLAlchemy

### 4. `agent/tools.py` — 100% específico de Valeria

**Qué hace:** Herramientas concretas para el Estudio Barchilon:
- `cargar_info_negocio()` — lee `business.yaml`
- `obtener_horario()` — retorna si está abierto ahora
- `buscar_en_knowledge()` — busca texto en archivos de `/knowledge`
- `registrar_solicitud_consulta()` — guarda solicitudes de consulta en JSON
- `detectar_area_legal()` — heurística para detectar área del derecho
- `calificar_lead()` — scoring de leads con prioridad alta/media/baja

**Framework vs modificación:** 0% framework. Es código 100% específico de Valeria. No pertenece al template AgentKit.

**Dificultad de adaptación a VendIA:** ALTA (6-8 hs). Hay que reescribir completamente:
- Reemplazar todo lo de estudio jurídico por herramientas de concesionaria
- Crear S-03: tool de consulta a Google Sheet de inventario
- Crear S-04: tool de captura de datos comerciales (vehículo, forma de compra, permuta)
- El pattern de tools existe y es extensible, pero el contenido es descartable

### 5. `agent/providers/whapi.py` — Framework + filtros de Valeria

**Qué hace:** Adaptador para Whapi.cloud. Parsea webhooks, filtra grupos (`@g.us`), mensajes propios (`from_me`), y mensajes de sistema/notificación. Envía mensajes via REST API.

**Framework vs modificación:** ~80% framework. Los filtros (`@g.us`, `from_me`, `type in system/notification`) son parte del template AgentKit original, no son específicos de Valeria.

**Dificultad de adaptación a VendIA:** BAJA (1 h). Whapi sirve igual para VendIA. Los filtros existentes ya cubren parte de S-01 (pero falta descartar broadcasts y status). S-01 requiere agregar filtro adicional para broadcasts y asegurar que el filtro esté en `main.py` también.

### 6. `config/prompts.yaml` — 100% específico de Valeria

**Qué hace:** Contiene el system prompt completo de Valeria (asistente virtual del Estudio Jurídico Barchilon) más mensajes de fallback y error.

**Framework vs modificación:** 0% framework. Es contenido 100% específico del negocio.

**Dificultad de adaptación a VendIA:** ALTA conceptualmente, BAJA técnicamente (2-3 hs). Hay que reescribir completamente el system prompt para que sea un asistente comercial de concesionaria. El formato YAML sirve. La dificultad está en el contenido: tono, reglas de negocio, criterios de derivación, guion de calificación.

### 7. Archivos auxiliares

| Archivo | Estado | Notas |
|---|---|---|
| `config/business.yaml` | 100% Valeria | Reemplazar con datos de concesionaria |
| `knowledge/estudio_barchilon.md` | 100% Valeria | Reemplazar con datos de inventario/concesionaria |
| `.env.example` | Framework | Agregar vars para Google Sheets, número vendedor, dueño |
| `tests/test_local.py` | 95% framework | Sirve para test local, requiere cambiar import si brain.py cambia mucho |
| `Dockerfile` | Framework | Servirá igual. Agregar dependencias de Google Sheets si es necesario |
| `requirements.txt` | Framework + asyncpg | Ya incluye asyncpg (bug conocido resuelto). Google Sheets requiere `gspread` + `oauth2client` |
| `start.sh` | Framework (Claude Code) | Script de onboarding obsoleto para VendIA |

---

## Estimación de horas por tarea

| Tarea | Descripción | Estimación |
|---|---|---|
| **T-01** | ✅ **COMPLETADA** | — |
| **T-02** | S-01 Filtro de canal (modificar webhook handler + whapi) | **2-3 hs** |
| **T-03** | Reescritura de system prompt para concesionaria | **3-4 hs** |
| **T-04** | S-03 Tool de consulta a Google Sheets de inventario | **4-5 hs** |
| **T-05** | S-02 + S-04 Calificación de leads y captura de datos | **6-8 hs** |
| **T-06** | S-05 Alerta a vendedor cuando lead caliente | **3-4 hs** |
| **T-07** | S-07 Reporte diario al dueño (cron 20:00) | **3-4 hs** |
| **T-08** | S-06 + S-08 Follow-up automático + override humano | **5-6 hs** |
| **Total T-02 a T-08** | | **26-34 hs** |

### Costos de refactor adicionales (no contemplados en T-02 a T-08)
- Cambio de Groq → DeepSeek en `brain.py`: ~3 hs
- Reemplazo total de `tools.py`: ~6-8 hs (ya incluido en T-04 + T-05)
- Reemplazo de `business.yaml` y `knowledge/`: ~1 h
- Actualización de `.env.example`: ~30 min
- Tests unitarios: ~2-3 hs (distribuido entre tareas)

---

## Riesgos identificados

1. **Bug conocido del framework:** `memory.py` reescribe `postgresql://` a `postgresql+asyncpg://`, pero si falta `asyncpg` en `requirements.txt` → crashea en Railway. Ya está solucionado (asyncpg en requirements.txt ✅).

2. **Base de datos actual (`agentkit.db`):** Contiene datos reales de Valeria en producción. AGENTS.md prohíbe tocarla. Cuidado con migraciones.

3. **Whapi como provider:** Es el más simple de configurar, pero SOUL.md exige migrar a Cloud API antes de escalar. Esto no está en ninguna tarea de AGENTS.md todavía.

4. **`brain.py` atado a Groq:** El cliente y el diagnóstico están hardcodeados a Groq. Migrar a DeepSeek implica refactorizar `_get_client()` o mejor aún, crear un provider pattern para el LLM similar al de WhatsApp. No está en el plan actual pero va a forzarse en T-03.

5. **No hay tests automatizados:** Solo existe `test_local.py` (simulador manual). No hay test unitarios ni de integración para ninguna tarea. AGENTS.md pide tests unitarios para S-01 pero no hay infraestructura de testing.

6. **CLAUDE.md (46 KB):** Archivo muy pesado de Claude Code heredado del proyecto original. Probablemente irrelevante para VendIA pero conviene revisar si tiene configuraciones que afecten.
