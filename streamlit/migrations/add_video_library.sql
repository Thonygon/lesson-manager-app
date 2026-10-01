create table if not exists videos (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    video_id text not null,
    youtube_url text not null default '',
    thumbnail_url text not null default '',
    title text not null default '',
    description text not null default '',
    subject text not null default '',
    custom_subject_name text not null default '',
    learner_stage text not null default '',
    level_or_band text not null default '',
    topic text not null default '',
    is_public boolean not null default false,
    status text not null default 'active' check (status in ('active', 'archived')),
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint videos_owner_video_unique unique (user_id, video_id)
);

create index if not exists idx_videos_user_updated_at
    on videos(user_id, updated_at desc);
create index if not exists idx_videos_public_updated_at
    on videos(is_public, updated_at desc);
create index if not exists idx_videos_subject_stage_level
    on videos(subject, learner_stage, level_or_band);

drop trigger if exists trg_videos_updated_at on videos;
create trigger trg_videos_updated_at
before update on videos
for each row execute function classio_set_updated_at();

create table if not exists learning_program_topic_videos (
    id bigint generated always as identity primary key,
    teacher_id uuid not null references auth.users(id) on delete cascade,
    program_id bigint not null references learning_programs(id) on delete cascade,
    topic_id bigint not null references learning_program_topics(id) on delete cascade,
    video_id bigint not null references videos(id) on delete cascade,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint learning_program_topic_videos_unique unique (teacher_id, program_id, topic_id, video_id)
);

create index if not exists idx_learning_program_topic_videos_program_topic
    on learning_program_topic_videos(program_id, topic_id, created_at asc);
create index if not exists idx_learning_program_topic_videos_video
    on learning_program_topic_videos(video_id);

drop trigger if exists trg_learning_program_topic_videos_updated_at on learning_program_topic_videos;
create trigger trg_learning_program_topic_videos_updated_at
before update on learning_program_topic_videos
for each row execute function classio_set_updated_at();

alter table if exists teacher_assignments
    drop constraint if exists teacher_assignments_assignment_type_check;
alter table if exists teacher_assignments
    add constraint teacher_assignments_assignment_type_check
    check (assignment_type in ('worksheet', 'exam', 'lesson_plan_topic', 'video'));

alter table if exists teacher_assignments
    drop constraint if exists teacher_assignments_source_type_check;
alter table if exists teacher_assignments
    add constraint teacher_assignments_source_type_check
    check (source_type in ('worksheet_builder', 'exam_builder', 'lesson_plan_builder', 'video_library'));

alter table videos enable row level security;
alter table learning_program_topic_videos enable row level security;

drop policy if exists "Videos read own or public" on videos;
create policy "Videos read own or public"
on videos
for select
using (auth.uid() = user_id or is_public = true);

drop policy if exists "Videos manage own" on videos;
create policy "Videos manage own"
on videos
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "Program topic videos read linked" on learning_program_topic_videos;
create policy "Program topic videos read linked"
on learning_program_topic_videos
for select
using (auth.uid() = teacher_id or exists (
    select 1
    from learning_program_assignments lpa
    where lpa.program_id = learning_program_topic_videos.program_id
      and lpa.student_user_id = auth.uid()::text
));

drop policy if exists "Program topic videos manage own" on learning_program_topic_videos;
create policy "Program topic videos manage own"
on learning_program_topic_videos
for all
using (auth.uid() = teacher_id)
with check (auth.uid() = teacher_id);
