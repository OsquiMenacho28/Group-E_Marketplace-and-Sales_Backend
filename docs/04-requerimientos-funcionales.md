# 4. Catálogo de Requerimientos Funcionales

El sistema **MaxiConecta Marketplace y Ventas** está conformado por **50 Requerimientos Funcionales**, organizados en 8 módulos o épicas. A continuación se presenta la matriz completa de requerimientos y perfiles de usuario autorizados.

---

## Módulo 1: Gestión de Catálogo

| Código | Requerimiento Funcional | Descripción Detallada | Actor(es) |
| :--- | :--- | :--- | :--- |
| **RF-01** | **Gestión de Productos** | Crear, editar, publicar y descontinuar productos, gestionando su estado (Borrador, Publicado, Inactivo, Descontinuado) y datos básicos (nombre, SKU maestro, marca, descripción rica). | Administrador |
| **RF-02** | **Categorías y Atributos** | Administrar un árbol jerárquico multinivel de categorías y definir atributos dinámicos específicos por categoría (talla, color, peso, material, etc.). | Administrador |
| **RF-03** | **Imágenes y Multimedia** | Cargar, ordenar y administrar imágenes y videos asociados a cada producto o variante en Supabase Storage, definiendo la imagen de portada y galerías. | Administrador, Vendedor Externo |
| **RF-04** | **Listas de Precios** | Administrar listas de precios diferenciadas según el canal de venta (Web vs POS), tipo de cliente (Retail vs Corporativo B2B), sucursal física y moneda. | Administrador, Gerente Comercial |
| **RF-05** | **Variantes de Producto** | Crear variantes específicas a partir de atributos (ej. talla M / color azul), generando automáticamente un SKU hijo único e independiente para control de inventario. | Administrador |
| **RF-06** | **Búsqueda Facetada** | Proveer al comprador un motor de búsqueda por texto completo con filtros acumulativos por rango de precio, marca, categoría, disponibilidad y atributos. | Cliente |
| **RF-07** | **Disponibilidad de Stock** | Consultar en tiempo real las existencias disponibles de un ítem contra el ERP de Inventarios antes de permitir su selección o agregación al carrito. | Cliente, Sistema |
| **RF-08** | **Sincronización Multicanal** | Sincronizar de forma consistente la información del catálogo (precios, descripciones y disponibilidad) entre la vitrina web, app y terminales POS. | Administrador, Sistema |

---

## Módulo 2: Puntos de Venta Físicos (POS)

| Código | Requerimiento Funcional | Descripción Detallada | Actor(es) |
| :--- | :--- | :--- | :--- |
| **RF-09** | **Apertura / Cierre de Caja** | Aperturar turno de caja con fondo inicial en efectivo, controlar el arqueo de caja intermedio y ejecutar el cierre con cuadre y reporte de diferencias. | Cajero |
| **RF-10** | **Comprobantes en POS** | Emitir comprobantes de venta impresos (tickets POS) y tramitar la emisión y timbrado de facturación electrónica en el acto ante el ERP de Facturación. | Cajero |
| **RF-11** | **Retiro en Sucursal** | Validar el código de retiro o código QR presentado por el cliente para órdenes con modalidad *Click & Collect*, registrando la entrega física del pedido. | Cajero |
| **RF-12** | **Suspender / Recuperar Venta** | Poner en espera una venta en curso guardando el estado actual de los ítems escaneados y recuperarla posteriormente sin perder los datos ni trabar la fila. | Cajero |

---

## Módulo 3: Marketplace Digital

| Código | Requerimiento Funcional | Descripción Detallada | Actor(es) |
| :--- | :--- | :--- | :--- |
| **RF-13** | **Carrito Persistente** | Permitir agregar, editar cantidades y remover productos de un carrito de compras que persiste entre sesiones del usuario utilizando Redis. | Cliente |
| **RF-14** | **Reserva Temporal de Stock** | Al entrar a la fase final de checkout, bloquear temporalmente las existencias en Inventarios con un TTL (ej. 15 min); si el pago no concluye, liberar el stock. | Sistema |
| **RF-15** | **Selección de Entrega** | Permitir al cliente elegir entre despacho a domicilio (seleccionando dirección registrada) o retiro en sucursal física habilitada. | Cliente |
| **RF-16** | **Selección de Pago** | Seleccionar la modalidad de pago deseada (tarjeta, pasarela digital, QR) y redirigir a la interfaz o webhook de cobro correspondiente. | Cliente |
| **RF-17** | **Promociones y Cupones** | Configurar y aplicar automáticamente descuentos por porcentaje o monto fijo, 2x1 y cupones promocionales con fechas de vigencia y montos mínimos. | Administrador, Gerente Comercial |
| **RF-18** | **Combos Comerciales** | Armar kits, bundles o paquetes promocionales de varios productos con un precio de venta global bonificado. | Administrador |
| **RF-19** | **Recomendaciones (Cross-selling)** | Presentar sugerencias algorítmicas de productos complementarios o de mayor valor (cross-selling y up-selling) durante la navegación del catálogo y checkout. | Cliente, Sistema |
| **RF-20** | **Reseñas y Calificaciones** | Permitir calificar de 1 a 5 estrellas y redactar opiniones únicamente a clientes que hayan comprado el producto, sujetas a moderación previa. | Cliente, Administrador |
| **RF-21** | **Lista de Deseos** | Guardar productos de interés futuro en una lista de favoritos personalizada vinculada a la cuenta del usuario. | Cliente |

---

## Módulo 4: Gestión de Clientes

| Código | Requerimiento Funcional | Descripción Detallada | Actor(es) |
| :--- | :--- | :--- | :--- |
| **RF-22** | **Registro y Autenticación** | Registro de nuevos usuarios, inicio de sesión seguro con contraseñas cifradas y autenticación basada en tokens JWT con Supabase Auth. | Cliente |
| **RF-23** | **Perfil y Direcciones** | Permitir al usuario actualizar su información personal y gestionar una libreta de múltiples direcciones de entrega con referencias geográficas. | Cliente |
| **RF-24** | **Sincronización con CRM** | Transmitir datos de contacto, historial de interacciones y categorizaciones hacia el sistema externo de CRM corporativo. | Sistema, Gerente Comercial |
| **RF-25** | **Fidelización y Puntos** | Acumular puntos calculados por cada compra completada y permitir canjearlos por descuentos en futuras transacciones. | Cliente, Sistema |
| **RF-26** | **Preferencias de Notificación** | Configurar los canales deseados (email, SMS, WhatsApp) y la frecuencia para notificaciones promocionales y de estado de órdenes. | Cliente |

---

## Módulo 5: Gestión de Ventas y Órdenes

| Código | Requerimiento Funcional | Descripción Detallada | Actor(es) |
| :--- | :--- | :--- | :--- |
| **RF-27** | **Generación de Orden** | Generar de forma atómica una orden de venta con código alfanumérico único una vez confirmada la aprobación del pago. | Sistema |
| **RF-28** | **Máquina de Estados de Orden** | Controlar el ciclo de vida estricto del pedido: *Pendiente -> Confirmada -> En Preparación -> Despachada -> Entregada* (o *Cancelada*). | Sistema, Administrador |
| **RF-29** | **Seguimiento de Pedido** | Consultar en tiempo real la etapa actual de preparación, despacho y transporte del pedido con número de guía. | Cliente |
| **RF-30** | **Notificaciones de Estado** | Enviar alertas automáticas al cliente cada vez que ocurra un cambio relevante en el estado de su orden. | Sistema |
| **RF-31** | **Cancelación Pre-Despacho** | Permitir la cancelación voluntaria de un pedido antes de que salga del almacén, liberando la reserva de stock y procesando la reversión del cobro. | Cliente, Administrador |
| **RF-32** | **Devoluciones Post-Entrega** | Registrar solicitudes de devolución de productos ya entregados, evaluando políticas de garantía y motivos justificados. | Cliente, Administrador |
| **RF-33** | **Reversión Contable e Inventario** | Disparar eventos automáticos para revertir el asiento de venta en Contabilidad e ingresar físicamente el producto devuelto a Inventarios. | Sistema |
| **RF-34** | **Cotizaciones B2B** | Elaborar presupuestos formales para compras corporativas por volumen, con condiciones comerciales específicas y fecha límite de validez. | Gerente Comercial |
| **RF-35** | **Aprobación de Cotizaciones** | Flujo jerárquico interno para revisión de descuentos excepcionales y margen comercial antes de emitir la proforma definitiva al cliente corporativo. | Gerente Comercial, Administrador |
| **RF-36** | **Conversión Cotización a Orden** | Transformar una cotización aprobada por el cliente B2B directamente en una orden de venta formal sin reintroducción manual de ítems. | Gerente Comercial |
| **RF-37** | **Historial de Compras** | Consultar el registro histórico de todas las compras realizadas por el cliente con acceso a facturas, comprobantes y detalle de ítems. | Cliente, Administrador |
| **RF-38** | **Registro y Validación de Pago** | Comprobar y asentar la recepción formal de fondos antes de habilitar la liberación del pedido hacia el área de despacho. | Cajero, Sistema |
| **RF-39** | **Gestión de Reembolsos** | Gestionar el retorno de fondos hacia la tarjeta o medio original de pago del cliente tras una devolución o cancelación aprobada. | Administrador, Sistema |

---

## Módulo 6: Integraciones con el ERP Corporativo

| Código | Requerimiento Funcional | Descripción Detallada | Actor(es) |
| :--- | :--- | :--- | :--- |
| **RF-40** | **Integración con Inventario** | Ejecutar consultas y rebajas o reintegros automáticos de stock físico y reservado comunicándose con el subsistema de Inventarios y Almacén. | Sistema |
| **RF-41** | **Integración con Entregas** | Generar la solicitud de despacho y generar la guía de transporte en el subsistema de Entregas y Despachos para ventas con envío a domicilio. | Sistema |
| **RF-42** | **Alertas de Quiebre de Stock** | Notificar inmediatamente al subsistema de Compras y Proveedores ante el agotamiento de productos o inventario por debajo del punto de reorden. | Sistema |
| **RF-43** | **Disponibilidad Futura** | Consultar en el módulo de Producción y Logística las órdenes de producción en curso y fechas estimadas de reabastecimiento. | Sistema |
| **RF-44** | **Asientos Contables Automáticos** | Transmitir a Contabilidad el desglose fiscal y comercial de cada venta, costo de ventas y reversiones para asentar libros diarios. | Sistema |
| **RF-45** | **Facturación Electrónica** | Enviar el payload fiscal al módulo de Pagos y Facturación para generar la factura electrónica timbrada con código único fiscal (CUF). | Sistema |

---

## Módulo 7: Reportes y Analítica

| Código | Requerimiento Funcional | Descripción Detallada | Actor(es) |
| :--- | :--- | :--- | :--- |
| **RF-46** | **Dashboard de KPIs** | Visualizar en tiempo real un panel ejecutivo con métricas de ventas brutas, ticket promedio, órdenes procesadas y productos top. | Gerente Comercial, Administrador |
| **RF-47** | **Reportes de Ventas Filtrados** | Generar reportes tabulares y gráficos con filtros multidimensionales (período de fechas, sucursal, canal online/físico, categoría y cliente). | Gerente Comercial |
| **RF-48** | **Analítica de Embudo y Abandono** | Analizar el funnel de conversión del marketplace (visitas -> carrito -> checkout -> pago) identificando la tasa de abandono de carritos. | Gerente Comercial |

---

## Módulo 8: Administración y Seguridad

| Código | Requerimiento Funcional | Descripción Detallada | Actor(es) |
| :--- | :--- | :--- | :--- |
| **RF-49** | **Roles y Permisos (RBAC)** | Administrar perfiles de usuario y restringir accesos a vistas, endpoints y acciones según el rol asignado (`Admin`, `Cajero`, `Gerente`, `Cliente`). | Administrador |
| **RF-50** | **Auditoría y Logs** | Registrar bitácoras inmutables con usuario, timestamp, IP y acción para operaciones sensibles (aprobaciones de cotizaciones, cancelaciones, cierres de caja). | Administrador, Sistema |
