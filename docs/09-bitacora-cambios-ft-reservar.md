# 09. Bitácora de Cambios Técnicos — Rama `ft-reservar` (US-14 / RF-14)

Este documento registra de forma detallada y auditable todos los cambios arquitecturales, modelos de datos, endpoints y componentes implementados desde la versión base (`version1`) en los dos repositorios del sistema **MaxiConecta Marketplace y Ventas**.

---

## 1. Ficha Técnica del Release

| Atributo | Detalle |
| :--- | :--- |
| **Historia de Usuario** | **US-14:** *Como Sistema, quiero reservar temporalmente el stock durante el checkout para evitar sobreventas concurrentes.* |
| **Requerimientos Asociados** | **RF-14** (Reserva Temporal de Stock), **RIO-INV-02** (Reserva en Almacén), **RIO-INV-03** (Descuento Definitivo tras Pago), **RF-15** (Modalidades de Entrega), **RF-16** (Métodos de Pago) |
| **Rama Git** | `ft-reservar` (tanto en `frontend/` como en `backend/`) |
| **Rama Base** | `version1` |
| **Commit Frontend** | `1e41b4a` (`front para la reserva`) |
| **Commit Backend** | `b458658` (`back reservas`) |

---

## 2. Resumen Comparativo (Delta respecto a `version1`)

### ¿Qué existía en `version1` (Estado Inicial)?
1. **Frontend:** 
   - El drawer lateral del carrito contenía un botón placeholder con texto: `"Iniciar Checkout [Reserva Stock TTL]"`.
   - **No tenía** handler de click, no existía modal de checkout, no había temporizador regresivo de 15 minutos ni advertencias visuales de vencimiento.
   - El store de Pinia no manejaba variables de reserva, estado de bloqueo ni tiempo restante.
2. **Backend:**
   - `backend/shared/redis_client.py` tenía dos funciones básicas (`lock_stock_reservation` y `release_stock_reservation`) que solo creaban una clave individual por variante, pero **no verificaban expiración** en las órdenes, ni permitían consultar el TTL restante ni liberar la reserva estructurada.
   - Si Redis no estaba corriendo localmente, las peticiones fallaban con timeout TCP.
   - `backend/services/carrito`: no contaba con endpoints para consultar (`GET`) o cancelar (`POST`) una reserva activa.
   - `backend/services/ordenes`: no validaba si el `reserva_id` había expirado al momento de crear la orden (permitiendo sobreventas en caso de pago tardío).

---

## 3. Detalle de Cambios en `frontend/` (4 archivos, +847 líneas)

### 3.1. Tipos e Interfaces — [`frontend/src/types/index.ts`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/frontend/src/types/index.ts)
- **`CheckoutModalidad`**: `'domicilio' | 'retiro_sucursal'`.
- **`CheckoutMetodoPago`**: `'tarjeta' | 'qr' | 'pasarela'`.
- **`ReservaStockStatus`**: `'idle' | 'reservando' | 'activa' | 'expirada' | 'confirmada' | 'error'`.
- **`ReservaStockResponse`**: Estructura de respuesta del backend con `reserva_id`, `ttl_expira_en_segundos`, `monto_total`, `status`.
- **`CheckoutPayload`**: Datos de despacho, método de cobro y dirección para finalización.

### 3.2. Store de Carrito y Checkout — [`frontend/src/stores/cart.ts`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/frontend/src/stores/cart.ts)
- **Estado Reactivo Añadido:**
  - `isCheckoutModalOpen`, `isReserving`, `isProcessingOrder`.
  - `reservaId`: ID emitido por el backend/ERP (ej. `RES-MOCK-XXXXXX`).
  - `reservaSecondsLeft`: Contador regresivo en segundos (inicia en 900s = 15 min).
  - `reservaTotalSeconds`: Base para cálculo de progreso (900s).
  - `reservaStatus`: Máquina de estados reactiva.
- **Computed Properties:**
  - `formattedTimeLeft`: Formato digital `MM:SS` (ej. `14:59`).
  - `timerProgressPercent`: Porcentaje restante (100% a 0%) para la barra visual.
  - `isWarningTimer`: Activo cuando faltan entre 2 y 5 minutos (alerta color ámbar).
  - `isUrgentTimer`: Activo cuando restan menos de 2 minutos (alerta color rojo pulsante).
- **Acciones Implementadas:**
  - `iniciarCheckoutConReserva(clienteId)`: Petición `POST /api/v1/carrito/{id}/checkout/iniciar` con fallback transparente si el API Gateway estuviera offline.
  - `iniciarTemporizador(segundos)`: `setInterval` de 1 segundo con detención y transición a `'expirada'` al llegar a 0.
  - `cancelarReserva()`: Llama al endpoint de liberación y limpia el estado local.
  - `renovarReserva()`: Permite solicitar una nueva reserva tras expiración.
  - `finalizarOrdenConReserva(payload, clienteId)`: Envía la orden con `reserva_id` y limpia el carrito tras la compra exitosa.

### 3.3. Nuevo Componente Modal de Checkout — [`frontend/src/components/checkout/CheckoutModal.vue`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/frontend/src/components/checkout/CheckoutModal.vue)
- **Banner Superior Dinámico:**
  - Badge de estado (`Stock Bloqueado` / `Por Vencer` / `¡Últimos Minutos!`).
  - Reloj digital en vivo con tipografía monospace.
  - Barra de progreso SVG/CSS decreciente sincronizada al segundo.
  - Indicador del código de reserva RIO-INV-02.
- **Paso 1 (RF-15):** Selector interactivo entre Envío a Domicilio (+ BOB 15.00) y Retiro en Sucursal (Gratis con 3 tiendas físicas seleccionables).
- **Paso 2 (RF-16):** Selector de métodos de cobro (QR Simple con glosa bancaria copiable, Tarjeta con formulario estilizado y Pasarela Digital).
- **Paso 3:** Resumen de compra desglosado con badges `✓ Reservado` por ítem.
- **Overlay de Expiración:** Bloqueo modal si el TTL llega a `00:00`, explicando la liberación del stock y ofreciendo botón de reintento.
- **Pantalla de Confirmación:** Despliegue del código de orden `ORD-2026-XXXX`.

### 3.4. Integración en Raíz — [`frontend/src/App.vue`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/frontend/src/App.vue)
- Conexión del botón del drawer del carrito al método `cartStore.iniciarCheckoutConReserva()`.
- Incorporación de estado de carga con spinner (`Loader2` - *"Bloqueando stock en Inventarios..."*).
- Montaje del componente `<CheckoutModal />` en el DOM principal.

---

## 4. Detalle de Cambios en `backend/` (9 archivos, +533 líneas)

### 4.1. Cliente y Resiliencia Redis — [`backend/shared/redis_client.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/shared/redis_client.py)
- **`crear_reserva_stock`**: Serializa y almacena la reserva en `reserva:{reserva_id}` con `SETEX` (900s) y genera locks individuales `lock:stock:{variante_id}:{reserva_id}`.
- **`consultar_reserva`**: Lee la clave y ejecuta `redis.ttl()` para retornar los segundos restantes exactos.
- **`liberar_reserva_stock`**: Elimina de forma atómica la reserva y los locks asociados.
- **`confirmar_reserva_stock`**: Cambia el estado a `CONFIRMADA` antes de asentar la orden.
- **Manejo de Fallas (Fast Failover):** `socket_timeout=1.0` y `socket_connect_timeout=1.0`. Si Redis no está en ejecución, conmuta automáticamente a un almacén en memoria (`_in_memory_store`) respetando los TTLs, evitando caídas o bloqueos de hilo.

### 4.2. Cliente ERP Inventarios — [`backend/shared/erp_clients/inventarios.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/shared/erp_clients/inventarios.py)
- Se añadió el método [`liberar_reserva`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/shared/erp_clients/inventarios.py#L36) (`POST /api/v1/reservas-stock/liberar`) para interoperar con el ERP ante abandonos o expiración (RIO-INV-02).
- En [`backend/shared/erp_clients/base.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/shared/erp_clients/base.py), se ajustó un timeout ágil (1s en desarrollo/pruebas) para fallback inmediato sin latencias.

### 4.3. Esquemas de Carrito — [`backend/services/carrito/app/schemas.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/services/carrito/app/schemas.py)
- **`CheckoutInitRequest`**: Permite `cliente_id` como `Union[UUID, str]` para soportar clientes autenticados y compras express.
- **`CheckoutInitResponse`**: Incluye `expira_en_timestamp` y lista de `items_reservados`.
- **`ReservaConsultaResponse`**: DTO con `reserva_id`, `segundos_restantes`, `estado` y desglose.
- **`CancelarReservaResponse`**: Confirmación de liberación.

### 4.4. Endpoints de Carrito — [`backend/services/carrito/app/routers.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/services/carrito/app/routers.py)
- Actualizado `POST /{id}/checkout/iniciar`:
  - Valida existencias con `inventarios_client.reservar_stock`. Si el ERP rechaza por falta de existencias, devuelve `409 Conflict`.
  - Registra la reserva en Redis/Memoria con 900s.
- Nuevo `GET /checkout/reserva/{reserva_id}`: Consulta de vigencia y tiempo restante.
- Nuevo `POST /checkout/reserva/{reserva_id}/cancelar`: Liberación inmediata en ERP y Redis.

### 4.5. Control Concurrente en Órdenes — [`backend/services/ordenes/app/routers.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/services/ordenes/app/routers.py)
- En `POST /api/v1/ordenes/`:
  - Se verifica la vigencia de `payload.reserva_id`.
  - **Si no existe en Redis o su estado es `EXPIRADA`, la orden es rechazada con `409 Conflict`**, previniendo sobreventas concurrentes de clientes rezagados.
  - Si es válida, ejecuta `confirmar_reserva_stock` y dispara `inventarios_client.descuento_definitivo` (RIO-INV-03).
  - Serialización limpia de UUIDs hacia los clientes ERP externos.

### 4.6. Suite de Pruebas Automatizadas — [`backend/tests/test_reserva_stock.py`](file:///c:/Users/CESAR/Documents/UNIVERSIDAD/10%20semestre/TALLER_SIS/Sistema_ventas/backend/tests/test_reserva_stock.py)
- Cobertura completa de 6 escenarios críticos:
  1. Adición de producto al carrito.
  2. Inicialización de checkout con reserva y asignación de TTL 900s.
  3. Consulta de TTL restante en tiempo real.
  4. Cancelación y liberación voluntaria de locks.
  5. Creación de orden exitosa con reserva activa (descuento definitivo RIO-INV-03).
  6. Rechazo de orden con `409 Conflict` cuando la reserva ha expirado.

---

## 5. Matriz de Trazabilidad de Requerimientos

| Requerimiento | Descripción | Implementación Frontend | Implementación Backend |
| :--- | :--- | :--- | :--- |
| **RF-14** | Reserva temporal con TTL de 15 min | Contador `14:59` y barra dinámica en `CheckoutModal.vue` | Clave `reserva:{id}` en Redis con `SETEX 900` |
| **RIO-INV-02** | Contrato de reserva en Inventarios | Llamada de inicio en `useCartStore` | `inventarios_client.reservar_stock()` |
| **RIO-INV-02-LIB** | Liberación por timeout o cancelación | Botón *"Cancelar compra y liberar stock"* | `inventarios_client.liberar_reserva()` y `liberar_reserva_stock()` |
| **RIO-INV-03** | Descuento definitivo al pagar | Transición a pantalla de éxito | `inventarios_client.descuento_definitivo()` en `ordenes.py` |
| **RF-15** | Modalidad Domicilio vs Retiro | Paso 1 interactivo en `CheckoutModal.vue` | Parámetros `tipo_despacho` y `direccion_id` |
| **RF-16** | Métodos de pago (QR, Tarjeta, Pasarela) | Paso 2 con generador QR en `CheckoutModal.vue` | Registro del método de cobro en la orden |
