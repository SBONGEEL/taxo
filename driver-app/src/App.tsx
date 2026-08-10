/** جذر التطبيق: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * ترتيب المزوّدين ليس اعتباطاً: `Config` قبل `Session` لأن تسجيل الجهاز يقرأ
 * عقد FCM من الإعدادات، و`Driver` و`Ride` تحتهما لأنهما لا يعملان بلا
 * مستخدم. والمظهرُ فوق الكل لأنه يُرسم قبل أن تصل أيُّ بيانات.
 *
 * **ما هو مبنيٌّ الآن**: الدخول واستعادة كلمة المرور، والتسجيل بخطواته
 * الثلاث، والرئيسيةُ ببطاقة الطلب والرحلة الجارية. وتبويبات الشريط السفلي
 * الثلاثة الباقية تُبنى في الجلسات التالية.
 *
 * وحالةُ الكبتن هي ما يقرّر أيَّ شاشةٍ يرى بعد الدخول: غيرُ المعتمد يرى «قيد
 * المراجعة» ولا يرى الرئيسية — لا لأننا نخفيها، بل لأن التوزيع لا يعرفه
 * أصلاً (`dispatch.eligible_driver_ids`).
 */

import { Suspense, lazy } from "react";
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import type { ReactNode } from "react";

import { CenteredMessage, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { ConfigProvider, useConfig } from "@/lib/config";
import { DriverProvider, useDriver } from "@/lib/driver";
import { RideProvider } from "@/lib/ride";
import { SessionProvider, useSession } from "@/lib/session";
import { ThemeProvider } from "@/lib/theme";
import { LoginScreen } from "@/screens/Login";

const ForgotPasswordScreen = lazy(() =>
  import("@/screens/ForgotPassword").then((m) => ({
    default: m.ForgotPasswordScreen,
  })),
);
const RegisterScreen = lazy(() =>
  import("@/screens/Register").then((m) => ({ default: m.RegisterScreen })),
);
const RegisterDocumentsScreen = lazy(() =>
  import("@/screens/RegisterDocuments").then((m) => ({
    default: m.RegisterDocumentsScreen,
  })),
);
const PendingScreen = lazy(() =>
  import("@/screens/Pending").then((m) => ({ default: m.PendingScreen })),
);
// الرئيسية تجرّ `mapbox-gl` وهو أكبر من التطبيق كله، فلا تُحمَّل مع الحزمة
// الأولى: من جاء ليسجّل دخوله لا ينتظر محرّك خرائط
const HomeScreen = lazy(() =>
  import("@/screens/Home").then((m) => ({ default: m.HomeScreen })),
);
const SoonScreen = lazy(() =>
  import("@/screens/Soon").then((m) => ({ default: m.SoonScreen })),
);

function Loading() {
  return (
    <CenteredMessage>
      <Spinner />
    </CenteredMessage>
  );
}

function Boot({ children }: { children: ReactNode }) {
  const { config, error, reload } = useConfig();
  const { loading } = useSession();

  // الإعدادات شرطٌ لرسم شاشة الدخول نفسها: منها يُعرف أيُّ مُحقِّقٍ يرسم
  if (!config && error) {
    return (
      <CenteredMessage>
        <div className="text-38 font-bold tracking-brand text-ink">TAXO</div>
        <ErrorNote message={error} />
        <button
          type="button"
          onClick={reload}
          className="text-13 font-semibold text-ink underline"
        >
          إعادة المحاولة
        </button>
      </CenteredMessage>
    );
  }

  if (!config || loading) {
    return (
      <CenteredMessage>
        <div className="text-38 font-bold tracking-brand text-ink">TAXO</div>
        <Spinner />
      </CenteredMessage>
    );
  }

  return <>{children}</>;
}

function Anonymous({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

function Guarded({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

/** جذرُ الكبتن: المعتمد يرى الرئيسية، وغيرُه يرى سببَ انتظاره. */
function DriverHome() {
  const { profile, loading } = useDriver();

  if (loading || !profile) return <Loading />;
  return profile.driver.status === "approved" ? (
    <HomeScreen />
  ) : (
    <PendingScreen />
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ConfigProvider>
        <SessionProvider>
          <Boot>
            <DriverProvider>
              <RideProvider>
                <Router>
                  <Suspense fallback={<Loading />}>
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
                        path="/forgot-password"
                        element={
                          <Anonymous>
                            <ForgotPasswordScreen />
                          </Anonymous>
                        }
                      />
                      <Route
                        path="/register"
                        element={
                          <Anonymous>
                            <RegisterScreen />
                          </Anonymous>
                        }
                      />
                      {/* بعد الخطوة الأولى صار له حساب، فالخطوة الثالثة محميّة */}
                      <Route
                        path="/register/documents"
                        element={
                          <Guarded>
                            <RegisterDocumentsScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/"
                        element={
                          <Guarded>
                            <DriverHome />
                          </Guarded>
                        }
                      />
                      {/* تبويبات الشريط السفلي — تُبنى في الجلسات التالية */}
                      <Route
                        path="/rides"
                        element={
                          <Guarded>
                            <SoonScreen title="سجل الرحلات" />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/wallet"
                        element={
                          <Guarded>
                            <SoonScreen title="المحفظة" />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/account"
                        element={
                          <Guarded>
                            <SoonScreen title="حسابي" />
                          </Guarded>
                        }
                      />
                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                  </Suspense>
                </Router>
              </RideProvider>
            </DriverProvider>
          </Boot>
        </SessionProvider>
      </ConfigProvider>
    </ThemeProvider>
  );
}
