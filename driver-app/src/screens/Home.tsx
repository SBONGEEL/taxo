/** الرئيسية — SPEC القسم 12/2، وشكلُها من `DESIGN.md` §5.3.
 *
 * خريطةٌ ملء الشاشة، وشريطٌ علوي (الحالة والأرباح والجرس والمظهر)، ولافتةُ
 * اشتراكٍ عند الحاجة، وثلاثُ إحصاءات فوق زرِّ الاتصال الكبير.
 *
 * **زرُّ الاتصال يفتح المقبس ولا يستدعي مساراً**: فتحُ `WS /ws/driver` هو
 * نفسه رفعُ `is_online` في الخلفية، وإغلاقُه يُسقط الكبتن من الفهرس الجغرافي
 * فوراً (`ws/routes.py::driver_socket`). فحالةٌ محليةٌ ثانية تقول «متصل»
 * والمقبسُ مغلق كذبةٌ على شاشةٍ ينتظر صاحبها طلباً.
 *
 * **ولا يُعرض «متصل» قبل أول بثِّ موقع**: `is_online` وحده لا يُدخل الكبتن
 * التوزيعَ — أول موقعٍ هو ما يفعل (القسم 10). ولذلك تقول الشاشة «بانتظار
 * إشارة الموقع» حتى يصل، بدل أن تَعِد بطلباتٍ لن تأتي.
 *
 * والرحلةُ الجارية تسبق كل شيء: من فتح التطبيق ورحلتُه جارية يراها لا زرَّ
 * الاتصال.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  acceptRide,
  arriveRide,
  cancelRide,
  arriveAtStop,
  completeRide,
  resumeFromStop,
  declineRide,
  getEarnings,
  getMyProgress,
  getMySubscription,
  getRouteLine,
  getStorefront,
  beginPause,
  getUnreadCount,
  rerouteRide,
  resumePause,
  startRide,
} from "@/api/endpoints";
import type {
  Currency,
  Earnings,
  MySubscription,
  MyProgress,
  NearbyDriver,
  Ride,
  Storefront,
} from "@/api/types";
import { listNearbyColleagues } from "@/api/endpoints";
import { useGarage } from "@/lib/garage";
import {
  etaMinutes,
  offRouteMeters,
  OFF_ROUTE_METERS,
  OFF_ROUTE_STREAK,
  type Sample,
} from "@/lib/eta";
import { ActiveRide } from "@/components/ActiveRide";
import { CaptainHome } from "@/components/home/CaptainHome";
import {
  BACK_ON_ROUTE_STREAK,
  nextInstruction,
  type NextInstruction,
  type RouteStep,
} from "@/lib/next-instruction";
import { CollectScreen } from "@/screens/Collect";
import { RateRiderScreen } from "@/screens/RateRider";
import { MapView } from "@/components/map/MapView";
import { CliqTransferSheet } from "@/components/CliqTransferSheet";
import { OfferSheet } from "@/components/OfferSheet";
import { ErrorNote } from "@/components/ui/Feedback";
import { useConfig, useFeature, useMapboxToken } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { CATEGORY_LABEL, CURRENCY_FULL, CURRENCY_LABEL, PREFERENCE_LABEL } from "@/lib/rideFormat";
import { isActive, useRide } from "@/lib/ride";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { PermissionNotice } from "@/components/PermissionNotice";
import { digits } from "@/lib/utils";

export function HomeScreen() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { user } = useSession();
  const womenService = useFeature(user?.country_code, "women_service_enabled");
  const { config } = useConfig();
  const { profile } = useDriver();
  const { activeSkin } = useGarage();
  // **زملاؤه حوله خلف مفتاحه** (قرارُ المالك، ويُشحن مطفأً): أن يرى الكبتنُ
  // زملاءَه سؤالُ سوقٍ لا سؤالُ عرض. **ومطفأً لا تُرسم الميزةُ أصلاً** — ولا
  // يُنادى البابُ فيردَّ ٤٠٣ فيُعرض للكبتن خطأٌ عن بابٍ لم يطرقه
  const colleaguesOn = useFeature(
    user?.country_code,
    "driver_map_nearby_enabled",
  );
  const preference = profile?.driver.gender_preference ?? "any";
  const { dark, toggle } = useTheme();
  const token = useMapboxToken();
  const {
    online,
    connecting,
    ride,
    offer,
    transfer,
    position,
    error,
    goOnline,
    goOffline,
    setRide,
    dismissOffer,
    dismissTransfer,
    clearError,
  } = useRide();

  /** **طلبٌ نُقر إشعارُه ولمّا يصل بعد** (§27.12).
   *
   * النقرةُ تحمل `?offer={ride_id}`، والعرضُ المعلَّق يصل مع أول اتصالٍ
   * بالمقبس. **فتنتظره الشاشةُ بدل أن تقول «بانتظار الطلبات…»** — وهي جملةٌ
   * يقرؤها من نقر طلباً بعينه على أن طلبَه ضاع.
   *
   * **ويُمسح المعرّفُ متى وصل العرضُ أو انتهى الانتظار**: معرّفٌ يبقى في
   * العنوان يجعل الشاشةَ تنتظر أبداً طلباً انقضت مهلتُه.
   */
  const awaited = params.get("offer");
  const awaitedOffer = Boolean(awaited) && offer === null;
  useEffect(() => {
    if (!awaited) return;
    if (offer !== null) {
      setParams({}, { replace: true });
      return;
    }
    // **مهلةٌ من عمر العرض نفسِه**: بعدها لم يعد هناك ما يُنتظر
    const timer = window.setTimeout(() => setParams({}, { replace: true }), 25_000);
    return () => window.clearTimeout(timer);
  }, [awaited, offer, setParams]);


  // ما بعد الإنهاء: التحصيل ثم التقييم — رحلةٌ واحدة لا شاشتان مستقلتان،
  // فالخروجُ منهما بيد الكبتن لا بحدثٍ من الخلفية
  const [settling, setSettling] = useState<Ride | null>(null);
  const [rating, setRating] = useState<Ride | null>(null);
  const [subscription, setSubscription] = useState<MySubscription | null>(null);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [storefront, setStorefront] = useState<Storefront | null>(null);
  const [progress, setProgress] = useState<MyProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const [unread, setUnread] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);

  // عملةُ الدولة من `/config` — لا تُشتق في الواجهة (`currency_for_country`)
  const currencyCode =
    config?.countries.find((c) => c.country_code === user?.country_code)
      ?.currency ?? "JOD";
  const currency = CURRENCY_LABEL[currencyCode];

  useEffect(() => {
    getMySubscription()
      .then(setSubscription)
      .catch(() => undefined);
    // **نداءٌ واحدٌ للبلاطات واللافتات معاً** — فلا تُرسم الشاشةُ على مرحلتين
    getStorefront()
      .then(setStorefront)
      .catch(() => undefined);
    // **المستوى من بابه لا من حسابٍ هنا**: `enabled: false` تعني أن السوقَ
    // لا يشغّل المهامَّ أصلاً — **فلا يُرسم «المستوى ٠»** وهو لا وجودَ له
    getMyProgress()
      .then(setProgress)
      .catch(() => undefined);
  }, []);

  // أرباحُ اليوم وعددُ رحلاته — تُعاد قراءتها حين **تتبدّل الرحلة الجارية**
  // لا عند كل تحديثٍ لها: العدد لا يتغير بين «وصلت» و«بدأت»، وربطُ الأثر
  // بالكائن نفسِه يجعل كلَّ إطارِ حالةٍ نداءً لا يغيّر رقماً
  useEffect(() => {
    getEarnings("today")
      .then(setEarnings)
      .catch(() => undefined);
  }, [ride?.id ?? null]);

  // العدّاد يُقرأ عند كل عودةٍ إلى الرئيسية: صفوفُ الوارد تُكتب من الخلفية
  // (اشتراكٌ يوشك، مستندٌ رُوجع) بلا أن يفتح الكبتن شيئاً
  useEffect(() => {
    getUnreadCount()
      .then((count) => setUnread(count.unread))
      .catch(() => undefined);
  }, [transfer, ride]);

  const tracking = isActive(ride);
  const located = position !== null;

  /** **زملاؤه على خريطته** — قراءةٌ كلَّ ثماني ثوانٍ ما دام المفتاحُ مفتوحاً
   *  وله موقعٌ مبثوث. **ولا تُقرأ أثناء رحلةٍ جارية**: الخريطةُ حينها لمساره
   *  هو، وسياراتٌ تتحرك حوله تشوّش على من يقود.
   *
   *  **والفشلُ صامتٌ تماماً**: مطفأً يردّ البابُ ٤٠٣ باسمه، ورسالةُ خطأٍ عن
   *  ميزةٍ لم يطلبها الكبتنُ تُقرأ عطباً في التطبيق. */
  const [colleagues, setColleagues] = useState<NearbyDriver[] | null>(null);
  // **`ref` بجانب الحالة**: `position` كائنٌ جديدٌ مع كلِّ بثّة (ثلاثُ ثوانٍ)،
  // فربطُ المؤقّت به يعيد فتحَه قبل أن يبلغ الثماني أبداً — وقراءتُه من
  // الإغلاق تُجمّد أوّلَ موضعٍ فيُسأل عن جيرانِ نقطةٍ غادرها منذ ساعة
  const positionRef = useRef(position);
  positionRef.current = position;
  useEffect(() => {
    if (!colleaguesOn || tracking || !located) {
      setColleagues(null);
      return;
    }
    let alive = true;
    const read = () => {
      const at = positionRef.current;
      if (!at) return;
      listNearbyColleagues(at.lat, at.lng)
        .then((list) => {
          if (alive) setColleagues(list);
        })
        .catch(() => undefined);
    };
    read();
    const timer = window.setInterval(read, 8_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [colleaguesOn, tracking, located]);

  // **خطُّ المسار على الطرق** (البند ٨): يُقرأ مرةً لكل رحلةٍ مُسنَدة — الخلفيةُ
  // جمّدته لحظةَ القبول، فما يراه الكبتن هو ما يراه راكبُه. ويُصفَّر بانتهائها
  const [routeLine, setRouteLine] = useState<number[][] | null>(null);
  // **خطواتُ الملاحة وعتبتُها** (البند ٧) — تصلان مع الخط من النداء نفسِه،
  // **والعتبةُ من الخلفية لا ثابتٌ هنا** (§17.3): رقمٌ في التطبيق يفترق عن
  // الخلفية أوّلَ تعديل. وفارغةٌ حالٌ صحيحة: المفتاحُ مطفأٌ فلا شريط
  const [steps, setSteps] = useState<RouteStep[]>([]);
  const [thresholdM, setThresholdM] = useState(OFF_ROUTE_METERS);

  // **الوصولُ المتوقَّع يُحسب هنا ولا يُطلب** (البند ١٧-٣): المسافةُ من الخطّ
  // المجمَّد على الرحلة، والسرعةُ من حركة الكبتن نفسِه. واستفتاءُ الخادم عنه
  // كان سيرفع فاتورةَ Directions سبعةَ أضعافٍ لرقمٍ يتبدّل بالدقيقة
  const samples = useRef<Sample[]>([]);
  const [eta, setEta] = useState<number | null>(null);
  useEffect(() => {
    if (!position) return;
    samples.current = [...samples.current.slice(-11), { at: position, t: Date.now() }];
    setEta(etaMinutes(routeLine, position, samples.current));
  }, [position, routeLine]);
  // **إعادةُ التوجيه عند انحرافٍ مستمرّ** (البند ١٧-٤) — **وثلاثُ قراءاتٍ
  // متتالية** لا واحدة: قفزةُ GPS تُنتج نداءً مدفوعاً بلا أن ينحرف أحد.
  // **والسقفُ في الخلفية**، وهذا العدّادُ راحةٌ لا حراسة: يكفّ عن الطلب حين
  // ينفد فلا يُرسل نداءً يُرَدّ
  // **الشريطُ يختفي فوراً ويعود متأنياً** — عدمُ تماثلٍ مقصود: الإخفاءُ يغيب
  // تلميحاً، والإظهارُ الخاطئ **يكذب**. فقفزةُ GPS تُخفيه، وثلاثُ قراءاتٍ على
  // الخط هي ما يعيده — وبغيرها يرفّ في يد من يقود
  const backOn = useRef(0);
  const [instruction, setInstruction] = useState<NextInstruction | null>(null);
  useEffect(() => {
    if (!position || steps.length === 0) {
      setInstruction(null);
      return;
    }
    const found = nextInstruction(steps, position, thresholdM);
    if (found === null) {
      backOn.current = 0;
      setInstruction(null);
      return;
    }
    backOn.current += 1;
    if (backOn.current >= BACK_ON_ROUTE_STREAK) setInstruction(found);
  }, [position, steps, thresholdM]);

  const drift = useRef(0);
  const [reroutesLeft, setReroutesLeft] = useState<number | null>(null);
  useEffect(() => {
    if (!ride || !position || !routeLine || reroutesLeft === 0) return;
    const away = offRouteMeters(routeLine, position);
    if (away === null || away < OFF_ROUTE_METERS) {
      drift.current = 0;
      return;
    }
    drift.current += 1;
    if (drift.current < OFF_ROUTE_STREAK) return;
    drift.current = 0;
    rerouteRide(ride.id)
      .then((line) => {
        if (line.points.length >= 2) setRouteLine(line.points);
        setReroutesLeft(line.reroutes_left ?? null);
      })
      // **وفشلُه صامتٌ**: الخطُّ القديم باقٍ، وكبتنٌ يقود لا يُقاطَع برسالة خطأ
      .catch(() => undefined);
  }, [position, routeLine, ride, reroutesLeft]);

  // **وتُنسى القراءاتُ عند تبدّل المسار**: سرعةٌ مقيسةٌ في رحلةٍ انتهت لا تصف
  // هذه، وأوّلُ رقمٍ يظهر في رحلةٍ جديدةٍ يكون محسوباً من حركةٍ ليست فيها
  useEffect(() => {
    samples.current = [];
    setEta(null);
  }, [routeLine]);
  useEffect(() => {
    const id = tracking ? ride.id : null;
    if (!id) {
      setRouteLine(null);
      setSteps([]);
      return;
    }
    let cancelled = false;
    getRouteLine(id)
      .then((line) => {
        // فارغٌ جوابٌ صحيح: تُرسم الدبابيسُ وحدها بلا خطأ يُعرض للكبتن
        if (cancelled) return;
        setRouteLine(line.points.length >= 2 ? line.points : null);
        // **والخطواتُ كذلك**: فارغةٌ تعني لا شريط، وهو سلوكٌ لا فرعُ خطأ
        setSteps(line.steps ?? []);
        if (line.deviation_threshold_m) setThresholdM(line.deviation_threshold_m);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [tracking ? ride.id : null]);
  // اشتراكٌ ساري شرطُ التوزيع (القسم 8) — والزرُّ يقول ذلك بدل أن يفتح
  // مقبساً ترفضه الخلفية
  const covered = subscription?.is_active === true;

  const run = useCallback(async (action: () => Promise<unknown>) => {
    setBusy(true);
    setActionError(null);
    try {
      await action();
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "تعذّر تنفيذ الإجراء",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  async function advance() {
    if (!ride) return;
    await run(async () => {
      if (ride.status === "accepted") setRide(await arriveRide(ride.id));
      else if (ride.status === "arrived") setRide(await startRide(ride.id));
      else if (ride.status === "in_progress" || ride.status === "at_stop") {
        // **الإنهاءُ من `at_stop` مسموحٌ عمداً**: مخرجُ السقف حين يطول
        // انتظارُ الراكب (SPEC القسم 5.10) — والخلفيةُ هي من يجيزه
        const finished = await completeRide(ride.id);
        setRide(null);
        setSettling(finished);
      }
    });
  }

  const goLabel = !covered
    ? "ابدأ الاستقبال — يتطلب اشتراكاً سارياً"
    : connecting
      ? "جارٍ الاتصال…"
      : online
        ? "إيقاف الاستقبال"
        : "ابدأ الاستقبال";

  /** سطرُ الاشتراك — **يُقال بحاله لا بوجوده**: «سارٍ حتى…» و«لا اشتراك»
   *  جملتان مختلفتان، **وبطاقةٌ صامتةٌ فوق زرٍّ لا يعمل تُقرأ عطباً**. */
  const subscriptionLine = !subscription
    ? null
    : covered
      ? `اشتراكك ساري${
          subscription.days_remaining <= 5
            ? ` — يتبقّى ${digits(String(subscription.days_remaining))} أيام`
            : ""
        }`
      : "لا اشتراك ساري — اشترك لتستقبل الطلبات";

  // **المركبةُ الأولى**: صفٌّ واحدٌ لكلِّ كبتنٍ في هذا السوق، ولو تعدّدت
  // فالمفعَّلةُ سؤالُ شاشةِ المركبة لا سؤالُ الرئيسية
  const vehicle = profile?.vehicles[0] ?? null;
  const vehicleLine = vehicle
    ? `${vehicle.make} ${vehicle.model} · ${digits(vehicle.plate_number)}`
    : null;
  const vehicleNote = vehicle
    ? `${vehicle.color} · ${CATEGORY_LABEL[vehicle.category]}`
    : null;

  // **المستوى `null` لا صفر** حين لا تكون المهامُّ مشغَّلةً في السوق
  const level = progress?.enabled ? progress.level : null;

  // تسبقان كلَّ شيء: من أنهى رحلةً يُحصّل ثم يُقيّم قبل أن يرى الخريطة
  if (settling) {
    return (
      <CollectScreen
        ride={settling}
        currencyLabel={currency}
        currencyFull={CURRENCY_FULL[currencyCode] ?? ""}
        onDone={() => {
          setRating(settling);
          setSettling(null);
        }}
      />
    );
  }
  if (rating) {
    return <RateRiderScreen ride={rating} onDone={() => setRating(null)} />;
  }

  /** **الخريطةُ عقدةٌ واحدة** — بطاقةً في الخمول، وملءَ الشاشة في التتبّع.
   *
   *  **ولا نسختان بخصائصَ متوازيةٍ**: نسختان تفترقان بحرفٍ يوماً، **وهو
   *  الشكلُ الثامن بعينه** على شاشةٍ واحدة. */
  const mapNode = (
    <MapView
        token={token}
        center={position}
        // **مركبتُه المفعَّلة، وحالُ اشتراكه من الباب الذي تقرؤه هذه الشاشةُ
        //   أصلاً** — `covered` هي نفسُها التي ترسم اللافتةَ وتقرّر زرَّ
        //   الاستقبال، فلا يقول موضعان على شاشةٍ واحدةٍ شيئين (الشكلُ الثامن)
        selfSkin={activeSkin}
        subscribed={covered}
        colleagues={colleagues}
        pickup={tracking ? ride.pickup : null}
        dropoff={tracking ? ride.dropoff : null}
        fit={tracking}
        // ويتقلّص الخطُّ خلفه كلّما تقدّم — من موقعه هو، فهو من يسير فيه
        routePoints={routeLine}
        trimAt={position}
        etaMinutes={eta}
    />
  );

  return (
    <div className="relative h-full overflow-hidden bg-bg">
      {!tracking ? (
        <CaptainHome
          name={user?.name ?? "كبتن"}
          rating={
            profile ? Number(profile.driver.rating_avg).toFixed(1) : null
          }
          level={level}
          online={online}
          unread={unread}
          dark={dark}
          onToggleTheme={toggle}
          onToggleOnline={() => {
            clearError();
            if (!covered) navigate("/subscription");
            else if (online) goOffline();
            else goOnline();
          }}
          goLabel={goLabel}
          goDisabled={connecting}
          earnings={earnings}
          // **نسبتُه هو مقروءةً من بابها** — ولا حسابَ في الجهاز (§14)
          commissionPercent={
            profile ? String(Number(profile.commission_percent)) : null
          }
          tiles={storefront?.tiles ?? []}
          banners={storefront?.banners ?? []}
          // **غيرُ `offer` المحلّيّ**: ذاك عرضُ رحلةٍ يصل بالمقبس، وهذا
          // عرضُ اشتراكٍ يصل مع الواجهة — واسمان متشابهان في ملفٍّ واحد
          // كافيان ليُقرأ أحدُهما مكانَ الآخر
          storefrontOffer={storefront?.offer ?? null}
          map={mapNode}
          subscriptionLine={subscriptionLine}
          vehicleLine={vehicleLine}
          vehicleNote={vehicleNote}
          statusPill={online && !offer ? (
            <div className="mb-12 flex justify-center">
              <span className="flex animate-pulse items-center gap-9 rounded-full border border-line bg-surface px-18 py-9 text-12.5 font-semibold text-ink">
                <span className="block size-8 rounded-full bg-ok" />
                {/* **النقرةُ حملت معرّفاً، فالشاشةُ تنتظره** (تصحيحُ المالك):
                    العرضُ المعلَّق يصل مع أول اتصالٍ بالمقبس
                    (`dispatch.pending_offer_frame`) — **فالانتظارُ انتظارُ
                    حدثٍ قادمٍ لا سؤالٌ مرةً ويأس**. وبغير هذا السطر يقرأ من
                    نقر إشعارَ طلبٍ «بانتظار الطلبات…» فيظنّ طلبَه ضاع. */}
                {awaitedOffer
                  ? "نفتح الطلب…"
                  : position
                    ? "بانتظار الطلبات…"
                    : "بانتظار إشارة الموقع…"}
              </span>
            </div>
          ) : null}
          extras={
            <>
            {/* التفضيلُ النافذ ظاهرٌ في الرئيسية لا في الإعدادات وحدها
                (المرحلة 10-ج): من ضيّق من يُقلّهم يرى طلباتٍ أقل، وسببُ القلة
                يجب أن يكون أمام عينه لا في شاشةٍ يفتحها بحثاً عن عطل */}
            {womenService && preference !== "any" ? (
              <button
                type="button"
                onClick={() => navigate("/account/settings")}
                className="pressable mb-10 flex w-full items-center justify-between rounded-14 border border-brand-brd bg-brand-soft px-14 py-12 text-start"
              >
                <span className="text-12.5 font-semibold text-brand">
                  أستقبل ركاباً: {PREFERENCE_LABEL[preference]}
                </span>
                <span className="text-11.5 text-muted underline">تغيير</span>
              </button>
            ) : null}

            {/* **تحذيرُ الأذونات — بيتُه `components/PermissionNotice`**.
                كان هنا سطرٌ واحدٌ لرفض الإشعارات وحدَه (شرطُ المالك
                2026-08-21)، **وانطفاءُ قناة «طلبات الرحلات» لا يظهر** — وهي
                الحالُ التي يفوت فيها الكبتنُ رحلةً بلا سببٍ ظاهر. فصار
                التحذيرُ يقرأ السجلَّ كلَّه، **ويفرّق المانعَ من الناصح**.

                **ومكانُه فوق زرِّ الاستقبال كما كان**: هناك يقرؤه وهو يقرّر
                أن يعمل، لا في شاشةٍ يفتحها باحثاً عن عطل. */}
            <PermissionNotice />

            {error || actionError ? (
              <div className="mb-10">
                <ErrorNote message={error ?? actionError} />
              </div>
            ) : null}
            </>
          }
        />
      ) : (
        <>
          {mapNode}
          {/* تدرّجٌ علوي 60px يفصل الشريط عن الخريطة (§2.9) */}
          <div className="pointer-events-none absolute inset-x-0 top-0 h-60 bg-gradient-to-b from-bg to-transparent" />
          <ActiveRide
          ride={ride}
          currencyLabel={currency}
          busy={busy}
          onAdvance={() => void advance()}
          onPause={() => void run(async () => setRide(await beginPause(ride.id)))}
          onResume={() => void run(async () => setRide(await resumePause(ride.id)))}
          onArriveStop={(stopId) =>
            void run(async () => setRide(await arriveAtStop(ride.id, stopId)))
          }
          onResumeStop={(stopId) =>
            void run(async () => setRide(await resumeFromStop(ride.id, stopId)))
          }
          instruction={instruction}
          genderPreference={profile?.driver.gender_preference ?? "any"}
          onCancel={(reason) =>
            void run(async () =>
              setRide(await cancelRide(ride.id, reason.label, reason.code)),
            )
          }
          />
        </>
      )}

      {offer ? (
        <OfferSheet
          offer={offer}
          currencyLabel={currency}
          categoryLabel={CATEGORY_LABEL[offer.ride.vehicle_category]}
          // **`null` لا سلسلةٌ فارغة**: طريقةُ الدفع يختارها الراكبُ بعد
          // الرحلة (§6) فلا تُعرف الآن — **و«لم تُعرف» خبرٌ، والفارغةُ تُرسم**
          methodLabel={null}
          busy={busy}
          onAccept={() =>
            void run(async () => {
              setRide(await acceptRide(offer.ride.id));
              dismissOffer();
            })
          }
          onDecline={() =>
            void run(async () => {
              await declineRide(offer.ride.id);
              dismissOffer();
            })
          }
        />
      ) : null}

      {/* بطاقةُ حوالة كليك — تصل من المقبس في أي وقت، وقد يكون الكبتن على
          الرئيسية لا على شاشة التحصيل (القسم 6.2) */}
      {transfer ? (
        <CliqTransferSheet
          transfer={transfer}
          currencyLabel={CURRENCY_LABEL[transfer.currency as Currency]}
          onConfirmed={dismissTransfer}
          onDispute={() => {
            const rideId = transfer.rideId;
            dismissTransfer();
            navigate(`/rides/${rideId}/dispute`);
          }}
          onDismiss={dismissTransfer}
        />
      ) : null}
    </div>
  );
}
