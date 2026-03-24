import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { writeLog } from '@/src/lib/logger';

/**
 * POST /api/bayesian-update
 *
 * Runs the Bayesian posterior update given ML scores + user answers.
 *
 * Body:
 * {
 *   mlScores:            Record<string, number>,
 *   confounderAnswers:   Record<string, number>,   // PHQ-2 / GAD-2 ordinal values
 *   answersByCondition:  Record<string, Record<string, string>>,
 *   patientSex?:         string,
 *   existingAnswers?:    Record<string, unknown>,  // raw quiz answers for silent prefill
 * }
 *
 * Response:
 * {
 *   posteriorScores: Record<string, number>,   // updated probabilities, same keys as mlScores
 *   details:         Record<string, object>,   // per-condition Bayesian trace
 * }
 */

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const PYTHON = process.env.PYTHON_BIN
  ?? (process.platform === 'win32'
    ? path.join(PROJECT_ROOT, 'ml_project_env_win', 'Scripts', 'python.exe')
    : path.join(PROJECT_ROOT, 'ml_project_env', 'bin', 'python3'));
const SCRIPT = path.join(PROJECT_ROOT, 'bayesian', 'run_bayesian.py');

function runPython(input: object): Promise<Record<string, unknown>> {
  return new Promise((resolve) => {
    const child = spawn(PYTHON, [SCRIPT], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONPATH: PROJECT_ROOT },
    });

    child.stdin.write(JSON.stringify(input));
    child.stdin.end();

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });

    child.on('close', (code) => {
      if (!stdout.trim()) {
        resolve({ error: `Python exited ${code}. stderr: ${stderr.slice(0, 400)}` });
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim()) as Record<string, unknown>);
      } catch {
        resolve({ error: `Could not parse Python output: ${stdout.slice(0, 200)}` });
      }
    });

    child.on('error', (err) => resolve({ error: `Spawn failed: ${err.message}` }));
  });
}

export async function POST(req: NextRequest) {
  let mlScores: Record<string, number>;
  let confounderAnswers: Record<string, number>;
  let answersByCondition: Record<string, Record<string, string>>;
  let patientSex: string | undefined;
  let existingAnswers: Record<string, unknown>;

  try {
    const body = await req.json() as {
      mlScores?: unknown;
      confounderAnswers?: unknown;
      answersByCondition?: unknown;
      patientSex?: unknown;
      existingAnswers?: unknown;
    };
    mlScores = (body.mlScores ?? {}) as Record<string, number>;
    confounderAnswers = (body.confounderAnswers ?? {}) as Record<string, number>;
    answersByCondition = (body.answersByCondition ?? {}) as Record<string, Record<string, string>>;
    patientSex = typeof body.patientSex === 'string' ? body.patientSex : undefined;
    existingAnswers = (body.existingAnswers ?? {}) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const result = await runPython({
    mode: 'update',
    ml_scores: mlScores,
    confounder_answers: confounderAnswers,
    answers_by_condition: answersByCondition,
    patient_sex: patientSex,
    existing_answers: existingAnswers,
  });

  if (result.error) {
    writeLog('bayesian_update_error', { mlScores, error: result.error });
    return NextResponse.json({ error: result.error }, { status: 500 });
  }

  writeLog('bayesian_update', { mlScores, confounderAnswers, answersByCondition, result });
  return NextResponse.json(result);
}
