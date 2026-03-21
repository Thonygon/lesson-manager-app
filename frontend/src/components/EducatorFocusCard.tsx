import React from 'react';
import { theme } from '../styles/theme';
import { educatorFocus } from '../data/mockData';

export const EducatorFocusCard: React.FC = () => {
  return (
    <div style={styles.card}>
      <div style={styles.badge}>EDUCATOR FOCUS</div>
      <h3 style={styles.title}>{educatorFocus.title}</h3>
      <p style={styles.desc}>{educatorFocus.description}</p>

      <div style={styles.progressSection}>
        <div style={styles.progressHeader}>
          <span style={styles.progressLabel}>Review Progress</span>
          <span style={styles.progressValue}>{educatorFocus.reviewProgress}%</span>
        </div>
        <div style={styles.progressTrack}>
          <div
            style={{
              ...styles.progressFill,
              width: `${educatorFocus.reviewProgress}%`,
            }}
          />
        </div>
      </div>

      <button style={styles.portalBtn}>Open Feedback Portal</button>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: theme.colors.focusCardBg,
    borderRadius: theme.radius.lg,
    padding: '24px',
  },
  badge: {
    display: 'inline-block',
    padding: '4px 10px',
    background: '#d4543e',
    color: '#ffffff',
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: '0.08em',
    borderRadius: theme.radius.sm,
    marginBottom: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: theme.colors.focusCardText,
    fontFamily: theme.fonts.display,
    marginBottom: 10,
    lineHeight: 1.3,
  },
  desc: {
    fontSize: 13,
    color: '#5a4a3a',
    lineHeight: 1.5,
    marginBottom: 20,
  },
  progressSection: {
    marginBottom: 20,
  },
  progressHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  progressLabel: {
    fontSize: 12,
    fontWeight: 600,
    color: theme.colors.focusCardText,
  },
  progressValue: {
    fontSize: 12,
    fontWeight: 700,
    color: theme.colors.focusCardText,
  },
  progressTrack: {
    width: '100%',
    height: 8,
    background: 'rgba(0, 0, 0, 0.08)',
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    background: theme.colors.focusCardProgress,
    borderRadius: 4,
    transition: 'width 0.5s ease',
  },
  portalBtn: {
    width: '100%',
    padding: '12px',
    background: 'transparent',
    border: `1.5px solid ${theme.colors.focusCardText}`,
    borderRadius: theme.radius.md,
    color: theme.colors.focusCardText,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
};
