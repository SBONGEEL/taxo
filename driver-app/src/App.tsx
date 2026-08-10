/** جذر التطبيق: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * ترتيب المزوّدين ليس اعتباطاً: `Config` قبل `Session` لأن تسجيل الجهاز يقرأ
 * عقد FCM من الإعدادات، والمظهرُ فوقهما لأنه يُرسم قبل أن تصل أي بيانات.
 *
 * **ما هو مبنيٌّ الآن**: الدخول واستعادة كلمة المرور، والتسجيل بخطواته
 * الثلاث. وبقيةُ شاشات القسم 12 تُضاف على هذه المسارات نفسها.
 *
 * وحالةُ الكبتن هي ما يقرّر أيَّ شاشةٍ يرى بعد الدخول: غيرُ المعتمد يرى
 * «قيد المراجعة» ولا يرى الرئيسية — لا لأننا نخفيها، بل لأن التوزيع لا
 * يعرفه أصلاً (`dispatch.eligible_driver_ids`).
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

/** موضعُ الرئيسية حتى تُبنى في الجلسة التالية. */
function Placeholder() {
  const { user, signOut } = useSession();
  return (
    <CenteredMessage>
      <div className="text-38 font-bold tracking-brand text-ink">TAXO</div>
      <p className="text-14 text-muted">
        أهلاً {user?.name} — الرئيسية قيد البناء.
      </p>
      <button
        type="button"
        onClick={() => void signOut()}
        className="text-13 font-semibold text-danger"
      >
        تسجيل الخروج
      </button>
    </CenteredMessage>
  );
}

/** جذرُ الكبتن: المعتمد يرى الرئيسية، وغيرُه يرى سببَ انتظاره. */
function DriverHome() {
  const { profile, loading } = useDriver();

  if (loading || !profile) {
    return (
      <CenteredMessage>
        <Spinner />
      </CenteredMessage>
    );
  }
  return profile.driver.status === "approved" ? (
    <Placeholder />
  ) : (
    <PendingScreen />
  );
}

function Guarded({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <ThemeProvider>
      <ConfigProvider>
        <SessionProvider>
          <Boot>
            <DriverProvider>
              <Router>
                <Suspense
                  fallback={
                    <CenteredMessage>
                      <Spinner />
                    </CenteredMessage>
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
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Suspense>
              </Router>
            </DriverProvider>
          </Boot>
        </SessionProvider>
      </ConfigProvider>
    </ThemeProvider>
  );
}
