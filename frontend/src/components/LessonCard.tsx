import React from 'react';
import { theme } from '../styles/theme';
import { Lesson } from '../data/mockData';
import { MdVideocam, MdLock, MdMoreVert } from 'react-icons/md';

interface LessonCardProps {
  lesson: Lesson;
}

export const LessonCard: React.FC<LessonCardProps> = ({ lesson }) => {
  const hasZoom = !!lesson.zoomLink;

  return (
    <div style={styles.card}>
      <div style={styles.left}>
        <div style={{ ...styles.avatar, background: lesson.color }}>
          <span style={{ fontSize: 24 }}>{lesson.avatar}</span>
        </div>
        <div style={styles.info}>
          <h4 style={styles.name}>{lesson.studentName}</h4>
          <div style={styles.meta}>
            <span style={styles.time}>
              {lesson.startTime} — {lesson.endTime}
            </span>
            <span style={styles.separator}>•</span>
            <span style={styles.subject}>{lesson.subject}</span>
          </div>
        </div>
      </div>

      <div style={styles.right}>
        {hasZoom ? (
          <button style={styles.zoomBtn}>
            <MdVideocam size={16} />
            <span>Launch Zoom</span>
          </button>
        ) : (
          <button style={styles.waitingBtn}>
            <MdLock size={14} />
            <span>Waiting...</span>
          </button>
        )}
        <button style={styles.moreBtn}>
          <MdMoreVert size={18} color={theme.colors.muted} />
        </button>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  card: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 20px',
    background: theme.colors.lessonCard,
    borderRadius: theme.radius.lg,
    border: `1px solid ${theme.colors.lessonCardBorder}`,
    transition: 'all 0.15s ease',
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  info: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  name: {
    fontSize: 15,
    fontWeight: 600,
    color: theme.colors.text,
  },
  meta: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    color: theme.colors.textSecondary,
  },
  time: {},
  separator: { opacity: 0.5 },
  subject: { fontStyle: 'italic' },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  zoomBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '8px 16px',
    background: theme.colors.zoomBg,
    color: theme.colors.zoomText,
    borderRadius: theme.radius.sm,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    border: 'none',
    transition: 'opacity 0.15s',
  },
  waitingBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '8px 16px',
    background: theme.colors.waitingBg,
    color: theme.colors.waitingText,
    borderRadius: theme.radius.sm,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'default',
    border: `1px solid ${theme.colors.border}`,
  },
  moreBtn: {
    width: 32,
    height: 32,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'transparent',
    border: 'none',
    cursor: 'pointer',
  },
};
