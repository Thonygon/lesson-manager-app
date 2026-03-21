import React from 'react';
import { theme } from '../styles/theme';
import { TopBar } from '../components/TopBar';
import { students } from '../data/mockData';

export const PaymentsPage: React.FC = () => {
  const payments = students.map((s, i) => ({
    id: s.id,
    studentName: s.name,
    avatar: s.avatar,
    color: s.color,
    amount: [250, 180, 320, 150, 200, 275][i],
    currency: 'USD',
    units: [10, 8, 12, 6, 8, 10][i],
    usedUnits: [6, 4, 8, 2, 5, 7][i],
    expiryDate: '2026-05-15',
  }));

  return (
    <div style={styles.page}>
      <TopBar title="Payments" />
      <div style={styles.content}>
        <div style={styles.summary}>
          <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}>Total Revenue (Month)</span>
            <span style={styles.summaryValue}>$4,280</span>
          </div>
          <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}>Outstanding Balance</span>
            <span style={styles.summaryValue}>$680</span>
          </div>
          <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}>Active Packages</span>
            <span style={styles.summaryValue}>{payments.length}</span>
          </div>
        </div>

        <div style={styles.list}>
          {payments.map((p) => (
            <div key={p.id} style={styles.card}>
              <div style={styles.cardLeft}>
                <div style={{ ...styles.avatar, background: p.color }}>
                  <span style={{ fontSize: 20 }}>{p.avatar}</span>
                </div>
                <div>
                  <h4 style={styles.name}>{p.studentName}</h4>
                  <p style={styles.meta}>
                    {p.usedUnits}/{p.units} sessions used • Expires {p.expiryDate}
                  </p>
                </div>
              </div>
              <div style={styles.cardRight}>
                <span style={styles.amount}>${p.amount}</span>
                <div style={styles.progressTrack}>
                  <div style={{ ...styles.progressFill, width: `${(p.usedUnits / p.units) * 100}%` }} />
                </div>
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
  content: { padding: '24px 32px', display: 'flex', flexDirection: 'column', gap: 24 },
  summary: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 },
  summaryCard: {
    background: theme.colors.cardBg, borderRadius: theme.radius.lg,
    padding: '24px', border: `1px solid ${theme.colors.border}`,
    display: 'flex', flexDirection: 'column', gap: 8,
  },
  summaryLabel: { fontSize: 12, fontWeight: 600, color: theme.colors.muted, textTransform: 'uppercase' as const, letterSpacing: '0.04em' },
  summaryValue: { fontSize: 28, fontWeight: 700, color: theme.colors.text, fontFamily: theme.fonts.display },
  list: { display: 'flex', flexDirection: 'column', gap: 10 },
  card: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px',
    background: theme.colors.cardBg, borderRadius: theme.radius.lg,
    border: `1px solid ${theme.colors.border}`,
  },
  cardLeft: { display: 'flex', alignItems: 'center', gap: 14 },
  avatar: { width: 44, height: 44, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  name: { fontSize: 14, fontWeight: 600, color: theme.colors.text },
  meta: { fontSize: 12, color: theme.colors.textSecondary, marginTop: 2 },
  cardRight: { display: 'flex', alignItems: 'center', gap: 16 },
  amount: { fontSize: 18, fontWeight: 700, color: theme.colors.accent, fontFamily: theme.fonts.display },
  progressTrack: { width: 80, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3 },
  progressFill: { height: '100%', background: theme.colors.primary, borderRadius: 3 },
};
