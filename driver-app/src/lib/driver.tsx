/** ملفُّ الكبتن: حالتُه ومركبتُه ومستنداتُه، مقروءةً مرةً ويقرؤها الجميع.
 *
 * حالةُ الكبتن (`pending` / `approved` / …) هي ما يقرّر أيَّ شاشةٍ يرى بعد
 * الدخول، فمكانُها فوق المسارات لا داخل شاشة. وتُقرأ من `GET /drivers/me`
 * وحده — لا تُخمَّن من وجود مستندات ولا من نجاح تسجيل.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import { getDriverProfile } from "@/api/endpoints";
import type { DriverProfile } from "@/api/types";
import { useSession } from "@/lib/session";

interface DriverState {
  profile: DriverProfile | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const DriverContext = createContext<DriverState>({
  profile: null,
  loading: true,
  refresh: async () => undefined,
});

export function DriverProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const [profile, setProfile] = useState<DriverProfile | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) return;
    setProfile(await getDriverProfile());
  }, [user]);

  useEffect(() => {
    if (!user) {
      setProfile(null);
      return;
    }
    setLoading(true);
    getDriverProfile()
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [user]);

  const value = useMemo<DriverState>(
    () => ({ profile, loading, refresh }),
    [profile, loading, refresh],
  );

  return (
    <DriverContext.Provider value={value}>{children}</DriverContext.Provider>
  );
}

export function useDriver() {
  return useContext(DriverContext);
}
