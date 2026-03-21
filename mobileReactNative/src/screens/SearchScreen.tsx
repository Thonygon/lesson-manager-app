import React, { useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TextInput } from 'react-native';
import { colors, spacing, radius, shadows } from '../styles/theme';
import { Header } from '../components/Header';
import { students, todayLessons } from '../data/mockData';

export const SearchScreen: React.FC = () => {
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
    <View style={styles.container}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Header title="Search" />

        <View style={styles.searchBox}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            placeholder="Search students, lessons..."
            placeholderTextColor={colors.muted}
            style={styles.searchInput}
            value={query}
            onChangeText={setQuery}
          />
        </View>

        {query.length > 0 ? (
          <>
            {filteredStudents.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>STUDENTS</Text>
                {filteredStudents.map((s) => (
                  <View key={s.id} style={[styles.resultCard, shadows.sm]}>
                    <View style={[styles.avatar, { backgroundColor: s.color }]}>
                      <Text style={styles.avatarText}>{s.avatar}</Text>
                    </View>
                    <Text style={styles.resultName}>{s.name}</Text>
                  </View>
                ))}
              </>
            )}
            {filteredLessons.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>LESSONS</Text>
                {filteredLessons.map((l) => (
                  <View key={l.id} style={[styles.resultCard, shadows.sm]}>
                    <View style={[styles.avatar, { backgroundColor: l.color }]}>
                      <Text style={styles.avatarText}>{l.avatar}</Text>
                    </View>
                    <View>
                      <Text style={styles.resultName}>{l.studentName}</Text>
                      <Text style={styles.resultMeta}>
                        {l.subject} • {l.startTime}
                      </Text>
                    </View>
                  </View>
                ))}
              </>
            )}
            {filteredStudents.length === 0 && filteredLessons.length === 0 && (
              <View style={styles.empty}>
                <Text style={styles.emptyText}>No results found</Text>
              </View>
            )}
          </>
        ) : (
          <View style={styles.placeholder}>
            <Text style={styles.placeholderIcon}>🔍</Text>
            <Text style={styles.placeholderText}>
              Start typing to search across students and lessons
            </Text>
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: spacing.xl, paddingTop: spacing.md, paddingBottom: 100 },
  searchBox: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    backgroundColor: colors.bgCard, borderRadius: radius.xl,
    paddingHorizontal: spacing.lg, paddingVertical: spacing.lg,
    marginBottom: spacing.xl,
    borderWidth: 1, borderColor: colors.borderStrong,
  },
  searchIcon: { fontSize: 18 },
  searchInput: { flex: 1, fontSize: 16, color: colors.text },
  sectionTitle: {
    fontSize: 11, fontWeight: '700', color: colors.muted,
    letterSpacing: 1.5, marginBottom: spacing.md, marginTop: spacing.md,
  },
  resultCard: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    backgroundColor: colors.bgCard, borderRadius: radius.md,
    padding: spacing.md, marginBottom: spacing.sm,
  },
  avatar: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 16 },
  resultName: { fontSize: 14, fontWeight: '500', color: colors.text },
  resultMeta: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  empty: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { fontSize: 14, color: colors.muted },
  placeholder: { alignItems: 'center', paddingVertical: 80 },
  placeholderIcon: { fontSize: 40, marginBottom: spacing.lg, opacity: 0.3 },
  placeholderText: { fontSize: 14, color: colors.muted, textAlign: 'center' },
});
