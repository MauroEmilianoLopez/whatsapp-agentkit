# AGENTS.md — VendIA

## Proposito

Plan operativo para adaptar el repo whatsapp-agentkit (configurado como "Valeria" para estudio juridico) en VendIA, agente comercial de WhatsApp para concesionarias de autos usados.

Define las skills del sistema y las tareas para llegar al MVP. Cada tarea es atomica, con criterios de aceptacion. Cualquier desviacion del plan se documenta aca antes de implementarse.

## Skills

### S-01: Filtro de canal
Procesar solo chats individuales 1 a 1. Descartar grupos, broadcasts, mensajes propios (enviados desde el celular del dueño) y mensajes de sistema al inicio del webhook handler.

### S-02: Calificacion de intencion
Clasificar cada conversacion en frio (consulta exploratoria), tibio (preguntas especificas, sin urgencia) o caliente (intencion clara de compra, urgencia o pedido de visita). Se actualiza en cada turno.

### S-03: Consulta de inventario
Consultar inventario antes de responder por disponibilidad. Fuente: Google Sheet con columnas marca, modelo, año, km, precio, estado, disponible. El bot nunca afirma disponibilidad sin consultar.

### S-04: Captura de datos comerciales
Capturar y persistir por cada lead: vehiculo de interes, forma de compra (contado/financiado/permuta), auto a entregar si hay permuta, urgencia, mejor horario de contacto. Guardado como metadata del lead.

### S-05: Alerta a vendedor
Cuando un lead pasa a caliente, enviar mensaje al numero del vendedor configurado con: nombre del cliente, vehiculo de interes, resumen en 3 lineas, link directo al chat de WhatsApp del cliente.

### S-06: Follow-up automatico
Lead tibio o caliente sin respuesta del cliente: a las 24 hs enviar primer follow-up, a las 72 hs enviar segundo y ultimo. Despues queda como lead inactivo para revision manual.

### S-07: Reporte diario al dueño
A las 20:00 hora local: enviar al dueño consultas recibidas, leads calientes generados, vehiculos mas consultados, leads pendientes de seguimiento, oportunidades perdidas.

### S-08: Override humano
Si un humano envia un mensaje al cliente desde el WhatsApp de la concesionaria, el bot se silencia automaticamente en esa conversacion por 12 horas. Despues vuelve a actuar salvo que el humano siga interviniendo.

## Tareas (orden de ejecucion)

### T-01: Diagnostico del repo
Estado: pendiente. Prioridad: critica, bloquea todo lo demas.
Leer agent/main.py, agent/brain.py, agent/memory.py, agent/providers/whapi.py, agent/tools.py (si existe), config/prompts.yaml.
Resumir que hace cada archivo, cuanto codigo es modificacion mia (Valeria) vs framework, y dificultad de adaptar a VendIA.
Aceptacion: documento de diagnostico por archivo y estimacion en horas de las tareas T-02 a T-08.
NO modificar nada.

### T-02: Implementar S-01 (filtro de canal)
Estado: pendiente, bloqueada por T-01. Prioridad: critica (bug de Valeria).
Modificar webhook handler para descartar grupos, broadcasts, status, mensajes propios y de sistema.
Aceptacion: test unitario con chat_type=group ignorado; test con chat individual procesado; verificacion manual en un grupo donde el bot no responde.

### T-03: Reescritura del prompt sistema
Estado: pendiente, bloqueada por T-01. Prioridad: alta.
Reemplazar config/prompts.yaml con prompt para asistente comercial de concesionaria argentina. Incluir tono, reglas de negocio (no prometer precios, no confirmar disponibilidad sin chequear, no inventar), guion de calificacion, criterios de derivacion a humano.
Aceptacion: simulador local responde 5 conversaciones tipo correctamente.

### T-04: Implementar S-03 (consulta de inventario)
Estado: pendiente, bloqueada por T-03. Prioridad: alta.
Crear tool que lee Google Sheet de inventario. Integrar al brain como contexto cuando el cliente pregunta por un auto especifico.
Aceptacion: el bot consulta el Sheet antes de afirmar disponibilidad; si no esta, lo dice; si esta, da datos correctos.

### T-05: Implementar S-02 + S-04 (calificacion y captura de datos)
Estado: pendiente, bloqueada por T-03. Prioridad: alta.
Extender memory.py para guardar nivel de lead, vehiculo de interes, forma de compra, permuta, urgencia. Crear logica de clasificacion post-respuesta.
Aceptacion: cada conversacion tiene los campos completos al cierre; clasificacion se actualiza en cada turno.

### T-06: Implementar S-05 (alerta a vendedor)
Estado: pendiente, bloqueada por T-05. Prioridad: alta.
Cuando un lead pasa a caliente, enviar mensaje al numero del vendedor configurado en .env. Incluir resumen y link.
Aceptacion: lead simulado caliente dispara mensaje al numero vendedor con datos correctos.

### T-07: Implementar S-07 (reporte diario)
Estado: pendiente, bloqueada por T-05. Prioridad: media.
Cron a las 20:00 hora local que arma y envia el reporte al numero del dueño.
Aceptacion: reporte llega a horario con los campos correctos.

### T-08: Implementar S-06 + S-08 (follow-up y override humano)
Estado: pendiente, bloqueada por T-05. Prioridad: media.
Sistema de follow-up programado y deteccion de intervencion humana para silenciar el bot.
Aceptacion: lead sin respuesta a las 24 hs recibe follow-up; intervencion humana silencia bot 12 hs.

### T-09: Adaptador Meta Cloud API
Estado: completada — 2026-06-04. Prioridad: critica (Whapi expirado, bloquea pruebas end-to-end).
Crear agent/providers/meta.py implementando ProveedorWhatsApp para Meta Cloud API.
Incluir parsear_webhook (formato Meta: entry > changes > value > messages) con los mismos filtros que whapi.py (grupos, propios, system/notification, broadcasts, status), enviar_mensaje via Graph API v25.0, y validar_webhook (GET con hub.mode/hub.verify_token/hub.challenge).
Actualizar agent/providers/__init__.py para que WHATSAPP_PROVIDER=meta instancie ProveedorMeta.
Actualizar .env.example con las nuevas variables META_*. No modificar .env real.
No modificar memory.py, brain.py, ni archivos no relacionados al adaptador.
Aceptacion: servidor arranca con WHATSAPP_PROVIDER=meta; GET /webhook responde al challenge de Meta; POST /webhook parsea payloads de Meta correctamente y filtra grupos/propios/system/broadcasts/status; enviar_mensaje hace POST a Graph API.
Bug corregido: main.py linea 109 retornaba PlainTextResponse(str(resultado)) en vez de resultado directo — Meta recibia repr() del objeto.
Bug corregido: numeros argentinos llegan como 549... pero Meta exige 54... al enviar. Solucion: _normalizar_telefono_ar() en meta.py.

### T-10: Token permanente Meta via System User
Estado: completada — 2026-06-06. Prioridad: alta.
Crear System User "VendIA Bot" en Business Manager, asignar activos (app, cuenta, WABA) con control total, generar token con permisos whatsapp_business_management + whatsapp_business_messaging.
Aceptacion: META_ACCESS_TOKEN del .env no caduca por al menos 60 dias; reinicio del servidor no rompe la conexion.
Nota: token expira ~2026-08-06. Programar recordatorio para regenerar antes de esa fecha.

### T-11: Filtro de grupos en provider Meta
Estado: pendiente. Prioridad: media.
Completar el TODO marcado en meta.py.parsear_webhook() para detectar mensajes de grupo via context.group_id en el payload de Meta Cloud API. Cuando se activen los webhooks de grupos en el dashboard de Meta, el bot debe descartarlos correctamente.
Aceptacion: si se activan webhooks de grupos en dashboard de Meta, el bot los descarta sin responder.

## Restricciones

No modificar archivos sin que este escrito en una tarea de este documento.
No tocar agentkit.db (base de Valeria en produccion).
No exponer contenido de .env al agente.
Mantener compatibilidad con Valeria mientras se desarrolla VendIA (no romper lo que ya funciona en Railway).
