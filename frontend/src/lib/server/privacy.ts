import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { CONSENT_VERSION } from '@/src/lib/privacy';

export interface ServerPrivacyContext {
  anonymousId: string;
  consentVersion: string;
  consentGrantedAt: string;
  expiresAt: string;
  purposes?: string[];
}

const DEFAULT_TTL_HOURS = 24;
const SENSITIVE_KEYS = new Set([
  'answers',
  'existinganswers',
  'clarificationqa',
  'answersbycondition',
  'confounderanswers',
  'result',
  'payload',
  'raw',
  'rawoutput',
  'errtext',
  'content',
  'groundingprompt',
  'question',
  'answer',
  'extracttext',
  'extractedtext',
]);

function getTtlHours(): number {
  const raw = Number(process.env.HEALTH_DATA_TTL_HOURS ?? DEFAULT_TTL_HOURS);
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_TTL_HOURS;
}

export function buildRetentionExpiry(now = new Date()): string {
  return new Date(now.getTime() + getTtlHours() * 60 * 60 * 1000).toISOString();
}

export function validatePrivacyContext(value: unknown): ServerPrivacyContext {
  const privacy = value as Partial<ServerPrivacyContext> | null | undefined;

  if (
    !privacy?.anonymousId ||
    !privacy.consentGrantedAt ||
    !privacy.expiresAt ||
    !privacy.consentVersion
  ) {
    throw new Error('Missing privacy consent context.');
  }

  if (privacy.consentVersion !== CONSENT_VERSION) {
    throw new Error('Consent version is outdated.');
  }

  if (new Date(privacy.expiresAt).getTime() <= Date.now()) {
    throw new Error('Consent has expired.');
  }

  return {
    anonymousId: privacy.anonymousId,
    consentVersion: privacy.consentVersion,
    consentGrantedAt: privacy.consentGrantedAt,
    expiresAt: privacy.expiresAt,
    purposes: Array.isArray(privacy.purposes) ? privacy.purposes : [],
  };
}

export function readOptionalPrivacyContext(value: unknown): ServerPrivacyContext | null {
  if (!value) return null;
  return validatePrivacyContext(value);
}

export function normalizeConsentGrantContext(value: unknown): ServerPrivacyContext {
  const privacy = value as Partial<ServerPrivacyContext> | null | undefined;

  if (
    !privacy?.anonymousId ||
    !privacy.consentGrantedAt ||
    !privacy.expiresAt
  ) {
    throw new Error('Missing privacy consent context.');
  }

  if (new Date(privacy.expiresAt).getTime() <= Date.now()) {
    throw new Error('Consent has expired.');
  }

  return {
    anonymousId: privacy.anonymousId,
    consentVersion: CONSENT_VERSION,
    consentGrantedAt: privacy.consentGrantedAt,
    expiresAt: privacy.expiresAt,
    purposes: Array.isArray(privacy.purposes) ? privacy.purposes : [],
  };
}

function getSupabaseAdmin(): SupabaseClient | null {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) return null;

  return createClient(url, key, {
    auth: { persistSession: false },
  });
}

export async function purgeExpiredPrivacyData(): Promise<void> {
  const supabase = getSupabaseAdmin();
  if (!supabase) return;

  const now = new Date().toISOString();

  await Promise.allSettled([
    supabase.from('health_data_sessions').delete().lte('retention_expires_at', now),
    supabase.from('consent_events').delete().lte('retention_expires_at', now),
    supabase.from('user_profiles').delete().lte('retention_expires_at', now),
  ]);
}

export async function recordConsentAcceptance(
  privacy: ServerPrivacyContext,
  metadata: Record<string, unknown> = {}
): Promise<void> {
  const supabase = getSupabaseAdmin();
  if (!supabase) return;

  const retentionExpiresAt = privacy.expiresAt;

  await purgeExpiredPrivacyData();

  const [profileResult, eventResult] = await Promise.all([
    supabase.from('user_profiles').upsert({
      anonymous_id: privacy.anonymousId,
      consent_version: privacy.consentVersion,
      consent_status: 'granted',
      consent_granted_at: privacy.consentGrantedAt,
      last_seen_at: new Date().toISOString(),
      retention_expires_at: retentionExpiresAt,
      profile: {
        purposes: privacy.purposes ?? [],
        ...metadata,
      },
    }),
    supabase.from('consent_events').insert({
      anonymous_id: privacy.anonymousId,
      event_type: 'granted',
      consent_version: privacy.consentVersion,
      occurred_at: privacy.consentGrantedAt,
      retention_expires_at: retentionExpiresAt,
      metadata,
    }),
  ]);

  if (profileResult.error) throw new Error(profileResult.error.message);
  if (eventResult.error) throw new Error(eventResult.error.message);
}

export async function recordConsentExit(privacy: ServerPrivacyContext): Promise<void> {
  const supabase = getSupabaseAdmin();
  if (!supabase) return;

  const now = new Date().toISOString();

  const [profileResult, eventResult] = await Promise.all([
    supabase.from('user_profiles').upsert({
      anonymous_id: privacy.anonymousId,
      consent_version: privacy.consentVersion,
      consent_status: 'revoked',
      consent_granted_at: privacy.consentGrantedAt,
      last_seen_at: now,
      retention_expires_at: now,
      profile: {
        exited_at: now,
      },
    }),
    supabase.from('consent_events').insert({
      anonymous_id: privacy.anonymousId,
      event_type: 'revoked',
      consent_version: privacy.consentVersion,
      occurred_at: now,
      retention_expires_at: now,
      metadata: {
        reason: 'explicit_exit',
      },
    }),
  ]);

  if (profileResult.error) throw new Error(profileResult.error.message);
  if (eventResult.error) throw new Error(eventResult.error.message);
}

export async function persistHealthSession(args: {
  privacy: ServerPrivacyContext;
  sessionKind: string;
  payload: Record<string, unknown>;
  profileSummary?: Record<string, unknown>;
}): Promise<void> {
  const supabase = getSupabaseAdmin();
  if (!supabase) return;

  const { privacy, sessionKind, payload, profileSummary = {} } = args;
  const now = new Date().toISOString();

  await purgeExpiredPrivacyData();

  const [profileResult, sessionResult] = await Promise.all([
    supabase.from('user_profiles').upsert({
      anonymous_id: privacy.anonymousId,
      consent_version: privacy.consentVersion,
      consent_status: 'granted',
      consent_granted_at: privacy.consentGrantedAt,
      last_seen_at: now,
      retention_expires_at: privacy.expiresAt,
      profile: {
        ...profileSummary,
        last_session_kind: sessionKind,
      },
    }),
    supabase.from('health_data_sessions').insert({
      anonymous_id: privacy.anonymousId,
      session_kind: sessionKind,
      payload,
      retention_expires_at: privacy.expiresAt,
    }),
  ]);

  if (profileResult.error) throw new Error(profileResult.error.message);
  if (sessionResult.error) throw new Error(sessionResult.error.message);
}

function summarizeSensitiveValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return { type: 'array', count: value.length };
  }

  if (value && typeof value === 'object') {
    return { type: 'object', count: Object.keys(value as Record<string, unknown>).length };
  }

  if (typeof value === 'string') {
    return { type: 'string', length: value.length };
  }

  return { type: typeof value };
}

export function sanitizeForLogging(input: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(input).map(([key, value]) => {
      const normalizedKey = key.replace(/[^a-z]/gi, '').toLowerCase();
      if (SENSITIVE_KEYS.has(normalizedKey)) {
        return [key, summarizeSensitiveValue(value)];
      }

      if (value && typeof value === 'object' && !Array.isArray(value)) {
        return [key, sanitizeForLogging(value as Record<string, unknown>)];
      }

      if (Array.isArray(value)) {
        return [
          key,
          value.map((item) =>
            item && typeof item === 'object'
              ? sanitizeForLogging(item as Record<string, unknown>)
              : item
          ),
        ];
      }

      return [key, value];
    })
  );
}

export function buildHealthDataSummary(answers: Record<string, unknown>): Record<string, unknown> {
  const answerKeys = Object.keys(answers);
  return {
    answerCount: answerKeys.length,
    answeredFields: answerKeys,
  };
}
