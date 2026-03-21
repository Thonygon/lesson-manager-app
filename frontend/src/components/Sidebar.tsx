import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { theme } from '../styles/theme';
import {
  MdDashboard,
  MdPeople,
  MdCalendarToday,
  MdPayments,
  MdSearch,
  MdAdd,
  MdHelpOutline,
  MdSettings,
} from 'react-icons/md';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: MdDashboard },
  { path: '/students', label: 'Students', icon: MdPeople },
  { path: '/lessons', label: 'Lessons', icon: MdCalendarToday },
  { path: '/payments', label: 'Payments', icon: MdPayments },
  { path: '/search', label: 'Search', icon: MdSearch },
];

export const Sidebar: React.FC = () => {
  const location = useLocation();

  return (
    <aside style={styles.sidebar}>
      <div style={styles.brand}>
        <h1 style={styles.brandTitle}>The Curated Studio</h1>
        <p style={styles.brandSub}>Private Educator</p>
      </div>

      <nav style={styles.nav}>
        {navItems.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path || 
            (path === '/lessons' && location.pathname === '/');
          return (
            <NavLink key={path} to={path} style={{ textDecoration: 'none' }}>
              <div
                style={{
                  ...styles.navItem,
                  ...(isActive ? styles.navItemActive : {}),
                }}
              >
                <Icon
                  size={20}
                  color={isActive ? theme.colors.sidebarActiveText : theme.colors.sidebarText}
                />
                <span
                  style={{
                    ...styles.navLabel,
                    color: isActive ? theme.colors.sidebarActiveText : theme.colors.sidebarText,
                    fontWeight: isActive ? 600 : 400,
                  }}
                >
                  {label}
                </span>
              </div>
            </NavLink>
          );
        })}
      </nav>

      <div style={styles.bottom}>
        <button style={styles.newLessonBtn}>
          <MdAdd size={20} />
          <span>New Lesson</span>
        </button>

        <div style={styles.bottomLinks}>
          <button style={styles.bottomLink}>
            <MdHelpOutline size={18} color={theme.colors.sidebarText} />
            <span>Help</span>
          </button>
          <button style={styles.bottomLink}>
            <MdSettings size={18} color={theme.colors.sidebarText} />
            <span>Settings</span>
          </button>
        </div>
      </div>
    </aside>
  );
};

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: 220,
    minHeight: '100vh',
    background: theme.colors.sidebarBg,
    display: 'flex',
    flexDirection: 'column',
    padding: '24px 0',
    borderRight: `1px solid ${theme.colors.border}`,
    position: 'fixed',
    left: 0,
    top: 0,
    bottom: 0,
    zIndex: 100,
  },
  brand: {
    padding: '0 24px',
    marginBottom: 36,
  },
  brandTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: theme.colors.text,
    fontFamily: theme.fonts.display,
    letterSpacing: '-0.01em',
  },
  brandSub: {
    fontSize: 12,
    color: theme.colors.muted,
    marginTop: 2,
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    padding: '0 12px',
    flex: 1,
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '10px 12px',
    borderRadius: theme.radius.md,
    transition: 'all 0.15s ease',
    cursor: 'pointer',
  },
  navItemActive: {
    background: theme.colors.sidebarActive,
  },
  navLabel: {
    fontSize: 14,
    color: theme.colors.sidebarText,
  },
  bottom: {
    padding: '0 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  newLessonBtn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: '12px 16px',
    background: theme.colors.primary,
    color: '#ffffff',
    borderRadius: theme.radius.md,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    border: 'none',
    transition: 'background 0.15s ease',
  },
  bottomLinks: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  bottomLink: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 12px',
    fontSize: 13,
    color: theme.colors.sidebarText,
    cursor: 'pointer',
    border: 'none',
    background: 'none',
    borderRadius: theme.radius.sm,
  },
};
