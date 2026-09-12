# 7. Administración del Proyecto en Jira y Cronograma

El plan de trabajo del proyecto **MaxiConecta Marketplace y Ventas** se administra en Jira siguiendo una estructura de desglose de trabajo (**WBS al Nivel 2**):
- **Nivel 1:** Corresponde a los **8 módulos funcionales** configurados como **Épicas**.
- **Nivel 2:** Corresponde a los **50 Requerimientos Funcionales** configurados como **Historias / Tareas**.

> [!NOTE]
> **Espacio de Jira del Grupo E:**  
> [Acceso al Proyecto en Jira](https://kevinsancalli.atlassian.net/?continue=https%3A%2F%2Fkevinsancalli.atlassian.net%2Fwelcome%2Fsoftware%3FprojectId%3D10000&atlOrigin=eyJpIjoiYTEwMDdiMzE2MWVjNDZkYjg5OTIwNTQ2YmM2ZTNmYWMiLCJwIjoiamlyYS1zb2Z0d2FyZSJ9)

---

## 7.a Matriz de Dependencias entre Módulos (WBS Nivel 1)

La secuencia entre módulos respeta las dependencias funcionales reales del sistema:
- **Catálogo** y **Clientes** no dependen de otros módulos y arrancan en paralelo el primer día.
- **Puntos de Venta Físicos** y **Marketplace Digital** requieren el catálogo y la autenticación listos.
- **Gestión de Ventas y Órdenes** requiere los canales comercializadores operativos.
- **Integraciones con ERP** y **Reportes y Analítica** requieren órdenes generando datos transaccionales.

| Épica / Módulo | Predecesora | Tipo de Dependencia | Período Estimado |
| :--- | :--- | :--- | :--- |
| **1. Gestión de Catálogo** | — (Inicio de proyecto) | — | 14 Sep – 28 Sep |
| **2. Gestión de Clientes** | — (Inicio de proyecto) | — | 14 Sep – 28 Sep |
| **3. Puntos de Venta Físicos** | Módulo 1: Catálogo | Finish-to-Start | 19 Sep – 30 Sep |
| **4. Marketplace Digital** | Módulo 1: Catálogo, Módulo 2: Clientes | Finish-to-Start | 30 Sep – 29 Oct |
| **5. Administración y Seguridad** | Módulo 4: Marketplace Digital | Finish-to-Start | 19 Sep – 25 Sep (Base) / Octubre |
| **6. Gestión de Ventas y Órdenes** | Módulo 5: Administración y Seguridad | Finish-to-Start | 02 Nov – 04 Dic |
| **7. Integraciones con el ERP** | Módulo 6: Ventas y Órdenes | Finish-to-Start | 03 Dic – 05 Dic |
| **8. Reportes y Analítica** | Módulo 6: Ventas y Órdenes | Finish-to-Start | 03 Dic – 05 Dic |

---

## 7.b Detalle Completo de Tareas (WBS Nivel 2: RF-01 al RF-50)

### Épica: Gestión de Catálogo
| Código | Tarea / Requerimiento Funcional | Inicio Estimado | Fin Estimado |
| :--- | :--- | :--- | :--- |
| **RF-03** | Imágenes y Multimedia | 14 Sep | 16 Sep |
| **RF-02** | Categorías y Atributos | 16 Sep | 18 Sep |
| **RF-01** | Gestión de Productos | 18 Sep | 20 Sep |
| **RF-05** | Variantes de Producto | 20 Sep | 22 Sep |
| **RF-04** | Listas de Precios | 22 Sep | 24 Sep |
| **RF-07** | Disponibilidad de Stock | 24 Sep | 26 Sep |
| **RF-06** | Búsqueda Facetada | 26 Sep | 27 Sep |
| **RF-08** | Sincronización Multicanal | 27 Sep | 28 Sep |

### Épica: Gestión de Clientes
| Código | Tarea / Requerimiento Funcional | Inicio Estimado | Fin Estimado |
| :--- | :--- | :--- | :--- |
| **RF-22** | Registro y Autenticación | 14 Sep | 17 Sep |
| **RF-23** | Perfil y Direcciones | 17 Sep | 20 Sep |
| **RF-24** | Sincronización con CRM | 20 Sep | 24 Sep |
| **RF-25** | Fidelización y Puntos | 24 Sep | 26 Sep |
| **RF-26** | Preferencias de Notificación | 26 Sep | 28 Sep |

### Épica: Administración y Seguridad
| Código | Tarea / Requerimiento Funcional | Inicio Estimado | Fin Estimado |
| :--- | :--- | :--- | :--- |
| **RF-49** | Roles y Permisos | 19 Sep | 22 Sep |
| **RF-50** | Auditoría y Logs | 22 Sep | 25 Sep |

### Épica: Puntos de Venta Físicos (POS)
| Código | Tarea / Requerimiento Funcional | Inicio Estimado | Fin Estimado |
| :--- | :--- | :--- | :--- |
| **RF-09** | Apertura/Cierre de Caja | 19 Sep | 22 Sep |
| **RF-10** | Comprobantes en POS | 22 Sep | 25 Sep |
| **RF-11** | Retiro en Sucursal | 25 Sep | 27 Sep |
| **RF-12** | Suspender/Recuperar Venta | 27 Sep | 30 Sep |

### Épica: Marketplace Digital
| Código | Tarea / Requerimiento Funcional | Inicio Estimado | Fin Estimado |
| :--- | :--- | :--- | :--- |
| **RF-13** | Carrito Persistente | 30 Sep | 02 Oct |
| **RF-14** | Reserva Temporal de Stock | 02 Oct | 05 Oct |
| **RF-15** | Selección de Entrega | 05 Oct | 09 Oct |
| **RF-16** | Selección de Pago | 09 Oct | 13 Oct |
| **RF-17** | Promociones y Cupones | 13 Oct | 17 Oct |
| **RF-18** | Combos Comerciales | 17 Oct | 20 Oct |
| **RF-19** | Recomendaciones (Cross-selling) | 20 Oct | 23 Oct |
| **RF-20** | Reseñas y Calificaciones | 23 Oct | 26 Oct |
| **RF-21** | Lista de Deseos | 26 Oct | 29 Oct |

### Épica: Gestión de Ventas y Órdenes
| Código | Tarea / Requerimiento Funcional | Inicio Estimado | Fin Estimado |
| :--- | :--- | :--- | :--- |
| **RF-27** | Generación de Orden | 02 Nov | 05 Nov |
| **RF-28** | Máquina de Estados de Orden | 05 Nov | 08 Nov |
| **RF-29** | Seguimiento de Pedido | 08 Nov | 11 Nov |
| **RF-30** | Notificaciones de Estado | 11 Nov | 14 Nov |
| **RF-31** | Cancelación Pre-Despacho | 14 Nov | 16 Nov |
| **RF-32** | Devoluciones Post-Entrega | 16 Nov | 19 Nov |
| **RF-33** | Reversión Contable e Inventario | 19 Nov | 22 Nov |
| **RF-34** | Cotizaciones B2B | 22 Nov | 24 Nov |
| **RF-35** | Aprobación de Cotizaciones | 24 Nov | 26 Nov |
| **RF-36** | Conversión Cotización a Orden | 26 Nov | 28 Nov |
| **RF-37** | Historial de Compras | 28 Nov | 30 Nov |
| **RF-38** | Registro y Validación de Pago | 30 Nov | 02 Dic |
| **RF-39** | Gestión de Reembolsos | 02 Dic | 04 Dic |

### Épica: Integraciones con el ERP
| Código | Tarea / Requerimiento Funcional | Inicio Estimado | Fin Estimado |
| :--- | :--- | :--- | :--- |
| **RF-40** | Integración con Inventario | 03 Dic | 04 Dic |
| **RF-41** | Integración con Entregas | 04 Dic | 05 Dic |
| **RF-42** | Alertas de Quiebre o Corrección | 05 Dic | 05 Dic |
| **RF-43** | Disponibilidad Futura (Proyección) | 05 Dic | 05 Dic |
| **RF-44** | Asientos Contables Automáticos | 05 Dic | 05 Dic |
| **RF-45** | Facturación Electrónica | 05 Dic | 05 Dic |

### Épica: Reportes y Analítica
| Código | Tarea / Requerimiento Funcional | Inicio Estimado | Fin Estimado |
| :--- | :--- | :--- | :--- |
| **RF-46** | Dashboard de KPIs | 03 Dic | 04 Dic |
| **RF-47** | Reportes de Ventas Filtrados | 04 Dic | 05 Dic |
| **RF-48** | Analítica de Embudo/Abandono | 05 Dic | 05 Dic |
