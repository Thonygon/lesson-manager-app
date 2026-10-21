import { useCallback, useEffect, useState } from 'react';

import { getRecords, type ClassioRecord, type ListKey } from '@/services/classio-data';

export function useRecords(key: ListKey) {
  const [records, setRecords] = useState<ClassioRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRecords(await getRecords(key));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load Classio records.');
    } finally {
      setLoading(false);
    }
  }, [key]);

  // The initial fetch uses the same loading transition as manual refresh.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void refresh(); }, [refresh]);
  return { records, loading, error, refresh };
}
