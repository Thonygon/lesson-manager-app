import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, spacing, radius, shadows } from '../styles/theme';
import { Lesson } from '../data/mockData';

interface LessonCardProps {
  lesson: Lesson;
  isFirst?: boolean;
}

export const LessonCard: React.FC<LessonCardProps> = ({ lesson, isFirst }) => {
  const hasZoom = !!lesson.zoomLink;

  return (
    <View style={[styles.card, shadows.md]}>
      <View style={styles.topRow}>
        <View style={styles.leftInfo}>
          <View style={[styles.avatar, { backgroundColor: lesson.color }]}>
            <Text style={styles.avatarText}>{lesson.avatar}</Text>
          </View>
          <View>
            <Text style={styles.name}>{lesson.studentName}</Text>
            <Text style={styles.subject}>{lesson.subject}</Text>
          </View>
        </View>

        <View style={styles.timeCol}>
          <Text style={styles.time}>{lesson.startTime}</Text>
          <Text style={styles.duration}>{lesson.duration} MINS</Text>
        </View>
      </View>

      {hasZoom && isFirst && (
        <TouchableOpacity activeOpacity={0.8} style={styles.zoomBtn}>
          <Text style={styles.zoomIcon}>📹</Text>
          <Text style={styles.zoomText}>Launch Zoom</Text>
        </TouchableOpacity>
      )}

      {!hasZoom && !isFirst && (
        <View style={styles.actionRow}>
          <TouchableOpacity style={styles.actionBtn}>
            <Text style={styles.actionBtnText}>Review Notes</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.moreBtn}>
            <Text style={styles.moreBtnText}>•••</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radius.xl,
    padding: spacing.xl,
    marginBottom: spacing.md,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  leftInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    flex: 1,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 20,
  },
  name: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  subject: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  timeCol: {
    alignItems: 'flex-end',
  },
  time: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  duration: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.muted,
    letterSpacing: 0.5,
    marginTop: 2,
  },
  zoomBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.zoomBg,
    borderRadius: radius.lg,
    paddingVertical: spacing.lg,
    marginTop: spacing.lg,
  },
  zoomIcon: {
    fontSize: 16,
  },
  zoomText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.zoomText,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginTop: spacing.lg,
  },
  actionBtn: {
    flex: 1,
    backgroundColor: colors.bgMuted,
    borderRadius: radius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  actionBtnText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.text,
  },
  moreBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.bgMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  moreBtnText: {
    fontSize: 16,
    color: colors.muted,
    fontWeight: '700',
  },
});
