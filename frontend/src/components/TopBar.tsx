import React from 'react';
import { theme } from '../styles/theme';
import { MdSearch, MdAdd, MdNotifications, MdSettings } from 'react-icons/md';

interface TopBarProps {
  title: string;
}

export const TopBar: React.FC<TopBarProps> = ({ title }) => {
  return (
    <header style={styles.header}>
      <h2 style={styles.title}>{title}</h2>

      <div style={styles.actions}>
        <div style={styles.searchBox}>
          <MdSearch size={18} color={theme.colors.muted} />
          <input
            type="text"
            placeholder="Search lessons..."
            style={styles.searchInput}
          />
        </div>

        <button style={styles.iconBtn}>
          <MdAdd size={20} color={theme.colors.textSecondary} />
        </button>
        <button style={styles.iconBtn}>
          <MdNotifications size={20} color={theme.colors.textSecondary} />
        </button>
        <button style={styles.iconBtn}>
          <MdSettings size={20} color={theme.colors.textSecondary} />
        </button>
        <div style={styles.avatar}>
          <span style={{ fontSize: 18 }}>👤</span>
        </div>
      </div>
    </header>
  );
};

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 32px',
    borderBottom: `1px solid ${theme.colors.border}`,
    background: theme.colors.bg2,
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: theme.colors.text,
    fontFamily: theme.fonts.display,
  },
  actions: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  searchBox: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 16px',
    background: theme.colors.panelSoft,
    borderRadius: theme.radius.full,
    border: `1px solid ${theme.colors.border}`,
    marginRight: 8,
  },
  searchInput: {
    background: 'none',
    border: 'none',
    outline: 'none',
    fontSize: 13,
    color: theme.colors.text,
    width: 160,
  },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'transparent',
    border: 'none',
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: '50%',
    background: theme.colors.accent,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 4,
  },
};
