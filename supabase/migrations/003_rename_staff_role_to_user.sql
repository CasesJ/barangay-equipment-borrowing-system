-- Replace the legacy Staff role with User in existing deployments.
-- This leaves Admin and User as the only permitted account roles.

alter table public.users drop constraint if exists users_role_check;

update public.users
set role = 'User'
where role = 'Staff';

alter table public.users
  alter column role set default 'User',
  add constraint users_role_check check (role in ('Admin', 'User'));
