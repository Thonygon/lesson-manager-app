import React from 'react';
import { theme } from '../styles/theme';
import { TopBar } from '../components/TopBar';
import { students } from '../data/mockData';
import { MdAdd, MdSearch, MdMoreVert } from 'react-icons/md';

export const StudentsPage: React.FC = () => {
  return (
    <div style={styles.page}>
      <TopBar title="Students" />
      <div style={styles.content}>
        <div style={styles.toolbar}>
          <div style={styles.searchBox}>
            <MdSearch size={18} color={theme.colors.muted} />
            <input type="text" placeholder="Search students..." style={styles.searchInput} />
          </div>
          <button style={styles.addBtn}>
            <MdAdd size={18} />
            <span>Add Student</span>
          </button>
        </div>

        <div style={styles.list}>
          {students.map((student) => (
            <div key={student.id} style={styles.card}>
              <div style={styles.cardLeft}>
                <div style={{ ...styles.avatar, background: student.color }}>
                  <span style={{ fontSize: 22 }}>{student.avatar}</span>
                </div>
                <div>
                  <h4 style={styles.name}>{student.name}</h4>
                  <p style={styles.meta}>Active • Next session: Today at 10:00 AM</p>
                </div>
              </div>
              <div style={styles.cardRight}>
                <div style={styles.badge}>4 sessions left</div>
                <button style={styles.moreBtn}>
                  <MdMoreVert size={18} color={theme.colors.muted} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  page: { flex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' },
  content: { padding: '24px 32px', display: 'flex', flexDirection: 'column', gap: 20 },
  toolbar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  searchBox: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '10px 16px',
    background: theme.colors.panelSoft,
    borderRadius: theme.radius.full,
    border: `1px solid ${theme.colors.border}`,
  },
  searchInput: { background: 'none', border: 'none', outline: 'none', fontSize: 14, color: theme.colors.text, width: 240 },
  addBtn: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '10px 20px',
    background: theme.colors.primary,
    color: '#fff',
    borderRadius: theme.radius.md,
    fontSize: 14, fontWeight: 600,
  },
  list: { display: 'flex', flexDirection: 'column', gap: 10 },
  card: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px',
    background: theme.colors.cardBg,
    borderRadius: theme.radius.lg,
    border: `1px solid ${theme.colors.border}`,
  },
  cardLeft: { display: 'flex', alignItems: 'center', gap: 14 },
  avatar: { width: 48, height: 48, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  name: { fontSize: 15, fontWeight: 600, color: theme.colors.text },
  meta: { fontSize: 13, color: theme.colors.textSecondary, marginTop: 2 },
  cardRight: { display: 'flex', alignItems: 'center', gap: 12 },
  badge: {
    padding: '4px 12px',
    background: theme.colors.accentMuted,
    color: theme.colors.accent,
    borderRadius: theme.radius.full,
    fontSize: 12, fontWeight: 600,
  },
  moreBtn: {
    width: 32, height: 32, borderRadius: '50%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'transparent',
  },
};
