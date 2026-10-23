import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Panel } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { getGenerationFeedbackForResource, saveGenerationIntentFeedback, type SmartToolKind } from '@/services/smart-tools';
import { colors } from '@/theme';

type Reason = 'content' | 'level' | 'format' | 'other';

export function GenerationIntentQuestion({ resourceType, resourceId, surface, revision = 0 }: { resourceType: SmartToolKind; resourceId: string; surface: 'generation_preview' | 'resource_page'; revision?: number }) {
  const { t } = useAppPreferences();
  const [generationId, setGenerationId] = useState('');
  const [answer, setAnswer] = useState<boolean | null>(null);
  const [reason, setReason] = useState<Reason | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    if (resourceId) void getGenerationFeedbackForResource(resourceType, resourceId).then((result) => {
      if (!active) return;
      if (!result.eligible || !result.generationId) { setGenerationId(''); setMessage(''); return; }
      setGenerationId(result.generationId);
      setAnswer(typeof result.satisfied === 'boolean' ? result.satisfied : null);
      setReason(['content', 'level', 'format', 'other'].includes(String(result.reason)) ? result.reason as Reason : null);
    }).catch(() => { /* Feedback availability never blocks the resource. */ });
    return () => { active = false; };
  }, [resourceType, resourceId, revision]);

  if (!generationId) return null;
  const submit = async (satisfied: boolean, selectedReason?: Reason) => {
    setBusy(true); setMessage('');
    try {
      await saveGenerationIntentFeedback(generationId, satisfied, surface, selectedReason);
      setAnswer(satisfied); setReason(satisfied ? null : selectedReason || null);
      setError(false); setMessage(t('smart.intentSaved'));
    } catch (cause) { setError(true); setMessage(cause instanceof Error ? cause.message : t('smart.intentFailed')); }
    finally { setBusy(false); }
  };
  return <Panel style={styles.panel}>
    <Text style={styles.title}>{t('smart.intentQuestion')}</Text>
    <View style={styles.actions}>
      <Button secondary={answer !== true} disabled={busy} onPress={() => void submit(true)}>{t('smart.intentYes')}</Button>
      <Button secondary={answer !== false} disabled={busy} onPress={() => void submit(false)}>{t('smart.intentNo')}</Button>
    </View>
    {answer === false ? <><Text style={styles.helper}>{t('smart.intentReason')}</Text><View style={styles.actions}>{(['content', 'level', 'format', 'other'] as const).map((item) => <Button key={item} secondary={reason !== item} disabled={busy} onPress={() => void submit(false, item)}>{t(`smart.intent${item[0].toUpperCase()}${item.slice(1)}`)}</Button>)}</View></> : null}
    <ActionFeedback message={message} tone={error ? 'error' : 'success'} />
  </Panel>;
}

const styles = StyleSheet.create({ panel: { marginTop: 18, gap: 10 }, title: { color: colors.ink, fontSize: 16, fontWeight: '800' }, helper: { color: colors.muted, fontSize: 12 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 } });
