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

import { Suspense, useEffect, useState } from "react";

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

import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { Welcome } from "@/components/welcome/Welcome";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { ConfigProvider, useConfig } from "@/lib/config";
import { CountriesProvider } from "@/lib/countries";
import { CountryProvider } from "@/lib/country";
import { listenToNativeAlertTaps } from "@/lib/alert-push";
import { AlertFeedProvider, recordPath } from "@/lib/alerts";
import { listenToPushTaps } from "@/lib/push";
import { SessionProvider, useSession } from "@/lib/session";
import { ThemeProvider, useTheme } from "@/lib/theme";
import { UpdateGate } from "@/lib/update-gate";
import { LoginScreen } from "@/screens/Login";

const OverviewScreen = lazy(() =>
  import("@/screens/Overview").then((m) => ({ default: m.OverviewScreen })),
);
// **إشعاراتُ المالك** (SPEC §٨١) — القائمةُ والإعدادُ والمعاينة
const AlertsScreen = lazy(() => import("@/screens/Alerts").then((m) => ({ default: m.AlertsScreen })));
const AlertSettingsScreen = lazy(() =>
  import("@/screens/AlertSettings").then((m) => ({ default: m.AlertSettingsScreen })),
);
const AlertPreviewScreen = lazy(() =>
  import("@/screens/AlertPreview").then((m) => ({ default: m.AlertPreviewScreen })),
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
const MobilePaymentsScreen = lazy(() =>
  import("@/screens/MobilePayments").then((m) => ({
    default: m.MobilePayments,
  })),
);
const FinanceScreen = lazy(() =>
  import("@/screens/Finance").then((m) => ({ default: m.FinanceScreen })),
);
// **الملخّصاتُ المالية** (A37–A39، SPEC §٦٥-د) — صفحةُ قراءةٍ بصلاحيةٍ مستقلّة
const FinanceSummaryScreen = lazy(() =>
  import("@/screens/FinanceSummary").then((m) => ({ default: m.FinanceSummaryScreen })),
);
// **«المالية العامة» و«مالية الدولة»** (SPEC §٧٤-أ/٩)
const FinanceOverviewScreen = lazy(() =>
  import("@/screens/FinanceOverview").then((m) => ({ default: m.FinanceOverviewScreen })),
);
const FinanceCountryScreen = lazy(() =>
  import("@/screens/FinanceSummary").then((m) => ({ default: m.FinanceCountryScreen })),
);
const PaymentsScreen = lazy(() =>
  import("@/screens/Payments").then((m) => ({ default: m.PaymentsScreen })),
);
const DisputesScreen = lazy(() =>
  import("@/screens/Disputes").then((m) => ({ default: m.DisputesScreen })),
);
// **نظامُ الدفع الجديد** (SPEC §٧٣-هـ المرحلة ١)
// **بطاقاتُ TAXO** (SPEC §٧٣-هـ المرحلة ٢)
const TaxoCardsScreen = lazy(() =>
  import("@/screens/TaxoCards").then((m) => ({ default: m.TaxoCardsScreen })),
);
const PaymentSystemScreen = lazy(() =>
  import("@/screens/PaymentSystem").then((m) => ({ default: m.PaymentSystemScreen })),
);
const UnconfirmedPaymentsScreen = lazy(() =>
  import("@/screens/UnconfirmedPayments").then((m) => ({ default: m.UnconfirmedPaymentsScreen })),
);
const OtpTemplatesScreen = lazy(() =>
  import("@/screens/OtpTemplatesScreen").then((m) => ({
    default: m.OtpTemplatesScreen,
  })),
);
const SettingsScreen = lazy(() =>
  import("@/screens/Settings").then((m) => ({ default: m.SettingsScreen })),
);
// **المرافقُ الحيويّة** (§٦٣-ج/٢) — حزمةٌ كسولةٌ بخريطتها: `mapbox-gl` لا يُحمَّل لمن لم يفتحها
const FacilitiesScreen = lazy(() =>
  import("@/screens/Facilities").then((m) => ({ default: m.FacilitiesScreen })),
);
// **الأماكن** (§٧١-د/١٤) — حزمةٌ كسولةٌ كأختها
const PlacesScreen = lazy(() =>
  import("@/screens/Places").then((m) => ({ default: m.PlacesScreen })),
);
// **مساراتُ بين المدن** (§٦٣-ج/٧) — حزمةٌ كسولةٌ كأختها
const IntercityScreen = lazy(() =>
  import("@/screens/Intercity").then((m) => ({ default: m.IntercityScreen })),
);
const ProvidersScreen = lazy(() =>
  import("@/screens/Providers").then((m) => ({ default: m.ProvidersScreen })),
);
// **«مناطق التسعير»** (SPEC §٧٤-أ/٥) — حزمةٌ كسولةٌ بخريطتها
const PricingZonesScreen = lazy(() =>
  import("@/screens/PricingZones").then((m) => ({ default: m.PricingZonesScreen })),
);
// **«الدول» والحدود** (SPEC §٧٤-أ/٢–٣)
const MarketsScreen = lazy(() =>
  import("@/screens/Markets").then((m) => ({ default: m.MarketsScreen })),
);
const ReleasesScreen = lazy(() =>
  import("@/screens/Releases").then((m) => ({ default: m.ReleasesScreen })),
);
const PoliciesScreen = lazy(() =>
  import("@/screens/Policies").then((m) => ({ default: m.PoliciesScreen })),
);
const SiteScreen = lazy(() =>
  import("@/screens/Site").then((m) => ({ default: m.SiteScreen })),
);
const RidesScreen = lazy(() =>
  import("@/screens/Rides").then((m) => ({ default: m.RidesScreen })),
);
const RidersScreen = lazy(() =>
  import("@/screens/Riders").then((m) => ({ default: m.RidersScreen })),
);
const PhotoReportsScreen = lazy(() =>
  import("@/screens/PhotoReports").then((m) => ({ default: m.PhotoReports })),
);
const FeedbackScreen = lazy(() =>
  import("@/screens/Feedback").then((m) => ({ default: m.FeedbackScreen })),
);
// **الرسائلُ المبلَّغُ عنها** (A30، §٦٦-ب/١٣) — بصلاحية `trip_chats.read`، والشاشةُ تقول المنعَ لمن لا يملكها
const ChatReportsScreen = lazy(() =>
  import("@/screens/ChatReports").then((m) => ({ default: m.ChatReportsScreen })),
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
// **فئاتُ الرحلة** (A40، SPEC §٦٧)
const RideCategoriesScreen = lazy(() =>
  import("@/screens/RideCategories").then((m) => ({ default: m.RideCategoriesScreen })),
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
const ErrorsScreen = lazy(() =>
  import("@/screens/Errors").then((m) => ({ default: m.ErrorsScreen })),
);
const VehicleSkinsScreen = lazy(() =>
  import("@/screens/VehicleSkins").then((m) => ({
    default: m.VehicleSkinsScreen,
  })),
);
const SkinPurchasesScreen = lazy(() =>
  import("@/screens/SkinPurchases").then((m) => ({
    default: m.SkinPurchasesScreen,
  })),
);
const ChangePasswordScreen = lazy(() =>
  import("@/screens/ChangePassword").then((m) => ({ default: m.ChangePasswordScreen })),
);
// **مراجعةُ تحويلات BaridiMob** (SPEC §٨٢-ب) — صفحةُ المراجع وحدُها، ويفتحها المالك
const TransfersScreen = lazy(() =>
  import("@/screens/Transfers").then((m) => ({ default: m.TransfersScreen })),
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
  const { loading, user, enrollmentRequired, passwordChangeRequired } = useSession();

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
    // تقرأ بادئةَ الهاتف من `/config` كما كانت. **ولا قبل أن تُفتح الأبواب** (قِيس على الإنتاج 2026-10-22): المالكُ دخل
    // أوّلَ مرّةٍ فردّ `/admin/countries` بـ403 `password_change_required`، وغيّر كلمتَه، **ولم تُسأل الأسواقُ ثانيةً** — فبقي
    // المبدّلُ «JO» وحده بلا ليبيا ولا الجزائر. **فزوالُ العلَم هو ما يُعيد السؤال**
    <CountriesProvider
      enabled={Boolean(user) && !enrollmentRequired && !passwordChangeRequired && !isReviewerOnly(user?.roles)}
    >
      <CountryProvider fallback={config.default_country_code}>
        {children}
      </CountryProvider>
    </CountriesProvider>
  );
}

/** **مراجعُ التحويلات وحدَه** (SPEC §٨٢-ب/٥) — لا يحمل `admin`، فكلُّ صفحةٍ غيرُ صفحته مغلقةٌ في الخادم؛ والشاشةُ تقوده إليها */
export function isReviewerOnly(roles: readonly string[] | undefined): boolean {
  return Boolean(roles?.includes("payment_reviewer") && !roles.includes("admin"));
}

function Guarded({ children }: { children: ReactNode }) {
  const { user, enrollmentRequired, passwordChangeRequired } = useSession();
  const { pathname } = useLocation();
  if (!user) return <Navigate to="/login" replace />;
  // **بوابةُ الإلزام** (12-د): الخلفيةُ ردّت `totp_enrollment_required`، فكلُّ
  // مسارٍ إداريٍّ مغلقٌ حتى يُسجّل عاملَه. وقيادتُه إلى الشاشة التي تفتح البابَ
  // أصدقُ من ترك كل شاشةٍ ترسم خطأً أحمر لا مخرجَ منه
  if (enrollmentRequired) return <Navigate to="/security" replace />;
  // **وبوّابةُ الكلمة بعدها** (SPEC §٧٦-م/٢): العاملُ أوّلاً — بابُ التغيير محروسٌ به — ثمّ الكلمة
  if (passwordChangeRequired) return <Navigate to="/account/password" replace />;
  if (isReviewerOnly(user.roles) && pathname !== "/transfers") return <Navigate to="/transfers" replace />;
  return <>{children}</>;
}

/** **شاشةُ تغيير الكلمة لا تخضع لبوّابة الكلمة** — وإلا صارت حلقةً مغلقة؛ **وتخضع لبوّابة العامل** كما يخضع بابُها في الخلفية. */
function AccountGuarded({ children }: { children: ReactNode }) {
  const { user, enrollmentRequired } = useSession();
  if (!user) return <Navigate to="/login" replace />;
  if (enrollmentRequired) return <Navigate to="/security" replace />;
  return <>{children}</>;
}

/** شاشةُ الأمان وحدها لا تخضع لبوابة الإلزام — وإلا صارت الحلقةُ مغلقة:
 *  «سجّل عاملاً» على بابٍ لا يُفتح قبل تسجيل عامل. */
function SecurityGuarded({ children }: { children: ReactNode }) {
  const { user, enrollmentRequired, passwordChangeRequired } = useSession();
  if (!user) return <Navigate to="/login" replace />;
  // **من سجّل عاملَه ولم يغيّر كلمتَه** يمضي إلى التغيير — شاشةُ الأمان تبقى له ما دام العاملُ ناقصاً
  if (passwordChangeRequired && !enrollmentRequired) return <Navigate to="/account/password" replace />;
  return <>{children}</>;
}

/** نقرةُ الإشعار تفتح وجهتَها — **داخل `Router` لأن `useNavigate` يحتاجه**.
 *
 * **ولا تُرسم شيئاً**: مستمعٌ يعيش ما عاش التطبيق، ويُفكّ عند التفكيك. وفي
 * المتصفح `listenToPushTaps` يعيد دالّةً فارغةً بلا نداءٍ ولا خطأ.
 *
 * **ولمَ لا يُعلَّق داخل الجلسة؟** لأن `SessionProvider` **خارج** `Router`،
 * ومستمعٌ يقود إلى مسارٍ لا يملك مُوجِّهاً يحتاج `window.location` — فيُعيد
 * تحميلَ الصفحة كاملةً ويُسقط الجلسةَ من الذاكرة.
 */
function PushTaps() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { user } = useSession();
  // **الوجهةُ تنتظر حتى تستقرّ البداية** (§٨١، قِيس على المحاكي ٢٠٢٦-١٠-٢١): نقرةٌ تُقلع التطبيقَ المقتولَ تصل قبل أن تُعرف الجلسة
  // **وقبل أن يحوّل الجذرُ إلى «نظرة عامة»** — فكان التحويلُ يقع بعدها ويمحوها. فتُحفظ، وتُنفَّذ حين يُعرف الداخلُ ويُغادَر «/»
  const [pending, setPending] = useState<string | null>(null);
  useEffect(() => {
    if (pending && user && pathname !== "/") {
      setPending(null);
      if (pathname + window.location.search !== pending) navigate(pending);
    }
  }, [pending, user, pathname, navigate]);
  useEffect(() => {
    let unlisten: (() => void) | null = null;
    let dropped = false;
    void listenToPushTaps((path) => navigate(path)).then((off) => {
      if (dropped) off();
      else unlisten = off;
    });
    // **إشعارُ المالك يرسمه الملحقُ الأصليّ** (§٨١) — نقرتُه تفتح سجلَّه، والمسارُ يُشتقّ هنا لا يُقرأ منه
    let unlistenNative: (() => void) | null = null;
    void listenToNativeAlertTaps((alert) => setPending(recordPath(alert))).then((off) => {
      if (dropped) off();
      else unlistenNative = off;
    });
    // **ومن عامل المتصفّح** (`public/alerts-sw.js`): «افتح» واللوحةُ مفتوحةٌ في لسانٍ آخر — تنتقل بلا إعادة تحميل
    const onWorker = (event: MessageEvent) => {
      const message = event.data as { type?: string; target?: string } | null;
      if (message?.type === "taxo:admin-alert-open" && typeof message.target === "string" && message.target.startsWith("/")) {
        setPending(message.target);
      }
    };
    navigator.serviceWorker?.addEventListener("message", onWorker);
    return () => {
      dropped = true;
      unlisten?.();
      unlistenNative?.();
      navigator.serviceWorker?.removeEventListener("message", onWorker);
    };
  }, [navigate]);
  return null;
}

/** **الترحيبُ عند كلِّ فتحة** — للوحة وتطبيقِ المشرف معاً (قرارُ المالك ٢٠٢٦-١٠-٠٤، §61-٥).
 *
 * **ولا يأخذان غيرَه** حتى يُصمَّما: تكوُّنُ الـX ثمّ يمضي — الداخلُ إلى حيث كان، وغيرُ الداخل إلى
 * شاشة الدخول القائمة **التي تحته أصلاً** (`Guarded`)، فلا تنقّلَ هنا ولا نداء. والسِمةُ سِمةُ
 * اللوحة لحظةَ الفتح (ليليٌّ افتراضاً)، **والشعارُ يُحتوى على الحاسوب** (`welcome.css`).
 */
function WelcomeGate() {
  const { dark } = useTheme();
  const [shown, setShown] = useState(true);
  if (!shown) return null;
  return <Welcome dark={dark} onDone={() => setShown(false)} />;
}

function Anonymous({ children }: { children: ReactNode }) {
  const { user } = useSession();
  return user ? <Navigate to="/campaigns" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider>
      {/* **بوّابةُ التحديث فوق كلِّ شيءٍ إلا السِمة** (البند ٨، §43). **ولا
          تعمل في متصفّح**: لا حزمةَ في متصفّحٍ لتُحدَّث — فهي لغلاف المشرف
          على الهاتف وحدَه */}
      <UpdateGate app="panel">
      <ConfigProvider>
        <SessionProvider>
          <Boot>
            <Router>
              <PushTaps />
              <Suspense
                fallback={
                  <Centered>
                    <Spinner />
                  </Centered>
                }
              >
                <ErrorBoundary>
                <AlertFeedProvider>
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
                    path="/alerts"
                    element={
                      <Guarded>
                        <AlertsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/alerts/settings"
                    element={
                      <Guarded>
                        <AlertSettingsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/alerts/preview"
                    element={
                      <Guarded>
                        <AlertPreviewScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/transfers"
                    element={
                      <Guarded>
                        <TransfersScreen />
                      </Guarded>
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
                  {/* **مساراتُ الهاتف** — بتخطيطٍ ثانٍ بلا غلاف اللوحة،
                      وتقرأ المسارات نفسَها. **ولا مشروعٌ رابع**: ما ينسخه
                      المشروعُ الرابع (الجلسة والصلاحيات وعقد الأخطاء
                      والسلّم) هو بعينه ما يفترق. */}
                  <Route
                    path="/m/payments"
                    element={
                      <Guarded>
                        <MobilePaymentsScreen />
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
                  {/* **«المدفوعات غير المؤكدة»** (A10، `design/PAYMENTS-UNCONFIRMED.md` §٥، SPEC §٦٤-ز) — الأقدمُ أوّلاً وأفعالُه
                      الأربعة، كلٌّ بسببٍ مكتوب */}
                  <Route
                    path="/taxo-cards"
                    element={
                      <Guarded>
                        <TaxoCardsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/payment-system"
                    element={
                      <Guarded>
                        <PaymentSystemScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/payments/unconfirmed"
                    element={
                      <Guarded>
                        <UnconfirmedPaymentsScreen />
                      </Guarded>
                    }
                  />
                  {/* **الملخّصاتُ المالية** (A37–A39، SPEC §٦٥-د) — **والمنعُ من الخادم** (٤٠٣ ⇒ صفحةُ «تحتاج الصلاحية»)، لا من الدور */}
                  <Route
                    path="/finance/summary"
                    element={
                      <Guarded>
                        <FinanceSummaryScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/finance/overview"
                    element={
                      <Guarded>
                        <FinanceOverviewScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/finance/country/:code"
                    element={
                      <Guarded>
                        <FinanceCountryScreen />
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
                    path="/pricing-zones"
                    element={
                      <Guarded>
                        <PricingZonesScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/markets"
                    element={
                      <Guarded>
                        <MarketsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/releases"
                    element={
                      <Guarded>
                        <ReleasesScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/policies"
                    element={
                      <Guarded>
                        <PoliciesScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/site"
                    element={
                      <Guarded>
                        <SiteScreen />
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
                    path="/places"
                    element={
                      <Guarded>
                        <PlacesScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/facilities"
                    element={
                      <Guarded>
                        <FacilitiesScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/intercity"
                    element={
                      <Guarded>
                        <IntercityScreen />
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
                    path="/photo-reports"
                    element={
                      <Guarded>
                        <PhotoReportsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/feedback"
                    element={
                      <Guarded>
                        <FeedbackScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/chat-reports"
                    element={
                      <Guarded>
                        <ChatReportsScreen />
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
                    path="/vehicle-skins"
                    element={
                      <Guarded>
                        <VehicleSkinsScreen />
                      </Guarded>
                    }
                  />
                  <Route
                    path="/vehicle-skins/purchases"
                    element={
                      <Guarded>
                        <SkinPurchasesScreen />
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
                    path="/ride-categories"
                    element={
                      <Guarded>
                        <RideCategoriesScreen />
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
                    path="/errors"
                    element={
                      <Guarded>
                        <ErrorsScreen />
                      </Guarded>
                    }
                  />
                  {/* **«غيّر كلمة مروري»** (SPEC §٧٦-م/٢) — لكلِّ مشرفٍ داخلٍ لا لمن يملك «الأمان» وحدَه، **وهي بوّابةُ أوّل دخول** */}
                  <Route
                    path="/account/password"
                    element={
                      <AccountGuarded>
                        <ChangePasswordScreen />
                      </AccountGuarded>
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
                </AlertFeedProvider>
                </ErrorBoundary>
              </Suspense>
              <WelcomeGate />
            </Router>
          </Boot>
        </SessionProvider>
      </ConfigProvider>
      </UpdateGate>
    </ThemeProvider>
  );
}
