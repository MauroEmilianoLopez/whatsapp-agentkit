# SOUL.md — VendIA

## Que es

VendIA es una capa comercial inteligente sobre WhatsApp para concesionarias de autos usados en Argentina y LATAM.

No es un CRM. No es una plataforma que reemplaza herramientas existentes. No es un bot que cierra ventas. Es una capa que se monta sobre el WhatsApp que la concesionaria ya usa, y lo vuelve un canal comercial ordenado: cada consulta se responde, se califica, se registra, y los leads calientes se derivan al vendedor humano en tiempo real.

## Por que existe

Las concesionarias de autos usados en Argentina venden mayoritariamente por WhatsApp. Reciben consultas desde Marketplace, Instagram, MercadoLibre, referidos y publicidad. Pero el canal esta roto: las consultas llegan tarde o no llegan, no hay seguimiento, no hay registro, y nadie sabe cuanto dinero se pierde por no responder.

El problema no es que falte tecnologia. El problema es que la tecnologia existente le pide al dueño cambiar su forma de trabajar. Y el dueño no va a cambiar su WhatsApp, porque su WhatsApp es donde ya esta su negocio. La solucion no puede ser "usa otro sistema". Tiene que ser "segui usando WhatsApp, yo te lo vuelvo mas inteligente".

VendIA existe porque ningun jugador grande va a resolver este problema bien para una concesionaria argentina mediana. Los productos horizontales apuntan a retail mayorista con compra recurrente. Las concesionarias venden bienes caros, de baja frecuencia, con permuta y financiacion: necesitan otro tipo de inteligencia, y necesitan a alguien que entienda el rubro.

## Para quien

Cliente ideal: concesionaria mediana en Argentina, con 20 a 100+ consultas de WhatsApp por dia. El dueño o gerente comercial decide y suele responder mensajes el mismo. Tienen vendedores propios que hoy reciben los chats desorganizados.

No es para: concesionarias muy chicas, concesionarias muy grandes con CRM corporativo, o cualquier rubro que no sea venta de vehiculos usados en LATAM.

## Principios innegociables

Uno: el bot nunca cierra ventas. Responde, califica, registra, deriva al humano.

Dos: el bot nunca inventa informacion. Si no sabe, lo dice.

Tres: la concesionaria nunca pierde el control. El dueño define que responde el bot.

Cuatro: el WhatsApp es del cliente, no nuestro. Sin lock-in.

Cinco: el vendedor humano es el cierre. Esa division es feature, no limitacion.

## Que NO es

No es un agente que reemplaza al vendedor. No es un CRM. No es una plataforma que el dueño tiene que aprender. No es un bot generico para todos los rubros. No es codigo propietario de cero: es un fork MIT adaptado, y la defensibilidad esta en el conocimiento del rubro.

## Decisiones de arquitectura

Stack: FastAPI + Python, DeepSeek como modelo de IA (deepseek/deepseek-chat, decision por costo bajo y consistencia con el stack local de OpenClaw), SQLite local / PostgreSQL prod, deploy en Railway.

Proveedor de WhatsApp: Whapi para validar con primer cliente piloto, migracion obligatoria a Cloud API (via 360Dialog o Twilio) antes de escalar a multiples clientes.

Patron: adaptador para providers (Whapi/Meta/Twilio intercambiables). Separacion entre cerebro, memoria, tools y providers.

Bug conocido del framework base (heredado de whatsapp-agentkit): cuando se deploya con PostgreSQL en Railway, agent/memory.py reescribe postgresql:// a postgresql+asyncpg://, pero el requirements.txt template solo trae aiosqlite. Si no se agrega asyncpg explicito a requirements.txt, el contenedor crashea con ModuleNotFoundError. A revisar antes del deploy.

Bug conocido de Argentina: webhooks de Meta entregan numeros con prefijo 549 (formato WhatsApp Argentina con 9 movil), pero Meta exige formato 54 sin el 9 al enviar respuestas. Resuelto en meta.py via _normalizar_telefono_ar().

Filosofia: clean architecture, type safety, skills reutilizables, spec primero codigo despues, cambios documentados en AGENTS.md.

## Metrica que importa

Leads recuperados que antes se perdian. Punto.

## Estado

Version 0.1 (pre-MVP). Fork de Hainrixz/whatsapp-agentkit (MIT), adaptado antes para Valeria (estudio juridico, modelo Groq llama-3.3-70b-versatile). Proximo hito: primer cliente piloto pagando en concesionaria argentina mediana.
