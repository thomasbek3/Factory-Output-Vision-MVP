"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { demoNowIso } from "@/lib/demoData";

type Speed = 1 | 60;

type TimeContextValue = {
  now: () => Date;
  speed: Speed;
  setSpeed: (speed: Speed) => void;
  jumpTo: (next: Date | string) => void;
};

const demoStart = new Date(demoNowIso);
const TimeContext = createContext<TimeContextValue | null>(null);

export function TimeProvider({ children }: { children: ReactNode }) {
  const [virtualNow, setVirtualNow] = useState<Date>(demoStart);
  const [speed, setSpeed] = useState<Speed>(1);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setVirtualNow((current) => new Date(current.getTime() + 1000 * speed));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [speed]);

  const jumpTo = useCallback((next: Date | string) => {
    setVirtualNow(next instanceof Date ? next : new Date(next));
  }, []);

  const value = useMemo<TimeContextValue>(
    () => ({
      now: () => virtualNow,
      speed,
      setSpeed,
      jumpTo,
    }),
    [jumpTo, speed, virtualNow],
  );

  return <TimeContext.Provider value={value}>{children}</TimeContext.Provider>;
}

export function useTime() {
  const value = useContext(TimeContext);
  if (!value) {
    throw new Error("useTime must be used inside TimeProvider");
  }
  return value;
}
