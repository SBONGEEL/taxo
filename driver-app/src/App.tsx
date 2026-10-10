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
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

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

import { CenteredMessage, Spinner } from "@/components/ui/Feedback";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { RouteTransition } from "@/components/ui/Motion";
import { StaleShellNotice } from "@/components/StaleShellNotice";
import { WomenModeNotice } from "@/components/WomenModeNotice";
import { BrandProvider } from "@/lib/brand";
import { ConfigProvider, useConfig, useFeature } from "@/lib/config";
import { UNCONFIRMED_FLAG, claimCaptainOpening, refreshCaptainUnconfirmed } from "@/lib/attention";
import { isUnlocked, play, unlock } from "@/lib/sound";
import { DriverProvider, useDriver } from "@/lib/driver";
import { GarageProvider } from "@/lib/garage";
import { RideProvider, useRide } from "@/lib/ride";
import { SessionProvider, useSession } from "@/lib/session";
import { RestoreAccountScreen } from "@/screens/RestoreAccount";
import { WelcomeSheet } from "@/components/WelcomeSheet";
import { Welcome, type WelcomeNext } from "@/components/welcome/Welcome";
import { setWelcomeOpen, subscribeWelcome, welcomeRequests } from "@/components/welcome/gate";
import { tokens } from "@/api/client";
import { CelebrationSheet } from "@/components/skins/CelebrationSheet";
import { BottomNavT2 } from "@/components/BottomNavT2";
import { RideComms } from "@/components/ride/RideComms";
import { showsNav } from "@/lib/tabs";
import { ThemeProvider } from "@/lib/theme";
import { UpdateGate } from "@/lib/update-gate";
import { bindHardwareBack } from "@/lib/hardware-back";
import { PermissionsIntroScreen } from "@/screens/PermissionsIntro";
import { walkDone } from "@/lib/permission-walk";
import { destinationFor } from "@/lib/notification-route";
import { routeCommsPush } from "@/lib/trip-comms";
import { listenToPush } from "@/lib/push";
import { PushNotices, presentNotice } from "@/components/PushNotices";
import { useNavCovered } from "@/lib/navCover";
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
const SettingsT2Screen = lazy(() =>
  import("@/screens/t2/SettingsT2").then((m) => ({ default: m.SettingsT2Screen })),
);
const WomenModeT2Screen = lazy(() =>
  import("@/screens/t2/WomenModeT2").then((m) => ({ default: m.WomenModeT2Screen })),
);
const MissionsT2Screen = lazy(() =>
  import("@/screens/t2/MissionsT2").then((m) => ({ default: m.MissionsT2Screen })),
);
const SubscriptionT2Screen = lazy(() =>
  import("@/screens/t2/SubscriptionT2").then((m) => ({ default: m.SubscriptionT2Screen })),
);
const ServicesT2Screen = lazy(() =>
  import("@/screens/t2/ServicesT2").then((m) => ({ default: m.ServicesT2Screen })),
);
const GuaranteesT2Screen = lazy(() =>
  import("@/screens/t2/GuaranteesT2").then((m) => ({ default: m.GuaranteesT2Screen })),
);
const CommutesT2Screen = lazy(() =>
  import("@/screens/t2/CommutesT2").then((m) => ({ default: m.CommutesT2Screen })),
);
const ServiceRouteT2 = lazy(() =>
  import("@/screens/t2/ServiceRouteT2").then((m) => ({ default: m.ServiceRouteT2 })),
);
const IntercityT2Screen = lazy(() =>
  import("@/screens/t2/IntercityT2").then((m) => ({ default: m.IntercityT2Screen })),
);
const PlansPreviewT2Screen = lazy(() =>
  import("@/screens/t2/PlansPreviewT2").then((m) => ({ default: m.PlansPreviewT2Screen })),
);
const VehicleT2Screen = lazy(() =>
  import("@/screens/t2/VehicleT2").then((m) => ({ default: m.VehicleT2Screen })),
);
const WalletT2Screen = lazy(() =>
  import("@/screens/t2/WalletT2").then((m) => ({ default: m.WalletT2Screen })),
);
const SkinStoreT2Screen = lazy(() =>
  import("@/screens/t2/SkinStoreT2").then((m) => ({ default: m.SkinStoreT2Screen })),
);
const PendingT2Screen = lazy(() =>
  import("@/screens/t2/PendingT2").then((m) => ({ default: m.PendingT2Screen })),
);
// الرئيسية تجرّ `mapbox-gl` وهو أكبر من التطبيق كله، فلا تُحمَّل مع الحزمة
// الأولى: من جاء ليسجّل دخوله لا ينتظر محرّك خرائط
// **C04–C08 في الداكن المرسوم** — الرئيسيةُ وطلبُها ورحلتُها وتحصيلُها، والمنطقُ من `useHomeScreen` نفسِه
const HomeT2Screen = lazy(() =>
  import("@/screens/t2/HomeT2").then((m) => ({ default: m.HomeT2Screen })),
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
const EarningsScreen = lazy(() =>
  import("@/screens/Earnings").then((m) => ({ default: m.EarningsScreen })),
);
const CliqSubscriptionScreen = lazy(() =>
  import("@/screens/CliqSubscription").then((m) => ({
    default: m.CliqSubscriptionScreen,
  })),
);
const WithdrawalsScreen = lazy(() =>
  import("@/screens/Withdrawals").then((m) => ({
    default: m.WithdrawalsScreen,
  })),
);
const AccountScreen = lazy(() =>
  import("@/screens/Account").then((m) => ({ default: m.AccountScreen })),
);
const CardsScreen = lazy(() =>
  import("@/screens/Cards").then((m) => ({ default: m.CardsScreen })),
);
const DeleteAccountScreen = lazy(() =>
  import("@/screens/DeleteAccount").then((m) => ({
    default: m.DeleteAccountScreen,
  })),
);
const PermissionsScreen = lazy(() =>
  import("@/screens/Permissions").then((m) => ({ default: m.PermissionsScreen })),
);
const DebtScreen = lazy(() =>
  import("@/screens/Debt").then((m) => ({ default: m.DebtScreen })),
);
const DebtCliqScreen = lazy(() =>
  import("@/screens/DebtCliq").then((m) => ({ default: m.DebtCliqScreen })),
);
const AdvancesScreen = lazy(() =>
  import("@/screens/Advances").then((m) => ({
    default: m.AdvancesScreen,
  })),
);
const ReferralsScreen = lazy(() =>
  import("@/screens/Referrals").then((m) => ({ default: m.ReferralsScreen })),
);
const CardReturnScreen = lazy(() =>
  import("@/screens/CardReturn").then((m) => ({ default: m.CardReturnScreen })),
);
const NotificationsT2Screen = lazy(() =>
  import("@/screens/t2/NotificationsT2").then((m) => ({
    default: m.NotificationsT2Screen,
  })),
);
const GarageScreen = lazy(() =>
  import("@/screens/Garage").then((m) => ({ default: m.GarageScreen })),
);
const UnconfirmedT2Screen = lazy(() =>
  import("@/screens/t2/UnconfirmedT2").then((m) => ({ default: m.UnconfirmedT2Screen })),
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

/** **اكتمالُ الإقلاع**: `/config` والجلسة — وقبله لا شاشةَ تُرسم تحت الترحيب. */
function useBooted(): boolean {
  const { config } = useConfig();
  const { loading } = useSession();
  return Boolean(config) && !loading;
}

function Boot({ children }: { children: ReactNode }) {
  // **ولا شاشةَ خطأٍ ولا انتظارٍ ثانية**: الترحيبُ فوق كلِّ شيءٍ حتى يكتمل الإقلاع، **وهو الذي يرسم حالَ الشبكة وزرَّ المحاولة**
  // (`lib/splash.ts`، §٦٢/١) — والإعداداتُ شرطٌ لرسم شاشة الدخول نفسِها (أيُّ مُحقِّقٍ يُرسم)
  if (!useBooted()) return null;
  return <>{children}</>;
}

function Anonymous({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

/** **ما يبقى مفتوحاً للكبتن في مهلة الحذف** (SPEC §59-ج): المحفظةُ وحدَها —
 *  **المهلةُ وقتُ سحب رصيده**، ولا يُحذف حسابٌ فيه رصيد. */
const OPEN_DURING_DELETION = ["/wallet"];

function Guarded({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const { pathname } = useLocation();
  // **بعد الدخول وحدَه**: التوقيعُ هويةُ من دخل، لا صوتٌ يُقابل به من يكتب كلمةَ مروره
  useSoundUnlock(Boolean(user));
  if (!user) return <Navigate to="/login" replace />;
  if (user.deletion_due_at && !OPEN_DURING_DELETION.some((path) => pathname.startsWith(path))) {
    return <RestoreAccountScreen dueAt={user.deletion_due_at} />;
  }
  return <>{children}</>;
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
  // **جولةُ أوّل فتحٍ تسبق الرئيسية** (قرارُ المالك 2026-09-11): تُعرض مرّةً
  // واحدةً بعد التثبيت، **ولمن اكتملت أذونُه لا تُعرض أصلاً** — الشاشةُ نفسُها
  // تقفز إذا لم ينقص شيء، فلا شرطَ ثانٍ هنا يمكن أن يفترق عنها.
  if (profile.driver.status === "approved" && !walkDone())
    return <PermissionsIntroScreen />;
  if (profile.driver.status === "approved")
    return (
      <>
        {/* **C04–C08 في المظهرين** (§٦٢/٣) — كانت الرئيسيةُ القديمةُ في الفاتح */}
        <HomeT2Screen />
        <WelcomeSheet />
        {/* **بعد ورقة الترحيب في ترتيب الرسم**: الاثنتان `z-50`، والأخيرةُ
            تعلو — وهديّةُ أول اشتراكٍ تقع **بعد** أن يقرأ الترحيب ويشترك،
            فالتزاحمُ نظريٌّ والترتيبُ يحسمه على كلِّ حال */}
        <CelebrationSheet />
      </>
    );
  if (profile.vehicles.length === 0)
    return <Navigate to="/register/documents" replace />;
  // **C03 في المظهرين** (§٦٢/٣) — كانت القائمةُ القديمةُ في الفاتح
  return <PendingT2Screen />;
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

/** **«ركّابٌ ينتظرون تأكيدك» عند كلِّ فتح** (`design/PAYMENTS-UNCONFIRMED.md` §٦، SPEC §٦٤-ز) — **بعد الترحيب وقبل الرئيسية**:
 *  الترحيبُ فوق المسارات كلِّها، فالصفحةُ تُفتح تحته وتظهر لحظةَ يذوب.
 *
 *  **مرّةً للفتحة** (`claimCaptainOpening`)، **وللمعتمد الذي أتمّ جولةَ أذوناته وحدَه** — شرطُ `DriverHome` بحرفه: الجولةُ تسبق
 *  الرئيسيةَ ولا تُغطّى. **ولا تُفتح فوق طلبٍ واردٍ أو رحلةٍ جارية**: بطاقةُ العرض بمهلتها أَولى، والفتحةُ تنتظر أن تصفو الرئيسية.
 *  **ومطفأً لا نداءَ أصلاً.** */
function CaptainUnconfirmedOpening() {
  const { user } = useSession();
  const { profile } = useDriver();
  const { ride, offer } = useRide();
  const enabled = useFeature(user?.country_code, UNCONFIRMED_FLAG);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  // **أين هو حين يصل الجواب** لا حين سُئل — من انتقل أو وصله عرضٌ في أثناء النداء لا يُنتزع منه
  const here = useRef({ pathname, busy: false });
  here.current = { pathname, busy: ride !== null || offer !== null };
  const owner =
    user && !user.deletion_due_at && profile?.driver.status === "approved" && walkDone() ? user.id : null;
  const busy = ride !== null || offer !== null;
  useEffect(() => {
    if (owner === null || !enabled || busy || pathname !== "/") return;
    if (!claimCaptainOpening(owner)) return;
    refreshCaptainUnconfirmed(owner)
      .then((data) => {
        if (here.current.pathname === "/" && !here.current.busy && data.items.length > 0) {
          navigate("/payments/unconfirmed");
        }
      })
      .catch(() => undefined);
  }, [owner, enabled, busy, pathname, navigate]);
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
      // **والتطبيقُ مفتوح: النظامُ لا يرسم شيئاً** — فيُرسم هنا بلاغٌ بصوته
      // (§٦١-ل/٣)، **من البابِ نفسِه الذي يرسم بلاغَ المقبس** (`presentNotice`)
      // — فلا يُرسم حدثٌ واحدٌ مرّتين إن وصل من الطريقين معاً.
      received: (data, { title, body }) => presentNotice({ title, body, data }),
      tapped: (data) => {
        // **نقرةُ رسالةٍ أو مكالمة** (§٦٦) تفتح المحادثةَ أو شاشةَ الرنين فوق ما هو أمامه — لا صفحةَ الرحلة
        if (routeCommsPush(data, "tap")) return;
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

/** المساراتُ التي ترسمها لوحةُ TAXO 2.0 **بلا شريط تبويب** — «C10» زرُّها في القاع، والرجوعُ يعيد إلى الشريط. **في المظهرين**. */
const T2_COVERING = ["/subscription"];

function NavBar() {
  const { pathname } = useLocation();
  // **ولا يظهر ورحلةٌ أو عرضٌ يملأ الشاشة** — وهذا سلوكٌ كان قائماً وكاد يضيع
  // حين رُفع الشريطُ من الشاشات إلى `App`: كان يُرسم في فرع «لا رحلة» وحدَه.
  // وضياعُه ليس تشويشاً بصرياً: قِيس أن `elementFromPoint` في منتصف زرِّ
  // «قبول» يعيد **الشريطَ** لا الزر — أي أن العرضَ لا يُقبل أصلاً. والسببُ
  // بنيويّ: ورقةُ المسار تحمل `transform` فتصنع سياقَ تكديسٍ خاصاً بها،
  // فـ`z-50` داخلها لا يعلو `z-30` خارجَها مهما كبر
  const { ride, offer } = useRide();
  const { profile } = useDriver();
  // **وشاشةٌ تقول إنها تغطّيه وهي ليست مساراً** (`lib/navCover`): التحصيلُ بعد الإنهاء (C08) — الرحلةُ صارت `null`
  // والمسارُ `/`، وزرُّه في القاع حيث يطفو الشريط. **ولا يقولها إلا شاشاتُ `screens/t2`** فالفاتحُ كما هو
  const coveredByScreen = useNavCovered();
  const covered = ride !== null || offer !== null || coveredByScreen;
  if (covered) return null;
  // **وجولةُ الأذونات شاشةُ قرارٍ تملأ الرئيسية** (عطبٌ قِيس على Note 20
  // 2026-09-17): كان الشريطُ يُرسم فوقها **فيغطّي زرَّ «اسمح بالموقع» و«ليس
  // الآن» معاً** — الزرُّ يُرى حافّةً بيضاءَ بلا نصّ. **والشرطُ هو شرطُ
  // `DriverHome` بحرفه**، فلا يفترقان: حيث تُعرض الجولةُ لا يُعرض الشريط.
  // و`finish()` يبدّل مفتاحَ الموقع فيُعاد الرسمُ ويعود الشريط.
  if (pathname === "/" && profile?.driver.status === "approved" && !walkDone())
    return null;
  return (
    <>
      {/* **وإشعارُ السِمة معه بالشرط نفسِه** (قِيس مرتين 2026-08-13): كان
          مثبّتاً بإزاحةٍ من الأسفل، فوقع مرةً على «ابدأ الاستقبال» ومرةً على
          سببِ «عدم التطابق» في ورقة الإلغاء — وهو أخطرُ الاثنين: كبتنةٌ ألغت
          لسببٍ أمنيٍّ لا تراه. وأيُّ إزاحةٍ ثابتةٍ ستصطدم بشيءٍ في شاشةٍ ما،
          فالقاعدةُ ليست رقماً بل شرطاً: **لا يُعرض تعريفٌ بمفتاحٍ فوق قرار**. */}
      <WomenModeNotice />
      {/* **والنسخةُ المحفوظةُ تُقال** حين عرضها العاملُ بعد مهلته (§٦٢-د/٦) */}
      <StaleShellNotice />
      {/* **TaxoTabs في المظهرين** (§٦٢/٣) — كان الشريطُ القديمُ يُرسم حتى في الداكن */}
      {showsNav(pathname) && !T2_COVERING.includes(pathname) ? <BottomNavT2 /> : null}
    </>
  );
}

function BoundaryByRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}

/** **الترحيبُ عند كلِّ فتحة — وهو شاشةُ الإقلاع نفسُها** (TAXO 2.0، البندان ١٠ و١١، و§٦٢/١ و/١٠).
 *
 * **يُركَّب من أوّل رسمٍ لا بعد الإقلاع**: كان داخل `Boot` فيُرسم بعد `/config` والجلسة — وقبله «ترحيبيةٌ» قديمةٌ في
 * `index.html`. **والآن يحلّ محلَّ إطار الإقلاع ويبقى حتى يكتمل الإقلاع** وحالُ الشبكة عليه — ثمّ: داخلٌ ⇒ يذوب · غيرُ داخلٍ ⇒
 * شاشاتُ الشراكة ثمّ «سجّل كشريك» أو «دخول». فوق المسارات لا مساراً بينها — **ولا يُطلب إذنُ الموقع إلا من جولة الأذونات
 * بلمسة الكبتن**، فالترحيبُ لا يقدّم طلبَ النظام على الإفصاح. **وسهمُ الرجوع في الدخول والتسجيل يعيده** (`gate.ts`).
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

export default function App() {
  // **`reducedMotion="user"` من مكانٍ واحد** (§8)
  return (
    <MotionConfig reducedMotion="user">
    <ThemeProvider>
      {/* **بوّابةُ التحديث فوق كلِّ شيءٍ إلا السِمة** (البند ٨، §43): من
          حزمتُه دون الحدِّ **لا يصل شاشةَ الدخول أصلاً**، فلا معنى لوضعها
          تحت الجلسة. وتحت السِمة لأنها ترسم شاشةً بألوان النظام */}
      <UpdateGate app="driver">
      <ConfigProvider>
        <SessionProvider>
          {/* تحت الجلسة والإعدادات: السِمة تُقرأ من جنس صاحبة الحساب ومن
              مفتاح دولتها، فلا معنى لها قبلهما */}
          <BrandProvider>
            <Router>
            <Boot>
              <DriverProvider>
                {/* **تحت الجلسة والكبتن**: الكراجُ نداءُ كبتنٍ مسجَّل، وفوق
                    `Router` لأن الخريطةَ والورقةَ والشاشةَ ثلاثةُ قرّاءٍ
                    لجوابٍ واحد — وثلاثةُ نداءاتٍ له تفترق */}
                <GarageProvider>
                <RideProvider>
                  {/* **المحادثةُ والمكالمةُ داخل الرحلة** (§٦٦) — تحت الرحلة لأنها تقرأ رحلتَها ومقبسَها، **وفوق الشاشات** لأن
                      المكالمةَ ترنّ في أيِّ شاشة، وطبقتُها مرسومةٌ داخلها (`CommsLayerT2`) */}
                  <RideComms>
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
                              <SubscriptionT2Screen />
                            </Guarded>
                          }
                        />
                        {/* **«عرض الباقات» لمن طلبُه قيد المراجعة** (C32، §٦٢-ج/٣٣) — عرضٌ بلا شراء، وبلا شريطٍ كـC10
                            (`showsNav` قائمةُ سماحٍ لا تذكره)، **ومن اعتُمد يُحوَّل إلى «الاشتراك»** */}
                        {/* **«الكل» في خدمات الرئيسية** (C04، §٦٢-ج/٤٣) — البلاطاتُ كلُّها بترتيب اللوحة، وبلا شريطٍ كالصفحات الفرعية */}
                        <Route
                          path="/services"
                          element={
                            <Guarded>
                              <ServicesT2Screen />
                            </Guarded>
                          }
                        />
                        {/* **الحجوزُ المضمونة** (§٦٣-ج/٣) — «القادمة» و«عروضٌ تنتظرك»، يبلغها مدخلُ الرئيسية ونقرةُ إشعارها،
                            **وبلا شريطٍ كالصفحات الفرعية**؛ ومطفأً تعيد الشاشةُ نفسُها إلى الرئيسية */}
                        <Route
                          path="/guarantees"
                          element={
                            <Guarded>
                              <GuaranteesT2Screen />
                            </Guarded>
                          }
                        />
                        {/* **المشاويرُ الثابتة** (§٦٣-ج/٦) — «مشاويرُك» و«مشاويرُ تنتظر كبتناً»، يبلغها مدخلُ الرئيسية **وبلا شريطٍ**
                            كأختها؛ والعروضُ خلف المفتاح، **وما اعتمده يُقرأ ولو أُطفئ** */}
                        <Route
                          path="/commutes"
                          element={
                            <Guarded>
                              <CommutesT2Screen />
                            </Guarded>
                          }
                        />
                        {/* **بين المدن** (§٦٣-ج/٧) — «أعلن رحلة» و«رحلاتُك»، يبلغها مدخلُ الرئيسية **وبلا شريطٍ** كأخواتها؛ والإعلانُ
                            خلف المفتاح، **وما أعلنه يُقرأ ولو أُطفئ** — ركّابُه ينتظرونه */}
                        <Route
                          path="/intercity"
                          element={
                            <Guarded>
                              <IntercityT2Screen />
                            </Guarded>
                          }
                        />
                        {/* **بلاطاتُ «خدماتك» تفتح ما يفعله الكبتنُ بكلِّ خدمة** (أمرُ المالك ٢٠٢٦-١٠-١٠، SPEC §٧٢) — عنوانٌ منطقيٌّ واحدٌ في
                            التطبيقين (`storefront.SERVICE_ROUTES`)، وحالُ البلاطة من مفتاح السوق في الخلفية */}
                        <Route
                          path="/services/:service"
                          element={
                            <Guarded>
                              <ServiceRouteT2 />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/subscription/plans"
                          element={
                            <Guarded>
                              <PlansPreviewT2Screen />
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
                              <WalletT2Screen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/subscription/cliq/:claimId"
                          element={
                            <Guarded>
                              <CliqSubscriptionScreen />
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
                              <SettingsT2Screen />
                            </Guarded>
                          }
                        />
                        {/* **الوضعُ النسائيّ** (CW1، §٦٢-ج/٢٣) — من صفِّه في «الإعدادات» وشارته في الرئيسية، **وبلا شريطٍ كالإعدادات** */}
                        <Route
                          path="/account/settings/women"
                          element={
                            <Guarded>
                              <WomenModeT2Screen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/account/vehicle"
                          element={
                            <Guarded>
                              <VehicleT2Screen />
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
                        <Route
                          path="/account/permissions"
                          element={
                            <Guarded>
                              <PermissionsScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/account/debt"
                          element={
                            <Guarded>
                              <DebtScreen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/debt/cliq/:claimId"
                          element={
                            <Guarded>
                              <DebtCliqScreen />
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
                          path="/account/delete"
                          element={
                            <Guarded>
                              <DeleteAccountScreen />
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
                              <SkinStoreT2Screen />
                            </Guarded>
                          }
                        />
                        <Route
                          path="/account/missions"
                          element={
                            <Guarded>
                              <MissionsT2Screen />
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
                        {/* **«ركّابٌ ينتظرون تأكيدك»** (C33، `design/PAYMENTS-UNCONFIRMED.md` §٦) — تفتحها الفتحةُ وسطرُ الرئيسية
                            ونقرةُ إشعارها، **وبلا شريطٍ** (`showsNav` قائمةُ سماحٍ لا تذكرها)؛ ومطفأً تعيد نفسَها إلى الرئيسية */}
                        <Route
                          path="/payments/unconfirmed"
                          element={
                            <Guarded>
                              <UnconfirmedT2Screen />
                            </Guarded>
                          }
                        />
                        <Route path="*" element={<Navigate to="/" replace />} />
                      </Routes>
                      )}
                    </RouteTransition>
                    </BoundaryByRoute>
                    <HardwareBack />
                    <CaptainUnconfirmedOpening />
                    <PushRouter />
                    <PushNotices />
                  <NavBar />
                  </RideComms>
                </RideProvider>
                </GarageProvider>
              </DriverProvider>
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
