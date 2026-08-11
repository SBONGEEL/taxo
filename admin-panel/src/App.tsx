/** جذر اللوحة: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * **ما هو مبنيٌّ الآن**: الدخول، والسائقون والوثائق، والمالية، والنزاعات،
 * والإشعارات الجماعية. وبقيةُ الأقسام
 * مرسومةٌ في القائمة معطّلةً بشارة «قريباً» — تقول للمستخدم حالها بدل أن
 * تجعله يشك في اللوحة (انظر `components/Shell.tsx`).
 *
 * والدولةُ الافتراضية من `/config` لا مكتوبةً هنا، فمزوّدُها تحت `Boot`.
 */

import { Suspense, lazy } from "react";
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import type { ReactNode } from "react";

import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { ConfigProvider, useConfig } from "@/lib/config";
import { CountryProvider } from "@/lib/country";
import { SessionProvider, useSession } from "@/lib/session";
import { ThemeProvider } from "@/lib/theme";
import { LoginScreen } from "@/screens/Login";

const CampaignsScreen = lazy(() =>
  import("@/screens/Campaigns").then((m) => ({ default: m.CampaignsScreen })),
);
const DriversScreen = lazy(() =>
  import("@/screens/Drivers").then((m) => ({ default: m.DriversScreen })),
);
const FinanceScreen = lazy(() =>
  import("@/screens/Finance").then((m) => ({ default: m.FinanceScreen })),
);
const DisputesScreen = lazy(() =>
  import("@/screens/Disputes").then((m) => ({ default: m.DisputesScreen })),
);

function Centered({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-16 bg-bg px-24 text-center">
      {children}
    </div>
  );
}

function Boot({ children }: { children: ReactNode }) {
  const { config, error, reload } = useConfig();
  const { loading } = useSession();

  if (!config && error) {
    return (
      <Centered>
        <div className="text-30 font-bold tracking-wordmark text-ink">TAXO</div>
        <ErrorNote message={error} />
        <button
          type="button"
          onClick={reload}
          className="text-13 font-semibold text-ink underline"
        >
          إعادة المحاولة
        </button>
      </Centered>
    );
  }

  if (!config || loading) {
    return (
      <Centered>
        <div className="text-30 font-bold tracking-wordmark text-ink">TAXO</div>
        <Spinner />
      </Centered>
    );
  }

  return (
    <CountryProvider fallback={config.default_country_code}>
      {children}
    </CountryProvider>
  );
}

function Guarded({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

function Anonymous({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <Navigate to="/campaigns" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider>
      <ConfigProvider>
        <SessionProvider>
          <Boot>
            <Router>
              <Suspense
                fallback={
                  <Centered>
                    <Spinner />
                  </Centered>
                }
              >
                <Routes>
                  <Route
                    path="/login"
                    element={
                      <Anonymous>
                        <LoginScreen />
                      </Anonymous>
                    }
                  />
                  <Route
                    path="/campaigns"
                    element={
                      <Guarded>
                        <CampaignsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/drivers"
                    element={
                      <Guarded>
                        <DriversScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/finance"
                    element={
                      <Guarded>
                        <FinanceScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/disputes"
                    element={
                      <Guarded>
                        <DisputesScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="*"
                    element={<Navigate to="/drivers" replace />}
                  />
                </Routes>
              </Suspense>
            </Router>
          </Boot>
        </SessionProvider>
      </ConfigProvider>
    </ThemeProvider>
  );
}
