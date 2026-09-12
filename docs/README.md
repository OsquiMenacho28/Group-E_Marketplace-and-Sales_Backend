# MaxiConecta — Marketplace y Ventas
## Documentación Oficial del Sistema de Información

Bienvenido al repositorio de documentación del sistema **MaxiConecta Marketplace y Ventas** (Grupo E - Taller de Sistemas de Información, Universidad Católica Boliviana "San Pablo").

El proyecto abarca una solución omnicanal completa (canales digitales y puntos de venta físicos) que forma parte integral de un ERP corporativo distribuido, estructurado bajo una arquitectura de microservicios desacoplada con **dos repositorios**:
- **`frontend/`**: Aplicación cliente construida en Vue 3 + TypeScript, Pinia, Vite y Tailwind CSS / Flowbite, albergando tres interfaces: Marketplace web, Punto de Venta (POS) y Panel Administrativo.
- **`backend/`**: Microservicios y API Gateway desarrollados en Python con FastAPI, Pydantic, Supabase (PostgreSQL), Redis y Docker.

---

## Índice de Documentación

1. **[01 - Resumen Ejecutivo](./01-resumen-ejecutivo.md)**
   - Presentación del sistema, propuesta de valor y catálogo de usuarios/actores.
2. **[02 - Arquitectura y Tecnología](./02-arquitectura-tecnologica.md)**
   - Modelo de arquitectura de microservicios, capas de presentación, negocio y persistencia, y stack tecnológico detallado.
3. **[03 - Modelo de Datos y Flujos de Información](./03-modelo-datos-y-flujos.md)**
   - Modelo estático de clases y entidades principales (diagramas Mermaid) y diagramas de secuencia de los flujos críticos (Marketplace, POS, Devoluciones, Cotizaciones B2B).
4. **[04 - Requerimientos Funcionales](./04-requerimientos-funcionales.md)**
   - Catálogo exhaustivo de los 50 Requerimientos Funcionales (RF-01 a RF-50) clasificados en las 8 épicas del sistema.
5. **[05 - Requerimientos No Funcionales](./05-requerimientos-no-funcionales.md)**
   - Especificaciones de seguridad, rendimiento, disponibilidad, escalabilidad, mantenibilidad, usabilidad, interoperabilidad y trazabilidad (RNF-01 a RNF-08).
6. **[06 - Interoperabilidad con el ERP Corporativo](./06-interoperabilidad-erp.md)**
   - Requerimientos y contratos de interoperabilidad (RIO) con los 6 módulos externos: Inventarios, Pagos y Facturación, Contabilidad, CRM, Entregas/Despachos y Producción/Logística.
7. **[07 - Plan de Proyecto en Jira y Cronograma Gantt](./07-plan-proyecto-jira.md)**
   - Estructura WBS (Nivel 1 y 2), matriz de dependencias Finish-to-Start, enlace a Jira y cronograma de ejecución.
8. **[08 - Plan de Sprints e Historias de Usuario para Jira](./08-historias-de-usuario-jira.md)**
   - Catálogo de las 50 Historias de Usuario distribuidas en 4 Sprints, con criterios de aceptación y subtareas de desarrollo estimadas en horas.

---

## Estructura del Espacio de Trabajo

```text
Sistema_ventas/
├── backend/                  # Repositorio Backend (FastAPI, Microservicios, API Gateway)
├── frontend/                 # Repositorio Frontend (Vue 3, Pinia, Tailwind CSS)
├── docs/                     # Especificación técnica y funcional completa (.md)
│   ├── README.md
│   ├── 01-resumen-ejecutivo.md
│   ├── 02-arquitectura-tecnologica.md
│   ├── 03-modelo-datos-y-flujos.md
│   ├── 04-requerimientos-funcionales.md
│   ├── 05-requerimientos-no-funcionales.md
│   ├── 06-interoperabilidad-erp.md
│   ├── 07-plan-proyecto-jira.md
│   └── 08-historias-de-usuario-jira.md
├── .agents/                  # Configuración y agente de IA para el proyecto
│   ├── agent.md              # Instrucciones y directrices del agente para el proyecto
│   └── skills/               # Habilidades especializadas del agente
│       ├── fastapi-backend-dev/
│       ├── vue3-frontend-dev/
│       └── erp-interoperability/
└── AGENTS.md                 # Enlace raíz a las directrices del agente
```
