import { createClient } from '@supabase/supabase-js';

const noStore = { 'Cache-Control': 'private, no-store', Vary: 'Authorization' };
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: noStore });
const objectMeta = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const safeCodes = (value: unknown, pattern: RegExp, limit: number) => Array.isArray(value)
  ? value.filter((item): item is string => typeof item === 'string' && pattern.test(item)).slice(0, limit) : [];

export async function GET(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to view AI intelligence.' }, 401);

  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publishableKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publishableKey) return json({ error: 'The protected platform-data service is not configured.' }, 503);

  try {
    const publicClient = createClient(url, publishableKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your Classio session has expired.' }, 401);
    if (!serverKey) return json({ error: 'The protected platform-data service is not configured.' }, 503);

    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: profile, error: profileError } = await server.from('profiles').select('role').eq('user_id', identity.user.id).limit(1).maybeSingle();
    if (profileError) throw profileError;
    if (profile?.role !== 'admin') return json({ error: 'Admin access is required.' }, 403);

    // Python EIC owns the telemetry summary; this Worker only reads small evidence lists.
    const [experiments, runs, jobs, validated, exposures, operations, approvals, modelReviews] = await Promise.all([
      server.from('ml_experiments').select('experiment_id,name,is_active,updated_at').order('updated_at', { ascending: false }).limit(20),
      server.from('ml_experiment_runs').select('run_id,experiment_id,run_status,integrity_status,evidence_verdict,maturity_verdict,operational_use,source_row_count,included_row_count,source_start_at,source_end_at,code_version,teachers_represented,students_represented,resources_represented,created_at').order('created_at', { ascending: false }).limit(24),
      server.from('system_jobs').select('job_id,job_type,status,progress_pct,current_stage,error_code,created_at').order('created_at', { ascending: false }).limit(24),
      server.from('ml_experiment_runs').select('run_id,experiment_id,run_status,integrity_status,evidence_verdict,maturity_verdict,operational_use,primary_metric_leader,source_row_count,included_row_count,source_start_at,source_end_at,code_version,teachers_represented,students_represented,resources_represented,completed_at,human_review_recommended_model_name,human_reviewed_at,human_reviewed_by').eq('is_current_validated_run', true).order('completed_at', { ascending: false }).limit(10),
      server.from('resource_exposures').select('exposure_id,resource_id,resource_type,exposure_type,surface,position,shown_at,model_component_id,model_version,heuristic_score,learned_score,final_score,context_json').order('shown_at', { ascending: false }).limit(40),
      server.from('classio_ai_operations').select('operation_id,source,feature_name,modality,status,started_at,finished_at,error_kind').order('started_at', { ascending: false }).limit(20),
      server.from('classio_ai_runtime_approvals').select('surface,provider,model,prompt_version,status,reviewed_by,reviewed_at').order('reviewed_at', { ascending: false }).limit(30),
      server.from('classio_model_card_reviews').select('component_id,model_version,status,reviewed_by,reviewed_at,review_reason').order('reviewed_at', { ascending: false }).limit(100),
    ]);
    const exposureIds = (exposures.data || []).map((row) => row.exposure_id);
    const operationIds = (operations.data || []).map((row) => row.operation_id);
    const validatedIds = (validated.data || []).map((row) => row.run_id);
    const [exposureEvents, relevance, intents, attempts, modelResults, usageTraces] = await Promise.all([
      exposureIds.length ? server.from('resource_exposure_events').select('exposure_id,event_type,event_at').in('exposure_id', exposureIds).order('event_at', { ascending: false }).limit(160) : Promise.resolve({ data: [], error: null }),
      exposureIds.length ? server.from('classio_teacher_relevance_feedback_events').select('exposure_id,action,reason,created_at').in('exposure_id', exposureIds).order('created_at', { ascending: false }).limit(80) : Promise.resolve({ data: [], error: null }),
      operationIds.length ? server.from('classio_generation_intent_feedback').select('generation_id,operation_id,feedback_surface,satisfied,reason,prompt_version,model_name,resource_type,resource_id,answered_at').in('operation_id', operationIds) : Promise.resolve({ data: [], error: null }),
      operationIds.length ? server.from('classio_provider_attempts').select('operation_id,attempt_no,provider,model_requested,status').in('operation_id', operationIds).order('attempt_no', { ascending: true }).limit(60) : Promise.resolve({ data: [], error: null }),
      validatedIds.length ? server.from('ml_run_models').select('run_id,model_name,execution_status,parameters_json,holdout_metrics_json').in('run_id', validatedIds).limit(40) : Promise.resolve({ data: [], error: null }),
      operationIds.length ? server.from('ai_usage_logs').select('meta_json').in('meta_json->>operation_id', operationIds).limit(40) : Promise.resolve({ data: [], error: null }),
    ]);
    const recommendationDecisions = (exposures.data || []).map((row) => {
      const context = row.context_json && typeof row.context_json === 'object' ? row.context_json as Record<string, unknown> : {};
      return { id: row.exposure_id, type: 'recommendation', surface: row.surface, resource: `${row.resource_type}:${row.resource_id}`, shown_at: row.shown_at,
        model_component_id: row.model_component_id, model_version: row.model_version, position: row.position, heuristic_score: row.heuristic_score,
        learned_score: row.learned_score, final_score: row.final_score,
        displayed_candidates: safeCodes(context.displayed_candidates, /^(?:worksheet|exam|video|plan|program|topic|objective):[a-z0-9_-]{1,80}$/i, 12),
        reason_codes: safeCodes(context.reason_codes, /^[a-z][a-z0-9_]{0,79}$/i, 4),
        explanation_version: typeof context.explanation_version === 'string' ? context.explanation_version : '',
        events: (exposureEvents.data || []).filter((event) => event.exposure_id === row.exposure_id).map((event) => ({ type: event.event_type, at: event.event_at })),
        feedback: (relevance.data || []).filter((event) => event.exposure_id === row.exposure_id).map((event) => ({ action: event.action, reason: event.reason, at: event.created_at })) };
    });
    const generationDecisions = (operations.data || []).map((row) => {
      const feedback = (intents.data || []).find((item) => item.operation_id === row.operation_id);
      const trace = (usageTraces.data || []).map((item) => objectMeta(item.meta_json)).find((meta) => meta.operation_id === row.operation_id);
      return { id: row.operation_id, type: 'generation', surface: row.source, feature_name: row.feature_name, modality: row.modality,
        status: row.status, shown_at: row.started_at, finished_at: row.finished_at, error_kind: row.error_kind,
        prompt_version: typeof trace?.prompt_version === 'string' ? trace.prompt_version : feedback?.prompt_version || '', model_name: typeof trace?.model === 'string' ? trace.model : feedback?.model_name || '', resource: feedback?.resource_type && feedback?.resource_id ? `${feedback.resource_type}:${feedback.resource_id}` : '',
        feedback: feedback?.answered_at ? { satisfied: feedback.satisfied, reason: feedback.reason, surface: feedback.feedback_surface, at: feedback.answered_at } : null,
        attempts: (attempts.data || []).filter((attempt) => attempt.operation_id === row.operation_id).map((attempt) => ({ provider: attempt.provider, model: attempt.model_requested, status: attempt.status })) };
    });
    const errors = [
      experiments.error?.message, runs.error?.message, jobs.error?.message, validated.error?.message, exposures.error?.message, operations.error?.message, approvals.error?.message, modelReviews.error?.message,
      exposureEvents.error?.message, relevance.error?.message, intents.error?.message, attempts.error?.message, modelResults.error?.message, usageTraces.error?.message,
    ].filter(Boolean);
    return json({
      contentCounts: {},
      experiments: experiments.data || [],
      recentRuns: runs.data || [],
      recentJobs: jobs.data || [],
      validatedRuns: validated.data || [],
      runtimeApprovals: approvals.data || [],
      modelReviews: modelReviews.data || [],
      modelResults: modelResults.data || [],
      recommendationDecisions,
      generationDecisions,
      warnings: errors,
      generatedAt: new Date().toISOString(),
    });
  } catch (reason) {
    console.error('Admin AI snapshot failed', reason);
    return json({ error: 'AI intelligence could not be loaded.' }, 502);
  }
}
