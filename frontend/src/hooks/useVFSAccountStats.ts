import { useMemo } from 'react';
import type { VFSAccount, VFSAccountStats } from '@/types/user';

export function useVFSAccountStats(accounts: VFSAccount[] | undefined): VFSAccountStats {
  return useMemo(() => {
    if (!accounts) {
      return { total_accounts: 0, active_accounts: 0, inactive_accounts: 0 };
    }
    const active = accounts.filter((a) => a.is_active).length;
    return {
      total_accounts: accounts.length,
      active_accounts: active,
      inactive_accounts: accounts.length - active,
    };
  }, [accounts]);
}
