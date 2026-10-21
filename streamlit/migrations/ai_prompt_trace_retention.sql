-- Generation usage metadata is technical prompt trace, retained for 90 days.
-- It must not contain the prompt text or free-form student data.
create extension if not exists pg_cron with schema extensions;
select cron.schedule(
    'classio-ai-prompt-trace-90d',
    '15 3 * * *',
    $$delete from public.ai_usage_logs
      where feature_name in ('quick_lesson_ai', 'quick_worksheet_ai',
                             'quick_exam_ai', 'learning_program_ai')
        and created_at < now() - interval '90 days'$$
);
