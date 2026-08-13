/** جذر التطبيق: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * ترتيب المزوّدين ليس اعتباطاً: `Config` قبل `Session` لأن تسجيل الجهاز يقرأ
 * عقد FCM من الإعدادات، و`Session` قبل `Ride` لأن المقبس لا يُفتح بلا مستخدم.
 */

import { Suspense, lazy } from "react";
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import type { ReactNode } from "react";

import { Brand } from "@/components/Brand";
import { Toasts } from "@/components/Toasts";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { BrandProvider } from "@/lib/brand";
import { ConfigProvider, useConfig } from "@/lib/config";
import { RideProvider } from "@/lib/ride";
import { PlacesProvider } from "@/lib/places";
import { SessionProvider, useSession } from "@/lib/session";
import { ThemeProvider } from "@/lib/theme";
import { LoginScreen } from "@/screens/Login";

// شاشة الدخول وحدها تُحمَّل مباشرةً؛ وما عداها كسولٌ. والرئيسية أهمُّها:
// تجرّ `mapbox-gl` (نحو 1.8 ميغابايت) وهو أكبر من التطبيق كله، فتحميلُها
// مع الحزمة الأولى يعني محرّك خرائطٍ ينتظره من جاء ليسجّل دخوله فقط.
const HomeScreen = lazy(() =>
  import("@/screens/Home").then((m) => ({ default: m.HomeScreen })),
);
const RegisterScreen = lazy(() =>
  import("@/screens/Register").then((m) => ({ default: m.RegisterScreen })),
);
const ForgotPasswordScreen = lazy(() =>
  import("@/screens/ForgotPassword").then((m) => ({
    default: m.ForgotPasswordScreen,
  })),
);
const AccountScreen = lazy(() =>
  import("@/screens/Account").then((m) => ({ default: m.AccountScreen })),
);
const RidesScreen = lazy(() =>
  import("@/screens/Rides").then((m) => ({ default: m.RidesScreen })),
);
const RideDetailsScreen = lazy(() =>
  import("@/screens/RideDetails").then((m) => ({
    default: m.RideDetailsScreen,
  })),
);
const PaymentScreen = lazy(() =>
  import("@/screens/Payment").then((m) => ({ default: m.PaymentScreen })),
);
const RatingScreen = lazy(() =>
  import("@/screens/Rating").then((m) => ({ default: m.RatingScreen })),
);
const WalletScreen = lazy(() =>
  import("@/screens/WalletHome").then((m) => ({ default: m.WalletScreen })),
);
const WalletTopupScreen = lazy(() =>
  import("@/screens/WalletTopup").then((m) => ({
    default: m.WalletTopupScreen,
  })),
);
const WalletTransferScreen = lazy(() =>
  import("@/screens/WalletTransfer").then((m) => ({
    default: m.WalletTransferScreen,
  })),
);
const CardsScreen = lazy(() =>
  import("@/screens/Cards").then((m) => ({ default: m.CardsScreen })),
);
const SettingsScreen = lazy(() =>
  import("@/screens/Settings").then((m) => ({ default: m.SettingsScreen })),
);
const NotificationsScreen = lazy(() =>
  import("@/screens/Notifications").then((m) => ({
    default: m.NotificationsScreen,
  })),
);
const BookingsScreen = lazy(() =>
  import("@/screens/Bookings").then((m) => ({ default: m.BookingsScreen })),
);
const PlacesScreen = lazy(() =>
  import("@/screens/Places").then((m) => ({ default: m.PlacesScreen })),
);
const CardReturnScreen = lazy(() =>
  import("@/screens/CardReturn").then((m) => ({ default: m.CardReturnScreen })),
);
const ProfileScreen = lazy(() =>
  import("@/screens/Profile").then((m) => ({ default: m.ProfileScreen })),
);

function Boot({ children }: { children: ReactNode }) {
  const { config, error, reload } = useConfig();
  const { loading } = useSession();

  // الإعدادات شرطٌ لرسم شاشة الدخول نفسها (أيُّ مُحقِّق، وأيُّ دول)
  if (!config && error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-16 px-24">
        <Brand subtitle="تعذّر الاتصال بالخادم" />
        <ErrorNote message={error} />
        <button
          type="button"
          onClick={reload}
          className="text-14 font-semibold text-ink underline"
        >
          إعادة المحاولة
        </button>
      </div>
    );
  }

  if (!config || loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-24">
        <Brand />
        <Spinner />
      </div>
    );
  }

  return <>{children}</>;
}

function Guarded({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

function Anonymous({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider>
      <ConfigProvider>
        <SessionProvider>
          {/* تحت الجلسة والإعدادات: السِمة تُقرأ من إعلان صاحبة الحساب ومن
              مفتاح دولتها، فلا معنى لها قبلهما */}
          <BrandProvider>
            <Boot>
              {/* تحت الجلسة: الأماكنُ والوجهاتُ الأخيرة كلاهما لحسابٍ بعينه */}
              <PlacesProvider>
              <RideProvider>
                <Router>
                  <Toasts />
                  <Suspense fallback={<Spinner />}>
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
                        path="/register"
                        element={
                          <Anonymous>
                            <RegisterScreen />
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

                      {/* العودة من صفحة الدفع المستضافة — عنوانٌ يعرفه المزود
                      (`settings.card_return_url`)، فلا يتغير */}
                      <Route
                        path="/payments/card/return"
                        element={
                          <Guarded>
                            <CardReturnScreen />
                          </Guarded>
                        }
                      />

                      <Route
                        path="/"
                        element={
                          <Guarded>
                            <HomeScreen />
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
                        path="/rides/:rideId"
                        element={
                          <Guarded>
                            <RideDetailsScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/rides/:rideId/pay"
                        element={
                          <Guarded>
                            <PaymentScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/rides/:rideId/rate"
                        element={
                          <Guarded>
                            <RatingScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/wallet"
                        element={
                          <Guarded>
                            <WalletScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/wallet/topup"
                        element={
                          <Guarded>
                            <WalletTopupScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/wallet/transfer"
                        element={
                          <Guarded>
                            <WalletTransferScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/account"
                        element={
                          <Guarded>
                            <AccountScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/account/places"
                        element={
                          <Guarded>
                            <PlacesScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/account/bookings"
                        element={
                          <Guarded>
                            <BookingsScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/account/settings"
                        element={
                          <Guarded>
                            <SettingsScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/account/notifications"
                        element={
                          <Guarded>
                            <NotificationsScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/account/cards"
                        element={
                          <Guarded>
                            <CardsScreen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/account/profile"
                        element={
                          <Guarded>
                            <ProfileScreen />
                          </Guarded>
                        }
                      />

                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                  </Suspense>
                </Router>
              </RideProvider>
              </PlacesProvider>
            </Boot>
          </BrandProvider>
        </SessionProvider>
      </ConfigProvider>
    </ThemeProvider>
  );
}
