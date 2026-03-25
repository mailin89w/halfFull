import fs from 'fs';
import path from 'path';
import { createClient } from '@supabase/supabase-js';

// ─── Local file fallback (dev / non-Vercel) ───────────────────────────────────

const LOGS_DIR = path.resolve(process.cwd(), '..', 'logs');

function todayFile(): string {
  const d = new Date();
  const ymd = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return path.join(LOGS_DIR, `${ymd}.jsonl`);
}

function writeLocalLog(entry: string): void {
  try {
    fs.mkdirSync(LOGS_DIR, { recursive: true });
    fs.appendFileSync(todayFile(), entry + '\n', 'utf8');
  } catch {
    // local FS not available (Vercel) — that's fine, Supabase handles it
  }
}

// ─── Supabase client (server-side only, uses service key) ─────────────────────

function getSupabase() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, {
    auth: { persistSession: false },
  });
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Write a structured log entry.
 * - Always console.logs in development.
 * - Writes to local JSONL file when filesystem is available (local dev).
 * - Writes to Supabase `app_logs` table when SUPABASE_URL + SUPABASE_SERVICE_KEY
 *   are set (production on Vercel). Fire-and-forget — never blocks the response.
 */
export function writeLog(event: string, data: Record<string, unknown>): void {
  const ts = new Date().toISOString();
  const entry = JSON.stringify({ ts, event, ...data });

  // Always log to console (visible in Vercel / Railway log streams)
  console.log(`[${event}]`, JSON.stringify(data, null, 2));

  // Local file (dev)
  writeLocalLog(entry);

  // Supabase (production) — async, never await
  const supabase = getSupabase();
  if (supabase) {
    supabase
      .from('app_logs')
      .insert({ ts, event, payload: data })
      .then(({ error }) => {
        if (error) console.error('[logger] Supabase insert failed:', error.message);
      });
  }
}
