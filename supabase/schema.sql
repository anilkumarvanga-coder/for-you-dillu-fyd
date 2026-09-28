-- Run once in Supabase SQL Editor. Only the server service role can access usage.
create table if not exists public.fyd_usage (
 user_id uuid primary key references auth.users(id) on delete cascade,
 day date not null, month date not null,
 day_count integer not null default 0, month_count integer not null default 0,
 last_request timestamptz not null default '-infinity'
);
alter table public.fyd_usage enable row level security;
revoke all on public.fyd_usage from anon, authenticated;
create or replace function public.reserve_fyd_request(student uuid) returns boolean
language plpgsql security definer set search_path = public as $$
declare u public.fyd_usage; today date := (now() at time zone 'UTC')::date;
month_start date := date_trunc('month', now() at time zone 'UTC')::date;
begin
 insert into public.fyd_usage(user_id,day,month) values(student,today,month_start) on conflict do nothing;
 select * into u from public.fyd_usage where user_id=student for update;
 if u.day <> today then u.day_count := 0; end if;
 if u.month <> month_start then u.month_count := 0; end if;
 if u.day_count >= 30 or u.month_count >= 300 or u.last_request > now()-interval '10 seconds' then return false; end if;
 update public.fyd_usage set day=today,month=month_start,day_count=u.day_count+1,month_count=u.month_count+1,last_request=now() where user_id=student;
 return true;
end $$;
revoke all on function public.reserve_fyd_request(uuid) from public, anon, authenticated;
grant execute on function public.reserve_fyd_request(uuid) to service_role;
