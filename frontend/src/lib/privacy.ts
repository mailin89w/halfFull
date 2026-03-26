'use client';

export const CONSENT_VERSION = '2026-03-26';
export const PRIVACY_STORAGE_KEY = 'halffull_privacy_v1';
export const ASSESSMENT_STORAGE_KEY = 'halffull_assessment_v2';
export const MEDGEMMA_STORAGE_KEY = 'halffull_medgemma_v1';
export const DEEP_STORAGE_KEY = 'halffull_deep_v1';
export const FOLLOWUP_STORAGE_KEY = 'halffull_followup_v1';
export const ML_SCORES_KEY = 'halffull_ml_scores_v1';
export const BAYESIAN_SCORES_KEY = 'halffull_bayesian_scores_v1';
export const BAYESIAN_ANSWERS_KEY = 'halffull_bayesian_answers_v1';
export const BAYESIAN_DETAILS_KEY = 'halffull_bayesian_details_v1';
export const CONFIRMED_CONDITIONS_KEY = 'halffull_confirmed_v1';

const DEFAULT_TTL_HOURS = 24;

export interface PrivacyConsentRecord {
  anonymousId: string;
  consentVersion: string;
  consentGrantedAt: string;
  expiresAt: string;
  purposes: string[];
}

export interface PersistedHealthEnvelope<T> {
  privacy?: PrivacyConsentRecord;
  updatedAt: string;
  value: T;
}

function ttlHours(): number {
  const raw = Number(process.env.NEXT_PUBLIC_HEALTH_DATA_TTL_HOURS ?? DEFAULT_TTL_HOURS);
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_TTL_HOURS;
}

export function getHealthDataTtlMs(): number {
  return ttlHours() * 60 * 60 * 1000;
}

export function buildExpiryDate(from = new Date()): string {
  return new Date(from.getTime() + getHealthDataTtlMs()).toISOString();
}

function canUseBrowserStorage(): boolean {
  return typeof window !== 'undefined';
}

export function createPrivacyConsentRecord(): PrivacyConsentRecord {
  const now = new Date();
  return {
    anonymousId: crypto.randomUUID(),
    consentVersion: CONSENT_VERSION,
    consentGrantedAt: now.toISOString(),
    expiresAt: buildExpiryDate(now),
    purposes: [
      'assessment_scoring',
      'ai_report_generation',
      'temporary_health_data_storage',
    ],
  };
}

export function isConsentExpired(record: PrivacyConsentRecord | null | undefined): boolean {
  if (!record?.expiresAt) return true;
  return new Date(record.expiresAt).getTime() <= Date.now();
}

export function readPrivacyConsent(): PrivacyConsentRecord | null {
  if (!canUseBrowserStorage()) return null;

  try {
    const raw = window.localStorage.getItem(PRIVACY_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PrivacyConsentRecord;
    if (isConsentExpired(parsed)) {
      clearStoredHealthData();
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function hasActivePrivacyConsent(): boolean {
  return readPrivacyConsent() !== null;
}

export function storePrivacyConsent(record: PrivacyConsentRecord): void {
  if (!canUseBrowserStorage()) return;
  window.localStorage.setItem(PRIVACY_STORAGE_KEY, JSON.stringify(record));
}

export function getPrivacyContext(): PrivacyConsentRecord | null {
  return readPrivacyConsent();
}

export function wrapPersistedHealthData<T>(
  value: T,
  privacy?: PrivacyConsentRecord
): PersistedHealthEnvelope<T> {
  return {
    privacy,
    updatedAt: new Date().toISOString(),
    value,
  };
}

export function unwrapPersistedHealthData<T>(raw: string | null): T | null {
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as PersistedHealthEnvelope<T>;
    if (parsed.privacy) {
      const current = readPrivacyConsent();
      if (!current) return null;
      if (parsed.privacy.anonymousId !== current.anonymousId) return null;
      if (isConsentExpired(parsed.privacy)) return null;
    }
    return parsed.value;
  } catch {
    return null;
  }
}

export function clearStoredHealthData(): void {
  if (!canUseBrowserStorage()) return;

  window.localStorage.removeItem(PRIVACY_STORAGE_KEY);
  window.sessionStorage.removeItem(ASSESSMENT_STORAGE_KEY);

  [
    MEDGEMMA_STORAGE_KEY,
    DEEP_STORAGE_KEY,
    FOLLOWUP_STORAGE_KEY,
    ML_SCORES_KEY,
    BAYESIAN_SCORES_KEY,
    BAYESIAN_ANSWERS_KEY,
    BAYESIAN_DETAILS_KEY,
    CONFIRMED_CONDITIONS_KEY,
  ].forEach((key) => window.sessionStorage.removeItem(key));
}

export function clearExpiredHealthData(): void {
  if (!canUseBrowserStorage()) return;
  if (!hasActivePrivacyConsent()) {
    window.localStorage.removeItem(PRIVACY_STORAGE_KEY);
  }
}
