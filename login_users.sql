-- Run once in the Supabase SQL Editor.
create table if not exists public.login_users (
  username text primary key,
  default_password text,
  updated_password text
);
alter table public.login_users enable row level security;
-- No policies: only the Python server (direct DB connection) can read it.
