-- CLASSIO - Student native language profile field

alter table students
    add column if not exists native_language text not null default '';

comment on column students.native_language is
    'Student native/home language used by AI generators for scaffolding and multilingual support when pedagogically useful.';