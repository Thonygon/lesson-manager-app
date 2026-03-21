import React from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput } from 'react-native';
import { colors, spacing, radius, shadows } from '../styles/theme';
import { Header } from '../components/Header';
import { students } from '../data/mockData';

export const StudentsScreen: React.FC = () => {
  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Header title="Students" />

        <View style={styles.searchBox}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            placeholder="Search students..."
            placeholderTextColor={colors.muted}
            style={styles.searchInput}
          />
        </View>

        {students.map((student) => (
          <TouchableOpacity
            key={student.id}
            activeOpacity={0.7}
            style={[styles.card, shadows.sm]}
          >
            <View style={styles.cardLeft}>
              <View style={[styles.avatar, { backgroundColor: student.color }]}>
                <Text style={styles.avatarText}>{student.avatar}</Text>
              </View>
              <View style={styles.info}>
                <Text style={styles.name}>{student.name}</Text>
                <Text style={styles.meta}>Active • Next: Today 10:00 AM</Text>
              </View>
            </View>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>4 left</Text>
            </View>
          </TouchableOpacity>
        ))}
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
    backgroundColor: colors.bgCard, borderRadius: radius.lg,
    paddingHorizontal: spacing.lg, paddingVertical: spacing.md,
    marginBottom: spacing.xl,
    borderWidth: 1, borderColor: colors.border,
  },
  searchIcon: { fontSize: 16 },
  searchInput: { flex: 1, fontSize: 15, color: colors.text },
  card: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: colors.bgCard, borderRadius: radius.lg,
    padding: spacing.lg, marginBottom: spacing.sm,
  },
  cardLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, flex: 1 },
  avatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 20 },
  info: { flex: 1 },
  name: { fontSize: 15, fontWeight: '600', color: colors.text },
  meta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  badge: {
    backgroundColor: colors.accentMuted, borderRadius: radius.full,
    paddingHorizontal: spacing.md, paddingVertical: spacing.xs,
  },
  badgeText: { fontSize: 11, fontWeight: '600', color: colors.accent },
});
