import React, { useState } from 'react';
import { theme } from '../styles/theme';
import { TopBar } from '../components/TopBar';
import { MdSearch } from 'react-icons/md';
import { students, todayLessons } from '../data/mockData';

export const SearchPage: React.FC = () => {
  const [query, setQuery] = useState('');

  const filteredStudents = students.filter((s) =>
    s.name.toLowerCase().includes(query.toLowerCase())
  );
  const filteredLessons = todayLessons.filter(
    (l) =>
      l.studentName.toLowerCase().includes(query.toLowerCase()) ||
      l.subject.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div style={styles.page}>
      <TopBar title="Search" />
      <div style={styles.content}>
        <div style={styles.searchBox}>
          <MdSearch size={22} color={theme.colors.muted} />
          <input
            type="text"
            placeholder="Search students, lessons, or subjects..."
            style={styles.searchInput}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {query && (
          <>
            {filteredStudents.length > 0 && (
              <div style={styles.section}>
                <h4 style={styles.sectionTitle}>Students</h4>
                {filteredStudents.map((s) => (
                  <div key={s.id} style={styles.resultCard}>
                    <div style={{ ...styles.avatar, background: s.color }}>
                      <span style={{ fontSize: 18 }}>{s.avatar}</span>
                    </div>
                    <span style={styles.resultName}>{s.name}</span>
                  </div>
                ))}
              </div>
            )}
            {filteredLessons.length > 0 && (
              <div style={styles.section}>
                <h4 style={styles.sectionTitle}>Lessons</h4>
                {filteredLessons.map((l) => (
                  <div key={l.id} style={styles.resultCard}>
                    <div style={{ ...styles.avatar, background: l.color }}>
                      <span style={{ fontSize: 18 }}>{l.avatar}</span>
                    </div>
                    <div>
                      <span style={styles.resultName}>{l.studentName}</span>
                      <p style={styles.resultMeta}>{l.subject} • {l.startTime}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {filteredStudents.length === 0 && filteredLessons.length === 0 && (
              <p style={styles.noResults}>No results found for "{query}"</p>
            )}
          </>
        )}

        {!query && (
          <div style={styles.placeholder}>
            <MdSearch size={48} color={theme.colors.border} />
            <p style={styles.placeholderText}>
              Start typing to search across students, lessons, and subjects
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  page: { flex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' },
  content: { padding: '24px 32px', display: 'flex', flexDirection: 'column', gap: 24 },
  searchBox: {
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '14px 20px',
    background: theme.colors.panelSoft,
    borderRadius: theme.radius.lg,
    border: `1px solid ${theme.colors.borderStrong}`,
  },
  searchInput: { background: 'none', border: 'none', outline: 'none', fontSize: 16, color: theme.colors.text, flex: 1 },
  section: { display: 'flex', flexDirection: 'column', gap: 8 },
  sectionTitle: { fontSize: 12, fontWeight: 600, color: theme.colors.muted, textTransform: 'uppercase' as const, letterSpacing: '0.06em', marginBottom: 4 },
  resultCard: {
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '12px 16px',
    background: theme.colors.cardBg, borderRadius: theme.radius.md,
    border: `1px solid ${theme.colors.border}`,
  },
  avatar: { width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  resultName: { fontSize: 14, fontWeight: 500, color: theme.colors.text },
  resultMeta: { fontSize: 12, color: theme.colors.textSecondary, marginTop: 2 },
  noResults: { fontSize: 14, color: theme.colors.muted, textAlign: 'center', padding: '40px 0' },
  placeholder: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
    padding: '80px 0', opacity: 0.6,
  },
  placeholderText: { fontSize: 14, color: theme.colors.muted, textAlign: 'center' },
};
