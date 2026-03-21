import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, spacing, radius } from '../styles/theme';
import { weekSchedule } from '../data/mockData';

export const WeeklySchedule: React.FC = () => {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Schedule</Text>
        <TouchableOpacity style={styles.monthSelector}>
          <Text style={styles.monthText}>October ▾</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.days}>
        {weekSchedule.map((day) => (
          <TouchableOpacity
            key={day.day}
            style={[styles.dayItem, day.isToday && styles.dayActive]}
            activeOpacity={0.7}
          >
            <Text
              style={[
                styles.dayLabel,
                day.isToday && styles.dayLabelActive,
              ]}
            >
              {day.day}
            </Text>
            <Text
              style={[
                styles.dayNum,
                day.isToday && styles.dayNumActive,
              ]}
            >
              {day.date}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.xl,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  monthSelector: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
  },
  monthText: {
    fontSize: 14,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  days: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  dayItem: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderRadius: radius.lg,
    gap: spacing.xs,
  },
  dayActive: {
    backgroundColor: colors.scheduleDayActive,
  },
  dayLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.muted,
    letterSpacing: 0.5,
  },
  dayLabelActive: {
    color: colors.scheduleDayActiveText,
    opacity: 0.8,
  },
  dayNum: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
  },
  dayNumActive: {
    color: colors.scheduleDayActiveText,
  },
});
