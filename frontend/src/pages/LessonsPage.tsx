import React from 'react';
import { theme } from '../styles/theme';
import { TopBar } from '../components/TopBar';
import { WeeklySchedule } from '../components/WeeklySchedule';
import { LessonCard } from '../components/LessonCard';
import { EducatorFocusCard } from '../components/EducatorFocusCard';
import { QuickActions } from '../components/QuickActions';
import { todayLessons } from '../data/mockData';

export const LessonsPage: React.FC = () => {
  return (
    <div style={styles.page}>
      <TopBar title="Lessons & Calendar" />

      <div style={styles.content}>
        <div style={styles.mainCol}>
          <WeeklySchedule />

          <div style={styles.todaySection}>
            <div style={styles.todayHeader}>
              <h3 style={styles.todayTitle}>Today's Lessons</h3>
              <span style={styles.todayCount}>
                {todayLessons.length} Sessions Remaining
              </span>
            </div>

            <div style={styles.lessonList}>
              {todayLessons.map((lesson) => (
                <LessonCard key={lesson.id} lesson={lesson} />
              ))}
            </div>
          </div>
        </div>

        <div style={styles.sideCol}>
          <EducatorFocusCard />
          <QuickActions />
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  page: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    minHeight: '100vh',
  },
  content: {
    display: 'flex',
    gap: 24,
    padding: '24px 32px',
    flex: 1,
  },
  mainCol: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
  },
  todaySection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  },
  todayHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  todayTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: theme.colors.text,
  },
  todayCount: {
    fontSize: 13,
    color: theme.colors.muted,
  },
  lessonList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  sideCol: {
    width: 300,
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    flexShrink: 0,
  },
};
