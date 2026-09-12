# MaxiConecta — Repositorio Backend

Arquitectura de Microservicios y API Gateway en **FastAPI (Python 3.10+)** con persistencia en **Supabase (PostgreSQL)**, **Redis** para caché y reservas de stock temporal, y orquestación con **Docker Compose**.

---

## 📁 Estructura del Repositorio

```text
backend/
├── docs/                     # Especificaciones del proyecto, RFs, RIO, Jira
│   ├── 01-resumen-ejecutivo.md
│   ├── 02-arquitectura-tecnologica.md
│   ├── 03-modelo-datos-y-flujos.md
│   ├── 04-requerimientos-funcionales.md
│   ├── 05-requerimientos-no-funcionales.md
│   ├── 06-interoperabilidad-erp.md
│   ├── 07-plan-proyecto-jira.md
│   └── 08-historias-de-usuario-jira.md
├── db/                       # DDL y scripts relacionales de Supabase
│   └── schema.sql            # 22 tablas, tipos ENUM, UUIDs e índices
├── gateway/                  # API Gateway inverso (puerto 8000)
├── services/                 # Los 6 microservicios independientes
│   ├── catalogo/             # Puerto 8001 (RF-01 a RF-08)
│   ├── pos/                  # Puerto 8002 (RF-09 a RF-12)
│   ├── carrito/              # Puerto 8003 (RF-13 a RF-21)
│   ├── clientes/             # Puerto 8004 (RF-22 a RF-26)
│   ├── ordenes/              # Puerto 8005 (RF-27 a RF-39)
│   └── reportes/             # Puerto 8006 (RF-46 a RF-48)
├── shared/                   # Módulos transversales (Config, DB, Redis, Auth, RIO)
├── docker-compose.yml        # Orquestador del backend y Redis
├── test_supabase.py          # Script de validación de conexión a Supabase
├── .env.example              # Plantilla de variables de entorno
└── .gitignore                # Ignora .env, cachés y artefactos locales
```

---

## 🏗️ Topología de Microservicios y Puertos

| Servicio | Puerto | Swagger UI | Responsabilidad |
| :--- | :---: | :---: | :--- |
| **`gateway`** | `8000` | [http://localhost:8000/docs](http://localhost:8000/docs) | Gateway unificado, CORS, RBAC y enrutamiento hacia microservicios |
| **`ms-catalogo`** | `8001` | [http://localhost:8001/docs](http://localhost:8001/docs) | Catálogo, categorías jerárquicas, variantes y precios |
| **`ms-pos`** | `8002` | [http://localhost:8002/docs](http://localhost:8002/docs) | Puntos de venta físicos, turnos, arqueo de caja y tickets |
| **`ms-carrito`** | `8003` | [http://localhost:8003/docs](http://localhost:8003/docs) | Carrito en Redis, cupones y bloqueo temporal de existencias |
| **`ms-clientes`** | `8004` | [http://localhost:8004/docs](http://localhost:8004/docs) | Perfiles de clientes, direcciones, puntos y sincronización CRM |
| **`ms-ordenes`** | `8005` | [http://localhost:8005/docs](http://localhost:8005/docs) | Máquina de estados de órdenes, pagos, cancelaciones y devoluciones |
| **`ms-reportes`** | `8006` | [http://localhost:8006/docs](http://localhost:8006/docs) | Tablero de KPIs, reportes de ventas y embudo de conversión |
| **`redis`** | `6379` | — | Memoria volátil para sesiones de carrito y TTL de stock |

---

## ⚙️ Configuración Inicial

1. **Crear archivo de entorno `.env`:**
   ```powershell
   Copy-Item .env.example .env
   ```
2. **Configurar las credenciales de Supabase en `.env`:**
   - `SUPABASE_URL`
   - `SUPABASE_KEY` (anon public)
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `DATABASE_URL`

3. **Validar conexión a la base de datos:**
   ```powershell
   python test_supabase.py
   ```

---

## 🚀 Ejecución del Backend

### Opción A: Orquestación Total con Docker Compose (Recomendado)
Desde la carpeta `backend/`:
```powershell
docker compose up --build
```
Para ejecutar en segundo plano:
```powershell
docker compose up --build -d
```
Para detener los contenedores:
```powershell
docker compose down
```

### Opción B: Ejecución Individual para Desarrollo
Si deseas desarrollar y probar un microservicio específico:
```powershell
# 1. Asegúrate de tener Redis corriendo (ej. con Docker)
docker run -d -p 6379:6379 --name redis-dev redis:7-alpine

# 2. Instalar dependencias del servicio deseado
cd services/catalogo
pip install -r requirements.txt

# 3. Iniciar con recarga en caliente
uvicorn app.main:app --reload --port 8001
```

---

## 📄 Base de Datos y Documentación
- **DDL Relacional:** [db/schema.sql](db/schema.sql) para ser ejecutado en el **SQL Editor** de Supabase.
- **Historias de Usuario Jira:** [docs/08-historias-de-usuario-jira.md](docs/08-historias-de-usuario-jira.md).
- **Contratos ERP RIO:** [docs/06-interoperabilidad-erp.md](docs/06-interoperabilidad-erp.md).
