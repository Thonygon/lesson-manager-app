alter table if exists public.quick_exams
    add column if not exists plan_language text not null default '',
    add column if not exists student_material_language text not null default '';

update public.quick_exams
set
    plan_language = coalesce(nullif(plan_language, ''), nullif(exam_data ->> 'plan_language', ''), ''),
    student_material_language = coalesce(
        nullif(student_material_language, ''),
        nullif(exam_data ->> 'student_material_language', ''),
        nullif(exam_data ->> 'plan_language', ''),
        coalesce(nullif(plan_language, ''), nullif(exam_data ->> 'plan_language', ''), '')
    )
where coalesce(plan_language, '') = ''
   or coalesce(student_material_language, '') = '';

create index if not exists idx_quick_exams_language_scope
    on public.quick_exams (student_material_language, plan_language);

alter table if exists public.videos
    add column if not exists student_material_language text not null default '';

create index if not exists idx_videos_language_scope
    on public.videos (student_material_language, subject, learner_stage, level_or_band);
