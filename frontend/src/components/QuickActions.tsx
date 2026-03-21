import React from 'react';
import { theme } from '../styles/theme';
import { quickActions, studioCapacity } from '../data/mockData';
import { MdAssignment, MdEmail, MdDescription, MdArchive } from 'react-icons/md';

const iconMap: Record<string, React.ReactNode> = {
  assignment: <MdAssignment size={24} color={theme.colors.accent} />,
  email: <MdEmail size={24} color="#d4543e" />,
  report: <MdDescription size={24} color={theme.colors.textSecondary} />,
  archive: <MdArchive size={24} color="#d4543e" />,
};

export const QuickActions: React.FC = () => {
  return (
    <div>
      <div style={styles.grid}>
        {quickActions.map((action) => (
          <button key={action.id} style={styles.actionBtn}>
            <div style={styles.iconWrap}>{iconMap[action.icon]}</div>
            <span style={styles.actionLabel}>{action.label}</span>
          </button>
        ))}
      </div>

      <div style={styles.capacityCard}>
        <span style={styles.capacityLabel}>STUDIO CAPACITY</span>
        <div style={styles.capacityValue}>
          <span style={styles.capacityCurrent}>{studioCapacity.current}</span>
          <span style={styles.capacityTotal}> / {studioCapacity.total}</span>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 10,
    marginBottom: 16,
  },
  actionBtn: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 8,
    padding: '18px 12px',
    background: theme.colors.cardBg,
    borderRadius: theme.radius.md,
    border: `1px solid ${theme.colors.border}`,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionLabel: {
    fontSize: 12,
    fontWeight: 500,
    color: theme.colors.textSecondary,
    textAlign: 'center',
  },
  capacityCard: {
    background: theme.colors.cardBg,
    borderRadius: theme.radius.md,
    padding: '16px 20px',
    border: `1px solid ${theme.colors.border}`,
  },
  capacityLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: theme.colors.muted,
    letterSpacing: '0.06em',
    marginBottom: 4,
    display: 'block',
  },
  capacityValue: {
    display: 'flex',
    alignItems: 'baseline',
  },
  capacityCurrent: {
    fontSize: 36,
    fontWeight: 700,
    color: theme.colors.text,
    fontFamily: theme.fonts.display,
  },
  capacityTotal: {
    fontSize: 18,
    color: theme.colors.muted,
    fontWeight: 500,
  },
};
