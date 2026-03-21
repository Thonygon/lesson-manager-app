import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { colors, spacing, radius, shadows } from '../styles/theme';
import { Header } from '../components/Header';
import { students } from '../data/mockData';

export const PaymentsScreen: React.FC = () => {
  const payments = students.map((s, i) => ({
    ...s,
    amount: [250, 180, 320, 150, 200, 275][i],
    units: [10, 8, 12, 6, 8, 10][i],
    usedUnits: [6, 4, 8, 2, 5, 7][i],
  }));

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Header title="Payments" />

        <View style={[styles.summaryCard, shadows.md]}>
          <Text style={styles.summaryLabel}>Monthly Revenue</Text>
          <Text style={styles.summaryValue}>$4,280</Text>
          <Text style={styles.summaryMeta}>↑ 12% from last month</Text>
        </View>

        <Text style={styles.sectionTitle}>ACTIVE PACKAGES</Text>

        {payments.map((p) => (
          <View key={p.id} style={[styles.card, shadows.sm]}>
            <View style={styles.cardTop}>
              <View style={styles.cardLeft}>
                <View style={[styles.avatar, { backgroundColor: p.color }]}>
                  <Text style={styles.avatarText}>{p.avatar}</Text>
                </View>
                <View>
                  <Text style={styles.name}>{p.name}</Text>
                  <Text style={styles.meta}>
                    {p.usedUnits}/{p.units} sessions
                  </Text>
                </View>
              </View>
              <Text style={styles.amount}>${p.amount}</Text>
            </View>
            <View style={styles.progressTrack}>
              <View
                style={[
                  styles.progressFill,
                  { width: `${(p.usedUnits / p.units) * 100}%` },
                ]}
              />
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
  summaryCard: {
    backgroundColor: colors.primary, borderRadius: radius.xl,
    padding: spacing.xxl, marginBottom: spacing.xl,
  },
  summaryLabel: { fontSize: 12, fontWeight: '600', color: 'rgba(255,255,255,0.7)', letterSpacing: 0.5 },
  summaryValue: { fontSize: 36, fontWeight: '700', color: '#ffffff', marginVertical: 4 },
  summaryMeta: { fontSize: 13, color: 'rgba(255,255,255,0.6)' },
  sectionTitle: {
    fontSize: 12, fontWeight: '700', color: colors.muted,
    letterSpacing: 1.5, marginBottom: spacing.lg,
  },
  card: {
    backgroundColor: colors.bgCard, borderRadius: radius.lg,
    padding: spacing.lg, marginBottom: spacing.sm,
  },
  cardTop: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: spacing.md,
  },
  cardLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  avatar: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 18 },
  name: { fontSize: 14, fontWeight: '600', color: colors.text },
  meta: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  amount: { fontSize: 18, fontWeight: '700', color: colors.accent },
  progressTrack: { height: 4, backgroundColor: colors.bgMuted, borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: colors.primary, borderRadius: 2 },
});
