-- ============================================================
-- CLASSIO — Bridge local teacher students with Classio-linked students
-- Safe additive columns so the newer teacher-student relationship system
-- can connect to the teacher's existing students list without duplicates.
-- ============================================================

alter table students
    add column if not exists linked_student_user_id uuid references auth.users(id) on delete set null,
    add column if not exists teacher_student_link_id bigint references teacher_student_links(id) on delete set null,
    add column if not exists student_source text not null default 'manual'
        check (student_source in ('manual', 'classio_link', 'classio_linked_existing')),
    add column if not exists linked_at timestamptz;

create index if not exists idx_students_linked_student_user_id
    on students(linked_student_user_id);

create index if not exists idx_students_teacher_student_link_id
    on students(teacher_student_link_id);

create unique index if not exists idx_students_user_linked_student_unique
    on students(user_id, linked_student_user_id)
    where linked_student_user_id is not null;

comment on column students.linked_student_user_id is
    'Classio app user id for the linked student when this local student row is bridged to teacher_student_links.';

comment on column students.teacher_student_link_id is
    'teacher_student_links.id associated with this teacher-owned local student record.';

comment on column students.student_source is
    'Origin of the local student row: manual, classio_link, or classio_linked_existing.';

