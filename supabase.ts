import { createClient, SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://qixqtmgnwdbzifxyroce.supabase.co';
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFpeHF0bWdud2RiemlmeHlyb2NlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4OTE2NjM4MCwiZXhwIjoyMTA0NzQyMzgwfQ.Khm_uU1UFZ2QURco8Qnb5q_yjm0WwuUD5baTj4cmYoo';

export const supabaseAdmin: SupabaseClient = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

export const BUCKET_NAME = 'productos';

export async function ensureStorageBucket(): Promise<void> {
  try {
    const { data: buckets } = await supabaseAdmin.storage.listBuckets();
    const exists = buckets?.some(b => b.name === BUCKET_NAME);
    if (!exists) {
      await supabaseAdmin.storage.createBucket(BUCKET_NAME, {
        public: true,
        fileSizeLimit: 10485760, // 10MB
        allowedMimeTypes: ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/svg+xml']
      });
      console.log(`[Supabase] Created bucket: ${BUCKET_NAME}`);
    }
  } catch (err) {
    console.warn('[Supabase] Warning checking storage bucket:', err);
  }
}
