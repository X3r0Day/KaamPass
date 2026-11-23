"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Catalog } from "./types";

export async function catalog(): Promise<Catalog> {
  const [places, skills] = await Promise.all([
    api<Catalog["places"]>("/localities"),
    api<Catalog["skills"]>("/skills"),
  ]);
  return { places, skills };
}
export function useLoad<T>(load: () => Promise<T>) {
  const [version, setVersion] = useState(0);
  const [state, set] = useState<{
    data?: T;
    err?: unknown;
    run?: () => Promise<T>;
    version?: number;
  }>({});
  useEffect(() => {
    let here = true;
    load().then(
      (data) => {
        if (here) set({ data, run: load, version });
      },
      (err) => {
        if (here) set({ err, run: load, version });
      },
    );
    return () => {
      here = false;
    };
  }, [load, version]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return {
    ...(state.run === load && state.version === version ? state : {}),
    reload,
  };
}
