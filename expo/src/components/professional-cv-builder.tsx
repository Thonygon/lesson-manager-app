import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button, Disclosure, Field, Panel } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { downloadResourcePdf } from '@/services/document-exports';
import { buildTemplateCv, saveTemplateCv, type CvLocale, type TemplateCvInput } from '@/services/professional-cv';
import { colors } from '@/theme';

const COPY = {
  en: { title: 'Create a CV', help: 'Build a teacher CV from your details. This template does not use AI.', name: 'Full name', email: 'Email', phone: 'Phone', location: 'Country or location', subjects: 'Subjects, separated by commas', stages: 'Teaching stages, separated by commas', languages: 'Teaching languages, separated by commas', summary: 'Professional summary (optional)', education: 'Education, one item per line', certifications: 'Certifications, separated by commas', experience: 'Experience, one item per line', skills: 'Skills, separated by commas', availability: 'Availability', rate: 'Rate', role: 'Role', teacher: 'Teacher', tutor: 'Tutor', create: 'Create and save CV', creating: 'Saving CV…', saved: 'CV saved to your library.', required: 'Enter your name, location, subjects, teaching stages, and teaching languages.', download: 'Download PDF' },
  es: { title: 'Crear un CV', help: 'Crea un CV docente con tus datos. Esta plantilla no usa IA.', name: 'Nombre completo', email: 'Correo', phone: 'Teléfono', location: 'País o ubicación', subjects: 'Asignaturas, separadas por comas', stages: 'Etapas educativas, separadas por comas', languages: 'Idiomas de enseñanza, separados por comas', summary: 'Resumen profesional (opcional)', education: 'Formación, un elemento por línea', certifications: 'Certificaciones, separadas por comas', experience: 'Experiencia, un elemento por línea', skills: 'Habilidades, separadas por comas', availability: 'Disponibilidad', rate: 'Tarifa', role: 'Función', teacher: 'Docente', tutor: 'Tutor', create: 'Crear y guardar CV', creating: 'Guardando CV…', saved: 'CV guardado en tu biblioteca.', required: 'Introduce nombre, ubicación, asignaturas, etapas e idiomas de enseñanza.', download: 'Descargar PDF' },
  tr: { title: 'Özgeçmiş oluştur', help: 'Bilgilerinizle öğretmen özgeçmişi hazırlayın. Bu şablon yapay zekâ kullanmaz.', name: 'Ad soyad', email: 'E-posta', phone: 'Telefon', location: 'Ülke veya konum', subjects: 'Dersler, virgülle ayırın', stages: 'Öğretim düzeyleri, virgülle ayırın', languages: 'Öğretim dilleri, virgülle ayırın', summary: 'Mesleki özet (isteğe bağlı)', education: 'Eğitim, satır başına bir öğe', certifications: 'Sertifikalar, virgülle ayırın', experience: 'Deneyim, satır başına bir öğe', skills: 'Beceriler, virgülle ayırın', availability: 'Uygunluk', rate: 'Ücret', role: 'Rol', teacher: 'Öğretmen', tutor: 'Özel öğretmen', create: 'Özgeçmiş oluştur ve kaydet', creating: 'Özgeçmiş kaydediliyor…', saved: 'Özgeçmiş kitaplığınıza kaydedildi.', required: 'Ad, konum, dersler, öğretim düzeyleri ve dilleri girin.', download: 'PDF indir' },
} as const;

const EMPTY: TemplateCvInput = { fullName: '', email: '', phone: '', location: '', role: 'teacher', subjects: '', teachingStages: '', teachingLanguages: '', summary: '', education: '', certifications: '', experience: '', skills: '', availability: '', rate: '' };

export function ProfessionalCvBuilder({ onSaved }: { onSaved: () => Promise<void> }) {
  const { language } = useAppPreferences();
  const locale: CvLocale = language === 'es' || language === 'tr' ? language : 'en';
  const copy = COPY[locale];
  const [input, setInput] = useState<TemplateCvInput>(EMPTY);
  const [document, setDocument] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const change = (key: keyof TemplateCvInput, value: string) => setInput((current) => ({ ...current, [key]: value }));
  const fields: { key: keyof TemplateCvInput; label: string; multiline?: boolean }[] = [
    { key: 'fullName', label: copy.name }, { key: 'email', label: copy.email }, { key: 'phone', label: copy.phone },
    { key: 'location', label: copy.location }, { key: 'subjects', label: copy.subjects },
    { key: 'teachingStages', label: copy.stages }, { key: 'teachingLanguages', label: copy.languages },
    { key: 'summary', label: copy.summary, multiline: true }, { key: 'education', label: copy.education, multiline: true },
    { key: 'certifications', label: copy.certifications }, { key: 'experience', label: copy.experience, multiline: true },
    { key: 'skills', label: copy.skills }, { key: 'availability', label: copy.availability }, { key: 'rate', label: copy.rate },
  ];
  const create = async () => {
    if (![input.fullName, input.location, input.subjects, input.teachingStages, input.teachingLanguages].every((value) => value.trim())) { setMessage(copy.required); return; }
    setBusy(true); setMessage('');
    try {
      const next = buildTemplateCv(input, locale);
      await saveTemplateCv(next);
      setDocument(next); setMessage(copy.saved); await onSaved();
    } catch (error) { setMessage(error instanceof Error ? error.message : copy.required); }
    finally { setBusy(false); }
  };

  return <Disclosure title={copy.title} summary={copy.help}><Panel style={styles.panel}>
    <Text style={styles.help}>{copy.help}</Text>
    <Text style={styles.label}>{copy.role}</Text>
    <View style={styles.roles}><Button secondary={input.role !== 'teacher'} onPress={() => change('role', 'teacher')}>{copy.teacher}</Button><Button secondary={input.role !== 'tutor'} onPress={() => change('role', 'tutor')}>{copy.tutor}</Button></View>
    <View style={styles.fields}>{fields.map((field) => <View key={field.key} style={styles.field}><Text style={styles.label}>{field.label}</Text><Field value={input[field.key]} onChangeText={(value) => change(field.key, value)} multiline={field.multiline} numberOfLines={field.multiline ? 3 : 1} style={field.multiline ? styles.multiline : undefined} /></View>)}</View>
    {message ? <Text style={styles.message}>{message}</Text> : null}
    <View style={styles.actions}><Button disabled={busy} onPress={() => void create()}>{busy ? copy.creating : copy.create}</Button>{document ? <Button secondary onPress={() => void downloadResourcePdf(String(document.title), document, locale)}>{copy.download}</Button> : null}</View>
  </Panel></Disclosure>;
}

const styles = StyleSheet.create({ panel: { gap: 10 }, help: { color: colors.muted, fontSize: 12, lineHeight: 18 }, label: { color: colors.ink, fontSize: 11, fontWeight: '800', marginBottom: 4 }, roles: { flexDirection: 'row', gap: 8 }, fields: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, field: { flexGrow: 1, minWidth: 240, width: '46%' }, multiline: { minHeight: 76, textAlignVertical: 'top' }, message: { color: colors.primary, fontSize: 12 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 } });
