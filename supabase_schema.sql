-- Ejecutar una sola vez en Supabase > SQL Editor.
create table if not exists public.user_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  plan text not null default 'free' check (plan in ('free', 'premium', 'lifetime')),
  premium_until timestamptz,
  used_video_to_audio boolean not null default false,
  used_audio_to_text boolean not null default false,
  used_video_to_text boolean not null default false,
  created_at timestamptz not null default now()
);

alter table public.user_profiles enable row level security;

create or replace function public.create_user_profile()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.user_profiles (id, email)
  values (new.id, lower(new.email));
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.create_user_profile();

create or replace function public.consume_free_use(p_user_id uuid, p_service text)
returns setof public.user_profiles
language plpgsql
security definer set search_path = public
as $$
declare
  field_name text;
begin
  if p_service not in ('video_to_audio', 'audio_to_text', 'video_to_text') then
    return;
  end if;

  field_name := 'used_' || p_service;
  return query execute format(
    'update public.user_profiles
     set %I = true
     where id = $1
       and (plan in (''premium'', ''lifetime'') and (plan = ''lifetime'' or premium_until > now())
            or (plan = ''free'' and %I = false))
     returning *', field_name, field_name
  ) using p_user_id;
end;
$$;

revoke all on function public.consume_free_use(uuid, text) from public;
grant execute on function public.consume_free_use(uuid, text) to service_role;
