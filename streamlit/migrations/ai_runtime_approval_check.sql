-- Let a generation surface verify one exact release without exposing the
-- staff approval ledger or requiring a service key in a legacy Streamlit app.
create or replace function public.classio_is_ai_runtime_approved(
    p_surface text, p_provider text, p_model text, p_prompt_version text
) returns boolean language sql stable security definer set search_path = '' as $$
    select exists (
        select 1 from public.classio_ai_runtime_approvals a
        where a.surface = p_surface and a.provider = p_provider
          and a.model = p_model and a.prompt_version = p_prompt_version
          and a.status = 'approved'
    );
$$;
revoke all on function public.classio_is_ai_runtime_approved(text,text,text,text) from public;
grant execute on function public.classio_is_ai_runtime_approved(text,text,text,text) to anon, authenticated, service_role;
