import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Disclosure, Field, Panel } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { downloadResourcePdf } from '@/services/document-exports';
import { buildTemplateCv, CV_COUNTRIES, profileCvDefaults, saveTemplateCv, type CvLocale, type TemplateCvInput } from '@/services/professional-cv';
import { getProfileWorkspace } from '@/services/profile';
import { colors } from '@/theme';

const COPY = {
  en: { title: 'Create a CV', help: 'Build a teacher CV from your details. This template does not use AI.', name: 'Full name', email: 'Email', phone: 'Phone', location: 'Country', subjects: 'Subjects, separated by commas', stages: 'Teaching stages, separated by commas', languages: 'Teaching languages, separated by commas', summary: 'Professional summary (optional)', education: 'Education, one item per line', certifications: 'Certifications, separated by commas', experience: 'Experience, one item per line', skills: 'Skills, separated by commas', availability: 'Availability', rate: 'Rate', role: 'Role', teacher: 'Teacher', tutor: 'Tutor', create: 'Create and save CV', creating: 'Saving CV…', saved: 'CV saved to your library.', required: 'Enter your name, country, subjects, teaching stages, and teaching languages.', invalidCountry: 'Choose a valid country from the suggestions.', invalidPhone: 'Use at least six digits and only digits, +, ( and ) for the phone number.', download: 'PDF' },
  es: { title: 'Crear un CV', help: 'Crea un CV docente con tus datos. Esta plantilla no usa IA.', name: 'Nombre completo', email: 'Correo', phone: 'Teléfono', location: 'País', subjects: 'Asignaturas, separadas por comas', stages: 'Etapas educativas, separadas por comas', languages: 'Idiomas de enseñanza, separados por comas', summary: 'Resumen profesional (opcional)', education: 'Formación, un elemento por línea', certifications: 'Certificaciones, separadas por comas', experience: 'Experiencia, un elemento por línea', skills: 'Habilidades, separadas por comas', availability: 'Disponibilidad', rate: 'Tarifa', role: 'Función', teacher: 'Docente', tutor: 'Tutor', create: 'Crear y guardar CV', creating: 'Guardando CV…', saved: 'CV guardado en tu biblioteca.', required: 'Introduce nombre, país, asignaturas, etapas e idiomas de enseñanza.', invalidCountry: 'Elige un país válido de las sugerencias.', invalidPhone: 'Usa al menos seis dígitos y solo números, +, ( y ) para el teléfono.', download: 'PDF' },
  tr: { title: 'Özgeçmiş oluştur', help: 'Bilgilerinizle öğretmen özgeçmişi hazırlayın. Bu şablon yapay zekâ kullanmaz.', name: 'Ad soyad', email: 'E-posta', phone: 'Telefon', location: 'Ülke', subjects: 'Dersler, virgülle ayırın', stages: 'Öğretim düzeyleri, virgülle ayırın', languages: 'Öğretim dilleri, virgülle ayırın', summary: 'Mesleki özet (isteğe bağlı)', education: 'Eğitim, satır başına bir öğe', certifications: 'Sertifikalar, virgülle ayırın', experience: 'Deneyim, satır başına bir öğe', skills: 'Beceriler, virgülle ayırın', availability: 'Uygunluk', rate: 'Ücret', role: 'Rol', teacher: 'Öğretmen', tutor: 'Özel öğretmen', create: 'Özgeçmiş oluştur ve kaydet', creating: 'Özgeçmiş kaydediliyor…', saved: 'Özgeçmiş kitaplığınıza kaydedildi.', required: 'Ad, ülke, dersler, öğretim düzeyleri ve dilleri girin.', invalidCountry: 'Önerilerden geçerli bir ülke seçin.', invalidPhone: 'Telefon için en az altı rakam ve yalnızca rakam, +, ( ve ) kullanın.', download: 'PDF' },
} as const;

const EMPTY: TemplateCvInput = { fullName: '', email: '', phone: '', location: '', role: 'teacher', subjects: '', teachingStages: '', teachingLanguages: '', summary: '', education: '', certifications: '', experience: '', skills: '', availability: '', rate: '' };

export function ProfessionalCvBuilder({ onSaved }: { onSaved: () => Promise<void> }) {
  const { language } = useAppPreferences();
  const locale: CvLocale = language === 'es' || language === 'tr' ? language : 'en';
  const copy = COPY[locale];
  const [input, setInput] = useState<TemplateCvInput>(EMPTY);
  const [document, setDocument] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error');
  useEffect(() => { let active = true; void getProfileWorkspace().then((profile) => { if (!active) return; const defaults = profileCvDefaults(profile); setInput((current) => { if (current === EMPTY) return { ...EMPTY, ...defaults }; const next = { ...current }; for (const [key, value] of Object.entries(defaults) as [keyof TemplateCvInput, string][]) if (!next[key] && value) Object.assign(next, { [key]: value }); return next; }); }).catch(() => {}); return () => { active = false; }; }, []);
  const change = (key: keyof TemplateCvInput, value: string) => setInput((current) => ({ ...current, [key]: value }));
  const countryMatches = input.location.trim() && !CV_COUNTRIES.includes(input.location.trim()) ? CV_COUNTRIES.filter((country) => country.toLocaleLowerCase().includes(input.location.trim().toLocaleLowerCase())).slice(0, 8) : [];
  const fields: { key: keyof TemplateCvInput; label: string; multiline?: boolean }[] = [
    { key: 'fullName', label: copy.name }, { key: 'email', label: copy.email }, { key: 'phone', label: copy.phone },
    { key: 'subjects', label: copy.subjects },
    { key: 'teachingStages', label: copy.stages }, { key: 'teachingLanguages', label: copy.languages },
    { key: 'summary', label: copy.summary, multiline: true }, { key: 'education', label: copy.education, multiline: true },
    { key: 'certifications', label: copy.certifications }, { key: 'experience', label: copy.experience, multiline: true },
    { key: 'skills', label: copy.skills }, { key: 'availability', label: copy.availability }, { key: 'rate', label: copy.rate },
  ];
  const create = async () => {
    if (![input.fullName, input.location, input.subjects, input.teachingStages, input.teachingLanguages].every((value) => value.trim())) { setMessageTone('error'); setMessage(copy.required); return; }
    setBusy(true); setMessage('');
    try {
      const next = buildTemplateCv(input, locale);
      await saveTemplateCv(next);
      setDocument(next); await onSaved(); setMessageTone('success'); setMessage(copy.saved);
    } catch (error) { setMessageTone('error'); const detail = error instanceof Error ? error.message : ''; setMessage(detail === 'Choose a valid country.' ? copy.invalidCountry : detail.startsWith('Enter a phone number') ? copy.invalidPhone : detail || copy.required); }
    finally { setBusy(false); }
  };

  return <Disclosure title={copy.title} summary={copy.help}><Panel style={styles.panel}>
    <Text style={styles.help}>{copy.help}</Text>
    <Text style={styles.label}>{copy.role}</Text>
    <View style={styles.roles}><Button secondary={input.role !== 'teacher'} onPress={() => change('role', 'teacher')}>{copy.teacher}</Button><Button secondary={input.role !== 'tutor'} onPress={() => change('role', 'tutor')}>{copy.tutor}</Button></View>
    <View style={styles.field}><Text style={styles.label}>{copy.location}</Text><Field value={input.location} onChangeText={(value) => change('location', value)} placeholder={copy.location} />{countryMatches.length ? <View style={styles.suggestions}>{countryMatches.map((country) => <Pressable accessibilityRole="button" key={country} onPress={() => change('location', country)} style={styles.suggestion}><Text style={styles.suggestionText}>{country}</Text></Pressable>)}</View> : null}</View>
    <View style={styles.fields}>{fields.map((field) => <View key={field.key} style={styles.field}><Text style={styles.label}>{field.label}</Text><Field value={input[field.key]} onChangeText={(value) => change(field.key, value)} multiline={field.multiline} numberOfLines={field.multiline ? 3 : 1} style={field.multiline ? styles.multiline : undefined} /></View>)}</View>

    <View style={styles.actions}><Button disabled={busy} onPress={() => void create()}>{busy ? copy.creating : copy.create}</Button>{document ? <Button secondary onPress={() => void downloadResourcePdf(String(document.title), document, locale)}>{copy.download}</Button> : null}</View><ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} />
  </Panel></Disclosure>;
}

const styles = StyleSheet.create({ panel: { gap: 10 }, help: { color: colors.muted, fontSize: 12, lineHeight: 18 }, label: { color: colors.ink, fontSize: 11, fontWeight: '800', marginBottom: 4 }, roles: { flexDirection: 'row', gap: 8 }, fields: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, field: { flexGrow: 1, minWidth: 240, width: '46%' }, suggestions: { borderWidth: 1, borderColor: colors.line, borderRadius: 12, backgroundColor: colors.surface, marginTop: 4, overflow: 'hidden' }, suggestion: { paddingHorizontal: 14, paddingVertical: 9 }, suggestionText: { color: colors.ink, fontSize: 13 }, multiline: { minHeight: 76, textAlignVertical: 'top' }, message: { color: colors.primary, fontSize: 12 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 } });
