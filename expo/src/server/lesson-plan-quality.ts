// Source: streamlit/helpers/lesson_planner.py:_lesson_plan_quality_issues.
export function lessonPlanQualityIssues(plan: Record<string, unknown>, input: { subject: string; stage: string; level: string; purpose: string; programContext?: string }): string[] {
  const issues: string[] = [];
  const core = plan.core_material && typeof plan.core_material === 'object' && !Array.isArray(plan.core_material) ? plan.core_material as Record<string, unknown> : {};
  const count = (value: unknown) => Array.isArray(value) ? value.length : 0;
  const has = (value: unknown) => typeof value === 'string' ? Boolean(value.trim()) : Array.isArray(value) ? value.length > 0 : Boolean(value);
  const subject = input.subject.toLowerCase().replaceAll(' ', '_');
  const family = ['english', 'spanish', 'language'].includes(subject) ? 'language' : ['mathematics', 'math'].includes(subject) ? 'math' : ['science', 'music', 'study_skills'].includes(subject) ? subject : 'general';
  const signals = [plan.title, plan.objective, input.programContext].filter(Boolean).join(' ').toLowerCase();
  const reading = ['reading', 'skim', 'scan', 'passage', 'text', 'evidence', 'comprehension', 'vocabulary in context', 'craft and structure', 'expression of ideas', 'standard english conventions'].some((marker) => signals.includes(marker));
  const listening = ['listening', 'audio', 'dictation', 'listen', 'pronunciation', 'conversation'].some((marker) => signals.includes(marker));
  if (!has(plan.title)) issues.push('lesson plan needs a title');
  if (!has(plan.objective)) issues.push('lesson plan needs an objective');
  if (count(plan.success_criteria) < 2) issues.push('lesson plan needs at least 2 success_criteria');
  if (count(plan.warm_up) < 2) issues.push('lesson plan needs at least 2 warm_up items');
  if (count(plan.guided_practice) < 1) issues.push('lesson plan needs guided_practice');
  if (count(plan.practice_questions) < 2) issues.push('lesson plan needs at least 2 practice_questions');
  if (family === 'language') {
    if (count(core.target_vocabulary) < 3) issues.push('language lesson plan needs at least 3 target_vocabulary items');
    if (['introduce_concept', 'review_topic', 'diagnose_difficulty'].includes(input.purpose)) {
      if (!has(plan.reading_passage)) issues.push('reading-focused language lesson plan needs a reading_passage');
      if (!has(core.gist_questions) || !has(core.detail_questions)) issues.push('reading-focused language lesson plan needs gist_questions and detail_questions');
    }
    if (input.purpose === 'practice_skill') {
      if (listening && !has(plan.listening_script)) issues.push('practice-skill language lesson plan needs a listening_script');
      else if (reading && !has(plan.reading_passage)) issues.push('practice-skill reading lesson plan needs a reading_passage');
      else if (!has(plan.reading_passage) && !has(plan.listening_script)) issues.push('practice-skill language lesson plan needs a reading_passage or listening_script');
    }
    if (input.stage === 'lower_secondary' && input.level === 'A1' && !has(plan.reading_passage) && input.purpose !== 'practice_skill') issues.push('lower-secondary A1 language lesson plan needs readable student text support');
  } else if (family === 'math') {
    if (!has(core.worked_example)) issues.push('math lesson plan needs worked_example');
    if (!has(core.guided_problem_set)) issues.push('math lesson plan needs guided_problem_set');
  } else if (family === 'science') {
    if (!has(core.concept_explanation)) issues.push('science lesson plan needs concept_explanation');
    if (!has(core.evidence_questions)) issues.push('science lesson plan needs evidence_questions');
  } else if (family === 'music') {
    if (!has(core.technical_focus)) issues.push('music lesson plan needs technical_focus');
    if (!has(core.practice_pattern)) issues.push('music lesson plan needs practice_pattern');
    if (!has(core.performance_goal)) issues.push('music lesson plan needs performance_goal');
  } else if (family === 'study_skills') {
    if (!has(core.strategy_name)) issues.push('study skills lesson plan needs strategy_name');
    if (!has(core.strategy_steps)) issues.push('study skills lesson plan needs strategy_steps');
    if (!has(core.student_action_plan)) issues.push('study skills lesson plan needs student_action_plan');
  }
  return issues;
}
