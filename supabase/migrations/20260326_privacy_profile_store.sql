create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.user_profiles (
  anonymous_id uuid primary key,
  consent_version text not null,
  consent_status text not null check (consent_status in ('granted', 'revoked', 'expired')),
  consent_granted_at timestamptz not null,
  last_seen_at timestamptz not null default now(),
  retention_expires_at timestamptz not null,
  profile jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.consent_events (
  id uuid primary key default gen_random_uuid(),
  anonymous_id uuid not null references public.user_profiles(anonymous_id) on delete cascade,
  event_type text not null check (event_type in ('granted', 'revoked', 'expired')),
  consent_version text not null,
  occurred_at timestamptz not null default now(),
  retention_expires_at timestamptz not null,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.health_data_sessions (
  id uuid primary key default gen_random_uuid(),
  anonymous_id uuid not null references public.user_profiles(anonymous_id) on delete cascade,
  session_kind text not null,
  payload jsonb not null default '{}'::jsonb,
  retention_expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_profiles_retention_expires_at
  on public.user_profiles (retention_expires_at);

create index if not exists idx_consent_events_retention_expires_at
  on public.consent_events (retention_expires_at);

create index if not exists idx_health_data_sessions_retention_expires_at
  on public.health_data_sessions (retention_expires_at);

drop trigger if exists trg_user_profiles_updated_at on public.user_profiles;
create trigger trg_user_profiles_updated_at
before update on public.user_profiles
for each row
execute function public.set_updated_at();

drop trigger if exists trg_health_data_sessions_updated_at on public.health_data_sessions;
create trigger trg_health_data_sessions_updated_at
before update on public.health_data_sessions
for each row
execute function public.set_updated_at();

create or replace function public.purge_expired_health_data()
returns void
language sql
as $$
  delete from public.health_data_sessions where retention_expires_at <= now();
  delete from public.consent_events where retention_expires_at <= now();
  delete from public.user_profiles where retention_expires_at <= now();
$$;
