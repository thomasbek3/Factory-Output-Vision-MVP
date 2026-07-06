"use client";

import { useCallback, useEffect, useState } from "react";

export type SavedClip = {
  id: string;
  eventId: string;
  stationId: string;
  ts: string;
  note: string | null;
  savedAt: string;
};

export function useSavedClips() {
  const [clips, setClips] = useState<SavedClip[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/clips", { cache: "no-store" });
      if (!response.ok) throw new Error(`Clips API returned ${response.status}`);
      const payload = (await response.json()) as { clips: SavedClip[] };
      setClips(payload.clips);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load saved clips.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const saveClip = useCallback(async (eventId: string, note?: string) => {
    const response = await fetch("/api/clips", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ eventId, note }),
    });
    if (!response.ok) throw new Error(`Save failed with ${response.status}`);
    const payload = (await response.json()) as { clip: SavedClip };
    setClips((current) => [payload.clip, ...current]);
    return payload.clip;
  }, []);

  return { clips, error, refresh, saveClip };
}
