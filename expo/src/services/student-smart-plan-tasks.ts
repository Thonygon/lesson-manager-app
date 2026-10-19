export type SmartPlanTaskTemplate = { category: string; titleKey: string; minutes: number; xp: number };

const template = (category: string, titleKey: string, minutes: number, xp = 10): SmartPlanTaskTemplate => ({ category, titleKey, minutes, xp });

const TASKS: Record<string, SmartPlanTaskTemplate[]> = {
  english: [template('vocabulary', 'taskVocabulary', 5), template('reading', 'taskReading', 10), template('grammar', 'taskGrammar', 8), template('speaking', 'taskSpeaking', 8), template('review', 'taskReview', 5), template('quiz', 'taskChallenge', 7, 15)],
  spanish: [template('vocabulary', 'taskVocabulary', 5), template('reading', 'taskReading', 10), template('grammar', 'taskGrammar', 8), template('speaking', 'taskSpeaking', 8), template('review', 'taskReview', 5), template('quiz', 'taskChallenge', 7, 15)],
  mathematics: [template('practice', 'taskMentalMath', 5), template('quiz', 'taskProblems', 10, 15), template('review', 'taskFormula', 5), template('review', 'taskMathErrorReview', 5), template('practice', 'taskShowWork', 10, 15)],
  science: [template('vocabulary', 'taskScienceTerms', 5), template('practice', 'taskClassification', 8), template('reading', 'taskExplainConcept', 8), template('quiz', 'taskScienceQuiz', 7, 15), template('review', 'taskScienceReview', 5)],
  music: [template('vocabulary', 'taskMusicTerms', 5), template('practice', 'taskRhythm', 8), template('review', 'taskSymbols', 6), template('quiz', 'taskTheory', 7, 15), template('practice', 'taskComposerMatch', 8)],
  study_skills: [template('practice', 'taskFocus', 10), template('review', 'taskMemory', 5), template('practice', 'taskOrganize', 8), template('review', 'taskReflect', 5), template('quiz', 'taskChallenge', 7, 15)],
  other: [template('practice', 'taskFocus', 10), template('review', 'taskReview', 5), template('quiz', 'taskChallenge', 7, 15)],
};

const GOAL_CATEGORIES: Record<string, string> = {
  improve_vocabulary: 'vocabulary', improve_reading: 'reading', improve_grammar: 'grammar', improve_speaking: 'speaking',
  mental_math_fluency: 'practice', problem_solving: 'quiz', equation_confidence: 'practice', science_terminology: 'vocabulary',
  concept_understanding: 'reading', classification_skills: 'practice', music_terminology: 'vocabulary', rhythm_practice: 'practice',
  theory_review: 'review', symbol_identification: 'review', focus_and_routine: 'practice', organization_skills: 'practice',
  memory_review: 'review', reflection_and_planning: 'review', review_mistakes: 'review', exam_preparation: 'quiz',
  homework_support: 'review', general_practice: 'practice',
};

const GOAL_GROUPS: Record<string, string[]> = {
  language: ['improve_vocabulary', 'improve_reading', 'improve_grammar', 'improve_speaking', 'review_mistakes', 'exam_preparation', 'homework_support', 'general_practice'],
  math: ['mental_math_fluency', 'problem_solving', 'equation_confidence', 'review_mistakes', 'exam_preparation', 'homework_support', 'general_practice'],
  science: ['science_terminology', 'concept_understanding', 'classification_skills', 'review_mistakes', 'exam_preparation', 'homework_support', 'general_practice'],
  music: ['music_terminology', 'rhythm_practice', 'theory_review', 'symbol_identification', 'review_mistakes', 'exam_preparation', 'general_practice'],
  study_skills: ['focus_and_routine', 'organization_skills', 'memory_review', 'reflection_and_planning', 'homework_support', 'general_practice'],
};

export function smartPlanGoalOptions(subject: string): string[] {
  const group = subject === 'english' || subject === 'spanish' ? 'language'
    : subject === 'mathematics' ? 'math'
      : subject === 'science' || subject === 'music' || subject === 'study_skills' ? subject : '';
  return group ? GOAL_GROUPS[group] : [...new Set(Object.values(GOAL_GROUPS).flat())];
}

/** Port of Streamlit's goal-first template ordering and 3/4/5 daily task budget. */
export function selectSmartPlanTaskTemplates(subject: string, goal: string, dailyMinutes: number): SmartPlanTaskTemplate[] {
  const templates = TASKS[subject] ?? TASKS.other;
  const category = GOAL_CATEGORIES[goal] ?? 'practice';
  const preferred = templates.filter((item) => item.category === category);
  const others = templates.filter((item) => item.category !== category);
  const count = dailyMinutes <= 15 ? 3 : dailyMinutes <= 30 ? 4 : 5;
  const selected = [...preferred, ...others].slice(0, count).map((item) => ({ ...item }));
  const total = selected.reduce((sum, item) => sum + item.minutes, 0);
  if (selected.length && total < dailyMinutes) selected[selected.length - 1].minutes += Math.min(10, dailyMinutes - total);
  return selected;
}

export function localSmartPlanDay(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** Mirrors Streamlit's task XP, completion bonus, and day-level streak transitions. */
export function syncSmartPlanRewards(
  current: { points: number; streak: number; lastCompletionDate?: string },
  oldTasks: { id: string; xp: number; done: boolean }[],
  newTasks: { id: string; xp: number; done: boolean }[],
  day = localSmartPlanDay(),
): { points: number; streak: number; lastCompletionDate: string } {
  const oldDone = new Map(oldTasks.map((task) => [task.id, task.done]));
  const earned = newTasks.reduce((sum, task) => sum + (task.done === Boolean(oldDone.get(task.id)) ? 0 : task.done ? task.xp : -task.xp), 0);
  let points = Math.max(0, current.points + earned);
  let streak = current.streak;
  let lastCompletionDate = current.lastCompletionDate || '';
  const wasComplete = oldTasks.length > 0 && oldTasks.every((task) => task.done);
  const isComplete = newTasks.length > 0 && newTasks.every((task) => task.done);
  if (isComplete && !wasComplete) {
    points += 20;
    const yesterday = new Date(`${day}T12:00:00`);
    yesterday.setDate(yesterday.getDate() - 1);
    if (lastCompletionDate === localSmartPlanDay(yesterday)) streak = Math.max(1, streak + 1);
    else if (lastCompletionDate !== day) streak = 1;
    lastCompletionDate = day;
  } else if (!isComplete && wasComplete) {
    points = Math.max(0, points - 20);
    if (lastCompletionDate === day) { lastCompletionDate = ''; streak = Math.max(0, streak - 1); }
  }
  return { points, streak, lastCompletionDate };
}

export function smartPlanWeeklyFocus(goal: string): string[] {
  return [goal, goal === 'review_mistakes' ? 'general_practice' : 'review_mistakes', goal === 'general_practice' ? 'exam_preparation' : 'general_practice', 'exam_preparation', 'review_mistakes'];
}
