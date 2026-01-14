import { create } from 'zustand';
import type { BotStatus, LogEntry } from '@/types/api';

interface BotState extends BotStatus {
  logs: LogEntry[];
  isConnected: boolean;
  updateStatus: (status: Partial<BotStatus>) => void;
  addLog: (log: LogEntry) => void;
  clearLogs: () => void;
  setConnected: (connected: boolean) => void;
  setLogs: (logs: LogEntry[]) => void;
}

const MAX_LOGS = 500;

export const useBotStore = create<BotState>((set) => ({
  running: false,
  status: 'stopped',
  last_check: null,
  stats: {
    slots_found: 0,
    appointments_booked: 0,
    active_users: 0,
  },
  logs: [],
  isConnected: false,

  updateStatus: (status) =>
    set((state) => ({
      ...state,
      ...status,
      stats: status.stats ? { ...state.stats, ...status.stats } : state.stats,
    })),

  addLog: (log) =>
    set((state) => {
      const newLogs = [...state.logs, log];
      // Keep only the last MAX_LOGS entries
      if (newLogs.length > MAX_LOGS) {
        return { logs: newLogs.slice(-MAX_LOGS) };
      }
      return { logs: newLogs };
    }),

  clearLogs: () => set({ logs: [] }),

  setConnected: (connected) => set({ isConnected: connected }),

  setLogs: (logs) => set({ logs }),
}));
