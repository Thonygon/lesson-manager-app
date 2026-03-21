import React from 'react';
import { theme } from '../styles/theme';
import { weekSchedule } from '../data/mockData';
import { MdChevronLeft, MdChevronRight } from 'react-icons/md';

export const WeeklySchedule: React.FC = () => {
  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={styles.title}>Weekly Schedule</h3>
        <div style={styles.arrows}>
          <button style={styles.arrowBtn}>
            <MdChevronLeft size={22} color={theme.colors.textSecondary} />
          </button>
          <button style={styles.arrowBtn}>
            <MdChevronRight size={22} color={theme.colors.textSecondary} />
          </button>
        </div>
      </div>

      <div style={styles.days}>
        {weekSchedule.map((day) => (
          <div
            key={day.day}
            style={{
              ...styles.dayItem,
              ...(day.isToday ? styles.dayActive : {}),
            }}
          >
            <span
              style={{
                ...styles.dayLabel,
                color: day.isToday ? theme.colors.scheduleDayActiveText : theme.colors.muted,
              }}
            >
              {day.day}
            </span>
            <span
              style={{
                ...styles.dayNum,
                color: day.isToday ? theme.colors.scheduleDayActiveText : theme.colors.text,
              }}
            >
              {day.date}
            </span>
            {day.dotCount > 0 && (
              <div style={styles.dots}>
                {Array.from({ length: Math.min(day.dotCount, 3) }).map((_, i) => (
                  <span
                    key={i}
                    style={{
                      ...styles.dot,
                      background: day.isToday
                        ? theme.colors.scheduleDayActiveText
                        : theme.colors.scheduleDot,
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: theme.colors.scheduleBg,
    borderRadius: theme.radius.lg,
    padding: '20px 24px',
    border: `1px solid ${theme.colors.border}`,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  title: {
    fontSize: 16,
    fontWeight: 600,
    color: theme.colors.text,
  },
  arrows: {
    display: 'flex',
    gap: 4,
  },
  arrowBtn: {
    width: 32,
    height: 32,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: theme.colors.panelSoft,
    border: `1px solid ${theme.colors.border}`,
    cursor: 'pointer',
  },
  days: {
    display: 'flex',
    gap: 8,
    justifyContent: 'space-between',
  },
  dayItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 6,
    padding: '12px 16px',
    borderRadius: theme.radius.md,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    minWidth: 56,
  },
  dayActive: {
    background: theme.colors.scheduleDayActive,
  },
  dayLabel: {
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: '0.05em',
  },
  dayNum: {
    fontSize: 18,
    fontWeight: 600,
  },
  dots: {
    display: 'flex',
    gap: 3,
    marginTop: 2,
  },
  dot: {
    width: 5,
    height: 5,
    borderRadius: '50%',
  },
};
