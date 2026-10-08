-- Additive migration: legacy Supabase-auth tables are deliberately preserved.
create table public.fyd_documents (
 id uuid primary key, owner text not null, name text not null, mime text not null,
 size bigint not null check(size > 0 and size <= 20000000), path text unique not null,
 dataset text unique, status text not null default 'uploading' check(status in ('uploading','queued','processing','ready','failed','queued_delete','deleting','delete_failed')),
 pages int not null default 0, processed int not null default 0, error text,
 created_at timestamptz not null default now(), started_at timestamptz
);
create table public.fyd_pages (
 document_id uuid references public.fyd_documents on delete cascade,
 page int not null, text text not null, primary key(document_id,page)
);
create table public.fyd_conversations(id uuid primary key,owner text not null,title text not null,created_at timestamptz default now());
create table public.fyd_messages(id bigint generated always as identity primary key,conversation uuid references public.fyd_conversations on delete cascade,role text check(role in ('user','assistant')),content text not null);
create table public.fyd_summaries(document_id uuid primary key references public.fyd_documents on delete cascade,status text not null,content text,error text,started_at timestamptz);
create table public.fyd_usage_v2(owner text primary key,day date not null,month date not null,day_count int not null default 0,month_count int not null default 0,last_request timestamptz default '-infinity');
-- No browser table access: Clerk is checked at gateway, owner checked in Python.
alter table public.fyd_documents enable row level security;
alter table public.fyd_pages enable row level security;
alter table public.fyd_conversations enable row level security;
alter table public.fyd_messages enable row level security;
alter table public.fyd_summaries enable row level security;
alter table public.fyd_usage_v2 enable row level security;
revoke all on public.fyd_documents, public.fyd_pages, public.fyd_conversations, public.fyd_messages, public.fyd_summaries, public.fyd_usage_v2 from anon,authenticated;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types) values('fyd-documents','fyd-documents',false,20000000,array['application/pdf','image/png','image/jpeg','image/webp']) on conflict(id) do nothing;
create or replace function public.fyd_reserve_v2(student text) returns boolean language plpgsql security definer set search_path=public as $$
declare u public.fyd_usage_v2; d date := (now() at time zone 'UTC')::date; m date := date_trunc('month',now() at time zone 'UTC')::date;
begin
 insert into fyd_usage_v2(owner,day,month) values(student,d,m) on conflict do nothing;
 select * into u from fyd_usage_v2 where owner=student for update;
 if u.day<>d then u.day_count:=0; end if;
 if u.month<>m then u.month_count:=0; end if;
 if u.day_count>=30 or u.month_count>=300 then return false; end if;
 update fyd_usage_v2 set day=d,month=m,day_count=u.day_count+1,month_count=u.month_count+1,last_request=now() where owner=student;
 return true;
end $$;
revoke all on function public.fyd_reserve_v2(text) from public,anon,authenticated;
grant execute on function public.fyd_reserve_v2(text) to service_role;
