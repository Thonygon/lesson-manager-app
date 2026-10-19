type ProgressAnswer = { exerciseType: string; isCorrect: boolean };
export type ExerciseProgress = { exerciseType: string; attempted: number; correct: number; xp: number };

function roundHalfEven(value: number): number {
  const lower = Math.floor(value);
  const fraction = value - lower;
  if (Math.abs(fraction - 0.5) < 1e-10) return lower % 2 === 0 ? lower : lower + 1;
  return Math.round(value);
}

export function practiceAccuracyPct(correct: number, attempted: number): number {
  return attempted > 0 ? roundHalfEven(correct / attempted * 1000) / 10 : 0;
}

/** Session scores are whole percentages in Streamlit; progress accuracy keeps one decimal. */
export function practiceSessionScorePct(correct: number, total: number): number {
  return total > 0 ? roundHalfEven(correct / total * 100) : 0;
}

/** Matches Streamlit's per-question progress counts and correct-answer XP split. */
export function aggregatePracticeProgress(rows: ProgressAnswer[], xpEarned: number): ExerciseProgress[] {
  const groups = new Map<string, ExerciseProgress>();
  for (const row of rows) {
    const group = groups.get(row.exerciseType) ?? { exerciseType: row.exerciseType, attempted: 0, correct: 0, xp: 0 };
    group.attempted += 1;
    group.correct += Number(row.isCorrect);
    groups.set(row.exerciseType, group);
  }
  const values = [...groups.values()];
  const totalCorrect = values.reduce((sum, group) => sum + group.correct, 0);
  for (const group of values) group.xp = xpEarned && totalCorrect
    ? roundHalfEven(xpEarned * group.correct / totalCorrect)
    : xpEarned && values.length ? roundHalfEven(xpEarned / values.length) : 0;
  return values;
}
