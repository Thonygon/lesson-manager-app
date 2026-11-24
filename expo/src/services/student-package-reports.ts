import type { ClassioRecord } from '@/services/classio-data';

export type StudentPackageReport = {
  payment: ClassioRecord;
  lessons: ClassioRecord[];
  balance: { subject: string; modality: string; purchased: number; delivered: number; remaining: number; startDate: string; expiryDate: string };
};

const day = (value: unknown) => String(value || '').slice(0, 10);
const packageStart = (row: ClassioRecord) => day(row.package_start_date || row.payment_date);
const units = (value: unknown) => Math.max(0, Math.trunc(Number(value) || 0));
const countable = (row: ClassioRecord) => !['[FREE]', '[DEMO]', '[DONT COUNT]', "[DON'T COUNT]"].some((tag) => String(row.note || '').toUpperCase().includes(tag));

// Match classio_recalculate_teacher_packages: a new package starts a new date
// window, even when the previous package has unused units or a manual expiry.
export function studentPackageReports(payments: ClassioRecord[], lessons: ClassioRecord[]): StudentPackageReport[] {
  const ordered = [...payments].sort((a, b) => packageStart(a).localeCompare(packageStart(b))
    || day(a.payment_date).localeCompare(day(b.payment_date))
    || Number(a.id || 0) - Number(b.id || 0));
  return ordered.map((payment, index) => {
    const startDate = packageStart(payment);
    const nextStart = ordered[index + 1] ? packageStart(ordered[index + 1]) : '';
    const matchingLessons = lessons.filter((lesson) => {
      const lessonDay = day(lesson.lesson_date);
      return !!startDate && !!lessonDay && lessonDay >= startDate && (!nextStart || lessonDay < nextStart);
    });
    const purchased = Math.max(0, units(payment.number_of_lesson) + Math.trunc(Number(payment.lesson_adjustment_units) || 0));
    const delivered = matchingLessons.filter(countable).reduce((sum, lesson) => sum + units(lesson.number_of_lesson), 0);
    return { payment, lessons: matchingLessons, balance: {
      subject: String(payment.subject_custom || payment.subject || ''), modality: String(payment.modality || ''),
      purchased, delivered, remaining: purchased - delivered, startDate,
      expiryDate: day(payment.package_expiry_date),
    } };
  });
}
