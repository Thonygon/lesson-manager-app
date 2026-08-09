alter table if exists public.videos
    add column if not exists watch_url text not null default '',
    add column if not exists image_url text not null default '',
    add column if not exists cover_image_url text not null default '',
    add column if not exists hero_image_url text not null default '',
    add column if not exists level text not null default '',
    add column if not exists author_name text not null default '';

update public.videos
set
    watch_url = coalesce(nullif(watch_url, ''), nullif(youtube_url, ''), ''),
    image_url = coalesce(nullif(image_url, ''), nullif(thumbnail_url, ''), ''),
    cover_image_url = coalesce(nullif(cover_image_url, ''), nullif(thumbnail_url, ''), ''),
    hero_image_url = coalesce(nullif(hero_image_url, ''), nullif(thumbnail_url, ''), ''),
    level = coalesce(nullif(level, ''), nullif(level_or_band, ''), '')
where coalesce(watch_url, '') = ''
   or coalesce(image_url, '') = ''
   or coalesce(cover_image_url, '') = ''
   or coalesce(hero_image_url, '') = ''
   or coalesce(level, '') = '';

update public.videos as v
set author_name = coalesce(nullif(v.author_name, ''), nullif(p.display_name, ''), nullif(p.username, ''), nullif(p.email, ''), '')
from public.profiles as p
where coalesce(p.user_id, '') = coalesce(v.user_id::text, '')
  and coalesce(v.author_name, '') = '';

alter table if exists public.quick_exams
    add column if not exists author_name text not null default '';

update public.quick_exams as qe
set author_name = coalesce(nullif(qe.author_name, ''), nullif(p.display_name, ''), nullif(p.username, ''), nullif(p.email, ''), '')
from public.profiles as p
where coalesce(p.user_id, '') = coalesce(qe.user_id::text, '')
  and coalesce(qe.author_name, '') = '';
