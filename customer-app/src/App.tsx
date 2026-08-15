/** جذر التطبيق: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * ترتيب المزوّدين ليس اعتباطاً: `Config` قبل `Session` لأن تسجيل الجهاز يقرأ
 * عقد FCM من الإعدادات، و`Session` قبل `Ride` لأن المقبس لا يُفتح بلا مستخدم.
 */

import { MotionConfig } from "framer-motion";
import { lazy, useEffect } from "react";
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
  useLocation,
} from "react-router-dom";
import type { ReactNode } from "react";

import { BottomNav } from "@/components/BottomNav";
import { WomenModeNotice } from "@/components/WomenModeNotice";
import { Toasts } from "@/components/Toasts";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { RouteTransition } from "@/components/ui/Motion";
import { BrandProvider } from "@/lib/brand";
import { ConfigProvider, useConfig } from "@/lib/config";
import { RideProvider, useRide } from "@/lib/ride";
import { PlacesProvider } from "@/lib/places";
import { SessionProvider, useSession } from "@/lib/session";
import { showsNav } from "@/lib/tabs";
import { hideSplash } from "@/lib/splash";
import { isUnlocked, play, unlock } from "@/lib/sound";
import { ThemeProvider } from "@/lib/theme";
import { bindHardwareBack } from "@/lib/hardware-back";
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

/** يفتح الصوتَ عند أوّل إيماءةٍ ويعزف توقيعَ العلامة مرةً واحدة.
 *
 * **التوقيعُ هنا لا في الشاشة الترحيبية** (قرارُ المالك §9.2): المتصفحاتُ تمنع
 * الصوتَ قبل إيماءةٍ من المستخدم، فنغمةُ الإقلاع **لا تُسمع في أوّل فتحة** —
 * وهي الفتحةُ التي يُبنى فيها الانطباعُ الأول. فتُنقل إلى أوّل لمسةٍ **بعد
 * الدخول**: أوّلُ ما يفعله صاحبُ الحساب في جلسته يُقابَل بتوقيع العلامة.
 *
 * ومرةً واحدةً في الجلسة: توقيعٌ يتكرر مع كل لمسةٍ يصير إزعاجاً لا هوية.
 */
function useSoundUnlock(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const open = () => {
      const first = !isUnlocked();
      unlock();
      // التوقيعُ بعد الفتح مباشرةً — و`isUnlocked` قبله يميّز أوّلَ لمسةٍ فعلاً
      if (first && isUnlocked()) play("signature");
    };
    // `pointerdown` لا `click`: يقع أبكر، ويكفي المتصفحَ إيماءةً
    window.addEventListener("pointerdown", open, { once: true });
    window.addEventListener("keydown", open, { once: true });
    return () => {
      window.removeEventListener("pointerdown", open);
      window.removeEventListener("keydown", open);
    };
  }, [active]);
}

function Boot({ children }: { children: ReactNode }) {
  const { config } = useConfig();
  const { loading } = useSession();

  // **الترحيبيةُ تُزال حين ينتهي الإقلاع** (`DESIGN.md` §7.5) — سواءٌ انتهى
  // بنجاحٍ أو بخطأ: شاشةُ خطأٍ تحت شاشةٍ ترحيبيةٍ باقيةٍ خطأٌ لا يراه أحد
  const booted = Boolean(config) && !loading;
  useEffect(() => {
    // **لا تُزال عند الخطأ**: الترحيبيةُ نفسُها هي من يعرض حالَ الشبكة الآن
    // (`DESIGN.md` §7.8) — تُبقي الشعارَ والدورانَ ونصَّ السبب وزرَّ المحاولة.
    // وكانت تُزال هنا حين كان الخطأُ يعني شاشةً بديلة، فصار إزالتُها تُدخل
    // المستخدمَ إلى واجهةٍ فارغة — وهو بعينه ما طُلب منعُه
    if (booted) hideSplash();
  }, [booted]);

  // الإعدادات شرطٌ لرسم شاشة الدخول نفسها (أيُّ مُحقِّق، وأيُّ دول)
  // **ولا شاشةَ خطأٍ ثانية**: الترحيبيةُ باقيةٌ فوق كل شيء وتحمل السببَ
  // وزرَّ المحاولة (§7.8)، وشاشةٌ تحتها لا يراها أحد
  if (!config) return null;

  // **ولا شاشةَ انتظارٍ ثانية**: الترحيبيةُ ما زالت فوق كل شيء حتى الآن،
  // وشاشتان متتاليتان تُقرآن تعثّراً (§7.5)
  if (!config || loading) return null;

  return <>{children}</>;
}

function Guarded({ children }: { children: ReactNode }) {
  const { user } = useSession();
  // **بعد الدخول وحدَه**: التوقيعُ هويةُ من دخل، لا صوتٌ يُقابل به من يكتب كلمةَ مروره
  useSoundUnlock(Boolean(user));
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

function Anonymous({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

/** الشريطُ **خارج الحركة وفوقها** — وهذا شرطُ انزلاق الحبّة لا تنميق.
 *
 * كان كلُّ شاشةٍ ترسم شريطَها، فمع كلِّ تنقّلٍ يُفكَّك شريطٌ ويُركَّب آخر —
 * و`layoutId` لا يقيس بين عنصرين لم يجتمعا في لحظة، فتقفز الحبّةُ ولا تنزلق.
 * قِيس: ثلاثةُ مواضعَ في تطبيق الراكب ولا موضعَ في الكبتن.
 *
 * وهو خارج `RouteTransition` كذلك كي **لا ينزلق مع الصفحة**: شريطُ تنقّلٍ
 * يسافر مع ما ينقلك إليه يُقرأ جزءاً من الصفحة لا ثابتاً فوقها.
 */
/** زرُّ الجهاز يُربط هنا لا في `main.tsx`: القاعدةُ تقرأ تاريخَ الملاح،
 *  فلا معنى لها خارج `Router`. */
function HardwareBack() {
  useEffect(() => bindHardwareBack(), []);
  return null;
}

function NavBar() {
  const { pathname } = useLocation();
  // **ولا إشعارَ فوق قرار**: رحلةٌ جاريةٌ تعني ورقةَ تتبّعٍ فيها «إلغاء»
  // و«أرسل تفاصيل رحلتك» — وتعريفٌ بمفتاحٍ يقف فوق أحدهما يُقرأ عطباً.
  // القاعدةُ نفسُها في تطبيق الكبتن، وهناك قِيست مرتين
  const { ride } = useRide();
  if (ride !== null) return null;
  return (
    <>
      <WomenModeNotice />
      {showsNav(pathname) ? <BottomNav /> : null}
    </>
  );
}

/** يلفّ الشاشاتِ بحدِّ خطأ، ويصفّره عند كل تنقّل — فرسالةُ عطبٍ في شاشةٍ
 *  لا تبقى على التي بعدها. */
function BoundaryByRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}

export default function App() {
  // **`reducedMotion="user"` من مكانٍ واحد** (§8): كلُّ حركةِ Framer في التطبيق
  // تصير فوريةً لمن طلب تقليلَ الحركة، بلا أن يفحص مكوّنٌ واحدٌ التفضيل
  return (
    <MotionConfig reducedMotion="user">
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
                  {/* **الحركةُ فوق `Suspense` لا تحته** (`ui/Motion.tsx`):
                      البديلُ فوقها كان يستبدل الشجرةَ المتحركةَ كلَّها فيموت
                      الانتقال — قِيس في المتصفح. و`Routes` مُثبَّتةٌ على الموقع
                      الذي تحمله الورقةُ الخارجة، وإلا رسمت الخارجةُ الداخلةَ */}
                  {/* **حدُّ الخطأ حول الشاشات** — لا فوق المزوّدين: خطأُ
                      شاشةٍ يُستبدل بها وحدها وتبقى السِمةُ والجلسةُ والشريط.
                      و`resetKey` المسارُ نفسُه، فلا تعلق الرسالةُ بعد تنقّل */}
                  <BoundaryByRoute>
                  <RouteTransition>
                    {(animated) => (
                    <Routes location={animated}>
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
                    )}
                  </RouteTransition>
                  </BoundaryByRoute>
                  <HardwareBack />
                  <NavBar />
                </Router>
              </RideProvider>
              </PlacesProvider>
            </Boot>
          </BrandProvider>
        </SessionProvider>
      </ConfigProvider>
      </ThemeProvider>
    </MotionConfig>
  );
}
