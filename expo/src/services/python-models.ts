import { requireSupabase } from '@/lib/supabase';

export type PythonAffinityScore = { score: number; run_id: string; matched: boolean; model_family: string };
export type PythonStudentScore = { scores: number[]; blend_weight: number; sample_count: number; model_version: string };
export type PythonTrainingSample = { features: Record<string, number>; target: number; label?: number; timestamp?: string; kind?: string; source?: string };

async function pythonModelRequest<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const base = process.env.EXPO_PUBLIC_CLASSIO_API_URL?.trim().replace(/\/$/, '');
  if (!base || !/^https:\/\//i.test(base)) throw new Error('Classio Python models are not configured.');
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session?.access_token) throw error ?? new Error('Your Classio session has expired.');
  const response = await fetch(`${base}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${data.session.access_token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) throw new Error(`Classio Python model request failed (${response.status}).`);
  return await response.json() as T;
}

export function getPythonAffinityModel() {
  return pythonModelRequest<{ run_id: string; winner: string; model_family: string; feature_schema_version: string }>('/v1/models/resource-affinity');
}

export function scorePythonResourceAffinity(kind: 'plan' | 'worksheet' | 'exam' | 'video', resourceId: number, context: Record<string, string>) {
  return pythonModelRequest<PythonAffinityScore>('/v1/resource-affinity/score', { kind, resource_id: resourceId, context });
}

export function scorePythonStudentCandidates(samples: PythonTrainingSample[], diagnosticSamples: PythonTrainingSample[], candidates: Record<string, number>[]) {
  return pythonModelRequest<PythonStudentScore>('/v1/student-recommendations/score', { samples, diagnostic_samples: diagnosticSamples, candidates });
}

export function getPythonProgramTopicRecommendations(programId: string, topicId: string) {
  if (!/^\d+$/.test(programId) || !/^\d+$/.test(topicId)) throw new Error('Choose a valid program topic.');
  return pythonModelRequest<{ worksheet_ranked: string[]; exam_ranked: string[]; lesson_purpose_ranked: string[]; source: string }>(`/v1/program-topics/${programId}/${topicId}/recommendations`);
}
