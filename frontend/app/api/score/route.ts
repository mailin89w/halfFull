import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { writeLog } from '@/src/lib/logger';

/**
 * POST /api/score
 *
 * Accepts a flat answers dict keyed by NHANES field_ids (values are
 * string-encoded NHANES codes, e.g. {"gender": "2", "age_years": "45"}).
 *
 * Spawns `scripts/score_answers.py` via the project venv Python, returns:
 *   { scores: { anemia: 0.31, thyroid: 0.55, ... } }
 *
 * Errors return { error: string } with an appropriate status code.
 */

// Project root is one level above the Next.js `frontend/` directory
const PROJECT_ROOT = path.resolve(process.cwd(), '..');

// Python interpreter: prefer venv, fall back to system python3
const PYTHON = process.env.PYTHON_BIN
  ?? path.join(PROJECT_ROOT, 'ml_project_env', 'bin', 'python3');

const SCORE_SCRIPT = path.join(PROJECT_ROOT, 'scripts', 'score_answers.py');

function runPython(answersJson: string): Promise<{ scores?: Record<string, number>; error?: string; warnings?: string[] }> {
  return new Promise((resolve) => {
    const child = spawn(PYTHON, [SCORE_SCRIPT], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONPATH: PROJECT_ROOT },
    });

    child.stdin.write(answersJson);
    child.stdin.end();

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });

    child.on('close', (code) => {
      if (!stdout.trim()) {
        resolve({ error: `Python exited with code ${code}. stderr: ${stderr.slice(0, 400)}` });
        return;
      }

      try {
        const parsed = JSON.parse(stdout.trim()) as Record<string, unknown>;
        if (parsed.error) {
          resolve({ error: String(parsed.error) });
        } else {
          resolve({
            scores: parsed as Record<string, number>,
            warnings: stderr
              .split(/\r?\n/)
              .map((line) => line.trim())
              .filter(Boolean),
          });
        }
      } catch {
        resolve({ error: `Could not parse Python output: ${stdout.slice(0, 200)}` });
      }
    });

    child.on('error', (err) => {
      resolve({ error: `Failed to spawn Python: ${err.message}` });
    });
  });
}

export async function POST(req: NextRequest) {
  let answers: Record<string, unknown>;

  try {
    const body = await req.json() as { answers?: unknown };
    answers = (body.answers ?? {}) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const result = await runPython(JSON.stringify(answers));

  if (result.error) {
    writeLog('score_error', { answers, error: result.error });
    return NextResponse.json({ error: result.error }, { status: 500 });
  }

  writeLog('score', { answers, scores: result.scores, warnings: result.warnings });
  return NextResponse.json({ scores: result.scores });
}
