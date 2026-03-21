import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { colors, spacing, radius, shadows } from '../styles/theme';
import { Header } from '../components/Header';
import { students } from '../data/mockData';

export const DashboardScreen: React.FC = () => {
  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Header title="Dashboard" />

        <View style={styles.statsRow}>
          <View style={[styles.statCard, shadows.sm]}>
            <Text style={styles.statValue}>6</Text>
            <Text style={styles.statLabel}>Active Students</Text>
          </View>
          <View style={[styles.statCard, shadows.sm]}>
            <Text style={styles.statValue}>142</Text>
            <Text style={styles.statLabel}>Total Lessons</Text>
          </View>
        </View>

        <View style={styles.statsRow}>
          <View style={[styles.statCard, shadows.sm]}>
            <Text style={styles.statValue}>$4.2K</Text>
            <Text style={styles.statLabel}>Revenue</Text>
          </View>
          <View style={[styles.statCard, shadows.sm]}>
            <Text style={styles.statValue}>94%</Text>
            <Text style={styles.statLabel}>Completion</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>STUDENT OVERVIEW</Text>

        {students.map((student) => (
          <View key={student.id} style={[styles.studentCard, shadows.sm]}>
            <View style={[styles.avatar, { backgroundColor: student.color }]}>
              <Text style={styles.avatarText}>{student.avatar}</Text>
            </View>
            <View style={styles.studentInfo}>
              <Text style={styles.studentName}>{student.name}</Text>
              <Text style={styles.studentMeta}>Active • 4 sessions left</Text>
            </View>
          </View>
        ))}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: spacing.xl, paddingTop: spacing.md, paddingBottom: 100 },
  statsRow: { flexDirection: 'row', gap: spacing.md, marginBottom: spacing.md },
  statCard: {
    flex: 1, backgroundColor: colors.bgCard, borderRadius: radius.xl,
    padding: spacing.xl, alignItems: 'center',
  },
  statValue: { fontSize: 28, fontWeight: '700', color: colors.text, marginBottom: 4 },
  statLabel: { fontSize: 12, fontWeight: '500', color: colors.muted },
  sectionTitle: {
    fontSize: 12, fontWeight: '700', color: colors.muted,
    letterSpacing: 1.5, marginTop: spacing.xl, marginBottom: spacing.lg,
  },
  studentCard: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    backgroundColor: colors.bgCard, borderRadius: radius.lg,
    padding: spacing.lg, marginBottom: spacing.sm,
  },
  avatar: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 18 },
  studentInfo: { flex: 1 },
  studentName: { fontSize: 15, fontWeight: '600', color: colors.text },
  studentMeta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
});
