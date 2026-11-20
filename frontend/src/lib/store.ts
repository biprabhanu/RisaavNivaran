// Tiny global store (no extra library): offline flag, health, meta, and a "data version"
// counter that pages watch so they refetch after Reset demo or an approval.
import { useSyncExternalStore } from 'react';
import type { HealthResponse, MetaResponse } from '../types/api';

export interface AppState {
  offline: boolean; // true = backend unreachable, reading from the bundled snapshot
  health: HealthResponse | null;
  meta: MetaResponse | null;
  dataVersion: number;
  offlineFrameIndex: number | null; // which snapshot frame offline pages show (null = last)
  toast: string | null;
}

let state: AppState = {
  offline: false,
  health: null,
  meta: null,
  dataVersion: 0,
  offlineFrameIndex: null,
  toast: null,
};
const listeners = new Set<() => void>();

export function getState(): AppState {
  return state;
}

export function setState(patch: Partial<AppState>): void {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useAppState(): AppState {
  return useSyncExternalStore(subscribe, getState, getState);
}

/** Tell every page to reload its data. */
export function bumpData(): void {
  setState({ dataVersion: state.dataVersion + 1 });
}

let toastTimer: ReturnType<typeof setTimeout> | undefined;
export function showToast(msg: string): void {
  setState({ toast: msg });
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => setState({ toast: null }), 4500);
}
