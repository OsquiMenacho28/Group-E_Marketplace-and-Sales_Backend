# 1. Resumen Ejecutivo del Sistema de Información

**Universidad Católica Boliviana "San Pablo"**  
Facultad de Ciencias Exactas e Ingeniería  
Departamento de Ingeniería de Sistemas  
**Materia:** Taller de Sistemas de Información  
**Ítem de Evaluación N.º 1:** Arquitectura del Sistema de Información y Plan de Proyecto (Jira)  
**Sistema:** MaxiConecta — Marketplace y Ventas  
**Docente:** Ing. Jorge Gustavo Palabral Velarde  
**Fecha:** 8 de Septiembre de 2026 | La Paz — Bolivia  

### Equipo de Trabajo — Grupo E
* **Oscar Alfredo Menacho Silva**
* **Cesar Raul Cayllante Cruz** *(Líder de Proyecto)*
* **Alex Mauricio Flores Beltran**
* **Michelle Doria Medina Ferrufino**
* **Kevin Cristian Sancalli Sanchez**

---

## 1.a Presentación del Sistema de Información

**MaxiConecta Marketplace y Ventas** es el módulo del ERP corporativo encargado de gestionar el ciclo comercial integral, desde la publicación del catálogo de productos hasta el cierre y seguimiento de cada venta, tanto en el canal digital (tienda web/móvil) como en el canal físico (puntos de venta POS en sucursales).

El sistema centraliza:
- La administración del catálogo de productos, categorías, variantes y precios diferenciados.
- El carrito de compras persistente y el proceso de checkout digital.
- La generación y el seguimiento de órdenes multicanal.
- La atención y cobro en cajas físicas (POS).
- La gestión de devoluciones, cancelaciones y cotizaciones B2B.

Al ser un módulo dentro de un ERP corporativo más amplio, **no opera de forma aislada**: se integra de manera continua y desacoplada con los demás subsistemas desarrollados por los otros grupos del curso:
1. **Inventarios y Almacén**
2. **Pagos y Facturación**
3. **Contabilidad**
4. **CRM (Customer Relationship Management)**
5. **Entregas y Despachos**
6. **Compras y Proveedores**
7. **Producción y Logística**

---

## 1.b Propuesta de Valor

MaxiConecta Marketplace y Ventas unifica la experiencia comercial omnicanal y simplifica las operaciones internas de la empresa, aportando valor tangible en tres frentes:

* **Para el cliente final:**
  - Experiencia de compra fluida y consistente entre el canal digital y físico.
  - Disponibilidad de stock unificado y acceso a promociones y cupones comerciales.
  - Trazabilidad y seguimiento de pedidos en tiempo real con selección de entrega a domicilio o retiro en sucursal.
  - Historial consolidado de compras y comprobantes de pago.

* **Para el negocio:**
  - Visibilidad centralizada de las ventas mediante tableros de control (Dashboards) y KPIs en tiempo real.
  - Reducción drástica de sobreventas (*overselling*) mediante mecanismos de reserva temporal de stock con expiración automática.
  - Generación rápida y automatizada de cotizaciones para clientes corporativos (B2B) con flujos de aprobación interna.

* **Para la operación interna:**
  - Automatización de procesos clave: descuento definitivo de inventario, emisión de factura electrónica con timbrado legal, generación de asientos contables automáticos y coordinación con despachos y paquetería.
  - Comunicación fluida y desacoplada con el resto del ecosistema ERP.

---

## 1.c Funcionalidades Principales y Módulos

Las capacidades del sistema se organizan en **8 módulos funcionales** que agrupan los 50 Requerimientos Funcionales identificados:

1. **Gestión de Catálogo:** Administración de productos, categorías jerárquicas, atributos dinámicos, variantes con SKUs independientes, precios diferenciados y sincronización multicanal.
2. **Puntos de Venta Físicos (POS):** Apertura y cierre de caja por turno, emisión e impresión de comprobantes/facturas electrónicas, retiro de pedidos en sucursal y suspensión/recuperación de ventas.
3. **Marketplace Digital:** Carrito persistente, reserva temporal de existencias, checkout multicanal, promociones, cupones, paquetes o combos, recomendaciones (cross-selling), reseñas y lista de deseos.
4. **Gestión de Clientes:** Autenticación segura mediante tokens JWT (Supabase Auth), administración de perfiles y múltiples direcciones, sincronización con CRM, fidelización por puntos y preferencias de notificación.
5. **Gestión de Ventas y Órdenes:** Máquina de estados de órdenes de venta, seguimiento en tiempo real, cancelaciones pre-despacho, devoluciones post-entrega, cotizaciones B2B, registro y validación de pagos y reembolsos.
6. **Integraciones con el ERP:** Protocolos y contratos de interoperabilidad automática con Inventarios, Entregas, Compras, Producción, Contabilidad y Pagos/Facturación.
7. **Reportes y Analítica:** Dashboards de KPIs en tiempo real, reportes de ventas multidimensionales (período, sucursal, canal, producto) y analítica de embudo de conversión / abandono de carrito.
8. **Administración y Seguridad:** Control de acceso basado en roles (RBAC) y registro trazable y auditable de operaciones críticas.

---

## 1.d Usuarios Principales (Perfiles y Actores)

El sistema atiende tanto a usuarios internos de la empresa como a usuarios externos:

| Nombre / Identificación | Categoría / Cargo | Intereses y Rol en el Sistema |
| :--- | :--- | :--- |
| **Cliente (Comprador)** | Externo, Primario | Encontrar productos fácilmente, comprar de forma rápida y segura, usar promociones, calificar productos y hacer seguimiento de sus órdenes. |
| **Cajero** | Interno, Primario | Procesar ventas en el punto de venta físico de forma ágil, aperturar/cerrar caja, emitir comprobantes/facturas y atender retiros en sucursal. |
| **Administrador de Marketplace y Ventas** | Interno, Primario | Mantener actualizado el catálogo de productos, precios y promociones; auditar la seguridad y supervisar el flujo completo de operaciones del módulo. |
| **Gerente Comercial / Analista de Ventas** | Interno, Secundario | Tomar decisiones estratégicas basadas en reportes y KPIs de ventas en tiempo real, y gestionar y aprobar cotizaciones B2B corporativas. |
| **Sistema (Procesos Automatizados)** | Interno, Primario (Actor no humano) | Ejecutar de forma confiable reservas temporales de stock, transiciones automáticas de estados de órdenes y emitir eventos a los módulos externos del ERP. |
| **Vendedor Externo / Proveedor Asociado** | Externo, Secundario | Gestionar imágenes, videos y detalles de productos asignados dentro del marketplace bajo moderación administrativa. |
