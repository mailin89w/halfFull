import fs from 'fs';
import path from 'path';

const LOGS_DIR = path.resolve(process.cwd(), '..', 'logs');

function todayFile(): string {
  const d = new Date();
  const ymd = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return path.join(LOGS_DIR, `${ymd}.jsonl`);
}

export function writeLog(event: string, data: Record<string, unknown>): void {
  try {
    fs.mkdirSync(LOGS_DIR, { recursive: true });
    const entry = JSON.stringify({ ts: new Date().toISOString(), event, ...data });
    fs.appendFileSync(todayFile(), entry + '\n', 'utf8');
    console.log(`[${event}]`, JSON.stringify(data, null, 2));
  } catch (err) {
    console.error('[logger] Failed to write log:', err);
  }
}
