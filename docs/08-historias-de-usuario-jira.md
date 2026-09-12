# 8. Plan de Sprints e Historias de Usuario para Jira

Planificación de **4 Sprints** para el sistema **MaxiConecta Marketplace y Ventas** que cubre los **50 Requerimientos Funcionales** (RF-01 a RF-50).  

- El **título/nombre de cada Historia de Usuario** coincide exactamente con la formulación estándar (`Como [Rol], quiero [Acción] para [Beneficio]`).
- Las **Tareas de Desarrollo** están desglosadas por especialidad técnica (`[BE]`, `[FE]`, `[DB]`, `[INT]`), eliminando tareas de QA y agregando subtareas de desarrollo específicas estimadas en horas para cargar directamente en Jira.

---

## Resumen de Capacidad por Sprint

| Sprint | Enfoque Principal | Épicas Involucradas | Historias (RFs) | Horas Est. |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | Base de Seguridad, Catálogo y Clientes | Épica 8, Épica 1, Épica 4 | 15 (RF-49, 50, 01-08, 22-26) | 163 h |
| **Sprint 2** | Canales de Venta (POS Físico y Marketplace) | Épica 2, Épica 3 | 13 (RF-09-12, 13-21) | 156 h |
| **Sprint 3** | Ventas, Órdenes, Pagos y Cotizaciones B2B | Épica 5 | 13 (RF-27-39) | 149 h |
| **Sprint 4** | Integraciones ERP y Reportes Analíticos | Épica 6, Épica 7 | 9 (RF-40-48) | 96 h |
| **TOTAL** | **Proyecto Completo** | **8 Épicas** | **50 Historias** | **564 h** |

---

# SPRINT 1: Base de Seguridad, Catálogo y Clientes

### ÉPICA 8: ADMINISTRACIÓN Y SEGURIDAD

#### US-49: Como Administrador, quiero restringir vistas y endpoints según roles para proteger operaciones sensibles contra accesos no autorizados

- **RF Asociado:** RF-49
- **Historia de Usuario:** Como Administrador, quiero restringir vistas y endpoints según roles (`Admin`, `Cajero`, `Gerente`, `Cliente`) para proteger operaciones sensibles contra accesos no autorizados.
- **Criterios de Aceptación:**
  - Token JWT verificado en API Gateway.
  - Roles extraídos de los claims del token.
  - Retorno HTTP 403 ante permisos insuficientes.
- **Tareas de Desarrollo:**
  - `[BE]` Middleware de autorización RBAC en FastAPI y dependencias `Depends(require_role)`. *(4 h)*
  - `[BE]` Decoradores y validación de claims JWT en microservicios internos. *(3 h)*
  - `[FE]` Route guards en Vue Router según roles del token en sesión. *(3 h)*
  - `[FE]` Directiva o componente condicional `<HasRole>` para renderizado según permisos. *(2 h)*
- **Total:** **12 h**

#### US-50: Como Administrador, quiero registrar logs de auditoría estructurados para tener trazabilidad técnica y legal de operaciones críticas

- **RF Asociado:** RF-50
- **Historia de Usuario:** Como Administrador, quiero registrar logs estructurados de cambios en entidades sensibles para contar con trazabilidad técnica y legal.
- **Criterios de Aceptación:**
  - Registro de usuario, timestamp, IP, entidad afectada y diff de cambios.
  - Tabla de auditoría inmutable en PostgreSQL.
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `audit_logs` en Supabase con índices y triggers de captura de cambios. *(3 h)*
  - `[BE]` Servicio asíncrono de inserción de logs en FastAPI con IP y usuario. *(3 h)*
  - `[BE]` Interceptor de eventos sensibles en microservicios para disparo de auditoría. *(3 h)*
- **Total:** **9 h**

---

### ÉPICA 1: GESTIÓN DE CATÁLOGO

#### US-01: Como Administrador, quiero gestionar el ciclo de vida de los productos para mantener actualizado el catálogo comercial

- **RF Asociado:** RF-01
- **Historia de Usuario:** Como Administrador, quiero crear, editar, publicar y descontinuar productos para controlar la oferta comercial activa.
- **Criterios de Aceptación:**
  - Estados soportados: Borrador, Publicado, Descontinuado.
  - SKU maestro único no editable tras publicación.
- **Tareas de Desarrollo:**
  - `[DB]` Esquema de tabla `productos` con restricciones de unicidad de SKU. *(2 h)*
  - `[BE]` CRUD de productos y validaciones con Pydantic v2. *(4 h)*
  - `[FE]` Formulario reactivo de administración de productos con validaciones en panel Admin. *(4 h)*
  - `[FE]` Tabla de gestión con paginación, filtros de estado y acciones rápidas. *(3 h)*
- **Total:** **13 h**

#### US-02: Como Administrador, quiero estructurar categorías jerárquicas y atributos dinámicos para clasificar y tipificar los productos

- **RF Asociado:** RF-02
- **Historia de Usuario:** Como Administrador, quiero estructurar categorías padre/hijo y asociarles atributos dinámicos para organizar el catálogo y tipificar variantes.
- **Criterios de Aceptación:**
  - Soporte de subcategorías sin límite fijo mediante `padre_id`.
  - Atributos dinámicos en formato JSONB.
- **Tareas de Desarrollo:**
  - `[DB]` Estructura autorreferencial recursiva (`padre_id`) y campo JSONB de atributos. *(2 h)*
  - `[BE]` Endpoints jerárquicos recursivos y validadores de atributos dinámicos. *(4 h)*
  - `[FE]` Componente de árbol de categorías colapsable y modal de edición. *(4 h)*
  - `[FE]` Constructor dinámico de campos de atributos según categoría seleccionada. *(3 h)*
- **Total:** **13 h**

#### US-03: Como Administrador o Vendedor Externo, quiero cargar y ordenar recursos multimedia para exhibir la galería visual del producto

- **RF Asociado:** RF-03
- **Historia de Usuario:** Como Administrador o Vendedor Externo, quiero subir y ordenar imágenes y videos de productos para mostrar la galería visual al comprador.
- **Criterios de Aceptación:**
  - Carga a Supabase Storage con compresión automática.
  - Definición de una imagen principal obligatoria.
- **Tareas de Desarrollo:**
  - `[BE]` Integración con Supabase Storage y endpoints de subida multipart. *(3 h)*
  - `[BE]` Generación de thumbnails y optimización/compresión de imágenes. *(3 h)*
  - `[FE]` Uploader drag & drop con previsualización inmediata y reordenamiento. *(4 h)*
  - `[FE]` Selector de imagen de portada y eliminación de recursos multimedia. *(2 h)*
- **Total:** **12 h**

#### US-04: Como Administrador o Gerente Comercial, quiero definir listas de precios diferenciadas para aplicar tarifas según canal, sucursal y tipo de cliente

- **RF Asociado:** RF-04
- **Historia de Usuario:** Como Administrador o Gerente Comercial, quiero definir listas de precios por sucursal, canal y tipo de cliente para aplicar precios mayoristas B2B o minoristas según corresponda.
- **Criterios de Aceptación:**
  - Priorización de reglas: Cliente B2B > Sucursal > Canal general.
  - Moneda parametrizable (BOB / USD).
- **Tareas de Desarrollo:**
  - `[DB]` Tablas `listas_precios` y `precios_items` con soporte de vigencias y canales. *(2 h)*
  - `[BE]` Motor de resolución de precios según canal (Web vs POS) y cliente (Retail vs B2B). *(4 h)*
  - `[FE]` Matriz de asignación de precios por sucursal y canal en Admin. *(3 h)*
  - `[FE]` Componente de visualización de precios con moneda dual (BOB / USD). *(2 h)*
- **Total:** **11 h**

#### US-05: Como Administrador, quiero generar variantes con SKU independiente para controlar el inventario por combinación de atributos

- **RF Asociado:** RF-05
- **Historia de Usuario:** Como Administrador, quiero generar variantes por combinación de atributos (talla, color) para controlar el stock y ventas de cada combinación individualmente.
- **Criterios de Aceptación:**
  - Generación automática de SKU hijo derivado.
  - Cada variante posee precio e inventario propio.
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `variantes` con clave foránea a producto y SKU único hijo. *(2 h)*
  - `[BE]` Generador algorítmico de combinaciones de variantes por atributos. *(4 h)*
  - `[FE]` Matriz de variantes editable con inputs masivos de precio y stock inicial. *(4 h)*
  - `[FE]` Selector interactivo de atributos (talla, color) en ficha de producto. *(3 h)*
- **Total:** **13 h**

#### US-06: Como Cliente, quiero buscar productos por texto completo y filtros facetados para localizar rápidamente los artículos deseados

- **RF Asociado:** RF-06
- **Historia de Usuario:** Como Cliente, quiero buscar productos por texto y aplicar filtros de categoría, precio y atributos para localizar rápidamente los artículos deseados.
- **Criterios de Aceptación:**
  - Búsqueda Full-Text Search insensible a mayúsculas/tildes.
  - Filtros combinables con recuento de coincidencias.
- **Tareas de Desarrollo:**
  - `[DB]` Configuración de índices GIN y campo `tsvector` para PostgreSQL Full-Text Search. *(3 h)*
  - `[BE]` Endpoint de búsqueda facetada con agregaciones de categorías, marcas y precios. *(4 h)*
  - `[FE]` Barra de búsqueda predictiva con autocompletado y debounce. *(3 h)*
  - `[FE]` Barra lateral de filtros facetados acumulativos con recuento de coincidencias. *(3 h)*
- **Total:** **13 h**

#### US-07: Como Cliente o Sistema, quiero consultar la disponibilidad de stock en tiempo real para evitar compras de productos agotados

- **RF Asociado:** RF-07
- **Historia de Usuario:** Como Cliente o Sistema, quiero ver el stock disponible en tiempo real por sucursal o almacén central para no intentar comprar productos agotados.
- **Criterios de Aceptación:**
  - Consulta directa al ERP de Inventarios (RIO-INV-01).
  - Indicador visual "Agotado" o "X unidades disponibles".
- **Tareas de Desarrollo:**
  - `[INT]` Conector HTTP asíncrono hacia el contrato RIO-INV-01 de Inventarios. *(4 h)*
  - `[BE]` Mecanismo de caché en Redis con TTL corto (30s) para mitigar latencia del ERP. *(3 h)*
  - `[FE]` Badges reactivos de disponibilidad en tarjetas de catálogo y detalle. *(2 h)*
- **Total:** **9 h**

#### US-08: Como Administrador o Sistema, quiero sincronizar el catálogo entre web y POS para mantener consistencia de datos y precios

- **RF Asociado:** RF-08
- **Historia de Usuario:** Como Administrador o Sistema, quiero sincronizar catálogo entre tienda web y terminales POS para evitar discrepancias de precio y datos entre canales.
- **Criterios de Aceptación:**
  - Actualización reactiva de precios ante cambios administrativos.
  - Endpoint de sincronización diferencial por timestamp `updated_at`.
- **Tareas de Desarrollo:**
  - `[BE]` Endpoint delta `/sync-catalogo` con paginación por timestamp `updated_at`. *(4 h)*
  - `[BE]` Notificador de cambios de catálogo hacia terminales POS conectadas. *(3 h)*
  - `[FE]` Servicio de sincronización en segundo plano e hidratación de caché local en POS. *(3 h)*
- **Total:** **10 h**

---

### ÉPICA 4: GESTIÓN DE CLIENTES

#### US-22: Como Cliente, quiero registrarme e iniciar sesión con credenciales seguras mediante JWT para acceder a mi cuenta y compras

- **RF Asociado:** RF-22
- **Historia de Usuario:** Como Cliente, quiero registrarme e iniciar sesión con credenciales seguras para acceder a mi carrito personal, historial y pedidos.
- **Criterios de Aceptación:**
  - Integración nativa con Supabase Auth.
  - Emisión de Refresh Token y Access Token JWT.
- **Tareas de Desarrollo:**
  - `[BE]` Integración con Supabase Auth para emisión y validación de tokens JWT. *(4 h)*
  - `[BE]` Endpoint `/me` para consulta de perfil y sesión activa. *(2 h)*
  - `[FE]` Formularios de Login y Registro con validación en tiempo real. *(4 h)*
  - `[FE]` Store de sesión en Pinia con persistencia en localStorage e interceptores Axios. *(3 h)*
- **Total:** **13 h**

#### US-23: Como Cliente, quiero administrar mi libreta de direcciones de entrega para seleccionarlas ágilmente en el checkout

- **RF Asociado:** RF-23
- **Historia de Usuario:** Como Cliente, quiero guardar múltiples direcciones de entrega y datos de contacto para seleccionarlas rápidamente al hacer checkout.
- **Criterios de Aceptación:**
  - Capacidad de marcar una dirección como predeterminada.
  - Validación de campos requeridos (calle, ciudad, referencia, teléfono).
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `direcciones_cliente` con geocoordenadas y flag predeterminada. *(2 h)*
  - `[BE]` CRUD de direcciones vinculadas al cliente autenticado. *(3 h)*
  - `[FE]` Vista de perfil con tarjetas interactivas de direcciones. *(3 h)*
  - `[FE]` Selector de dirección predeterminada en paso de despacho de checkout. *(2 h)*
- **Total:** **10 h**

#### US-24: Como Sistema o Gerente Comercial, quiero sincronizar los clientes con el CRM corporativo para centralizar la información comercial

- **RF Asociado:** RF-24
- **Historia de Usuario:** Como Sistema o Gerente Comercial, quiero enviar altas y actualizaciones de clientes al CRM del ERP para mantener centralizada la ficha de clientes en la empresa.
- **Criterios de Aceptación:**
  - Consumo del contrato RIO-CRM-01.
  - Reintentos exponenciales ante caídas temporales del CRM.
- **Tareas de Desarrollo:**
  - `[INT]` Cliente HTTP para contrato RIO-CRM-01 con manejo de reintentos exponenciales. *(4 h)*
  - `[BE]` Cola o tarea asíncrona de sincronización ante eventos de alta/modificación de cliente. *(3 h)*
  - `[BE]` Mapeador de datos entre esquema interno y contrato RIO-CRM. *(2 h)*
- **Total:** **9 h**

#### US-25: Como Cliente, quiero acumular y canjear puntos de fidelidad para obtener descuentos por compras recurrentes

- **RF Asociado:** RF-25
- **Historia de Usuario:** Como Cliente, quiero acumular puntos por compras y canjearlos en futuras órdenes para obtener descuentos por lealtad.
- **Criterios de Aceptación:**
  - Regla de acumulación configurable (ej. 1 punto por cada 10 BOB).
  - Consulta de saldo de puntos en checkout (RIO-CRM-03).
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `puntos_fidelidad` con saldo y movimientos. *(2 h)*
  - `[INT]` Consulta y redención de puntos contra el CRM mediante RIO-CRM-03. *(3 h)*
  - `[BE]` Motor de conversión de compras en puntos acumulables. *(3 h)*
  - `[FE]` Widget visual de saldo de puntos e input de canje en carrito/checkout. *(3 h)*
- **Total:** **11 h**

#### US-26: Como Cliente, quiero configurar mis canales de notificación para recibir actualizaciones de mis pedidos por el medio preferido

- **RF Asociado:** RF-26
- **Historia de Usuario:** Como Cliente, quiero configurar si recibo notificaciones por Email, SMS o WhatsApp para controlar cómo me comunican el estado de mis pedidos.
- **Criterios de Aceptación:**
  - Switches de activación independientes para pedidos y promociones.
- **Tareas de Desarrollo:**
  - `[DB]` Campo JSONB en `perfiles_clientes` para canales de notificación. *(1 h)*
  - `[BE]` Endpoints de lectura y actualización de preferencias. *(2 h)*
  - `[FE]` Panel de switches interactivos en la sección de perfil de usuario. *(2 h)*
- **Total:** **5 h**

---

# SPRINT 2: Puntos de Venta Físicos (POS) y Marketplace Digital

### ÉPICA 2: PUNTOS DE VENTA FÍSICOS (POS)

#### US-09: Como Cajero, quiero aperturar, controlar y cerrar caja por turno para asegurar el cuadre de efectivo y cobros presenciales

- **RF Asociado:** RF-09
- **Historia de Usuario:** Como Cajero, quiero declarar fondo inicial, registrar arqueos y realizar cierre de turno para garantizar el cuadre de efectivo y cobros en el punto físico.
- **Criterios de Aceptación:**
  - Imposibilidad de vender sin una caja en estado "Abierta".
  - Reporte de diferencias (sobrantes/faltantes) al cierre.
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `caja_turnos` con campos de fondos, totales por método y diferencias. *(3 h)*
  - `[BE]` Endpoints de apertura, registro de arqueos intermedios y balance de cierre. *(4 h)*
  - `[FE]` Modal interactivo de apertura de caja con validación de fondo inicial. *(3 h)*
  - `[FE]` Pantalla de arqueo y cuadre de caja con reporte de diferencias. *(3 h)*
- **Total:** **13 h**

#### US-10: Como Cajero, quiero emitir e imprimir comprobantes y facturas electrónicas para entregar respaldo tributario al cliente

- **RF Asociado:** RF-10
- **Historia de Usuario:** Como Cajero, quiero emitir ticket de venta y facturación electrónica instantánea para entregar el comprobante legal al cliente en mostrador.
- **Criterios de Aceptación:**
  - Envío a ERP Facturación (RIO-PAG-02) para obtener CUF.
  - Formato térmico imprimible (80mm) con código QR tributario.
- **Tareas de Desarrollo:**
  - `[INT]` Integración con RIO-PAG-02 para timbrado legal y obtención de código CUF. *(4 h)*
  - `[BE]` Generación de formato de ticket con desglose de ítems, impuestos y QR tributario. *(3 h)*
  - `[FE]` Plantilla de impresión térmica (80mm) con estilos print CSS. *(3 h)*
  - `[FE]` Disparador automático de diálogo de impresión tras confirmar cobro. *(2 h)*
- **Total:** **12 h**

#### US-11: Como Cajero, quiero validar y entregar pedidos con retiro en sucursal para despachar compras Click and Collect

- **RF Asociado:** RF-11
- **Historia de Usuario:** Como Cajero, quiero buscar pedidos *Click & Collect* por código o QR y marcar entrega para despachar físicamente compras hechas por la web.
- **Criterios de Aceptación:**
  - Validación de identidad del titular o código seguro de retiro.
  - Transición del estado de la orden a "Entregada".
- **Tareas de Desarrollo:**
  - `[BE]` Endpoint de búsqueda de órdenes por código de retiro o escaneo QR. *(3 h)*
  - `[BE]` Validación de estado de orden y actualización a "Entregada" en sucursal. *(3 h)*
  - `[FE]` Vista de escaneo/búsqueda rápida para retiro en sucursal en interfaz POS. *(3 h)*
  - `[FE]` Modal de confirmación de entrega con firma o documento del receptor. *(2 h)*
- **Total:** **11 h**

#### US-12: Como Cajero, quiero suspender y recuperar ventas en curso para agilizar la fila de atención en caja

- **RF Asociado:** RF-12
- **Historia de Usuario:** Como Cajero, quiero pausar una venta con ítems escaneados y continuar con otro cliente para no congelar la fila de atención si el cliente olvida un artículo.
- **Criterios de Aceptación:**
  - Almacenamiento local o en Redis de la lista suspendida.
  - Recuperación de la venta en 1 clic restaurando ítems y subtotal.
- **Tareas de Desarrollo:**
  - `[BE]` Almacenamiento volátil de tickets suspendidos en Redis. *(3 h)*
  - `[FE]` Cola reactiva en Pinia (`usePosStore`) de ventas pausadas. *(3 h)*
  - `[FE]` Panel lateral de ventas en espera con atajos de teclado (`F4` suspender, `F5` recuperar). *(3 h)*
  - `[FE]` Restauración atómica de ítems, cantidades y precios en la terminal. *(2 h)*
- **Total:** **11 h**

---

### ÉPICA 3: MARKETPLACE DIGITAL

#### US-13: Como Cliente, quiero un carrito de compras persistente en Redis para conservar mis artículos entre sesiones y dispositivos

- **RF Asociado:** RF-13
- **Historia de Usuario:** Como Cliente, quiero agregar productos a mi carrito y mantenerlos entre sesiones y dispositivos para completar mi compra cuando me resulte conveniente.
- **Criterios de Aceptación:**
  - Persistencia en Redis asociada al `cliente_id` (o sesión anónima).
  - Actualización inmediata de cantidades y recálculo de importes.
- **Tareas de Desarrollo:**
  - `[BE]` Servicio de carrito en Redis con serialización JSON bajo clave `cart:{cliente_id}`. *(4 h)*
  - `[BE]` Endpoints de adición, actualización de cantidad y remoción de ítems. *(3 h)*
  - `[FE]` Drawer lateral deslizante de carrito con actualización reactiva en tiempo real. *(4 h)*
  - `[FE]` Store de carrito en Pinia sincronizado con el backend. *(3 h)*
- **Total:** **14 h**

#### US-14: Como Sistema, quiero reservar temporalmente el stock durante el checkout para evitar sobreventas concurrentes

- **RF Asociado:** RF-14
- **Historia de Usuario:** Como Sistema, quiero bloquear las unidades del carrito en Inventarios con TTL de 15 minutos para evitar sobreventas mientras el cliente procesa el pago.
- **Criterios de Aceptación:**
  - Ejecución de RIO-INV-02 al pasar al paso de pago.
  - Liberación automática del stock si el TTL expira sin confirmación.
- **Tareas de Desarrollo:**
  - `[BE]` Temporizador de reserva en Redis con `SETEX` y TTL de 15 minutos (900s). *(4 h)*
  - `[INT]` Solicitud de reserva formal al ERP de Inventarios (RIO-INV-02). *(4 h)*
  - `[BE]` Worker/tarea en segundo plano para liberación automática de stock si expira el TTL. *(3 h)*
  - `[FE]` Contador regresivo visible en el checkout con alerta de expiración. *(3 h)*
- **Total:** **14 h**

#### US-15: Como Cliente, quiero seleccionar entre envío a domicilio o retiro en sucursal para elegir cómo recibir mi compra

- **RF Asociado:** RF-15
- **Historia de Usuario:** Como Cliente, quiero elegir entre "Envío a domicilio" o "Retiro en sucursal" para decidir cómo recibir mis productos.
- **Criterios de Aceptación:**
  - Domicilio: cálculo de costo de flete según zona.
  - Retiro: selección de sucursal con stock disponible.
- **Tareas de Desarrollo:**
  - `[BE]` Algoritmo de cálculo de costo de flete según zona y dirección de entrega. *(3 h)*
  - `[BE]` Endpoint de consulta de sucursales habilitadas con stock para retiro. *(3 h)*
  - `[FE]` Paso 1 del Checkout con selector interactivo Domicilio vs Retiro. *(3 h)*
  - `[FE]` Selector de sucursal con visualización de mapa o lista de tiendas. *(2 h)*
- **Total:** **11 h**

#### US-16: Como Cliente, quiero seleccionar el método de pago y procesar la transacción para completar mi compra digital

- **RF Asociado:** RF-16
- **Historia de Usuario:** Como Cliente, quiero seleccionar mi método de pago (Tarjeta, QR, Pasarela) para completar la transacción monetaria de forma confiable.
- **Criterios de Aceptación:**
  - Generación de token transaccional (RIO-PAG-01).
  - Manejo de redirección y webhooks de resultado (Éxito, Rechazado, Pendiente).
- **Tareas de Desarrollo:**
  - `[INT]` Conexión con pasarela de cobro digital (RIO-PAG-01) para emisión de token de pago. *(4 h)*
  - `[BE]` Endpoints de webhook receptor de notificaciones de pago (Aprobado / Rechazado). *(4 h)*
  - `[FE]` Componente selector de métodos de pago (Tarjeta, QR Simple, Pasarela). *(3 h)*
  - `[FE]` Pantalla de procesamiento y visualización de QR dinámico. *(3 h)*
- **Total:** **14 h**

#### US-17: Como Administrador o Gerente Comercial, quiero configurar promociones y cupones de descuento para dinamizar las ventas

- **RF Asociado:** RF-17
- **Historia de Usuario:** Como Administrador o Gerente Comercial, quiero crear cupones de descuento y promociones por fecha para incentivar las ventas con campañas comerciales.
- **Criterios de Aceptación:**
  - Validación de vigencia, límite de usos y monto mínimo de compra.
  - Descuento visible desglosado en el resumen del pedido.
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `cupones` con reglas de vigencia, límite de usos y monto mínimo. *(2 h)*
  - `[BE]` Motor de validación y cálculo de descuentos porcentuales o de monto fijo. *(4 h)*
  - `[FE]` Input de cupón en carrito con retroalimentación inmediata de descuento. *(3 h)*
  - `[FE]` Interfaz de creación y administración de cupones en panel Admin. *(3 h)*
- **Total:** **12 h**

#### US-18: Como Administrador, quiero configurar combos y paquetes comerciales para ofrecer productos agrupados a precio preferencial

- **RF Asociado:** RF-18
- **Historia de Usuario:** Como Administrador, quiero agrupar varios productos en un combo con precio promocional para fomentar compras combinadas de mayor valor.
- **Criterios de Aceptación:**
  - Desglose de existencias individuales de cada ítem del paquete.
  - Visualización del combo como artículo único con detalle de componentes.
- **Tareas de Desarrollo:**
  - `[DB]` Tablas `combos` y `combos_items` para paquetes promocionales. *(2 h)*
  - `[BE]` Lógica de validación de disponibilidad conjunta de todos los ítems del combo. *(4 h)*
  - `[FE]` Ficha visual de combo en vitrina con desglose de productos incluidos. *(3 h)*
  - `[FE]` Gestor de armado de combos con cálculo de ahorro en panel Admin. *(3 h)*
- **Total:** **12 h**

#### US-19: Como Cliente o Sistema, quiero recibir recomendaciones de productos complementarios para descubrir artículos afines a mi compra

- **RF Asociado:** RF-19
- **Historia de Usuario:** Como Cliente o Sistema, quiero ver sugerencias de productos complementarios en la ficha y carrito para descubrir accesorios o versiones superiores.
- **Criterios de Aceptación:**
  - Sugerencias basadas en categoría compartida o configuración manual.
- **Tareas de Desarrollo:**
  - `[BE]` Endpoint `/productos/{id}/recomendados` por relación de categoría o complementariedad. *(4 h)*
  - `[FE]` Carrusel interactivo de recomendaciones en la ficha de producto. *(3 h)*
  - `[FE]` Sección "Frecuentemente comprados juntos" con botón de adición conjunta al carrito. *(3 h)*
- **Total:** **10 h**

#### US-20: Como Cliente o Administrador, quiero calificar productos comprados y moderar reseñas para compartir experiencias verificadas

- **RF Asociado:** RF-20
- **Historia de Usuario:** Como Cliente o Administrador, quiero calificar productos comprados (1-5 estrellas) y moderar comentarios para compartir experiencias reales y mantener la calidad del contenido.
- **Criterios de Aceptación:**
  - Solo clientes con orden entregada pueden calificar el producto.
  - Estado "Pendiente de Moderación" antes de ser pública la reseña.
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `resenas` con calificación, comentario y flag de moderación. *(2 h)*
  - `[BE]` Endpoint de envío de reseña con validación estricta de orden entregada al cliente. *(3 h)*
  - `[BE]` Endpoints administrativos de aprobación y rechazo de reseñas. *(2 h)*
  - `[FE]` Formulario de calificación con selector de estrellas en perfil del cliente. *(3 h)*
  - `[FE]` Bandeja de moderación de comentarios en panel Admin. *(2 h)*
- **Total:** **12 h**

#### US-21: Como Cliente, quiero guardar productos en una lista de deseos para reservarlos para futuras decisiones de compra

- **RF Asociado:** RF-21
- **Historia de Usuario:** Como Cliente, quiero guardar artículos favoritos en mi lista de deseos para revisitarlos y comprarlos posteriormente.
- **Criterios de Aceptación:**
  - Toggle de corazón en tarjetas de producto.
  - Opción de "Mover todo al carrito" desde la lista.
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `deseos` con restricción de clave única cliente-variante. *(2 h)*
  - `[BE]` Endpoints de agregar, quitar y consultar lista de deseos. *(3 h)*
  - `[FE]` Botón de favoritos (corazón) interactivo en tarjetas de producto. *(2 h)*
  - `[FE]` Vista de lista de deseos con acción masiva "Mover al Carrito". *(3 h)*
- **Total:** **10 h**

---

# SPRINT 3: Ventas, Órdenes, Pagos y Cotizaciones B2B

### ÉPICA 5: GESTIÓN DE VENTAS Y ÓRDENES

#### US-27: Como Sistema, quiero generar automáticamente una orden de venta con código único para formalizar la transacción tras el cobro

- **RF Asociado:** RF-27
- **Historia de Usuario:** Como Sistema, quiero crear una orden de venta formal al confirmarse el cobro para dejar constancia legal y contractual de la transacción.
- **Criterios de Aceptación:**
  - Generación de código de orden único (ej. `ORD-2026-0001`).
  - Vínculo inmutable con líneas de pedido, precios pactados y token de pago.
- **Tareas de Desarrollo:**
  - `[DB]` Tablas `ordenes` y `orden_items` con campos de auditoría y estados. *(3 h)*
  - `[BE]` Servicio transaccional atómico de generación de orden y código único. *(4 h)*
  - `[FE]` Pantalla de agradecimiento y confirmación de pedido con número de orden y resumen. *(3 h)*
  - `[BE]` Generación de comprobante digital en PDF. *(3 h)*
- **Total:** **13 h**

#### US-28: Como Sistema o Administrador, quiero controlar la máquina de estados de la orden para garantizar transiciones válidas en su ciclo de vida

- **RF Asociado:** RF-28
- **Historia de Usuario:** Como Sistema o Administrador, quiero controlar las transiciones estrictas de estado de una orden para evitar inconsistencias operativas.
- **Criterios de Aceptación:**
  - Transiciones válidas: *Pendiente -> Confirmada -> Preparando -> Despachada -> Entregada* (o *Cancelada*).
  - Registro de auditoría de cada transición con usuario y timestamp.
- **Tareas de Desarrollo:**
  - `[BE]` Implementación de State Machine pattern con matriz de transiciones válidas. *(4 h)*
  - `[BE]` Disparadores de eventos y registro en bitácora ante cada cambio de estado. *(3 h)*
  - `[FE]` Componente visual de línea de tiempo interactiva (stepper) del pedido. *(3 h)*
  - `[FE]` Selector de cambio de estado en módulo de órdenes en panel Admin. *(2 h)*
- **Total:** **12 h**

#### US-29: Como Cliente, quiero consultar el seguimiento de mi pedido en tiempo real para conocer su avance y fecha estimada de entrega

- **RF Asociado:** RF-29
- **Historia de Usuario:** Como Cliente, quiero consultar el avance de mi orden con número de tracking para conocer cuándo llegará mi paquete.
- **Criterios de Aceptación:**
  - Consulta del estado de entrega en Entregas y Despachos (RIO-ENT-02).
  - Consulta pública accesible con número de pedido y correo.
- **Tareas de Desarrollo:**
  - `[INT]` Integración con RIO-ENT-02 para consulta del estado de entrega en tiempo real. *(4 h)*
  - `[BE]` Endpoint público `/ordenes/{codigo}/tracking` con sanitización de datos. *(3 h)*
  - `[FE]` Portal público de seguimiento por número de guía y correo electrónico. *(3 h)*
- **Total:** **10 h**

#### US-30: Como Sistema, quiero enviar notificaciones automáticas ante cambios de estado del pedido para mantener informado al cliente

- **RF Asociado:** RF-30
- **Historia de Usuario:** Como Sistema, quiero emitir alertas automáticas al cliente ante cada avance del pedido para mantenerlo informado proactivamente.
- **Criterios de Aceptación:**
  - Envío respetando el canal elegido en RF-26 (Email / SMS).
  - Plantillas dinámicas de mensaje con datos de orden y tracking.
- **Tareas de Desarrollo:**
  - `[BE]` Event listener desacoplado para captura de transiciones de estado de orden. *(3 h)*
  - `[BE]` Servicio de plantillas dinámicas de email (confirmación, despacho, entrega). *(4 h)*
  - `[BE]` Despachador de notificaciones según preferencias configuradas por el cliente. *(3 h)*
- **Total:** **10 h**

#### US-31: Como Cliente o Administrador, quiero cancelar pedidos antes de su despacho para liberar el stock y tramitar la reversión de cobro

- **RF Asociado:** RF-31
- **Historia de Usuario:** Como Cliente o Administrador, quiero solicitar o autorizar la cancelación de un pedido antes de su envío para detener el despacho no deseado y recuperar el dinero.
- **Criterios de Aceptación:**
  - Permitido únicamente si la orden NO ha pasado a "Despachada".
  - Desbloqueo de stock e inicio de reversión de cobro.
- **Tareas de Desarrollo:**
  - `[BE]` Validador de regla de negocio: solo pedidos no despachados pueden cancelarse. *(3 h)*
  - `[INT]` Disparo de liberación de reserva en Inventarios y reversión en Pagos. *(4 h)*
  - `[FE]` Botón "Cancelar Pedido" con modal de confirmación y selección de motivo. *(3 h)*
- **Total:** **10 h**

#### US-32: Como Cliente o Administrador, quiero gestionar solicitudes de devolución post-entrega para tramitar garantías y cambios comerciales

- **RF Asociado:** RF-32
- **Historia de Usuario:** Como Cliente o Administrador, quiero registrar una solicitud de devolución para un producto ya entregado para procesar garantías o cambios justificados.
- **Criterios de Aceptación:**
  - Plazo máximo configurable tras la entrega (ej. 7 días calendario).
  - Adjuntar motivo y evidencia fotográfica.
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `devoluciones` con soporte de URLs de evidencias y estados. *(2 h)*
  - `[BE]` Endpoint de radicación de solicitud con carga de fotografías a Supabase Storage. *(4 h)*
  - `[FE]` Formulario guiado de solicitud de devolución en sección "Mis Pedidos". *(3 h)*
  - `[FE]` Bandeja de evaluación y dictamen de devoluciones en panel Admin. *(3 h)*
- **Total:** **12 h**

#### US-33: Como Sistema, quiero revertir asientos contables y reingresar stock automáticamente para asegurar consistencia ante devoluciones

- **RF Asociado:** RF-33
- **Historia de Usuario:** Como Sistema, quiero revertir asientos y sumar al stock físico tras una devolución aceptada para garantizar el cuadre contable e inventarial automático.
- **Criterios de Aceptación:**
  - Llamada a RIO-INV-04 (reingreso de stock).
  - Llamada a RIO-CON-04 (asiento de reversión contable).
- **Tareas de Desarrollo:**
  - `[INT]` Comunicación con RIO-INV-04 para reingreso físico/lógico al almacén origen. *(4 h)*
  - `[INT]` Comunicación con RIO-CON-04 para asiento contable de reversión y ajuste de costo. *(4 h)*
  - `[BE]` Orquestador de transacciones compensatorias ante fallos de integración. *(4 h)*
- **Total:** **12 h**

#### US-34: Como Gerente Comercial, quiero emitir cotizaciones comerciales B2B con vigencia temporal para ofertar pedidos corporativos por volumen

- **RF Asociado:** RF-34
- **Historia de Usuario:** Como Gerente Comercial, quiero crear una cotización formal con precios por volumen y fecha de vigencia para negociar ventas mayoristas con clientes corporativos.
- **Criterios de Aceptación:**
  - Selección de cliente B2B y líneas de producto con precio negociado.
  - Cálculo automático de fecha de expiración de la proforma.
- **Tareas de Desarrollo:**
  - `[DB]` Tablas `cotizaciones_b2b` y `cotizacion_items`. *(2 h)*
  - `[BE]` Endpoints de cotización con cálculo de vigencia y listas de precios B2B. *(4 h)*
  - `[FE]` Creador interactivo de proformas comerciales en panel comercial. *(4 h)*
  - `[BE]` Generación de proforma comercial en PDF membretado. *(3 h)*
- **Total:** **13 h**

#### US-35: Como Gerente Comercial o Administrador, quiero someter cotizaciones a aprobación interna para validar márgenes y descuentos excepcionales

- **RF Asociado:** RF-35
- **Historia de Usuario:** Como Gerente Comercial o Administrador, quiero someter cotizaciones con descuentos especiales a aprobación interna para controlar los márgenes de ganancia mínimos del negocio.
- **Criterios de Aceptación:**
  - Si el descuento supera el umbral (ej. > 15%), requiere visto bueno del Administrador.
  - Registro de comentarios y firma de aprobación.
- **Tareas de Desarrollo:**
  - `[BE]` Motor de reglas para umbrales de descuento con necesidad de visto bueno. *(4 h)*
  - `[BE]` Endpoints de firma/aprobación o rechazo con comentarios comerciales. *(3 h)*
  - `[FE]` Bandeja de cotizaciones por autorizar con comparativa de margen y descuento. *(3 h)*
- **Total:** **10 h**

#### US-36: Como Gerente Comercial, quiero convertir cotizaciones B2B aprobadas en órdenes formales para agilizar la venta sin recapturar datos

- **RF Asociado:** RF-36
- **Historia de Usuario:** Como Gerente Comercial, quiero transformar una cotización aprobada directamente en una orden de venta para iniciar el despacho sin recapturar los ítems cotizados.
- **Criterios de Aceptación:**
  - Congelar los precios acordados en la cotización.
  - La cotización pasa a estado inactivo "Convertida".
- **Tareas de Desarrollo:**
  - `[BE]` Endpoint `/cotizaciones/{id}/convertir` que genera la orden congelando precios. *(4 h)*
  - `[INT]` Reserva de existencias en Inventarios para la orden corporativa. *(3 h)*
  - `[FE]` Botón "Convertir a Venta Formal" y redirección al detalle de orden. *(2 h)*
- **Total:** **9 h**

#### US-37: Como Cliente o Administrador, quiero consultar el historial completo de compras y comprobantes para llevar control de transacciones

- **RF Asociado:** RF-37
- **Historia de Usuario:** Como Cliente o Administrador, quiero consultar todas las compras pasadas con descarga de facturas para llevar control contable y reimprimir comprobantes.
- **Criterios de Aceptación:**
  - Filtro por fecha, estado y código de orden.
  - Descarga directa de factura en PDF o XML.
- **Tareas de Desarrollo:**
  - `[BE]` Endpoint paginado con filtros por rango de fechas, canal y comprobante. *(3 h)*
  - `[FE]` Vista "Mis Pedidos" con tarjetas de historial y descarga de comprobantes. *(4 h)*
  - `[FE]` Buscador y visualizador de facturas electrónicas timbradas. *(3 h)*
- **Total:** **10 h**

#### US-38: Como Cajero o Sistema, quiero registrar y validar el pago de una orden para autorizar su preparación y despacho

- **RF Asociado:** RF-38
- **Historia de Usuario:** Como Cajero o Sistema, quiero registrar el pago recibido y conciliarlo antes de despachar para garantizar que no salgan productos sin fondos asegurados.
- **Criterios de Aceptación:**
  - Conciliación de montos parciales o totales (efectivo, tarjeta, transferencias).
  - Bloqueo de cambio a "En Preparación" si el saldo pendiente > 0.
- **Tareas de Desarrollo:**
  - `[DB]` Tabla `pagos` con vinculación a órdenes y método utilizado. *(2 h)*
  - `[BE]` Validador de liquidación completa antes de habilitar paso a preparación. *(3 h)*
  - `[FE]` Modal de registro de cobro y validación de saldos en módulo de ventas. *(3 h)*
- **Total:** **8 h**

#### US-39: Como Administrador o Sistema, quiero gestionar reembolsos de pagos aprobados para reintegrar el dinero ante anulaciones o devoluciones

- **RF Asociado:** RF-39
- **Historia de Usuario:** Como Administrador o Sistema, quiero tramitar el retorno de fondos ante cancelaciones aprobadas para devolver el dinero al cliente en cumplimiento de garantías.
- **Criterios de Aceptación:**
  - Comunicación con pasarela de pagos (RIO-PAG-03) para reversión.
  - Registro del ID de devolución bancaria en el sistema.
- **Tareas de Desarrollo:**
  - `[INT]` Comunicación con RIO-PAG-03 para ejecución de reembolso bancario/pasarela. *(4 h)*
  - `[BE]` Registro del identificador de reembolso y actualización del balance de orden. *(3 h)*
  - `[FE]` Panel de reembolsos pendientes con confirmación y bitácora de dispersión. *(3 h)*
- **Total:** **10 h**

---

# SPRINT 4: Integraciones ERP y Reportes Analíticos

### ÉPICA 6: INTEGRACIONES CON EL ERP CORPORATIVO

#### US-40: Como Sistema, quiero sincronizar descuentos y reintegros de inventario con el ERP de Inventarios para mantener existencias reales

- **RF Asociado:** RF-40
- **Historia de Usuario:** Como Sistema, quiero sincronizar consumos y reingresos con el ERP de Inventarios y Almacén para mantener las existencias de toda la empresa cuadradas en tiempo real.
- **Criterios de Aceptación:**
  - Implementación estricta de RIO-INV-03 y RIO-INV-04.
  - Registro de almacén de origen y tipo de movimiento en el payload.
- **Tareas de Desarrollo:**
  - `[INT]` Implementación del cliente `InventariosClient` para RIO-INV-03 y RIO-INV-04. *(5 h)*
  - `[BE]` Manejo de colas y reintentos ante indisponibilidad temporal del ERP de Inventarios. *(4 h)*
  - `[DB]` Registro de conciliación de movimientos de stock enviados. *(2 h)*
- **Total:** **11 h**

#### US-41: Como Sistema, quiero generar órdenes de despacho en el ERP de Entregas para coordinar rutas y transportistas de envíos a domicilio

- **RF Asociado:** RF-41
- **Historia de Usuario:** Como Sistema, quiero enviar órdenes con entrega a domicilio al ERP de Entregas y Despachos para programar rutas de flete y empaquetado sin intervención manual.
- **Criterios de Aceptación:**
  - Implementación de RIO-ENT-01 al confirmarse la orden.
  - Recepción y guardado del `tracking_id` retornado por Entregas.
- **Tareas de Desarrollo:**
  - `[INT]` Implementación del cliente `EntregasClient` para RIO-ENT-01 y almacenamiento de guía. *(4 h)*
  - `[BE]` Mapeo de especificaciones de bulto, peso volumétrico y geodatos de entrega. *(3 h)*
  - `[BE]` Webhook receptor de actualizaciones de estado de ruta desde Entregas. *(3 h)*
- **Total:** **10 h**

#### US-42: Como Sistema, quiero enviar alertas de quiebre de stock al módulo de Compras para solicitar la reposición oportuna de mercadería

- **RF Asociado:** RF-42
- **Historia de Usuario:** Como Sistema, quiero alertar al módulo de Compras y Proveedores ante existencias críticas para disparar órdenes de compra antes de que se produzca un desabastecimiento.
- **Criterios de Aceptación:**
  - Disparo de alerta si `stock_disponible <= punto_reorden`.
- **Tareas de Desarrollo:**
  - `[BE]` Tarea programada o trigger de evaluación de existencias vs punto de reorden. *(4 h)*
  - `[INT]` Cliente de despacho de eventos de quiebre hacia el módulo de Compras. *(3 h)*
  - `[FE]` Vista de alertas de quiebre de stock en panel Admin. *(2 h)*
- **Total:** **9 h**

#### US-43: Como Sistema o Administrador, quiero consultar proyecciones de fabricación en el ERP de Producción para prever disponibilidad futura

- **RF Asociado:** RF-43
- **Historia de Usuario:** Como Sistema o Administrador, quiero consultar fechas estimadas de fabricación en el ERP de Producción para mostrar fechas de preventa y habilitar cotizaciones B2B a futuro.
- **Criterios de Aceptación:**
  - Consumo de RIO-PRD-01 con SKU y cantidad proyectada.
- **Tareas de Desarrollo:**
  - `[INT]` Implementación de `ProduccionClient` para consumo de RIO-PRD-01. *(4 h)*
  - `[BE]` Endpoint de proyección de lotes fabriles futuros por SKU. *(3 h)*
  - `[FE]` Badge interactivo de fecha estimada de disponibilidad en catálogo. *(2 h)*
- **Total:** **9 h**

#### US-44: Como Sistema, quiero generar asientos contables automáticos en el ERP de Contabilidad para asentar ingresos, costos y reversiones

- **RF Asociado:** RF-44
- **Historia de Usuario:** Como Sistema, quiero enviar los datos comerciales al ERP de Contabilidad para asentar libros de ventas, impuestos y costo de ventas automáticamente.
- **Criterios de Aceptación:**
  - Implementación de RIO-CON-01 (ventas), RIO-CON-02 (costo) y RIO-CON-04 (reversión).
  - Desglose de ingresos netos, débitos fiscales y comisiones.
- **Tareas de Desarrollo:**
  - `[INT]` Implementación de `ContabilidadClient` para RIO-CON-01, 02 y 04. *(5 h)*
  - `[BE]` Mapeador de cuentas contables (ventas, débito fiscal, comisiones, costo). *(4 h)*
  - `[BE]` Registro de log de auditoría contable con número de asiento devuelto por ERP. *(2 h)*
- **Total:** **11 h**

#### US-45: Como Sistema, quiero transmitir datos fiscales al ERP de Pagos y Facturación para la emisión de facturas electrónicas timbradas

- **RF Asociado:** RF-45
- **Historia de Usuario:** Como Sistema, quiero transmitir detalles fiscales al ERP de Pagos y Facturación para obtener el timbrado tributario y código CUF de cada venta.
- **Criterios de Aceptación:**
  - Envío de RIO-PAG-02 al confirmarse la transacción.
  - Almacenamiento del número de factura, CUF y URL del documento fiscal.
- **Tareas de Desarrollo:**
  - `[INT]` Implementación de `PagosClient` para RIO-PAG-02 (emisión y timbrado CUF). *(5 h)*
  - `[BE]` Parser y almacenamiento seguro de código CUF, número de factura y XML/PDF. *(3 h)*
  - `[FE]` Visor e impresor de factura legal timbrada en portal de clientes y Admin. *(3 h)*
- **Total:** **11 h**

---

### ÉPICA 7: REPORTES Y ANALÍTICA

#### US-46: Como Gerente Comercial o Administrador, quiero visualizar un dashboard de KPIs en tiempo real para evaluar el rendimiento de ventas

- **RF Asociado:** RF-46
- **Historia de Usuario:** Como Gerente Comercial o Administrador, quiero ver métricas clave de ventas, ticket promedio y productos líderes para evaluar el rendimiento comercial de un vistazo.
- **Criterios de Aceptación:**
  - KPIs: Ventas brutas del día/mes, número de pedidos, ticket medio y conversión.
  - Gráficos interactivos de tendencias.
- **Tareas de Desarrollo:**
  - `[BE]` Endpoints de agregaciones estadísticas de ventas, tickets y pedidos con caché Redis. *(4 h)*
  - `[FE]` Dashboard con cards de métricas en tiempo real y tendencias porcentuales. *(4 h)*
  - `[FE]` Gráficos interactivos de evolución de ventas diarias y mensuales. *(4 h)*
- **Total:** **12 h**

#### US-47: Como Gerente Comercial, quiero generar reportes de ventas filtrados y exportables para análisis comerciales y auditorías

- **RF Asociado:** RF-47
- **Historia de Usuario:** Como Gerente Comercial, quiero exportar tablas de ventas filtradas por canal, sucursal, producto y fecha para respaldar análisis de auditoría y reuniones de directorio.
- **Criterios de Aceptación:**
  - Filtros acumulativos con previsualización en pantalla.
  - Exportación en formato CSV y Excel (.xlsx).
- **Tareas de Desarrollo:**
  - `[BE]` Motor de consultas SQL dinámicas con filtros acumulativos y paginación. *(4 h)*
  - `[BE]` Generador de exportación a archivos CSV y Excel (.xlsx). *(4 h)*
  - `[FE]` Interfaz de selección de filtros y tabla interactiva de previsualización. *(4 h)*
- **Total:** **12 h**

#### US-48: Como Gerente Comercial, quiero analizar el embudo de conversión y carritos abandonados para optimizar el proceso de compra

- **RF Asociado:** RF-48
- **Historia de Usuario:** Como Gerente Comercial, quiero analizar las tasas de caída en cada etapa del embudo de compra para detectar fricciones en el checkout y optimizar la conversión.
- **Criterios de Aceptación:**
  - Métricas de embudo: Vistas de catálogo -> Adición a carrito -> Checkout iniciado -> Pago exitoso.
  - Tasa porcentual de carritos abandonados.
- **Tareas de Desarrollo:**
  - `[BE]` Algoritmo de agregación de pasos de embudo (visita, carrito, checkout, compra). *(4 h)*
  - `[BE]` Cálculo de tasa de carritos abandonados y métricas de fuga. *(3 h)*
  - `[FE]` Visualización gráfica interactiva del funnel de conversión con porcentajes de retención. *(4 h)*
- **Total:** **11 h**

---

## Matriz de Distribución de Horas por Especialidad de Desarrollo

| Épica | Backend `[BE]` | Frontend `[FE]` | Base de Datos `[DB]` | Integraciones ERP `[INT]` | Total Horas |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Épica 1: Catálogo** | 31 h | 34 h | 9 h | 4 h | **78 h** |
| **Épica 2: Puntos de Venta (POS)** | 14 h | 22 h | 3 h | 8 h | **47 h** |
| **Épica 3: Marketplace Digital** | 33 h | 40 h | 8 h | 16 h | **97 h** |
| **Épica 4: Gestión de Clientes** | 19 h | 17 h | 5 h | 7 h | **48 h** |
| **Épica 5: Ventas y Órdenes** | 50 h | 35 h | 7 h | 27 h | **119 h** |
| **Épica 6: Integraciones ERP** | 17 h | 7 h | 4 h | 33 h | **61 h** |
| **Épica 7: Reportes y Analítica** | 19 h | 16 h | 0 h | 0 h | **35 h** |
| **Épica 8: Administración y Seguridad** | 10 h | 5 h | 3 h | 0 h | **18 h** |
| **TOTALES** | **193 h (34%)** | **176 h (31%)** | **39 h (7%)** | **95 h (17%)** | **~564 h (Buffer 11%)** |
