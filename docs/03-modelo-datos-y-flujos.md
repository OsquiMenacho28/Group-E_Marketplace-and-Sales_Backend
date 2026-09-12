# 3. Modelo Estructural de Datos y Flujos de Información

Este documento detalla el modelo estático de datos (entidades, atributos, operaciones y asociaciones) y los diagramas de secuencia que definen el movimiento dinámico de información entre los componentes internos y los sistemas externos del ERP.

---

## 3.a Modelo Estructural de Datos Estático (Diagrama de Clases)

El modelo se organiza conceptualmente alrededor de **tres agregados principales**:
1. **Agregado Producto:** Producto, Categoría, Variante y Reseña.
2. **Agregado Cliente:** Cliente, Dirección, Carrito de Compras e Ítems de Carrito.
3. **Agregado Orden:** Orden de Venta, Ítems de Orden, Pagos y Cotizaciones B2B.

```mermaid
classDiagram
    class Categoria {
        +uuid id
        +string nombre
        +uuid padre_id
    }

    class Producto {
        +uuid id
        +string sku
        +string nombre
        +text descripcion
        +EstadoProducto estado
        +publicar()
        +descontinuar()
    }

    class Variante {
        +uuid id
        +uuid producto_id
        +jsonb atributos
        +numeric precio
    }

    class Resena {
        +uuid id
        +uuid producto_id
        +uuid cliente_id
        +int calificacion
        +text comentario
        +moderar()
    }

    class Cliente {
        +uuid id
        +string nombre
        +string email
        +string telefono
        +registrar()
        +actualizarPerfil()
    }

    class Direccion {
        +uuid id
        +uuid cliente_id
        +string linea1
        +string ciudad
    }

    class Carrito {
        +uuid id
        +uuid cliente_id
        +EstadoCarrito estado
        +timestamp expira_en
        +agregarItem()
        +vaciar()
    }

    class ItemCarrito {
        +uuid id
        +uuid carrito_id
        +uuid variante_id
        +int cantidad
    }

    class Orden {
        +uuid id
        +uuid cliente_id
        +EstadoOrden estado
        +numeric total
        +timestamp creada_en
        +cambiarEstado()
        +cancelar()
    }

    class ItemOrden {
        +uuid id
        +uuid orden_id
        +uuid variante_id
        +int cantidad
        +numeric precio_unit
    }

    class Pago {
        +uuid id
        +uuid orden_id
        +numeric monto
        +MetodoPago metodo
        +EstadoPago estado
        +validar()
        +reembolsar()
    }

    class Cotizacion {
        +uuid id
        +uuid cliente_id
        +EstadoCotizacion estado
        +date vigencia
        +aprobar()
        +convertirAOrden()
    }

    Categoria "1" --> "0..*" Categoria : subcategorias
    Categoria "1" --> "0..*" Producto : clasifica
    Producto "1" --> "1..*" Variante : compone
    Producto "1" --> "0..*" Resena : recibe
    Cliente "1" --> "0..*" Resena : escribe
    Cliente "1" --> "0..*" Direccion : posee
    Cliente "1" --> "0..1" Carrito : tiene
    Carrito "1" --> "0..*" ItemCarrito : contiene
    Variante "1" --> "0..*" ItemCarrito : se agrega en
    Cliente "1" --> "0..*" Orden : genera
    Orden "1" --> "1..*" ItemOrden : contiene
    Variante "1" --> "0..*" ItemOrden : se vende en
    Orden "1" --> "1..*" Pago : liquida
    Cliente "1" --> "0..*" Cotizacion : solicita
    Cotizacion "0..1" --> "0..1" Orden : se convierte en
```

---

## 3.b Modelos de Flujo de Información (Diagramas de Secuencia)

### Flujo 1: Proceso de Compra en el Marketplace Digital
Describe la compra efectuada por un cliente a través de la tienda web/móvil, involucrando validaciones de inventario, procesamiento de cobro electrónico, generación formal de la orden y solicitud de entrega a domicilio.

```mermaid
sequenceDiagram
    autonumber
    actor Cliente as Cliente (Browser)
    participant MS_Checkout as Carrito / CheckoutService
    participant ERP_Inv as ERP Inventarios y Almacén
    participant ERP_Pag as ERP Pagos y Facturación
    participant MS_Orden as MS Órdenes y Ventas
    participant ERP_Ent as ERP Entregas y Despachos

    Cliente ->> MS_Checkout: confirmarCompra(carritoId, direccionId, metodoPago)
    MS_Checkout ->> ERP_Inv: reservarStock(items) [RIO-INV-02]
    ERP_Inv -->> MS_Checkout: stockReservado(reservaId, status: OK)
    MS_Checkout ->> ERP_Pag: solicitarCobro(monto, metodo, token) [RIO-PAG-01]
    ERP_Pag -->> MS_Checkout: pagoConfirmado(transaccionId, autorizacion: OK)
    MS_Checkout ->> MS_Orden: generarOrden(carritoId, transaccionId, reservaId)
    MS_Orden ->> ERP_Inv: confirmarDescuentoDefinitivo(reservaId) [RIO-INV-03]
    MS_Orden ->> ERP_Ent: solicitarDespacho(ordenId, direccionId) [RIO-ENT-01]
    ERP_Ent -->> MS_Orden: despachoProgramado(trackingNumber)
    MS_Orden -->> MS_Checkout: ordenCreada(ordenId, trackingNumber, estado: Confirmada)
    MS_Checkout -->> Cliente: confirmarPedido(ordenId, estado: Confirmada)
```

---

### Flujo 2: Venta Presencial en Punto de Venta Físico (POS)
Describe la atención en caja física por un cajero, con validación de stock local de la sucursal, cobro presencial (efectivo/tarjeta) y emisión inmediata del comprobante/factura electrónica.

```mermaid
sequenceDiagram
    autonumber
    actor Cajero as Cajero (POS)
    participant POS_UI as Frontend POS (Vue 3)
    participant Gateway as API Gateway
    participant MS_POS as MS Punto de Venta
    participant ERP_Inv as ERP Inventarios y Almacén
    participant ERP_Pag as ERP Pagos y Facturación

    Cajero ->> POS_UI: Escanear producto (SKU / Código de barras)
    POS_UI ->> Gateway: GET /api/v1/catalogo/stock-local/{sucursalId}/{sku}
    Gateway ->> ERP_Inv: GET /disponibilidad/{sku}?sucursal={id} [RIO-INV-01]
    ERP_Inv -->> POS_UI: 200 OK (Existencias disponibles)
    POS_UI -->> Cajero: Ítem agregado al subtotal

    Cajero ->> POS_UI: Seleccionar método de pago y cobrar
    POS_UI ->> Gateway: POST /api/v1/pos/ventas (Detalle venta, método)
    Gateway ->> MS_POS: Iniciar transacción de cobro
    MS_POS ->> ERP_Pag: POST /pagos/pos (Monto, terminal, método) [RIO-PAG-01]
    ERP_Pag -->> MS_POS: 200 OK (Transacción Aprobada)
    MS_POS ->> ERP_Inv: POST /stock/descuento-directo (SKU, Cantidad, Sucursal) [RIO-INV-03]
    ERP_Inv -->> MS_POS: 200 OK (Inventario rebajado)
    MS_POS ->> ERP_Pag: POST /facturacion/emitir (Datos fiscales, ítems) [RIO-PAG-02]
    ERP_Pag -->> MS_POS: 200 OK (Factura generada - CUF / No. Factura)
    MS_POS -->> Gateway: 201 Created (Comprobante y Factura)
    Gateway -->> POS_UI: 201 Created
    POS_UI -->> Cajero: Imprimir ticket / factura fiscal
```

---

### Flujo 3: Cancelación y Devolución con Reversión Contable e Inventario
Garantiza la consistencia financiera e inventarial cuando una orden se cancela antes de su despacho o se autoriza una devolución posterior.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Administrador / Cliente
    participant Panel as Web / Panel de Gestión
    participant Gateway as API Gateway
    participant MS_Orden as MS Órdenes y Ventas
    participant ERP_Inv as ERP Inventarios y Almacén
    participant ERP_Pag as ERP Pagos y Facturación
    participant ERP_Con as ERP Contabilidad

    Admin ->> Panel: Solicitar cancelación / devolución (ordenId, motivo)
    Panel ->> Gateway: POST /api/v1/ordenes/{id}/devolucion
    Gateway ->> MS_Orden: Validar reglas comerciales de devolución
    MS_Orden ->> ERP_Inv: POST /reingreso-stock (items, almacenId) [RIO-INV-04]
    ERP_Inv -->> MS_Orden: 200 OK (Stock reintegrado físico y lógico)
    MS_Orden ->> ERP_Pag: POST /reembolsos/reversar (pagoId, monto) [RIO-PAG-03]
    ERP_Pag -->> MS_Orden: 200 OK (Cobro revertido / Nota de crédito emitida)
    MS_Orden ->> ERP_Con: POST /asientos/reversion (ordenId, montos) [RIO-CON-04]
    ERP_Con -->> MS_Orden: 200 OK (Asiento de reversión registrado)
    MS_Orden ->> MS_Orden: UPDATE orden SET estado = 'Cancelada' / 'Devuelta'
    MS_Orden -->> Gateway: 200 OK (Operación completada con éxito)
    Gateway -->> Panel: Devolución procesada y confirmada
    Panel -->> Admin: Notificación visual de anulación exitosa
```

---

### Flujo 4: Cotizaciones Corporativas B2B
Permite a clientes empresariales solicitar cotizaciones por volumen con listas de precios preferenciales, pasando por un flujo de aprobación comercial antes de convertirse en una orden formal.

```mermaid
sequenceDiagram
    autonumber
    actor Gerente as Gerente Comercial
    participant Panel as Panel de Gestión (Vue 3)
    participant Gateway as API Gateway
    participant MS_Orden as MS Órdenes y Ventas
    participant ERP_Inv as ERP Inventarios y Almacén

    Gerente ->> Panel: Crear propuesta de cotización (Cliente B2B, SKU, Precio preferencial)
    Panel ->> Gateway: POST /api/v1/cotizaciones (EmpresaId, Items, Vigencia)
    Gateway ->> MS_Orden: Validar estructura y política comercial
    MS_Orden ->> ERP_Inv: GET /disponibilidad-futura (Volumen requerido) [RIO-PRD-01]
    ERP_Inv -->> MS_Orden: 200 OK (Disponibilidad proyectada suficiente)
    MS_Orden ->> MS_Orden: INSERT Cotizacion (Estado: Pendiente Aprobación)
    MS_Orden -->> Panel: Cotización registrada

    Gerente ->> Panel: Aprobar cotización y enviar proforma al cliente
    Panel ->> Gateway: PATCH /api/v1/cotizaciones/{id} (Aprobada)
    Gateway ->> MS_Orden: Ejecutar aprobación comercial y emitir PDF proforma
    MS_Orden -->> Panel: Proforma enviada al cliente

    Note over Gerente, Panel: El cliente B2B acepta la propuesta cotizada

    Gerente ->> Panel: Convertir cotización aprobada a Orden Formal
    Panel ->> Gateway: POST /api/v1/cotizaciones/{id}/convertir-a-orden
    Gateway ->> MS_Orden: Generar orden de venta B2B
    MS_Orden ->> ERP_Inv: POST /stock/reserva (Items, Vigencia) [RIO-INV-02]
    ERP_Inv -->> MS_Orden: 200 OK (Stock reservado para orden B2B)
    MS_Orden -->> Gateway: 201 Created (Orden de Venta Formal generada)
    Gateway -->> Panel: Orden B2B creada exitosamente
```
