import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, spacing, radius } from '../styles/theme';
import { upcomingFocus } from '../data/mockData';

export const UpcomingFocus: React.FC = () => {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Upcoming Focus</Text>
        <Text style={styles.headerAction}>PRIORITY</Text>
      </View>

      <TouchableOpacity activeOpacity={0.8} style={styles.card}>
        <View style={styles.cardTop}>
          <View>
            <Text style={styles.label}>{upcomingFocus.label}</Text>
            <Text style={styles.title}>{upcomingFocus.title}</Text>
          </View>
          <Text style={styles.sparkle}>✦</Text>
        </View>

        <View style={styles.timerRow}>
          <Text style={styles.timerIcon}>⏱</Text>
          <Text style={styles.timerText}>{upcomingFocus.startsIn}</Text>
        </View>

        <View style={styles.progressTrack}>
          <View
            style={[
              styles.progressFill,
              { width: `${upcomingFocus.preparationComplete}%` },
            ]}
          />
        </View>
        <Text style={styles.progressLabel}>
          {upcomingFocus.preparationComplete}% PREPARATION COMPLETE
        </Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.lg,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  headerAction: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.accent,
    letterSpacing: 0.8,
  },
  card: {
    backgroundColor: colors.focusBg,
    borderRadius: radius.xl,
    padding: spacing.xl,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
  },
  label: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.accent,
    letterSpacing: 1,
    marginBottom: 4,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.focusText,
    lineHeight: 28,
  },
  sparkle: {
    fontSize: 24,
    color: colors.accent,
  },
  timerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: spacing.lg,
  },
  timerIcon: {
    fontSize: 14,
  },
  timerText: {
    fontSize: 13,
    color: colors.focusText,
    opacity: 0.7,
  },
  progressTrack: {
    height: 6,
    backgroundColor: 'rgba(0, 0, 0, 0.08)',
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: spacing.sm,
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 3,
  },
  progressLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.primary,
    letterSpacing: 0.5,
  },
});
