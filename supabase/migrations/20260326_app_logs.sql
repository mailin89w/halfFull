create table if not exists public.app_logs (
  id bigserial primary key,
  ts timestamptz not null default now(),
  event text not null,
  payload jsonb not null default '{}'::jsonb
);

create index if not exists idx_app_logs_ts
  on public.app_logs (ts desc);

alter table public.app_logs enable row level security;
