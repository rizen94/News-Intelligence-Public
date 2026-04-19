import { useCallback, useMemo, useState } from 'react';

const STORAGE_PREFIX = 'ni_v9_pinned_threads';

function readIds(domain: string): { storylineIds: Set<number>; eventIds: Set<number> } {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}_${domain}`);
    if (!raw) return { storylineIds: new Set(), eventIds: new Set() };
    const parsed = JSON.parse(raw) as {
      storylineIds?: number[];
      eventIds?: number[];
    };
    return {
      storylineIds: new Set(parsed.storylineIds ?? []),
      eventIds: new Set(parsed.eventIds ?? []),
    };
  } catch {
    return { storylineIds: new Set(), eventIds: new Set() };
  }
}

function writeIds(
  domain: string,
  storylineIds: Set<number>,
  eventIds: Set<number>
) {
  try {
    localStorage.setItem(
      `${STORAGE_PREFIX}_${domain}`,
      JSON.stringify({
        storylineIds: [...storylineIds],
        eventIds: [...eventIds],
      })
    );
  } catch {
    /* ignore quota */
  }
}

/**
 * Per-domain pinned storyline / event IDs for Monitor (client-only; phase 2: API filters).
 */
export function usePinnedThreads(domain: string) {
  const [version, setVersion] = useState(0);
  const { storylineIds, eventIds } = useMemo(() => {
    void version;
    return readIds(domain);
  }, [domain, version]);

  const bump = useCallback(() => setVersion(v => v + 1), []);

  const toggleStoryline = useCallback(
    (id: number) => {
      const cur = readIds(domain);
      if (cur.storylineIds.has(id)) cur.storylineIds.delete(id);
      else cur.storylineIds.add(id);
      writeIds(domain, cur.storylineIds, cur.eventIds);
      bump();
    },
    [domain, bump]
  );

  const pinStoryline = useCallback(
    (id: number) => {
      const cur = readIds(domain);
      cur.storylineIds.add(id);
      writeIds(domain, cur.storylineIds, cur.eventIds);
      bump();
    },
    [domain, bump]
  );

  const unpinStoryline = useCallback(
    (id: number) => {
      const cur = readIds(domain);
      cur.storylineIds.delete(id);
      writeIds(domain, cur.storylineIds, cur.eventIds);
      bump();
    },
    [domain, bump]
  );

  const toggleEvent = useCallback(
    (id: number) => {
      const cur = readIds(domain);
      if (cur.eventIds.has(id)) cur.eventIds.delete(id);
      else cur.eventIds.add(id);
      writeIds(domain, cur.storylineIds, cur.eventIds);
      bump();
    },
    [domain, bump]
  );

  const isStorylinePinned = useCallback(
    (id: number) => storylineIds.has(id),
    [storylineIds]
  );

  const isEventPinned = useCallback(
    (id: number) => eventIds.has(id),
    [eventIds]
  );

  return {
    pinnedStorylineIds: storylineIds,
    pinnedEventIds: eventIds,
    toggleStoryline,
    pinStoryline,
    unpinStoryline,
    toggleEvent,
    isStorylinePinned,
    isEventPinned,
  };
}
