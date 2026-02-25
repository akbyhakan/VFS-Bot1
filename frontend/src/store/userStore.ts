import { create } from 'zustand';
import type { VFSAccount } from '@/types/user';

interface VFSAccountState {
  accounts: VFSAccount[];
  selectedAccount: VFSAccount | null;
  isLoading: boolean;
  error: string | null;
  setAccounts: (accounts: VFSAccount[]) => void;
  addAccount: (account: VFSAccount) => void;
  updateAccount: (account: VFSAccount) => void;
  deleteAccount: (id: number) => void;
  setSelectedAccount: (account: VFSAccount | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
}

export const useVFSAccountStore = create<VFSAccountState>((set) => ({
  accounts: [],
  selectedAccount: null,
  isLoading: false,
  error: null,

  setAccounts: (accounts) => set({ accounts }),

  addAccount: (account) =>
    set((state) => ({
      accounts: [...state.accounts, account],
    })),

  updateAccount: (updatedAccount) =>
    set((state) => ({
      accounts: state.accounts.map((account) =>
        account.id === updatedAccount.id ? updatedAccount : account
      ),
      selectedAccount:
        state.selectedAccount?.id === updatedAccount.id ? updatedAccount : state.selectedAccount,
    })),

  deleteAccount: (id) =>
    set((state) => ({
      accounts: state.accounts.filter((account) => account.id !== id),
      selectedAccount: state.selectedAccount?.id === id ? null : state.selectedAccount,
    })),

  setSelectedAccount: (account) => set({ selectedAccount: account }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  clearError: () => set({ error: null }),
}));

// Backward compatibility alias
export const useUserStore = useVFSAccountStore;
