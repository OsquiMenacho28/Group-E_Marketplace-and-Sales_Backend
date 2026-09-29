# 10. Bitácora de Cambios Técnicos — Búsqueda Facetada y Full-Text Search (US-06 / RF-06)

Este documento detalla la implementación integral de la historia de usuario **US-06** y el requerimiento funcional **RF-06 (Búsqueda Facetada)** en los repositorios de **MaxiConecta Marketplace y Ventas**.

---

## 1. Ficha Técnica del Release

| Atributo | Detalle |
| :--- | :--- |
| **Historia de Usuario** | **US-06:** *Como Cliente, quiero buscar productos por texto completo y filtros facetados para localizar rápidamente los artículos deseados.* |
| **Requerimiento Funcional** | **RF-06** (Búsqueda Facetada en Catálogo) |
| **Criterios de Aceptación** | 1. Búsqueda Full-Text Search (FTS) insensible a mayúsculas y tildes (`unaccent`).<br>2. Filtros facetados acumulativos combinables (categoría, marca, rango de precio y stock) con recuento dinámico de coincidencias.<br>3. Autocompletado predictivo (*typeahead*) con *debounce* de entrada.<br>4. Barra lateral interactiva con chips de filtros activos y opción de restablecer. |
| **Rama Git** | `ft-reservar` (tanto en `backend/` como en `frontend/`) |
| **Suite de Pruebas** | `backend/tests/test_busqueda_facetada.py` (8/8 pruebas exitosas) |

---

## 2. Resumen de Cambios Técnicos

### 2.1. Base de Datos PostgreSQL / Supabase — [`backend/db/schema.sql`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/db/schema.sql)
- **Extensiones Habilitadas:**
  - `CREATE EXTENSION IF NOT EXISTS "unaccent";` para normalización ortográfica automática.
  - `CREATE EXTENSION IF NOT EXISTS "pg_trgm";` para búsquedas difusas y trigramas.
- **Columna Generada FTS:**
  - `search_vector tsvector GENERATED ALWAYS AS (to_tsvector('spanish', coalesce(nombre, '') || ' ' || coalesce(marca, '') || ' ' || coalesce(sku, '') || ' ' || coalesce(descripcion, ''))) STORED;`
- **Índices de Alto Rendimiento:**
  - `idx_productos_fts_gin`: Índice GIN sobre `search_vector`.
  - `idx_productos_nombre_trgm`: Índice GIN trigram sobre el nombre del producto.
  - `idx_productos_marca`: Índice B-Tree para optimización de facetas por marca.
  - `idx_variantes_precio`: Índice B-Tree para rangos de precio eficientes.

### 2.2. Backend — Microservicio de Catálogo (FastAPI)
- **Modelos Pydantic en [`schemas.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/services/catalogo/app/schemas.py):**
  - `FacetItem`: `{ id: str, etiqueta: str, total: int, seleccionado: bool }`
  - `RangoPrecioFacet`: `{ min: float, max: float }`
  - `FacetasCatalogo`: Agregación de listas de categorías, marcas, rango de precios, conteo en stock y total general.
  - `BusquedaFacetadaResponse`: Paginación, productos filtrados y objeto de facetas reactivas.
  - `SugerenciaItem`: Datos para autocompletado rápido (id, nombre, SKU, categoría, marca, precio, thumbnail).
- **Endpoints en [`routers.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/services/catalogo/app/routers.py):**
  - `GET /api/v1/catalogo/buscar` y `/api/v1/catalogo/productos/buscar`:
    - Parámetros: `q`, `categoria_ids`, `marcas`, `precio_min`, `precio_max`, `en_stock`, `ordenar_por`, `pagina`, `limite`.
    - Motor de búsqueda FTS con normalización `_normalize_text` (insensible a tildes y mayúsculas/minúsculas).
    - Agregación dinámica de recuento de facetas (*counts*) calculadas sobre el universo de búsqueda.
    - Fallback resiliente con catálogo semilla en memoria si Supabase no estuviera conectado en el entorno local.
  - `GET /api/v1/catalogo/sugerencias`:
    - Autocompletado predictivo *typeahead* de baja latencia con límite configurable.

### 2.3. Frontend — Vue 3 + Tailwind CSS
- **Tipos e Interfaces en [`types/index.ts`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/frontend/src/types/index.ts):**
  - Definición de `FacetItem`, `RangoPrecioFacet`, `FacetasCatalogo`, `BusquedaFacetadaResponse` y `SugerenciaItem`.
- **Vista de Marketplace en [`MarketplaceView.vue`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/frontend/src/views/marketplace/MarketplaceView.vue):**
  - **Buscador Predictivo con Debounce:**
    - Debounce de 150ms para autocompletado y 300ms para búsqueda principal.
    - Menú flotante interactivo tipo *typeahead* con miniaturas, precios y acceso directo.
    - Botón para limpiar búsqueda rápida (`X`).
  - **Barra Lateral de Filtros Facetados Acumulativos:**
    - Lista de categorías con recuento dinámico `(N)`.
    - Lista de marcas con recuento dinámico `(N)`.
    - Selector de rango de precios con botones rápidos (`< 1.000`, `1.000 - 3.000`, `3.000 - 8.000`, `> 8.000`) e inputs manuales Mín/Máx.
    - Checkbox de disponibilidad inmediata ("Solo en stock").
    - Diseño responsive adaptable (drawer modal para dispositivos móviles y barra fija sticky para pantallas grandes).
  - **Barra de Chips de Filtros Activos:**
    - Indicadores visuales de filtros aplicados con remoción individual (`X`) y botón general "Limpiar todos".
  - **Selector de Ordenamiento:**
    - Más relevantes, Precio menor a mayor, Precio mayor a menor y Nombre A - Z.
  - **Estado Vacío Intuitivo (*Empty State*):**
    - Mensaje amigable y botón de reinicio cuando ninguna combinación de filtros arroja resultados.

---

## 3. Resultados de Pruebas Automatizadas

Se diseñó y ejecutó la suite `backend/tests/test_busqueda_facetada.py` con el siguiente resultado:

```text
======================================================================
INICIANDO SUITE DE PRUEBAS: US-06 / RF-06 BÚSQUEDA FACETADA Y FTS
======================================================================

[TEST 1] Consulta de búsqueda global sin filtros (Catálogo completo y facetas)...
  -> OK: 8 productos encontrados.
     Categorías facetadas: 5, Marcas facetadas: 6
     Rango de precios: Bs. 799.0 - Bs. 18500.0

[TEST 2] Búsqueda FTS insensible a tildes ('camara' sin tilde vs 'Cámara')...
  -> OK: Búsqueda 'camara' localizó con éxito: 'Cámara Digital Sony Alpha 7 IV Full-Frame Mirrorless'

[TEST 2.1] Búsqueda FTS insensible a tildes ('mecanico' sin tilde vs 'Mecánico')...
  -> OK: Búsqueda 'mecanico' localizó: 'Teclado Mecánico Inalámbrico Logitech MX Mechanical'

[TEST 3] Búsqueda por SKU parcial ('XPS15')...
  -> OK: Localizado producto por SKU: LAP-DELL-XPS15

[TEST 4] Filtro facetado por marca ('Logitech')...
  -> OK: 2 ítems Logitech filtrados y faceta seleccionada.

[TEST 5] Filtro por rango de precio (Bs. 1.000 a Bs. 3.000)...
  -> OK: 3 productos dentro del rango 1000 - 3000 BOB.

[TEST 6] Filtro combinado acumulativo: q='Sony' + precio_min=10000...
  -> OK: Filtro combinado resolvió exclusivamente: 'Cámara Digital Sony Alpha 7 IV Full-Frame Mirrorless'

[TEST 7] Autocompletado predictivo con prefijo 'lap'...
  -> OK: 2 sugerencias devueltas:
     - [Laptops y PCs] Laptop Dell XPS 15 (OLED 4K, i7 13va Gen) (LAP-DELL-XPS15) - Bs. 8999.00
     - [Laptops y PCs] Apple MacBook Pro 16" Chip M3 Pro (LAP-APP-MBP16) - Bs. 18500.00

[TEST 8] Ordenamiento por precio ascendente y descendente...
  -> OK: Precio ascendente verificado: [799.0, 1150.0, 2450.0] ...
  -> OK: Precio descendente verificado: [18500.0, 16999.0, 8999.0] ...

======================================================================
¡TODAS LAS PRUEBAS DE US-06 (RF-06) PASARON EXITOSAMENTE (8/8)!
======================================================================
```
