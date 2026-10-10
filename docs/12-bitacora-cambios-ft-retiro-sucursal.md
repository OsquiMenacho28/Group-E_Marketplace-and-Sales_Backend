# 12. Bitácora de Cambios Técnicos — Rama `ft-retiro-sucursal` (US-11 / RF-11 / KAN-27)

Este documento registra de forma detallada y auditable el análisis, diseño de arquitectura, endpoints backend, modelos de datos, validaciones de identidad y componentes frontend implementados para la historia de usuario **KAN-27** y sus 6 subtareas asignadas en Jira.

---

## 1. Ficha Técnica del Release

| Atributo | Detalle |
| :--- | :--- |
| **Épica / Historia Jira** | **KAN-10 / KAN-27:** *Como Cajero, quiero validar y entregar pedidos con retiro en sucursal para despachar compras Click and Collect.* |
| **Requerimiento Funcional** | **RF-11 — Retiro en Sucursal** (Módulo 2: Puntos de Venta Físicos POS) |
| **Requerimientos Secundarios** | **RF-15** (Modalidad Retiro en Tienda), **RF-28** (Máquina de Estados de Orden), **RF-50** (Auditoría y Trazabilidad Inmutable) |
| **Actor Responsable** | Cajero (con permisos de rol `cajero` y `administrador`) |
| **Rama Git** | `ft-retiro-sucursal` (tanto en repositorio `backend` como en `frontend`) |
| **Rama Base** | `version1` / `main` |
| **Commit Backend** | `c27b324` (`feat(be): endpoint validacion qr click and collect y auditoria despacho KAN-324 KAN-325`) |
| **Commit Frontend** | `a18f326` (`feat(fe): modulo click and collect con escaner qr y confirmacion de receptor KAN-326 KAN-327`) |

---

## 2. Matriz de Subtareas de Jira

| Código | Tarea / Subtarea | Estimación | Tipo | Estado |
| :--- | :--- | :---: | :---: | :---: |
| **KAN-107** | Análisis y diseño del flujo de retiro en sucursal | 1 h | Análisis / Diseño | **100% Completado** |
| **KAN-108** | Validación de identidad y estado del pedido | 1 h | Reglas de Negocio | **100% Completado** |
| **KAN-324** | [BE] Endpoint para validación de código/QR de retiro Click & Collect | 3 h | Backend (FastAPI) | **100% Completado** |
| **KAN-325** | [BE] Lógica de actualización de pedido a 'Entregado' y auditoría de despacho | 2 h | Backend / DB | **100% Completado** |
| **KAN-326** | [FE] Vista de módulo Click & Collect con escáner de código y detalle de pedido | 3 h | Frontend (Vue 3) | **100% Completado** |
| **KAN-327** | [FE] Flujo de confirmación de entrega y registro de receptor | 3 h | Frontend (Vue 3) | **100% Completado** |
| **TOTAL** | **Historia de Usuario Completa KAN-27** | **13 h** | Full-Stack | **100% Completado** |

---

## 3. Subtarea KAN-107: Análisis y Diseño del Flujo de Retiro en Sucursal

### 3.1. Flujo Operativo Integral (Click & Collect)
1. **Compra Web y Notificación:** El cliente selecciona retiro en tienda en el marketplace (`tipo_despacho: 'retiro_sucursal'`). El sistema emite un código único seguro de retiro (ej. `RET-789214`) y una cadena de código QR estructurada (`MAXI-CC|ORD-2026-CC101|RET-789214|SUC-01`).
2. **Presentación en Mostrador:** El comprador acude a la sucursal seleccionada y presenta su código alfanumérico o código QR desde su celular o comprobante impreso.
3. **Escaneo / Búsqueda:** El cajero utiliza el lector de código de barras / QR del POS o introduce manualmente el código o CI del cliente.
4. **Validación Automática del Sistema:**
   - Verificación de existencia de la orden.
   - Verificación de sucursal física asignada (alertando si el pedido pertenece a otra sucursal).
   - Verificación estricta de estado (debe estar en `confirmada`, `en_preparacion` o `despachada`).
5. **Inspección Física:** El cajero extrae el paquete de bodega o paquetería y contrasta los ítems en pantalla con el contenido físico.
6. **Verificación de Identidad del Receptor:** Se comprueba el documento de identidad en físico del titular o tercero autorizado con carta de poder/autorización.
7. **Confirmación y Despacho:** El cajero registra nombre y documento del receptor, notas y confirma la entrega. La orden pasa de forma atómica a `entregada`, se guarda la bitácora inmutable en `audit_logs` (RF-50) y se genera el acta de recepción digital.

---

## 4. Subtarea KAN-108: Validación de Identidad y Estado del Pedido

### Reglas de Negocio Implementadas:
1. **Regla de Entregabilidad:**
   - Solo pueden ser entregadas órdenes en estados activos: `confirmada`, `en_preparacion`, `despachada` o `pendiente_retiro`.
   - Si la orden ya está en estado `entregada`: El sistema rechaza la operación (`es_entregable: false`) y despliega la ficha de auditoría previa (fecha, hora, cajero responsable y receptor original).
   - Si la orden está en estado `cancelada`: El sistema bloquea el despacho indicando que los fondos o existencias ya fueron devueltos a almacén.
2. **Validación de Identidad del Receptor:**
   - **Caso A (Titular):** El documento presentado debe coincidir con el CI/NIT registrado al momento de la compra.
   - **Caso B (Tercero Autorizado):** Se exige registro obligatorio de nombre completo, CI del tercero, parentesco o número de carta poder.
3. **Checklist de Verificación Obligatorio:** En frontend no se permite confirmar la entrega sin marcar las 3 casillas de verificación:
   - Verificación de documento de identidad en físico.
   - Inspección física de productos completos y sin daños.
   - Conformidad verbal o escrita del receptor.

---

## 5. Subtarea KAN-324: [BE] Endpoint para Validación de Código/QR

### 5.1. Contrato del Endpoint
- **Ruta:** `POST /api/v1/pos/click-and-collect/validar`
- **Payload Request:**
```json
{
  "codigo": "RET-789214",
  "sucursal_id": "SUC-01"
}
```
- **Soporte de Entrada:** Admite código de retiro (`RET-789214`), código de orden (`ORD-2026-CC101`), documento de identidad del cliente (`4829102`) o lectura de código QR compuesto (`MAXI-CC|ORD-2026-CC101|RET-789214|SUC-01`).

- **Payload Response (200 OK):**
```json
{
  "orden_id": "3b749d44-0db0-4e36-9694-84c1724490f1",
  "codigo_orden": "ORD-2026-CC101",
  "codigo_retiro": "RET-789214",
  "codigo_qr": "MAXI-CC|ORD-2026-CC101|RET-789214|SUC-01",
  "estado": "confirmada",
  "es_entregable": true,
  "motivo_rechazo": null,
  "sucursal_id": "SUC-01",
  "sucursal_nombre": "Sucursal Central - La Paz",
  "fecha_compra": "2026-10-10T09:30:00Z",
  "cliente_nombre": "Carlos Mendoza Patzi",
  "cliente_documento": "4829102",
  "cliente_telefono": "+591 71234567",
  "cliente_email": "carlos.mendoza@gmail.com",
  "subtotal": 15766.00,
  "descuento": 0.0,
  "total": 15766.00,
  "metodo_pago": "QR Simple (Aprobado)",
  "cuf_factura": "CUF-1028374029-20261010-093011-8849",
  "numero_factura": 1421,
  "items": [
    {
      "sku": "LAP-DELL-XPS15",
      "nombre_producto": "Laptop Dell XPS 15 (OLED 4K, i7 13va Gen)",
      "cantidad": 1,
      "precio_unitario": 6767.00,
      "total_linea": 6767.00
    },
    {
      "sku": "MOU-LOG-MX3S",
      "nombre_producto": "Mouse Inalámbrico Logitech MX Master 3S",
      "cantidad": 1,
      "precio_unitario": 8999.00,
      "total_linea": 8999.00
    }
  ],
  "despacho": null
}
```

---

## 6. Subtarea KAN-325: [BE] Lógica de Actualización a 'Entregado' y Auditoría

### 6.1. Contrato del Endpoint de Confirmación
- **Ruta:** `POST /api/v1/pos/click-and-collect/confirmar-entrega`
- **Permisos:** Requiere autenticación JWT con rol `cajero` o `administrador`.
- **Payload Request:**
```json
{
  "orden_id": "3b749d44-0db0-4e36-9694-84c1724490f1",
  "codigo_retiro": "RET-789214",
  "receptor_nombre": "Carlos Mendoza Patzi",
  "receptor_documento": "4829102",
  "receptor_tipo": "titular",
  "receptor_telefono": "+591 71234567",
  "observaciones": "Paquete revisado y entregado en mostrador",
  "cajero_id": "c0000000-0000-0000-0000-000000000002",
  "cajero_nombre": "Oscar Menacho",
  "sucursal_id": "SUC-01",
  "sucursal_nombre": "Sucursal Central - La Paz"
}
```

- **Acciones Backend:**
  1. Verifica que la orden no haya sido entregada previamente (HTTP 400 si ya fue entregada).
  2. Actualiza el estado de la orden a `'entregada'`.
  3. Inserta registro inmutable en `audit_logs` con acción `'DESPACHO_CLICK_AND_COLLECT'`.
  4. Genera correlativo oficial de acta: `ACTA-CC-2026-XXXX`.

---

## 7. Subtarea KAN-326: [FE] Vista de Módulo Click & Collect y Escáner

- Integración en la interfaz POS (`src/views/pos/PosView.vue`):
  - Conmutador directo de modo: **"Venta Mostrador POS"** vs **"Retiro Click & Collect (RF-11)"**.
  - Campo de escáner con icono QR/Barcode con autofocus y detector del evento `Enter` propio de lectores ópticos físicos.
  - Simulador de escaneo rápido de códigos QR para pruebas de mostrador.
  - Pestaña de listado de pedidos Click & Collect de la sucursal actual con filtros dinámicos (`Todos`, `Listos para Entrega`, `Entregados`).
  - Panel lateral reactivo con desglose de ítems, estado del pedido, titular, documento y CUF de factura.

---

## 8. Subtarea KAN-327: [FE] Flujo de Confirmación de Entrega y Registro de Receptor

- Modal de confirmación de despacho:
  - Selector interactivo entre **Titular del Pedido** (precarga automática de datos) y **Tercero Autorizado** (permite ingresar CI, nombre y parentesco).
  - Verificación visual de los 3 checks obligatorios de entrega.
  - Campo de observaciones para el cajero.
  - Botón de despacho con estado de carga y validaciones.
  - Modal final de **Acta de Entrega Digital / Comprobante de Retiro** imprimible (estilos print CSS) con código QR de auditoría, sello de entregado y firmas.
