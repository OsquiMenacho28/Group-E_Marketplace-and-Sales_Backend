import express, { Request, Response, NextFunction } from 'express';
import multer from 'multer';
import sharp from 'sharp';
import { randomUUID } from 'node:crypto';
import { supabaseAdmin, BUCKET_NAME, ensureStorageBucket } from './supabase';

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024 // 10 MB
  },
  fileFilter: (_req, file, cb) => {
    if (file.mimetype.startsWith('image/')) {
      cb(null, true);
    } else {
      cb(new Error('Solo se permiten archivos de imagen válidos (PNG, JPEG, WebP, etc.).'));
    }
  }
});

export function createApiMiddleware() {
  const router = express();
  router.use(express.json());

  // Ensure storage bucket is initialized
  ensureStorageBucket().catch(err => console.error('Bucket initialization error:', err));

  // Health check
  router.get('/health', (_req: Request, res: Response) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  });

  // GET /productos - Lista de productos con categoría y cantidad de imágenes
  router.get('/productos', async (_req: Request, res: Response) => {
    try {
      const { data: productos, error } = await supabaseAdmin
        .from('productos')
        .select(`
          id,
          sku,
          nombre,
          descripcion,
          marca,
          estado,
          categoria_id,
          created_at,
          categorias ( id, nombre ),
          imagenes_producto ( id, url, es_principal, orden )
        `)
        .order('created_at', { ascending: false });

      if (error) {
        console.error('Error fetching productos:', error);
        return res.status(500).json({ error: error.message });
      }

      res.json({ productos });
    } catch (err: any) {
      res.status(500).json({ error: err?.message || 'Error interno del servidor' });
    }
  });

  // GET /categorias - Lista de categorías
  router.get('/categorias', async (_req: Request, res: Response) => {
    try {
      const { data: categorias, error } = await supabaseAdmin
        .from('categorias')
        .select('*')
        .order('nombre', { ascending: true });

      if (error) return res.status(500).json({ error: error.message });
      res.json({ categorias });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // POST /productos - Crear nuevo producto
  router.post('/productos', async (req: Request, res: Response) => {
    try {
      const { sku, nombre, descripcion, marca, categoria_id, estado } = req.body;
      if (!sku || !nombre) {
        return res.status(400).json({ error: 'El SKU y el nombre son requeridos.' });
      }

      const { data, error } = await supabaseAdmin
        .from('productos')
        .insert([{
          sku,
          nombre,
          descripcion: descripcion || '',
          marca: marca || '',
          categoria_id: categoria_id || null,
          estado: estado || 'publicado'
        }])
        .select()
        .single();

      if (error) return res.status(500).json({ error: error.message });
      res.status(201).json({ producto: data });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // GET /productos/:id/imagenes - Listar imágenes de un producto
  router.get('/productos/:id/imagenes', async (req: Request, res: Response) => {
    try {
      const { id } = req.params;
      const { data: imagenes, error } = await supabaseAdmin
        .from('imagenes_producto')
        .select('*')
        .eq('producto_id', id)
        .order('orden', { ascending: true })
        .order('created_at', { ascending: true });

      if (error) return res.status(500).json({ error: error.message });

      // Añadir thumbnailUrl derivado para vista rápida optimizada
      const enriched = (imagenes || []).map(img => {
        let thumbnailUrl = img.url;
        if (img.url.includes(`/object/public/${BUCKET_NAME}/${id}/`)) {
          thumbnailUrl = img.url.replace(`/${id}/`, `/${id}/thumbs/`);
        }
        return {
          ...img,
          thumbnailUrl
        };
      });

      res.json({ imagenes: enriched });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // POST /productos/:id/imagenes - Cargar una o múltiples imágenes (Multipart)
  // Subtarea KAN-75: Integración con Supabase Storage y endpoints de subida multipart
  // Subtarea KAN-76: Generación de thumbnails y optimización/compresión de imágenes
  router.post(
    '/productos/:id/imagenes',
    upload.array('imagenes', 10),
    async (req: Request, res: Response) => {
      try {
        const { id: productoId } = req.params;
        const files = (req.files as Express.Multer.File[]) || (req.file ? [req.file] : []);

        if (!files || files.length === 0) {
          return res.status(400).json({ error: 'No se enviaron archivos de imagen.' });
        }

        // Verificar que el producto exista
        const { data: producto, error: pErr } = await supabaseAdmin
          .from('productos')
          .select('id, nombre')
          .eq('id', productoId)
          .single();

        if (pErr || !producto) {
          return res.status(404).json({ error: 'Producto no encontrado.' });
        }

        // Obtener imágenes existentes para calcular orden y si ya hay principal
        const { data: existingImages } = await supabaseAdmin
          .from('imagenes_producto')
          .select('id, es_principal, orden')
          .eq('producto_id', productoId)
          .order('orden', { ascending: false });

        let currentMaxOrder = (existingImages && existingImages.length > 0)
          ? Math.max(...existingImages.map(i => i.orden || 0))
          : -1;

        const hasPrincipal = existingImages?.some(i => i.es_principal);

        const uploadedResults = [];

        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          const fileUid = randomUUID();
          const mainFileName = `${fileUid}.webp`;
          const mainPath = `${productoId}/${mainFileName}`;
          const thumbPath = `${productoId}/thumbs/${mainFileName}`;

          const originalSize = file.size;

          // 1. Optimización y compresión con Sharp: Máx 1920x1080, WebP 85% calidad
          const optimizedBuffer = await sharp(file.buffer)
            .resize({ width: 1920, height: 1080, fit: 'inside', withoutEnlargement: true })
            .webp({ quality: 85, effort: 4 })
            .toBuffer();

          // 2. Generación de Thumbnail con Sharp: 320x320 Cover, WebP 80% calidad
          const thumbnailBuffer = await sharp(file.buffer)
            .resize(320, 320, { fit: 'cover', position: 'centre' })
            .webp({ quality: 80, effort: 3 })
            .toBuffer();

          // 3. Subida a Supabase Storage: Imagen Optimizada Principal
          const { error: mainUploadError } = await supabaseAdmin.storage
            .from(BUCKET_NAME)
            .upload(mainPath, optimizedBuffer, {
              contentType: 'image/webp',
              upsert: true,
              cacheControl: '31536000'
            });

          if (mainUploadError) {
            console.error('Error subiendo imagen principal a Storage:', mainUploadError);
            throw new Error(`Fallo al subir ${file.originalname}: ${mainUploadError.message}`);
          }

          // 4. Subida a Supabase Storage: Thumbnail
          const { error: thumbUploadError } = await supabaseAdmin.storage
            .from(BUCKET_NAME)
            .upload(thumbPath, thumbnailBuffer, {
              contentType: 'image/webp',
              upsert: true,
              cacheControl: '31536000'
            });

          if (thumbUploadError) {
            console.warn('Advertencia subiendo thumbnail a Storage:', thumbUploadError);
          }

          // 5. Obtener URLs públicas
          const { data: { publicUrl: mainUrl } } = supabaseAdmin.storage
            .from(BUCKET_NAME)
            .getPublicUrl(mainPath);

          const { data: { publicUrl: thumbUrl } } = supabaseAdmin.storage
            .from(BUCKET_NAME)
            .getPublicUrl(thumbPath);

          // Determinar si esta imagen es portada
          currentMaxOrder += 1;
          const isPrincipal = !hasPrincipal && i === 0;

          // 6. Registrar en la tabla imagenes_producto de PostgreSQL
          const { data: dbRecord, error: dbError } = await supabaseAdmin
            .from('imagenes_producto')
            .insert([{
              producto_id: productoId,
              url: mainUrl,
              es_principal: isPrincipal,
              orden: currentMaxOrder
            }])
            .select()
            .single();

          if (dbError) {
            console.error('Error insertando en imagenes_producto:', dbError);
            throw new Error(`Error en base de datos: ${dbError.message}`);
          }

          uploadedResults.push({
            ...dbRecord,
            thumbnailUrl: thumbUrl,
            stats: {
              nombreOriginal: file.originalname,
              pesoOriginalBytes: originalSize,
              pesoOptimizadoBytes: optimizedBuffer.length,
              pesoThumbnailBytes: thumbnailBuffer.length,
              porcentajeAhorro: Math.round((1 - optimizedBuffer.length / originalSize) * 100)
            }
          });
        }

        res.status(201).json({
          success: true,
          message: `${uploadedResults.length} recurso(s) multimedia procesado(s) exitosamente.`,
          imagenes: uploadedResults
        });
      } catch (err: any) {
        console.error('Error en POST /productos/:id/imagenes:', err);
        res.status(500).json({ error: err.message || 'Error al procesar y subir imágenes' });
      }
    }
  );

  // PUT /productos/:id/imagenes/reordenar - Reordenar galería visual
  // Subtarea KAN-77: Reordenamiento de recursos multimedia
  router.put('/productos/:id/imagenes/reordenar', async (req: Request, res: Response) => {
    try {
      const { id: productoId } = req.params;
      const { ordenes } = req.body as { ordenes: Array<{ id: string; orden: number }> };

      if (!Array.isArray(ordenes)) {
        return res.status(400).json({ error: 'El cuerpo debe contener un arreglo "ordenes" con { id, orden }.' });
      }

      // Actualizar secuencialmente o en paralelo
      const updates = ordenes.map(item =>
        supabaseAdmin
          .from('imagenes_producto')
          .update({ orden: item.orden })
          .eq('id', item.id)
          .eq('producto_id', productoId)
      );

      await Promise.all(updates);

      // Retornar lista ordenada actualizada
      const { data: updatedList, error } = await supabaseAdmin
        .from('imagenes_producto')
        .select('*')
        .eq('producto_id', productoId)
        .order('orden', { ascending: true });

      if (error) return res.status(500).json({ error: error.message });

      res.json({
        success: true,
        message: 'Orden de galería actualizado exitosamente.',
        imagenes: updatedList
      });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // PATCH /productos/:id/imagenes/:imagenId/principal - Marcar como imagen de portada
  // Subtarea KAN-78: Selector de imagen de portada
  router.patch('/productos/:id/imagenes/:imagenId/principal', async (req: Request, res: Response) => {
    try {
      const { id: productoId, imagenId } = req.params;

      // 1. Quitar 'es_principal' de todas las imágenes de este producto
      await supabaseAdmin
        .from('imagenes_producto')
        .update({ es_principal: false })
        .eq('producto_id', productoId);

      // 2. Asignar 'es_principal = true' a la imagen seleccionada
      const { data: updated, error } = await supabaseAdmin
        .from('imagenes_producto')
        .update({ es_principal: true })
        .eq('id', imagenId)
        .eq('producto_id', productoId)
        .select()
        .single();

      if (error) return res.status(500).json({ error: error.message });

      res.json({
        success: true,
        message: 'Imagen designada como portada principal del producto.',
        imagen: updated
      });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // DELETE /productos/:id/imagenes/:imagenId - Eliminar recurso multimedia
  // Subtarea KAN-78: Eliminación de recursos multimedia
  router.delete('/productos/:id/imagenes/:imagenId', async (req: Request, res: Response) => {
    try {
      const { id: productoId, imagenId } = req.params;

      // 1. Consultar registro para obtener URL y saber si era principal
      const { data: imgRecord, error: findError } = await supabaseAdmin
        .from('imagenes_producto')
        .select('*')
        .eq('id', imagenId)
        .eq('producto_id', productoId)
        .single();

      if (findError || !imgRecord) {
        return res.status(404).json({ error: 'Recurso multimedia no encontrado.' });
      }

      // 2. Extraer path del storage si está almacenado en Supabase Storage
      try {
        const urlObj = new URL(imgRecord.url);
        const marker = `/storage/v1/object/public/${BUCKET_NAME}/`;
        if (urlObj.pathname.includes(marker)) {
          const relativePath = urlObj.pathname.substring(urlObj.pathname.indexOf(marker) + marker.length);
          const thumbRelativePath = relativePath.replace(`/${productoId}/`, `/${productoId}/thumbs/`);
          await supabaseAdmin.storage.from(BUCKET_NAME).remove([relativePath, thumbRelativePath]);
        }
      } catch (storageErr) {
        console.warn('Aviso: no se pudo eliminar del storage:', storageErr);
      }

      // 3. Eliminar de la base de datos
      const { error: delError } = await supabaseAdmin
        .from('imagenes_producto')
        .delete()
        .eq('id', imagenId)
        .eq('producto_id', productoId);

      if (delError) return res.status(500).json({ error: delError.message });

      // 4. Si la imagen eliminada era la principal, reasignar automáticamente a la primera disponible
      if (imgRecord.es_principal) {
        const { data: remaining } = await supabaseAdmin
          .from('imagenes_producto')
          .select('id')
          .eq('producto_id', productoId)
          .order('orden', { ascending: true })
          .limit(1);

        if (remaining && remaining.length > 0) {
          await supabaseAdmin
            .from('imagenes_producto')
            .update({ es_principal: true })
            .eq('id', remaining[0].id);
        }
      }

      res.json({
        success: true,
        message: 'Recurso multimedia eliminado correctamente.'
      });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  return router;
}
