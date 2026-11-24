import { StyleSheet, Text, View } from 'react-native';

import { Button, Panel } from '@/components/ui';
import type { ClassioRecord } from '@/services/classio-data';
import { downloadStudentPackageReport } from '@/services/document-exports';
import { studentPackageReports } from '@/services/student-package-reports';
import { colors } from '@/theme';

export function PackageReportDownloads({ studentName, lessons, payments, locale }: { studentName: string; lessons: ClassioRecord[]; payments: ClassioRecord[]; locale: 'en' | 'es' | 'tr' }) {
  const copy = {
    en: { title: 'Reports by package', help: 'Each report includes this package, its lessons, totals, and balance. Lessons are assigned by package start date.', pdf: 'Download PDF', word: 'Download Word', units: 'units', starts: 'Starts' },
    es: { title: 'Informes por paquete', help: 'Cada informe incluye el paquete, sus clases, totales y saldo. Las clases se asignan según la fecha de inicio del paquete.', pdf: 'Descargar PDF', word: 'Descargar Word', units: 'unidades', starts: 'Inicio' },
    tr: { title: 'Pakete göre raporlar', help: 'Her rapor paketi, derslerini, toplamları ve bakiyeyi içerir. Dersler paket başlangıç tarihine göre eşleştirilir.', pdf: 'PDF indir', word: 'Word indir', units: 'birim', starts: 'Başlangıç' },
  }[locale];
  const reports = studentPackageReports(payments, lessons).reverse();
  if (!reports.length) return null;
  return <Panel style={styles.panel}><Text style={styles.title}>{copy.title}</Text><Text style={styles.help}>{copy.help}</Text>
    {reports.map(({ payment, lessons: packageLessons, balance }) => <View key={String(payment.id)} style={styles.row}>
      <View style={styles.copy}><Text style={styles.name}>{balance.subject} · {balance.modality}</Text><Text style={styles.meta}>{copy.starts}: {balance.startDate} · {balance.purchased} {copy.units}</Text></View>
      <View style={styles.actions}><Button secondary onPress={() => void downloadStudentPackageReport(studentName, payment, packageLessons, locale, balance, 'pdf')}>{copy.pdf}</Button><Button secondary onPress={() => void downloadStudentPackageReport(studentName, payment, packageLessons, locale, balance, 'docx')}>{copy.word}</Button></View>
    </View>)}
  </Panel>;
}

const styles = StyleSheet.create({
  panel: { marginTop: 12, gap: 8 },
  title: { color: colors.ink, fontSize: 17, fontWeight: '900' },
  help: { color: colors.muted, fontSize: 11, lineHeight: 17 },
  row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingVertical: 12, borderTopWidth: 1, borderTopColor: colors.line },
  copy: { flexGrow: 1, minWidth: 180 },
  name: { color: colors.ink, fontSize: 12, fontWeight: '800' },
  meta: { color: colors.muted, fontSize: 10, marginTop: 3 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
});
