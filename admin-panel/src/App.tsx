/** جذر اللوحة: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * **وأقسامُ المرحلة 11 كلُّها مبنيّةٌ الآن**: الدخول، ونظرةٌ عامة، والخريطة
 * الحيّة، وسجل الرحلات، والسائقون والوثائق، والركّاب، والنزاعات، والمالية،
 * والاشتراكات والباقات، والتسعيرة، والتقارير، والإشعارات الجماعية،
 * والمستخدمون والصلاحيات، وسجل التدقيق، والإعدادات، وعقود المزوّدين.
 * وآليةُ «قريباً» في `components/Shell.tsx` باقيةٌ لأقسام المرحلة 12.
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

import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { ConfigProvider, useConfig } from "@/lib/config";
import { CountriesProvider } from "@/lib/countries";
import { CountryProvider } from "@/lib/country";
import { SessionProvider, useSession } from "@/lib/session";
import { ThemeProvider } from "@/lib/theme";
import { LoginScreen } from "@/screens/Login";

const OverviewScreen = lazy(() =>
  import("@/screens/Overview").then((m) => ({ default: m.OverviewScreen })),
);
const LiveMapScreen = lazy(() =>
  import("@/screens/LiveMap").then((m) => ({ default: m.LiveMapScreen })),
);
const CampaignsScreen = lazy(() =>
  import("@/screens/Campaigns").then((m) => ({ default: m.CampaignsScreen })),
);
const DriversScreen = lazy(() =>
  import("@/screens/Drivers").then((m) => ({ default: m.DriversScreen })),
);
const FinanceScreen = lazy(() =>
  import("@/screens/Finance").then((m) => ({ default: m.FinanceScreen })),
);
const PaymentsScreen = lazy(() =>
  import("@/screens/Payments").then((m) => ({ default: m.PaymentsScreen })),
);
const DisputesScreen = lazy(() =>
  import("@/screens/Disputes").then((m) => ({ default: m.DisputesScreen })),
);
const OtpTemplatesScreen = lazy(() =>
  import("@/screens/OtpTemplatesScreen").then((m) => ({
    default: m.OtpTemplatesScreen,
  })),
);
const SettingsScreen = lazy(() =>
  import("@/screens/Settings").then((m) => ({ default: m.SettingsScreen })),
);
const ProvidersScreen = lazy(() =>
  import("@/screens/Providers").then((m) => ({ default: m.ProvidersScreen })),
);
const RidesScreen = lazy(() =>
  import("@/screens/Rides").then((m) => ({ default: m.RidesScreen })),
);
const RidersScreen = lazy(() =>
  import("@/screens/Riders").then((m) => ({ default: m.RidersScreen })),
);
const OffersScreen = lazy(() =>
  import("@/screens/Offers").then((m) => ({ default: m.OffersScreen })),
);
const SubscriptionsScreen = lazy(() =>
  import("@/screens/Subscriptions").then((m) => ({
    default: m.SubscriptionsScreen,
  })),
);
const PricingScreen = lazy(() =>
  import("@/screens/Pricing").then((m) => ({ default: m.PricingScreen })),
);
const ReportsScreen = lazy(() =>
  import("@/screens/Reports").then((m) => ({ default: m.ReportsScreen })),
);
const UsersScreen = lazy(() =>
  import("@/screens/Users").then((m) => ({ default: m.UsersScreen })),
);
const AuditScreen = lazy(() =>
  import("@/screens/Audit").then((m) => ({ default: m.AuditScreen })),
);
const SecurityScreen = lazy(() =>
  import("@/screens/Security").then((m) => ({ default: m.SecurityScreen })),
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
  const { loading, user } = useSession();

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
    // **الأسواقُ تُسأل بعد الدخول وحده**: البابُ `StaffUser`، وشاشةُ الدخول
    // تقرأ بادئةَ الهاتف من `/config` كما كانت
    <CountriesProvider enabled={Boolean(user)}>
      <CountryProvider fallback={config.default_country_code}>
        {children}
      </CountryProvider>
    </CountriesProvider>
  );
}

function Guarded({ children }: { children: ReactNode }) {
  const { user, enrollmentRequired } = useSession();
  if (!user) return <Navigate to="/login" replace />;
  // **بوابةُ الإلزام** (12-د): الخلفيةُ ردّت `totp_enrollment_required`، فكلُّ
  // مسارٍ إداريٍّ مغلقٌ حتى يُسجّل عاملَه. وقيادتُه إلى الشاشة التي تفتح البابَ
  // أصدقُ من ترك كل شاشةٍ ترسم خطأً أحمر لا مخرجَ منه
  if (enrollmentRequired) return <Navigate to="/security" replace />;
  return <>{children}</>;
}

/** شاشةُ الأمان وحدها لا تخضع لبوابة الإلزام — وإلا صارت الحلقةُ مغلقة:
 *  «سجّل عاملاً» على بابٍ لا يُفتح قبل تسجيل عامل. */
function SecurityGuarded({ children }: { children: ReactNode }) {
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
                <ErrorBoundary>
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
                    path="/overview"
                    element={
                      <Guarded>
                        <OverviewScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/live-map"
                    element={
                      <Guarded>
                        <LiveMapScreen />
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
                    path="/payments"
                    element={
                      <Guarded>
                        <PaymentsScreen />
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
                    path="/otp-templates"
                    element={
                      <Guarded>
                        <OtpTemplatesScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <Guarded>
                        <SettingsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/providers"
                    element={
                      <Guarded>
                        <ProvidersScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/rides"
                    element={
                      <Guarded>
                        <RidesScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/riders"
                    element={
                      <Guarded>
                        <RidersScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/subscriptions"
                    element={
                      <Guarded>
                        <SubscriptionsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/offers"
                    element={
                      <Guarded>
                        <OffersScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/pricing"
                    element={
                      <Guarded>
                        <PricingScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/reports"
                    element={
                      <Guarded>
                        <ReportsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/users"
                    element={
                      <Guarded>
                        <UsersScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/audit"
                    element={
                      <Guarded>
                        <AuditScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/security"
                    element={
                      <SecurityGuarded>
                        <SecurityScreen />
                      </SecurityGuarded>
                    }
                  />
                  <Route
                    path="*"
                    element={<Navigate to="/overview" replace />}
                  />
                </Routes>
                </ErrorBoundary>
              </Suspense>
            </Router>
          </Boot>
        </SessionProvider>
      </ConfigProvider>
    </ThemeProvider>
  );
}
