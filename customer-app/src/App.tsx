/** جذر التطبيق: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * ترتيب المزوّدين ليس اعتباطاً: `Config` قبل `Session` لأن تسجيل الجهاز يقرأ
 * عقد FCM من الإعدادات، و`Session` قبل `Ride` لأن المقبس لا يُفتح بلا مستخدم.
 */

import { MotionConfig } from "framer-motion";
import { Suspense, useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

// **`lazy` مُغلَّفٌ بإعادةٍ واحدة** (`lib/chunk-retry.ts`): حزمةٌ كسولةٌ
// باسمٍ زال بعد رفعٍ تُعيد الصفحةَ مرّةً لتجلب `index` الجديد. والتغليفُ
// هنا لا في مواضع النداء — **فما يُطبَّق في موضعٍ لا يُنسى في الثامن
// والسبعين**، وهي مواضعُ `lazy` في هذه الملفّات الثلاثة.
import { lazyChunk as lazy } from "@/lib/chunk-retry";
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import type { ReactNode } from "react";

import { BottomNavT2 } from "@/components/BottomNavT2";
import { Welcome, type WelcomeNext } from "@/components/welcome/Welcome";
import { setWelcomeOpen, subscribeWelcome, welcomeRequests } from "@/components/welcome/gate";
import { tokens } from "@/api/client";
import { StaleShellNotice } from "@/components/StaleShellNotice";
import { WomenModeNotice } from "@/components/WomenModeNotice";
import { Toasts } from "@/components/Toasts";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { RouteTransition } from "@/components/ui/Motion";
import { BrandProvider } from "@/lib/brand";
import { ConfigProvider, useConfig } from "@/lib/config";
import { RideProvider, useRide } from "@/lib/ride";
import { PlacesProvider } from "@/lib/places";
import { SessionProvider, useSession } from "@/lib/session";
import { RestoreAccountScreen } from "@/screens/RestoreAccount";
import { showsNav } from "@/lib/tabs";
import { useNavCovered } from "@/lib/navCover";
import { isUnlocked, play, unlock } from "@/lib/sound";
import { ThemeProvider } from "@/lib/theme";
import { UpdateGate } from "@/lib/update-gate";
import { bindHardwareBack } from "@/lib/hardware-back";
import { LoginScreen } from "@/screens/Login";

// شاشة الدخول وحدها تُحمَّل مباشرةً؛ وما عداها كسولٌ. والرئيسية أهمُّها:
// تجرّ `mapbox-gl` (نحو 1.8 ميغابايت) وهو أكبر من التطبيق كله، فتحميلُها
// مع الحزمة الأولى يعني محرّك خرائطٍ ينتظره من جاء ليسجّل دخوله فقط.
const DriverNotInstalledScreen = lazy(() =>
  import("@/screens/SwitchApp").then((m) => ({ default: m.DriverNotInstalledScreen })),
);
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
const LegalT2Screen = lazy(() =>
  import("@/screens/t2/LegalT2").then((m) => ({ default: m.LegalT2Screen })),
);
const HelpT2Screen = lazy(() =>
  import("@/screens/t2/HelpT2").then((m) => ({ default: m.HelpT2Screen })),
);
const RideDetailsScreen = lazy(() =>
  import("@/screens/RideDetails").then((m) => ({
    default: m.RideDetailsScreen,
  })),
);
const PaymentScreen = lazy(() =>
  import("@/screens/Payment").then((m) => ({ default: m.PaymentScreen })),
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
const DeleteAccountScreen = lazy(() =>
  import("@/screens/DeleteAccount").then((m) => ({
    default: m.DeleteAccountScreen,
  })),
);
const CardsScreen = lazy(() =>
  import("@/screens/Cards").then((m) => ({ default: m.CardsScreen })),
);
const SettingsScreen = lazy(() =>
  import("@/screens/Settings").then((m) => ({ default: m.SettingsScreen })),
);
const RatingT2Screen = lazy(() =>
  import("@/screens/t2/RatingT2").then((m) => ({ default: m.RatingT2Screen })),
);
const AccountT2Screen = lazy(() =>
  import("@/screens/t2/AccountT2").then((m) => ({ default: m.AccountT2Screen })),
);
const WalletT2Screen = lazy(() =>
  import("@/screens/t2/WalletT2").then((m) => ({ default: m.WalletT2Screen })),
);
const RidesT2Screen = lazy(() =>
  import("@/screens/t2/RidesT2").then((m) => ({ default: m.RidesT2Screen })),
);
const NotificationsT2Screen = lazy(() =>
  import("@/screens/t2/NotificationsT2").then((m) => ({
    default: m.NotificationsT2Screen,
  })),
);
const ReferralsScreen = lazy(() =>
  import("@/screens/Referrals").then((m) => ({ default: m.ReferralsScreen })),
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
const WomenServiceT2Screen = lazy(() =>
  import("@/screens/t2/WomenServiceT2").then((m) => ({ default: m.WomenServiceT2Screen })),
);
const PublicTrackScreen = lazy(() =>
  import("@/screens/t2/PublicTrackT2").then((m) => ({ default: m.PublicTrackScreen })),
);

/** **رابطُ التتبّع العامّ** «/t/:token» (§٦٣-ج/١) — يفتحه **من لا حسابَ له** في متصفّحٍ عاديّ.
 *
 * **شجرةٌ وحدَها لا مسارٌ بين المسارات**: داخل الشجرة الأمّ يقف أمامه ثلاثة — `Boot` ينتظر الجلسة، **والترحيبُ يغطّي كلَّ
 * شيءٍ ثمّ يحوّل غيرَ الداخل إلى «الدخول»** (`WelcomeGate`)، و`*` يعيد كلَّ مسارٍ لا يُعرف إلى `/` المحروس. وفتحُ ثلاثتها
 * لمسارٍ واحدٍ يعني ثلاثةَ استثناءاتٍ في ثلاثة مواضع، **ويكفي أن يُنسى أحدُها ليصير الرابطُ شاشةَ دخول**.
 *
 * **فيُرسم بالسِمة والإعدادات وحدهما**: السِمةُ لألوان الهوية، و`GET /config` العامُّ لتوكن الخريطة — **ولا جلسةَ ولا مقبس
 * ولا تسجيلَ جهاز**: زائرُ رابطٍ ليس مستخدماً للتطبيق. */
function isPublicTrack(pathname: string): boolean {
  return /^\/t\/[^/]+\/?$/.test(pathname);
}

function PublicTrackApp() {
  return (
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <ConfigProvider>
          <Router>
            <ErrorBoundary resetKey="public-track">
              <Suspense fallback={null}>
                <Routes>
                  <Route path="/t/:token" element={<PublicTrackScreen />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </Router>
        </ConfigProvider>
      </ThemeProvider>
    </MotionConfig>
  );
}

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

/** **اكتمالُ الإقلاع**: `/config` والجلسة — وقبله لا شاشةَ تُرسم تحت الترحيب. */
function useBooted(): boolean {
  const { config } = useConfig();
  const { loading } = useSession();
  return Boolean(config) && !loading;
}

function Boot({ children }: { children: ReactNode }) {
  // **ولا شاشةَ خطأٍ ولا انتظارٍ ثانية**: الترحيبُ فوق كلِّ شيءٍ حتى يكتمل الإقلاع، **وهو الذي يرسم حالَ الشبكة وزرَّ المحاولة**
  // (`lib/splash.ts`، §٦٢/١) — وشاشةٌ تحته لا يراها أحد، وشاشتان متتاليتان تُقرآن تعثّراً (§7.5)
  if (!useBooted()) return null;
  return <>{children}</>;
}

function Guarded({ children }: { children: ReactNode }) {
  const { user } = useSession();
  // **بعد الدخول وحدَه**: التوقيعُ هويةُ من دخل، لا صوتٌ يُقابل به من يكتب كلمةَ مروره
  useSoundUnlock(Boolean(user));
  if (!user) return <Navigate to="/login" replace />;
  // **حسابٌ في مهلة الحذف يرى شاشةَ الاستعادة وحدَها** (SPEC §59-ج) — والقرارُ
  // من الجلسة نفسِها لا من نداءٍ ثانٍ. **ولا بابَ آخرَ للراكب في المهلة**:
  // الخلفيةُ تردّ الرحلةَ والجهازَ، والشاشةُ لا تَعِد بما يُردّ.
  if (user.deletion_due_at) return <RestoreAccountScreen dueAt={user.deletion_due_at} />;
  return <>{children}</>;
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
  // **وأطوارُ الطلب في الرئيسية** (R06) حالٌ داخل `/` لا مسار — فتقول هي ما تغطّيه (`lib/navCover`)
  const coveredByScreen = useNavCovered();
  if (ride !== null) return null;
  // **وشاشاتُ TAXO 2.0 التي لا شريطَ فيها في اللوحة** (R14 · R06) تغطّيه — **في المظهرين** (§٦٢/٣)
  const coveredByT2 = T2_COVERING.includes(pathname) || coveredByScreen;
  return (
    <>
      <WomenModeNotice />
      {/* **والنسخةُ المحفوظةُ تُقال** حين عرضها العاملُ بعد مهلته (§٦٢-د/٦) */}
      <StaleShellNotice />
      {/* **وشريطُ TaxoTabs في المظهرين** — كان القائمُ يُرسم في الليليّ (`ByTheme`)، والوجهاتُ هي هي (`lib/tabs.ts`) */}
      {showsNav(pathname) && !coveredByT2 ? <BottomNavT2 /> : null}
    </>
  );
}

/** المساراتُ التي ترسمها لوحةُ TAXO 2.0 **بلا شريط تبويب** — R14 «الإشعارات». */
const T2_COVERING = ["/account/notifications"];


/** **الترحيبُ عند كلِّ فتحة — وهو شاشةُ الإقلاع نفسُها** (TAXO 2.0، البندان ١٠ و١١، و§٦٢/١ و/١٠).
 *
 * **يُركَّب من أوّل رسمٍ لا بعد الإقلاع**: كان داخل `Boot` فيُرسم بعد `/config` والجلسة — **وقبله «ترحيبيةٌ» قديمةٌ في `index.html`**،
 * فرأى المالكُ القديمَ ثمّ الجديدَ في كلِّ فتحة. **والآن يحلّ محلَّ إطار الإقلاع** (أوّلُ إطارٍ منه بعينه)، **ويبقى حتى يكتمل الإقلاع**
 * وحالُ الشبكة عليه — ثمّ: **داخلٌ ⇒ يذوب** · **غيرُ داخلٍ ⇒ «حساب جديد» أو «دخول»** إلى شاشتيهما.
 *
 * فوق المسارات لا مساراً بينها: الشاشةُ التي تحته تُرسم في الوقت نفسِه، **فلا انتظارَ بعد أن يمضي**. **وسهمُ الرجوع في الدخول
 * والتسجيل يعيده** (`gate.ts`) إلى زرّيه بلا حركة.
 */
function WelcomeGate() {
  const { user, biometry } = useSession();
  const booted = useBooted();
  const navigate = useNavigate();
  // **ما يُعرف قبل الإقلاع** يختار الطورَ الأوّلَ وحدَه: رمزٌ محفوظٌ يعني عائداً — والفرعُ الأخيرُ من الجلسة بعد الإقلاع
  const heldToken = useRef(Boolean(tokens.access())).current;
  // **وصاحبُ البصمة عائدٌ لا جديد**: جلستُه محفوظةٌ خلف بصمته، وشاشةُ الدخول تحمل زرَّها — فيرى ما يراه الداخلُ ويمضي إليها
  const armed = Boolean(biometry?.available && biometry.armed);
  const signedIn = Boolean(user);
  const [shown, setShown] = useState(true);
  const [reopened, setReopened] = useState(false);
  useEffect(() => setWelcomeOpen(shown), [shown]);
  const requests = useSyncExternalStore(subscribeWelcome, welcomeRequests);
  const seen = useRef(requests);
  useEffect(() => {
    if (requests === seen.current) return;
    seen.current = requests;
    setReopened(true);
    setShown(true);
  }, [requests]);
  const done = useCallback(
    (next?: WelcomeNext) => {
      setShown(false);
      setReopened(false);
      if (signedIn) return;
      navigate(next ?? "/login", { replace: true });
    },
    [signedIn, navigate],
  );
  if (!shown) return null;
  return (
    <Welcome
      key={reopened ? `again-${requests}` : "boot"}
      booted={booted}
      signedIn={signedIn || armed}
      returning={heldToken || armed}
      reopened={reopened}
      onDone={done}
    />
  );
}

/** يلفّ الشاشاتِ بحدِّ خطأ، ويصفّره عند كل تنقّل — فرسالةُ عطبٍ في شاشةٍ
 *  لا تبقى على التي بعدها. */
function BoundaryByRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}

export default function App() {
  // **رابطُ التتبّع العامّ قبل الإقلاع كلِّه** — شجرتُه وحدَها (`PublicTrackApp`)
  if (isPublicTrack(window.location.pathname)) return <PublicTrackApp />;
  // **`reducedMotion="user"` من مكانٍ واحد** (§8): كلُّ حركةِ Framer في التطبيق
  // تصير فوريةً لمن طلب تقليلَ الحركة، بلا أن يفحص مكوّنٌ واحدٌ التفضيل
  return (
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
      {/* **بوّابةُ التحديث فوق كلِّ شيءٍ إلا السِمة** (البند ٨، §43): من
          حزمتُه دون الحدِّ **لا يصل شاشةَ الدخول أصلاً**، فلا معنى لوضعها
          تحت الجلسة. وتحت السِمة لأنها ترسم شاشةً بألوان النظام */}
      <UpdateGate app="rider">
      <ConfigProvider>
        <SessionProvider>
          {/* تحت الجلسة والإعدادات: السِمة تُقرأ من إعلان صاحبة الحساب ومن
              مفتاح دولتها، فلا معنى لها قبلهما */}
          <BrandProvider>
            <Router>
            <Boot>
              {/* تحت الجلسة: الأماكنُ والوجهاتُ الأخيرة كلاهما لحسابٍ بعينه */}
              <PlacesProvider>
              <RideProvider>
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
                      <Route path="/account/switch/driver-not-installed" element={<DriverNotInstalledScreen />} />

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
                            <RidesT2Screen />
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
                            {/* **نهايةُ الرحلة «R10» في المظهرين** — المنطقُ واحد (`useRating`) */}
                            <RatingT2Screen />
                          </Guarded>
                        }
                      />
                      <Route
                        path="/wallet"
                        element={
                          <Guarded>
                            <WalletT2Screen />
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
                            <AccountT2Screen />
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
                        path="/account/referrals"
                        element={
                          <Guarded>
                            <ReferralsScreen />
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
                            <NotificationsT2Screen />
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
                      {/* **حذفُ الحساب بعد مهلة** (SPEC §59) — حلّ محلَّ «إغلاق
                          الحساب»، والبابُ `‎/account/deletion` للدورين */}
                      <Route
                        path="/account/delete"
                        element={
                          <Guarded>
                            <DeleteAccountScreen />
                          </Guarded>
                        }
                      />
                      {/* **«الشروط والخصوصية»** (§٦١-ط/٣) — صفحةٌ واحدةٌ للوجهين تتبع المظهرَ القائم */}
                      <Route
                        path="/account/legal"
                        element={
                          <Guarded>
                            <LegalT2Screen />
                          </Guarded>
                        }
                      />
                      {/* **«المساعدة والدعم»** (R30، §٦٢-ج/١٦) — الأسئلةُ وبريدُ الدعم من إعدادات الموقع، **والشريطُ تحتها كأخواتها** */}
                      <Route
                        path="/account/help"
                        element={
                          <Guarded>
                            <HelpT2Screen />
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
                      {/* **الخدمةُ النسائية** (RW1، §٦٢-ج/٢٣) — من بطاقتها في «حسابي»، **والشريطُ تحتها كأخواتها** */}
                      <Route
                        path="/account/women"
                        element={
                          <Guarded>
                            <WomenServiceT2Screen />
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
              </RideProvider>
              </PlacesProvider>
            </Boot>
            {/* **فوق `Boot` لا داخلَه**: يُرسم من أوّل إطار ويبقى حتى يكتمل الإقلاع (§٦٢/١) */}
            <WelcomeGate />
            </Router>
          </BrandProvider>
        </SessionProvider>
      </ConfigProvider>
      </UpdateGate>
      </ThemeProvider>
    </MotionConfig>
  );
}
