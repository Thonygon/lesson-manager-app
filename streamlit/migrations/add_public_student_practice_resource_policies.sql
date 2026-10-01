-- Browser-hosted student practice needs the same public resource visibility
-- that Streamlit receives through its trusted backend.

alter table if exists public.worksheets enable row level security;
alter table if exists public.quick_exams enable row level security;

drop policy if exists "Worksheets read own or public" on public.worksheets;
create policy "Worksheets read own or public"
on public.worksheets
for select
using (auth.uid() = user_id or is_public = true);

drop policy if exists "Quick exams read own or public" on public.quick_exams;
create policy "Quick exams read own or public"
on public.quick_exams
for select
using (auth.uid()::text = user_id or is_public = true);
