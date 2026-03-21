import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { colors, spacing } from '../styles/theme';
import { Header } from '../components/Header';
import { UpcomingFocus } from '../components/UpcomingFocus';
import { WeeklySchedule } from '../components/WeeklySchedule';
import { LessonCard } from '../components/LessonCard';
import { todayLessons } from '../data/mockData';

export const LessonsScreen: React.FC = () => {
  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Header title="The Curated Studio" />
        <UpcomingFocus />
        <WeeklySchedule />

        <View style={styles.todaySection}>
          <Text style={styles.todayTitle}>TODAY'S SESSIONS</Text>
          {todayLessons.map((lesson, index) => (
            <LessonCard key={lesson.id} lesson={lesson} isFirst={index === 0} />
          ))}
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: 100,
  },
  todaySection: {
    marginTop: spacing.sm,
  },
  todayTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.muted,
    letterSpacing: 1.5,
    marginBottom: spacing.lg,
  },
});
