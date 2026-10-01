-- Normalize lesson-note defaults to a canonical internal token.
-- The app translates this token into the user's preferred UI language.

alter table public.classes
  alter column note set default '__NO_TOPIC_REGISTERED__';

update public.classes
set note = '__NO_TOPIC_REGISTERED__'
where note is null
   or btrim(note) = ''
   or btrim(
        regexp_replace(
          replace(replace(lower(note), '&lt;', '<'), '&gt;', '>'),
          '(</?\s*div\b[^>]*>|/?\s*div\s*>)',
          '',
          'gi'
        )
      ) = '';
