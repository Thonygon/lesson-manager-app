import React from 'react';
import { theme } from '../styles/theme';
import { TopBar } from '../components/TopBar';
import { students } from '../data/mockData';

export const DashboardPage: React.FC = () => {
  const activeStudents = students.length;
  const totalLessons = 142;
  const monthlyRevenue = '$4,280';

  return (
    <div style={styles.page}>
      <TopBar title="Dashboard" />
      <div style={styles.content}>
        <div style={styles.statsGrid}>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Active Students</span>
            <span style={styles.statValue}>{activeStudents}</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Total Lessons</span>
            <span style={styles.statValue}>{totalLessons}</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Monthly Revenue</span>
            <span style={styles.statValue}>{monthlyRevenue}</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Completion Rate</span>
            <span style={styles.statValue}>94%</span>
          </div>
        </div>

        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Student Status Overview</h3>
          <div style={styles.studentGrid}>
            {students.map((student) => (
              <div key={student.id} style={styles.studentCard}>
                <div style={{ ...styles.studentAvatar, background: student.color }}>
                  <span style={{ fontSize: 20 }}>{student.avatar}</span>
                </div>
                <div>
                  <p style={styles.studentName}>{student.name}</p>
                  <p style={styles.studentStatus}>Active • 4 sessions left</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  page: { flex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' },
  content: { padding: '24px 32px', display: 'flex', flexDirection: 'column', gap: 28 },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 },
  statCard: {
    background: theme.colors.cardBg,
    borderRadius: theme.radius.lg,
    padding: '24px',
    border: `1px solid ${theme.colors.border}`,
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  statLabel: { fontSize: 12, fontWeight: 600, color: theme.colors.muted, letterSpacing: '0.04em', textTransform: 'uppercase' as const },
  statValue: { fontSize: 32, fontWeight: 700, color: theme.colors.text, fontFamily: theme.fonts.display },
  section: {},
  sectionTitle: { fontSize: 18, fontWeight: 700, color: theme.colors.text, marginBottom: 16 },
  studentGrid: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 },
  studentCard: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
    padding: '16px 20px',
    background: theme.colors.cardBg,
    borderRadius: theme.radius.md,
    border: `1px solid ${theme.colors.border}`,
  },
  studentAvatar: {
    width: 44,
    height: 44,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  studentName: { fontSize: 14, fontWeight: 600, color: theme.colors.text },
  studentStatus: { fontSize: 12, color: theme.colors.textSecondary, marginTop: 2 },
};
