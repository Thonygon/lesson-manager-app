-- Revert lesson notes to a clean NULL-based structure.
-- Missing notes should be NULL in the database and formatted in the app.

alter table public.classes
  alter column note drop default;

update public.classes
set note = null
where note is null
   or btrim(note) = ''
   or note = '__NO_TOPIC_REGISTERED__'
   or btrim(
        regexp_replace(
          replace(replace(lower(note), '&lt;', '<'), '&gt;', '>'),
          '(</?\s*div\b[^>]*>|/?\s*div\s*>)',
          '',
          'gi'
        )
      ) = '';
