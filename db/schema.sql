-- ==============================================================================
-- MAXICONECTA - MARKETPLACE Y VENTAS (GRUPO E)
-- DDL DE BASE DE DATOS PARA SUPABASE (POSTGRESQL 15+)
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------------------------
-- ENUMS Y TIPOS DE DATOS
-- ------------------------------------------------------------------------------
CREATE TYPE estado_producto_enum AS ENUM ('borrador', 'publicado', 'inactivo', 'descontinuado');
CREATE TYPE canal_venta_enum AS ENUM ('web', 'pos', 'b2b');
CREATE TYPE tipo_cliente_enum AS ENUM ('retail', 'corporativo_b2b');
CREATE TYPE estado_caja_enum AS ENUM ('abierta', 'cerrada', 'en_arqueo');
CREATE TYPE estado_orden_enum AS ENUM ('pendiente', 'confirmada', 'en_preparacion', 'despachada', 'entregada', 'cancelada');
CREATE TYPE tipo_despacho_enum AS ENUM ('domicilio', 'retiro_sucursal');
CREATE TYPE metodo_pago_enum AS ENUM ('tarjeta', 'qr', 'transferencia', 'efectivo', 'pasarela');
CREATE TYPE estado_pago_enum AS ENUM ('pendiente', 'aprobado', 'rechazado', 'reembolsado');
CREATE TYPE estado_cotizacion_enum AS ENUM ('borrador', 'pendiente_aprobacion', 'aprobada', 'rechazada', 'convertida', 'vencida');
CREATE TYPE estado_devolucion_enum AS ENUM ('solicitada', 'aprobada', 'rechazada', 'completada');

-- ------------------------------------------------------------------------------
-- 1. GESTIÓN DE CATÁLOGO (RF-01 a RF-08)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    padre_id UUID REFERENCES categorias(id) ON DELETE SET NULL,
    atributos_dinamicos JSONB DEFAULT '[]'::jsonb,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS productos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku VARCHAR(100) UNIQUE NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    marca VARCHAR(100),
    categoria_id UUID NOT NULL REFERENCES categorias(id),
    estado estado_producto_enum DEFAULT 'borrador',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS variantes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    producto_id UUID NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    sku VARCHAR(100) UNIQUE NOT NULL,
    nombre_variante VARCHAR(255) NOT NULL,
    atributos JSONB NOT NULL DEFAULT '{}'::jsonb,
    precio NUMERIC(12, 2) NOT NULL CHECK (precio >= 0),
    precio_costo NUMERIC(12, 2) DEFAULT 0 CHECK (precio_costo >= 0),
    codigo_barras VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS imagenes_producto (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    producto_id UUID NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    variante_id UUID REFERENCES variantes(id) ON DELETE SET NULL,
    url VARCHAR(500) NOT NULL,
    es_principal BOOLEAN DEFAULT FALSE,
    orden INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS listas_precios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(100) NOT NULL,
    canal canal_venta_enum NOT NULL,
    tipo_cliente tipo_cliente_enum NOT NULL,
    sucursal_id UUID,
    moneda VARCHAR(10) DEFAULT 'BOB',
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS precios_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lista_precio_id UUID NOT NULL REFERENCES listas_precios(id) ON DELETE CASCADE,
    variante_id UUID NOT NULL REFERENCES variantes(id) ON DELETE CASCADE,
    precio NUMERIC(12, 2) NOT NULL CHECK (precio >= 0),
    fecha_inicio TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_fin TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_lista_variante UNIQUE(lista_precio_id, variante_id)
);

-- ------------------------------------------------------------------------------
-- 2. GESTIÓN DE CLIENTES (RF-22 a RF-26)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS perfiles_clientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE, -- Vínculo opcional con auth.users de Supabase
    nombre_completo VARCHAR(200) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    telefono VARCHAR(50),
    nit_ci VARCHAR(50),
    razon_social VARCHAR(200),
    tipo_cliente tipo_cliente_enum DEFAULT 'retail',
    preferencias_notificacion JSONB DEFAULT '{"email": true, "sms": false, "whatsapp": false}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS direcciones_cliente (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cliente_id UUID NOT NULL REFERENCES perfiles_clientes(id) ON DELETE CASCADE,
    direccion VARCHAR(255) NOT NULL,
    referencia TEXT,
    ciudad VARCHAR(100) NOT NULL,
    latitud NUMERIC(10, 7),
    longitud NUMERIC(10, 7),
    es_predeterminada BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS puntos_fidelidad (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cliente_id UUID UNIQUE NOT NULL REFERENCES perfiles_clientes(id) ON DELETE CASCADE,
    puntos_saldo INT DEFAULT 0 CHECK (puntos_saldo >= 0),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 3. PUNTOS DE VENTA FÍSICOS (POS) (RF-09 a RF-12)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS caja_turnos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sucursal_id UUID NOT NULL,
    cajero_id UUID NOT NULL,
    fondo_inicial NUMERIC(12, 2) NOT NULL CHECK (fondo_inicial >= 0),
    total_efectivo NUMERIC(12, 2) DEFAULT 0,
    total_tarjeta NUMERIC(12, 2) DEFAULT 0,
    total_qr NUMERIC(12, 2) DEFAULT 0,
    monto_cierre_real NUMERIC(12, 2),
    diferencia NUMERIC(12, 2),
    estado estado_caja_enum DEFAULT 'abierta',
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE
);

-- ------------------------------------------------------------------------------
-- 4. MARKETPLACE DIGITAL, PROMOCIONES Y COMBOS (RF-13 a RF-21)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cupones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo VARCHAR(50) UNIQUE NOT NULL,
    descripcion VARCHAR(200),
    tipo_descuento VARCHAR(20) NOT NULL CHECK (tipo_descuento IN ('porcentaje', 'monto_fijo')),
    valor_descuento NUMERIC(10, 2) NOT NULL CHECK (valor_descuento > 0),
    monto_minimo NUMERIC(12, 2) DEFAULT 0,
    usos_maximos INT DEFAULT 100,
    usos_actuales INT DEFAULT 0,
    fecha_inicio TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_fin TIMESTAMP WITH TIME ZONE,
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS combos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    precio_combo NUMERIC(12, 2) NOT NULL CHECK (precio_combo > 0),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS combos_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    combo_id UUID NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
    variante_id UUID NOT NULL REFERENCES variantes(id) ON DELETE CASCADE,
    cantidad INT NOT NULL DEFAULT 1 CHECK (cantidad > 0)
);

CREATE TABLE IF NOT EXISTS resenas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    producto_id UUID NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    cliente_id UUID NOT NULL REFERENCES perfiles_clientes(id) ON DELETE CASCADE,
    calificacion INT NOT NULL CHECK (calificacion BETWEEN 1 AND 5),
    comentario TEXT,
    aprobada BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deseos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cliente_id UUID NOT NULL REFERENCES perfiles_clientes(id) ON DELETE CASCADE,
    variante_id UUID NOT NULL REFERENCES variantes(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_deseo_cliente_variante UNIQUE(cliente_id, variante_id)
);

-- ------------------------------------------------------------------------------
-- 5. GESTIÓN DE VENTAS Y ÓRDENES (RF-27 a RF-39)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ordenes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_orden VARCHAR(50) UNIQUE NOT NULL,
    cliente_id UUID NOT NULL REFERENCES perfiles_clientes(id),
    sucursal_id UUID,
    canal canal_venta_enum NOT NULL DEFAULT 'web',
    tipo_despacho tipo_despacho_enum NOT NULL DEFAULT 'domicilio',
    direccion_entrega_id UUID REFERENCES direcciones_cliente(id),
    subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),
    descuento NUMERIC(12, 2) DEFAULT 0 CHECK (descuento >= 0),
    costo_envio NUMERIC(12, 2) DEFAULT 0 CHECK (costo_envio >= 0),
    total NUMERIC(12, 2) NOT NULL CHECK (total >= 0),
    moneda VARCHAR(10) DEFAULT 'BOB',
    estado estado_orden_enum DEFAULT 'pendiente',
    caja_turno_id UUID REFERENCES caja_turnos(id),
    tracking_number VARCHAR(100),
    cuf_factura VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orden_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    orden_id UUID NOT NULL REFERENCES ordenes(id) ON DELETE CASCADE,
    variante_id UUID NOT NULL REFERENCES variantes(id),
    sku VARCHAR(100) NOT NULL,
    nombre_producto VARCHAR(255) NOT NULL,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(12, 2) NOT NULL CHECK (precio_unitario >= 0),
    total_linea NUMERIC(12, 2) NOT NULL CHECK (total_linea >= 0)
);

CREATE TABLE IF NOT EXISTS pagos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    orden_id UUID NOT NULL REFERENCES ordenes(id) ON DELETE CASCADE,
    transaccion_id VARCHAR(100) UNIQUE,
    metodo metodo_pago_enum NOT NULL,
    monto NUMERIC(12, 2) NOT NULL CHECK (monto > 0),
    moneda VARCHAR(10) DEFAULT 'BOB',
    estado estado_pago_enum DEFAULT 'pendiente',
    raw_payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS devoluciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    orden_id UUID NOT NULL REFERENCES ordenes(id),
    cliente_id UUID NOT NULL REFERENCES perfiles_clientes(id),
    motivo TEXT NOT NULL,
    estado estado_devolucion_enum DEFAULT 'solicitada',
    evidencia_urls JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolucion_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS cotizaciones_b2b (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_cotizacion VARCHAR(50) UNIQUE NOT NULL,
    cliente_id UUID NOT NULL REFERENCES perfiles_clientes(id),
    gerente_id UUID,
    subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),
    descuento_porcentaje NUMERIC(5, 2) DEFAULT 0,
    total NUMERIC(12, 2) NOT NULL CHECK (total >= 0),
    vigencia_hasta DATE NOT NULL,
    estado estado_cotizacion_enum DEFAULT 'borrador',
    orden_id UUID REFERENCES ordenes(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cotizacion_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cotizacion_id UUID NOT NULL REFERENCES cotizaciones_b2b(id) ON DELETE CASCADE,
    variante_id UUID NOT NULL REFERENCES variantes(id),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(12, 2) NOT NULL CHECK (precio_unitario >= 0),
    total_linea NUMERIC(12, 2) NOT NULL CHECK (total_linea >= 0)
);

-- ------------------------------------------------------------------------------
-- 6. ADMINISTRACIÓN, SEGURIDAD Y AUDITORÍA (RF-49, RF-50)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    user_role VARCHAR(50),
    ip_address VARCHAR(45),
    action VARCHAR(100) NOT NULL,
    entity VARCHAR(100) NOT NULL,
    entity_id UUID,
    payload_before JSONB,
    payload_after JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices de alto rendimiento
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria_id);
CREATE INDEX IF NOT EXISTS idx_productos_estado ON productos(estado);
CREATE INDEX IF NOT EXISTS idx_variantes_producto ON variantes(producto_id);
CREATE INDEX IF NOT EXISTS idx_ordenes_cliente ON ordenes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_ordenes_estado ON ordenes(estado);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
