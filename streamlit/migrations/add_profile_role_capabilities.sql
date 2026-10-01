-- ============================================================
-- CLASSIO — Dual-role profile capabilities
-- Additive migration so public identity and active app mode can be decoupled.
-- Existing role-based logic continues to work through safe fallbacks.
-- ============================================================

alter table profiles
    add column if not exists primary_role text
        check (primary_role in ('teacher', 'student', 'tutor')),
    add column if not exists can_teach boolean,
    add column if not exists can_study boolean,
    add column if not exists last_active_mode text
        check (last_active_mode in ('teacher', 'student'));

update profiles
set
    primary_role = coalesce(primary_role, role),
    can_teach = coalesce(can_teach, case when role in ('teacher', 'tutor') then true else false end),
    can_study = coalesce(can_study, case when role = 'student' then true else false end),
    last_active_mode = coalesce(last_active_mode, case when role = 'student' then 'student' else 'teacher' end)
where
    primary_role is null
    or can_teach is null
    or can_study is null
    or last_active_mode is null;

comment on column profiles.primary_role is
    'Canonical public-facing role for community and onboarding. Does not change when switching app mode.';

comment on column profiles.can_teach is
    'Whether this user account can access teacher features and appear in teacher discovery.';

comment on column profiles.can_study is
    'Whether this user account can access student features and appear in student discovery.';

comment on column profiles.last_active_mode is
    'Most recent app interface mode used by the account: teacher or student.';

