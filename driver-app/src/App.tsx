/** جذر التطبيق: المزوّدون، والمسارات، وحارسُ الجلسة.
 *
 * ترتيب المزوّدين ليس اعتباطاً: `Config` قبل `Session` لأن تسجيل الجهاز يقرأ
 * عقد FCM من الإعدادات، و`Driver` و`Ride` تحتهما لأنهما لا يعملان بلا
 * مستخدم. والمظهرُ فوق الكل لأنه يُرسم قبل أن تصل أيُّ بيانات.
 *
 * **ما هو مبنيٌّ الآن**: الدخول واستعادة كلمة المرور، والتسجيل بخطواته
 * الثلاث، والرئيسيةُ ببطاقة الطلب والرحلة الجارية، والاشتراك، وسجلُّ الرحلات
 * بتفاصيله ونزاعه، والمحفظةُ بطلبات سحبها، وحسابي بإعداداته ومركبته وبطاقاته.
 * والإشعاراتُ وبطاقةُ تأكيد حوالة كليك. وبذلك تمّت شاشات المرحلة 10.
 *
 * وحالةُ الكبتن هي ما يقرّر أيَّ شاشةٍ يرى بعد الدخول: غيرُ المعتمد يرى «قيد
 * المراجعة» ولا يرى الرئيسية — لا لأننا نخفيها، بل لأن التوزيع لا يعرفه
 * أصلاً (`dispatch.eligible_driver_ids`).
 */

import { MotionConfig } from "framer-motion";
import { lazy, useEffect } from "react";
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import type { ReactNode } from "react";

import { CenteredMessage, Spinner } from "@/components/ui/Feedback";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { RouteTransition } from "@/components/ui/Motion";
import { WomenModeNotice } from "@/components/WomenModeNotice";
import { BrandProvider } from "@/lib/brand";
import { ConfigProvider, useConfig } from "@/lib/config";
import { hideSplash } from "@/lib/splash";
import { isUnlocked, play, unlock } from "@/lib/sound";
import { DriverProvider, useDriver } from "@/lib/driver";
import { GarageProvider } from "@/lib/garage";
import { RideProvider, useRide } from "@/lib/ride";
import { SessionProvider, useSession } from "@/lib/session";
import { WelcomeSheet } from "@/components/WelcomeSheet";
import { CelebrationSheet } from "@/components/skins/CelebrationSheet";
import { BottomNav } from "@/components/BottomNav";
import { showsNav } from "@/lib/tabs";
import { ThemeProvider } from "@/lib/theme";
import { bindHardwareBack } from "@/lib/hardware-back";
import { destinationFor } from "@/lib/notification-route";
import { listenToPush } from "@/lib/push";
import { LoginScreen } from "@/screens/Login";

const RiderNotInstalledScreen = lazy(() =>
  import("@/screens/SwitchApp").then((m) => ({ default: m.RiderNotInstalledScreen })),
);
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
const RidesScreen = lazy(() =>
  import("@/screens/Rides").then((m) => ({ default: m.RidesScreen })),
);
const RideDetailsScreen = lazy(() =>
  import("@/screens/RideDetails").then((m) => ({
    default: m.RideDetailsScreen,
  })),
);
const DisputeScreen = lazy(() =>
  import("@/screens/Dispute").then((m) => ({ default: m.DisputeScreen })),
);
const WalletScreen = lazy(() =>
  import("@/screens/Wallet").then((m) => ({ default: m.WalletScreen })),
);
const EarningsScreen = lazy(() =>
  import("@/screens/Earnings").then((m) => ({ default: m.EarningsScreen })),
);
const WithdrawalsScreen = lazy(() =>
  import("@/screens/Withdrawals").then((m) => ({
    default: m.WithdrawalsScreen,
  })),
);
const AccountScreen = lazy(() =>
  import("@/screens/Account").then((m) => ({ default: m.AccountScreen })),
);
const SettingsScreen = lazy(() =>
  import("@/screens/Settings").then((m) => ({ default: m.SettingsScreen })),
);
const VehicleScreen = lazy(() =>
  import("@/screens/Vehicle").then((m) => ({ default: m.VehicleScreen })),
);
const CardsScreen = lazy(() =>
  import("@/screens/Cards").then((m) => ({ default: m.CardsScreen })),
);
const DeactivationScreen = lazy(() =>
  import("@/screens/Deactivation").then((m) => ({
    default: m.DeactivationScreen,
  })),
);
const AdvancesScreen = lazy(() =>
  import("@/screens/Advances").then((m) => ({
    default: m.AdvancesScreen,
  })),
);
const MissionsScreen = lazy(() =>
  import("@/screens/Missions").then((m) => ({ default: m.MissionsScreen })),
);
const ReferralsScreen = lazy(() =>
  import("@/screens/Referrals").then((m) => ({ default: m.ReferralsScreen })),
);
const CardReturnScreen = lazy(() =>
  import("@/screens/CardReturn").then((m) => ({ default: m.CardReturnScreen })),
);
const NotificationsScreen = lazy(() =>
  import("@/screens/Notifications").then((m) => ({
    default: m.NotificationsScreen,
  })),
);
const SubscriptionScreen = lazy(() =>
  import("@/screens/Subscription").then((m) => ({
    default: m.SubscriptionScreen,
  })),
);
const GarageScreen = lazy(() =>
  import("@/screens/Garage").then((m) => ({ default: m.GarageScreen })),
);
const SkinStoreScreen = lazy(() =>
  import("@/screens/SkinStore").then((m) => ({ default: m.SkinStoreScreen })),
);

function Loading() {
  return (
    <CenteredMessage>
      <Spinner />
    </CenteredMessage>
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

function Boot({ children }: { children: ReactNode }) {
  const { config } = useConfig();
  const { loading } = useSession();

  // **الترحيبيةُ تُزال حين ينتهي الإقلاع** (`DESIGN.md` §7.5) — بنجاحٍ أو بخطأ
  const booted = Boolean(config) && !loading;
  useEffect(() => {
    // **لا تُزال عند الخطأ**: الترحيبيةُ نفسُها هي من يعرض حالَ الشبكة الآن
    // (`DESIGN.md` §7.8) — تُبقي الشعارَ والدورانَ ونصَّ السبب وزرَّ المحاولة.
    // وكانت تُزال هنا حين كان الخطأُ يعني شاشةً بديلة، فصار إزالتُها تُدخل
    // المستخدمَ إلى واجهةٍ فارغة — وهو بعينه ما طُلب منعُه
    if (booted) hideSplash();
  }, [booted]);

  // الإعدادات شرطٌ لرسم شاشة الدخول نفسها: منها يُعرف أيُّ مُحقِّقٍ يرسم
  // **ولا شاشةَ خطأٍ ثانية**: الترحيبيةُ باقيةٌ فوق كل شيء وتحمل السببَ
  // وزرَّ المحاولة (§7.8)، وشاشةٌ تحتها لا يراها أحد
  if (!config) return null;

  // **ولا شاشةَ انتظارٍ ثانية**: الترحيبيةُ ما زالت فوق كل شيء (§7.5)
  if (!config || loading) return null;

  return <>{children}</>;
}

function Anonymous({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

function Guarded({ children }: { children: ReactNode }) {
  const { user } = useSession();
  // **بعد الدخول وحدَه**: التوقيعُ هويةُ من دخل، لا صوتٌ يُقابل به من يكتب كلمةَ مروره
  useSoundUnlock(Boolean(user));
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

/** جذرُ الكبتن: المعتمد يرى الرئيسية، ومن لم يُقدّم بعدُ يُساق إلى خطوته
 *  الثالثة، ومن قدّم يرى سببَ انتظاره.
 *
 * **والقرارُ هنا لا في تنقّلٍ بعد التسجيل**، وهذا ما وجدته المرحلةُ ١٣: شاشةُ
 * «الخطوة ٣ من ٣» كاملةٌ ولا بابَ إليها إلا سطرُ `navigate` في نهاية التسجيل —
 * فإذا سبقَه `Anonymous` بردِّه إلى الجذر (والجلسةُ صارت قائمة) هبط الكبتنُ على
 * «طلبك قيد المراجعة» **بلا مركبةٍ ولا مستند**: تُراجَع الإدارةُ ما لا وجودَ
 * له، ولا زرَّ في التطبيق كلِّه يوصله إلى الرفع. وهي قاعدةٌ بلا باب بعينها.
 *
 * **ومن لا مركبةَ له لم يبدأ أصلاً**: المركبةُ أوّلُ ما تُنشئه تلك الشاشة، فلا
 * تحتاج نداءَ مستنداتٍ ثانياً لتعرف — والملفُّ محمولٌ أصلاً.
 */
function DriverHome() {
  const { profile, loading } = useDriver();

  if (loading || !profile) return <Loading />;
  // **الورقةُ عند نفس النقطة التي تقرّر «معتمد»** — لا شرطٌ ثانٍ في مكوّنٍ آخر
  // يمكن أن يفترق عنه. ومن ليس معتمداً لا يراها أصلاً، وهو المقصود: تُعرض
  // **بعد الاعتماد** لا عند التسجيل (قرارُ المالك)
  if (profile.driver.status === "approved")
    return (
      <>
        <HomeScreen />
        <WelcomeSheet />
        {/* **بعد ورقة الترحيب في ترتيب الرسم**: الاثنتان `z-50`، والأخيرةُ
            تعلو — وهديّةُ أول اشتراكٍ تقع **بعد** أن يقرأ الترحيب ويشترك،
            فالتزاحمُ نظريٌّ والترتيبُ يحسمه على كلِّ حال */}
        <CelebrationSheet />
      </>
    );
  if (profile.vehicles.length === 0)
    return <Navigate to="/register/documents" replace />;
  return <PendingScreen />;
}

/** الشريطُ **خارج الحركة وفوقها** — انظر `customer-app/src/App.tsx` لنفس العلّة:
 * شريطٌ يُفكَّك ويُركَّب مع كلِّ شاشةٍ لا تنزلق حبّتُه، لأن `layoutId` لا يقيس
 * بين عنصرين لم يجتمعا في لحظة. قِيس: لا موضعَ واحدٌ يتغيّر في هذا التطبيق.
 */
/** زرُّ الجهاز يُربط هنا لا في `main.tsx`: القاعدةُ تقرأ تاريخَ الملاح،
 *  فلا معنى لها خارج `Router`. */
function HardwareBack() {
  useEffect(() => bindHardwareBack(), []);
  return null;
}

/** نقرةُ إشعارِ النظام تفتح شاشتَه — **من نفس البيت الذي يفتحه صفُّ الوارد**.
 *
 * **ومحلُّه داخل `Router` لا في `main.tsx`**: هو يلاحُ لا يُصغي فحسب.
 *
 * **والإقلاعُ البارد يسلّم النقرةَ بعد تعليق المستمعين** — فالمكوّنُ يُركَّب
 * مع الشجرة، والإضافةُ تحتفظ بالحدث حتى يوجد من يستقبله. وهذا بعينه ما وقع
 * مقيساً في زرِّ التبديل (§23): `appUrlOpen` لا يقع في الإقلاع البارد،
 * فيُقرأ غيابُ الحدث «لم يُنقر» وهو نُقر.
 */
function PushRouter() {
  const navigate = useNavigate();
  useEffect(() => {
    let dispose: (() => void) | null = null;
    void listenToPush({
      // **والتطبيقُ مفتوح: النظامُ لا يرسم شيئاً** — وما يصل هنا يصله
      // المقبسُ أصلاً، فلا يُرسم فوقه شيءٌ ثانٍ يُقرأ حدثين لحدثٍ واحد
      received: () => undefined,
      tapped: (data) => {
        const to = destinationFor(data.type, data);
        if (to) navigate(to);
      },
    }).then((off) => {
      dispose = off;
    });
    return () => dispose?.();
  }, [navigate]);
  return null;
}

function NavBar() {
  const { pathname } = useLocation();
  // **ولا يظهر ورحلةٌ أو عرضٌ يملأ الشاشة** — وهذا سلوكٌ كان قائماً وكاد يضيع
  // حين رُفع الشريطُ من الشاشات إلى `App`: كان يُرسم في فرع «لا رحلة» وحدَه.
  // وضياعُه ليس تشويشاً بصرياً: قِيس أن `elementFromPoint` في منتصف زرِّ
  // «قبول» يعيد **الشريطَ** لا الزر — أي أن العرضَ لا يُقبل أصلاً. والسببُ
  // بنيويّ: ورقةُ المسار تحمل `transform` فتصنع سياقَ تكديسٍ خاصاً بها،
  // فـ`z-50` داخلها لا يعلو `z-30` خارجَها مهما كبر
  const { ride, offer } = useRide();
  const covered = ride !== null || offer !== null;
  if (covered) return null;
  return (
    <>
      {/* **وإشعارُ السِمة معه بالشرط نفسِه** (قِيس مرتين 2026-08-13): كان
          مثبّتاً بإزاحةٍ من الأسفل، فوقع مرةً على «ابدأ الاستقبال» ومرةً على
          سببِ «عدم التطابق» في ورقة الإلغاء — وهو أخطرُ الاثنين: كبتنةٌ ألغت
          لسببٍ أمنيٍّ لا تراه. وأيُّ إزاحةٍ ثابتةٍ ستصطدم بشيءٍ في شاشةٍ ما،
          فالقاعدةُ ليست رقماً بل شرطاً: **لا يُعرض تعريفٌ بمفتاحٍ فوق قرار**. */}
      <WomenModeNotice />
      {showsNav(pathname) ? <BottomNav /> : null}
    </>
  );
}

function BoundaryByRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}

export default function App() {
  // **`reducedMotion="user"` من مكانٍ واحد** (§8)
  return (
    <MotionConfig reducedMotion="user">
    <ThemeProvider>
      <ConfigProvider>
        <SessionProvider>
          {/* تحت الجلسة والإعدادات: السِمة تُقرأ من جنس صاحبة الحساب ومن
              مفتاح دولتها، فلا معنى لها قبلهما */}
          <BrandProvider>
            <Boot>
              <DriverProvider>
                {/* **تحت الجلسة والكبتن**: الكراجُ نداءُ كبتنٍ مسجَّل، وفوق
                    `Router` لأن الخريطةَ والورقةَ والشاشةَ ثلاثةُ قرّاءٍ
                    لجوابٍ واحد — وثلاثةُ نداءاتٍ له تفترق */}
                <GarageProvider>
                <RideProvider>
                  <Router>
                    {/* **الحركةُ فوق `Suspense` لا تحته**، و`Routes` مُثبَّتةٌ على
                        الموقع الذي تحمله الورقةُ الخارجة — نفسُ ما قِيس في تطبيق
                        الراكب: بلا الأولى يموت الانتقال عند أوّل مسارٍ كسول،
                        وبلا الثانية ترسم الورقةُ الخارجةُ الشاشةَ الداخلة */}
                    {/* **حدُّ الخطأ حول الشاشات** — انظر تطبيق الراكب:
                        استثناءٌ غيرُ ملتقَطٍ يُبيّض الشاشةَ صامتاً، وقد مرّ
                        عطبٌ ماليٌّ كذلك يوماً كاملاً */}
                    <BoundaryByRoute>
                    <RouteTransition>
                      {(animated) => (
                      <Routes location={animated}>
                        <Route path="/account/switch/rider-not-installed" element={<RiderNotInstalledScreen />} />

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
                        <Route
                          path="/subscription"
                          element={
                            <Guarded>
                              <SubscriptionScreen />
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
                          path="/rides/:rideId/dispute"
                          element={
                            <Guarded>
                              <DisputeScreen />
                            </Guarded>
                          }
                        />
                        {/* تبويبات الشريط السفلي الباقية — الجلسات التالية */}
                        <Route
                          path="/wallet"
                          element={
                            <Guarded>
                              <WalletScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/wallet/withdrawals"
                          element={
                            <Guarded>
                              <WithdrawalsScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/wallet/earnings"
                          element={
                            <Guarded>
                              <EarningsScreen />
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
                          path="/account/settings"
                          element={
                            <Guarded>
                              <SettingsScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/account/vehicle"
                          element={
                            <Guarded>
                              <VehicleScreen />
                            </Guarded>
                          }
                        />
                        {/* عنوانُ العودة من صفحة المزود — خاصٌّ بهذا التطبيق */}
                        <Route
                          path="/payments/card/return"
                          element={
                            <Guarded>
                              <CardReturnScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/notifications"
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
                          path="/account/advances"
                          element={
                            <Guarded>
                              <AdvancesScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/account/deactivation"
                          element={
                            <Guarded>
                              <DeactivationScreen />
                            </Guarded>
                          }
                        />
                        {/* **مركباتي تحت «حسابي»**: زينةٌ تُفتح عن قصدٍ لا
                            تبويبٌ يُضغط في كلِّ رحلة (نفسُ موضع «المهام») */}
                        <Route
                          path="/account/garage"
                          element={
                            <Guarded>
                              <GarageScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/account/garage/store"
                          element={
                            <Guarded>
                              <SkinStoreScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/account/missions"
                          element={
                            <Guarded>
                              <MissionsScreen />
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
                        <Route path="*" element={<Navigate to="/" replace />} />
                      </Routes>
                      )}
                    </RouteTransition>
                    </BoundaryByRoute>
                    <HardwareBack />
                    <PushRouter />
                  <NavBar />
                  </Router>
                </RideProvider>
                </GarageProvider>
              </DriverProvider>
            </Boot>
          </BrandProvider>
        </SessionProvider>
      </ConfigProvider>
    </ThemeProvider>
    </MotionConfig>
  );
}
