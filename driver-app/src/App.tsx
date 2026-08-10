/** جذر التطبيق: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * ترتيب المزوّدين ليس اعتباطاً: `Config` قبل `Session` لأن تسجيل الجهاز يقرأ
 * عقد FCM من الإعدادات، والمظهرُ فوقهما لأنه يُرسم قبل أن تصل أي بيانات.
 *
 * **ما هو مبنيٌّ الآن**: الدخول واستعادة كلمة المرور. وبقيةُ شاشات القسم 12
 * تُضاف على هذه المسارات نفسها في الجلسات التالية من المرحلة 10.
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
import { SessionProvider, useSession } from "@/lib/session";
import { ThemeProvider } from "@/lib/theme";
import { LoginScreen } from "@/screens/Login";

const ForgotPasswordScreen = lazy(() =>
  import("@/screens/ForgotPassword").then((m) => ({
    default: m.ForgotPasswordScreen,
  })),
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
        <button type="button" onClick={reload} className="text-13 font-semibold text-ink underline">
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

/** موضعُ الشاشات المحميّة حتى تُبنى في الجلسة التالية. */
function Placeholder() {
  const { user, signOut } = useSession();
  return (
    <CenteredMessage>
      <div className="text-38 font-bold tracking-brand text-ink">TAXO</div>
      <p className="text-14 text-muted">أهلاً {user?.name} — الرئيسية قيد البناء.</p>
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
            <Router>
              <Suspense fallback={<CenteredMessage><Spinner /></CenteredMessage>}>
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
                    path="/"
                    element={
                      <Guarded>
                        <Placeholder />
                      </Guarded>
                    }
                  />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Suspense>
            </Router>
          </Boot>
        </SessionProvider>
      </ConfigProvider>
    </ThemeProvider>
  );
}
