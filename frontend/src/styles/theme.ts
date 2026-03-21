export const theme = {
  colors: {
    // Primary backgrounds
    bg1: '#0f1c1a',
    bg2: '#142220',
    bg3: '#1a2d2a',
    bgCard: '#1b2926',
    
    // Panels
    panel: 'rgba(22, 38, 34, 0.95)',
    panelSoft: '#1e3330',
    panelHover: '#243d39',
    
    // Text
    text: '#f0ede6',
    textSecondary: '#a8b5a0',
    muted: '#6b7a6e',
    
    // Borders
    border: 'rgba(255, 255, 255, 0.06)',
    borderStrong: 'rgba(255, 255, 255, 0.12)',
    
    // Accent colors
    accent: '#c8a45c',       // Gold/amber
    accentLight: '#dbb978',
    accentMuted: 'rgba(200, 164, 92, 0.15)',
    
    primary: '#4a9e8e',      // Teal
    primaryLight: '#5bbdaa',
    
    success: '#34D399',
    warning: '#FBBF24',
    danger: '#F87171',
    
    // Sidebar
    sidebarBg: '#0d1815',
    sidebarActive: 'rgba(200, 164, 92, 0.12)',
    sidebarText: '#a8b5a0',
    sidebarActiveText: '#c8a45c',
    
    // Cards
    cardBg: '#192b27',
    cardBgHover: '#1e3430',
    lessonCard: '#283b2e',
    lessonCardBorder: 'rgba(168, 181, 160, 0.1)',
    
    // Schedule
    scheduleBg: '#0f1c1a',
    scheduleDayBg: '#192b27',
    scheduleDayActive: '#c8a45c',
    scheduleDayActiveText: '#0f1c1a',
    scheduleDot: '#c8a45c',
    
    // Buttons
    btnPrimary: '#4a9e8e',
    btnPrimaryHover: '#5bbdaa',
    btnSecondary: '#283b2e',
    btnDanger: '#F87171',
    
    // Focus card
    focusCardBg: '#f5f0e8',
    focusCardText: '#2c1810',
    focusCardLabel: '#8b5e34',
    focusCardProgress: '#4a9e8e',
    
    // Zoom button
    zoomBg: '#4a9e8e',
    zoomText: '#ffffff',
    waitingBg: 'rgba(255, 255, 255, 0.08)',
    waitingText: '#a8b5a0',
  },
  
  shadows: {
    sm: '0 2px 8px rgba(0, 0, 0, 0.25)',
    md: '0 8px 24px rgba(0, 0, 0, 0.3)',
    lg: '0 16px 48px rgba(0, 0, 0, 0.4)',
  },
  
  radius: {
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '20px',
    full: '9999px',
  },
  
  fonts: {
    sans: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    display: "'Playfair Display', Georgia, serif",
  },
};

export type Theme = typeof theme;
