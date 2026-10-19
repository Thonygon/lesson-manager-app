// Mirrors the supported exam preparation paths in the Streamlit program builder.
export const PROGRAM_EXAM_TARGETS: Record<string, readonly string[]> = {
  english: ['sat_rw', 'ielts_academic', 'ielts_general', 'toefl_ibt'],
  spanish: ['dele'],
};

export const PROGRAM_EXAM_TARGET_LABELS: Record<string, string> = {
  sat_rw: 'Digital SAT Reading and Writing',
  ielts_academic: 'IELTS Academic',
  ielts_general: 'IELTS General Training',
  toefl_ibt: 'TOEFL iBT',
  dele: 'DELE',
};

export function programExamTargets(subject: string): readonly string[] {
  return PROGRAM_EXAM_TARGETS[subject.trim().toLowerCase()] || [];
}
