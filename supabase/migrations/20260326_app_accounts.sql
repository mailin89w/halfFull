create table if not exists public.app_accounts (
  id uuid primary key default gen_random_uuid(),
  login text not null,
  password_hash text not null,
  anonymous_id uuid not null references public.user_profiles(anonymous_id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_app_accounts_login_lower
  on public.app_accounts (lower(login));

drop trigger if exists trg_app_accounts_updated_at on public.app_accounts;
create trigger trg_app_accounts_updated_at
before update on public.app_accounts
for each row
execute function public.set_updated_at();
