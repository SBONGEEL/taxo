/** الشاشة الرئيسية: خريطةٌ ملء الشاشة وورقةٌ سفلية (SPEC القسم 11.2–11.4).
 *
 * شاشةٌ واحدة بأربعة أطوار لا أربع شاشات: الخريطة هي نفسها في كل طور، وتبديلُ
 * المسار بينها يعيد بناء الخريطة ويُفقد التوسيط والسيارات المتحركة.
 *
 * | الطور | الورقة السفلية |
 * |---|---|
 * | `idle` | «إلى أين؟» + سيارات الكباتن القريبين تتحرك |
 * | `pick-dropoff` / `pick-pickup` | دبوسٌ ثابت في مركز الشاشة والخريطة تتحرك تحته |
 * | `confirm` | الفئة والسعر المقدّر وزر الطلب |
 * | رحلةٌ جارية | بطاقة التتبع (`TrackingSheet`) |
 *
 * والرحلة الجارية تسبق كل شيء: من فتح التطبيق ورحلتُه جارية يرى رحلته لا
 * حقلَ «إلى أين؟» — وهي تصل من `GET /rides/me/active` عند كل اتصالٍ بالمقبس.
 */

import { AnimatePresence, motion } from "framer-motion";
import { Bell, Crosshair, MapPin, Moon, Search, Sun } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  createBooking,
  getRouteLine,
  requestRide,
  unreadCount,
  updateMe,
} from "@/api/endpoints";
import type {
  Coordinates,
  GenderPreference,
  Ride,
  VehicleCategory,
} from "@/api/types";
import { DestinationSearch } from "@/components/home/DestinationSearch";
import { ConfirmRide } from "@/components/home/ConfirmRide";
import { MapView, type MapHandle } from "@/components/map/MapView";
import type { DraftStop } from "@/components/home/StopsEditor";
import { TrackingSheet } from "@/components/ride/TrackingSheet";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { useCountryConfig, useMapboxToken } from "@/lib/config";
import { DEFAULT_CENTER, currentPosition, reverseGeocode, type Place } from "@/lib/geocode";
import { RIDE_STATUS_LABEL } from "@/lib/labels";
import { isActive, useRide } from "@/lib/ride";
import { usePlaces } from "@/lib/places";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { formatMoney } from "@/lib/utils";

type Phase = "idle" | "pick-pickup" | "pick-dropoff" | "pick-stop" | "confirm";

/** ما يحمله «أعد الطلب» — نقطتان وعنواناهما، **بلا محطاتٍ ولا سعر**. */
interface AgainState {
  pickup: Coordinates;
  pickupAddress: string | null;
  dropoff: Coordinates;
  dropoffAddress: string | null;
}

export function HomeScreen() {
  const navigate = useNavigate();
  // مبدّلُ السِمة في رأس الخريطة (قرار 25) — **إضافةً** إلى صفِّ الإعدادات لا
  // بدلاً منه: من يبدّلها لأن الشمس على الشاشة يبدّلها وهو ينظر إلى الخريطة
  const { dark, setChoice } = useTheme();
  // **عنوانُ الدبوس يُقرأ أثناء التحريك** (تصميمُ `pgPinMap`): بغيره تؤكّد
  // نقطةً لا تعرف أين هي — والخريطةُ وحدها لا تقول «الجبيهة» ولا «شارع كذا».
  // **ومهلةٌ بعد سكون الحركة لا نداءٌ لكل إطار**: `onMoveEnd` يقع مرةً لكل
  // سحبة، لكن سحبتين متتاليتين ندءان، فيُلغى الأولُ بعلَمِ إبطال
  const [pinAddress, setPinAddress] = useState<string | null>(null);
  const [pinLoading, setPinLoading] = useState(false);
  const { user, refreshUser } = useSession();
  const { places } = usePlaces();
  const location = useLocation();
  const { ride, drivers, driverPing, setViewport, refresh, setRide } = useRide();
  const token = useMapboxToken();
  const countryConfig = useCountryConfig(user?.country_code);
  const map = useRef<MapHandle>(null);

  const fallback = DEFAULT_CENTER[user?.country_code ?? "JO"];
  const [center, setCenter] = useState<Coordinates>(fallback);
  const [phase, setPhase] = useState<Phase>("idle");
  const [searchOpen, setSearchOpen] = useState(false);
  const [pickup, setPickup] = useState<Coordinates | null>(null);
  const [pickupAddress, setPickupAddress] = useState<string | null>(null);
  const [dropoff, setDropoff] = useState<Coordinates | null>(null);
  const [dropoffAddress, setDropoffAddress] = useState<string | null>(null);
  // المحطاتُ الوسيطة **بترتيبها** — تُرتَّب وتُحذف هنا قبل التأكيد، فلا
  // مسارَ لتعديلها على رحلةٍ قائمة (SPEC القسم 5.10)
  const [stops, setStops] = useState<DraftStop[]>([]);
  // ارتدّ الطلبُ بسبب تفضيلٍ لا تستطيع تغييره — فيُفتح لها الباب
  const [blockedByPreference, setBlockedByPreference] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<string | null>(null);
  // **قراءةٌ واحدةٌ عند فتح الرئيسية** لا استفتاءٌ دوريّ: ما يصل والتطبيقُ مفتوح
  // يصل على المقبس (`Toasts`)، وما فاتها يُقرأ حين تعود — فاستفتاءٌ كلَّ ثوانٍ
  // يسأل عن جوابٍ لا يتغيّر إلا بحدثٍ نراه أصلاً
  const [unreadNotifications, setUnreadNotifications] = useState(false);
  useEffect(() => {
    let cancelled = false;
    unreadCount()
      .then((body) => !cancelled && setUnreadNotifications(body.unread > 0))
      .catch(() => undefined); // جرسٌ بلا نقطةٍ أهونُ من شاشةِ خطأ
    return () => {
      cancelled = true;
    };
  }, []);

  const tracking = isActive(ride);

  // **مسارُ الرحلة على الطرق** (البند ٨): يُقرأ **مرةً لكل رحلة** بعد القبول —
  // الخلفيةُ جمّدته على الرحلة لحظتَها، فقراءةٌ ثانية تعيد الشيءَ نفسَه.
  // ويُصفَّر بتبدّل الرحلة كي لا يبقى خطُّ رحلةٍ انتهت على خريطة التالية
  const [routeLine, setRouteLine] = useState<number[][] | null>(null);
  const drawableRide = ride && tracking && ride.status !== "searching" && ride.driver
    ? ride.id
    : null;
  useEffect(() => {
    if (!drawableRide) {
      setRouteLine(null);
      return;
    }
    let cancelled = false;
    getRouteLine(drawableRide)
      .then((line) => {
        // قائمةٌ فارغةٌ جوابٌ صحيح: تُرسم الدبابيسُ وحدها بلا خطأ يُعرض
        if (!cancelled) setRouteLine(line.points.length >= 2 ? line.points : null);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [drawableRide]);

  // رحلةٌ انتهت أو أُلغيت تبقى على الشاشة حتى يراها صاحبها: شاشة الدفع تلي
  // `completed` مباشرةً في تدفّق القسم 5، و«لم نجد كبتناً» خبرٌ يُقرأ لا حالةٌ
  // تختفي. ويطويها المستخدم بيده
  const outcome = ride && !tracking && ride.id !== dismissed ? ride : null;

  // أول رسمة: موقع الجهاز إن سُمح، وإلا مركزُ الدولة (SPEC القسم 11.3)
  useEffect(() => {
    let cancelled = false;
    currentPosition().then((position) => {
      if (cancelled || !position) return;
      setCenter(position);
      setPickup((current) => current ?? position);
      map.current?.flyTo(position, 15);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // **«أعد الطلب»**: يصل بنقطتَي رحلةٍ مضت في حالة التنقّل، فتُفتح شاشةُ
  // التأكيد بهما مباشرةً (`FUTURE-FEATURES` بند 3). و`replace` بعدها: رجوعٌ
  // إلى الخلف ثم تقدّمٌ لا يجوز أن يعيد فتحها من جديد
  useEffect(() => {
    const again = (location.state as { again?: AgainState } | null)?.again;
    if (!again) return;
    setPickup(again.pickup);
    setPickupAddress(again.pickupAddress);
    setDropoff(again.dropoff);
    setDropoffAddress(again.dropoffAddress);
    setPhase("confirm");
    window.history.replaceState({}, "");
  }, [location.state]);

  // مركز الخريطة يذهب للخلفية فترسل السيارات حوله — لا سياراتَ بلا مركز
  useEffect(() => {
    if (!tracking) setViewport(center);
  }, [center, tracking, setViewport]);

  // أثناء الرحلة: الإطار يضم الكبتن والوجهة معاً
  useEffect(() => {
    if (!ride || !tracking) return;
    // **بعد ركوب الراكب الإطارُ يضم الوجهة لا نقطة الانطلاق** — و`at_stop`
    // منها (المرحلة 12-ب): قفزةٌ إلى الانطلاق وسط الرحلة تُرجع الخريطة إلى
    // مكانٍ غادره الاثنان
    const riding = ride.status === "in_progress" || ride.status === "at_stop";
    const target = riding ? ride.dropoff : ride.pickup;
    if (driverPing) {
      map.current?.fitBounds({ lat: driverPing.lat, lng: driverPing.lng }, target);
    } else {
      map.current?.flyTo(target, 14);
    }
    // عند تبدّل الحالة وحدها لا مع كل بثّ موقع، وإلا قاومت الخريطةُ إصبعَ
    // المستخدم كلما حرّكها
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ride?.status, tracking]);

  const describe = useCallback(
    async (point: Coordinates, target: "pickup" | "dropoff") => {
      if (!token) return;
      const address = await reverseGeocode(token, point);
      if (target === "pickup") setPickupAddress(address);
      else setDropoffAddress(address);
    },
    [token],
  );

  function pickPlace(place: Place) {
    setDropoff(place.coordinates);
    setDropoffAddress(place.address || place.name);
    setPhase("confirm");
    if (pickup) map.current?.fitBounds(pickup, place.coordinates);
  }

  function confirmPin() {
    const point = map.current?.center() ?? center;
    if (phase === "pick-pickup") {
      setPickup(point);
      void describe(point, "pickup");
      setPhase(dropoff ? "confirm" : "idle");
      return;
    }
    if (phase === "pick-stop") {
      // العنوانُ يُطلب بعد الإضافة فيظهر السطر فوراً ثم يُستبدل باسمه
      setStops((current) => [...current, { ...point, address: null }]);
      setPhase("confirm");
      if (token) {
        const index = stops.length;
        void reverseGeocode(token, point).then((address) =>
          setStops((current) =>
            current.map((stop, at) => (at === index ? { ...stop, address } : stop)),
          ),
        );
      }
      return;
    }
    setDropoff(point);
    void describe(point, "dropoff");
    setPhase("confirm");
    if (pickup) map.current?.fitBounds(pickup, point);
  }

  /** حجزٌ لموعد (12-ط) — **لا يُنشئ رحلةً ولا يغيّر شاشة**: الحجزُ ليس رحلة،
   * فتبقى الرئيسيةُ كما هي ويُذهب به إلى «رحلاتي المجدولة» ليراه مكتوباً. */
  async function schedule(
    category: VehicleCategory,
    preference: GenderPreference,
    when: string,
  ) {
    if (!pickup || !dropoff) return;
    setRequesting(true);
    setError(null);
    try {
      await createBooking({
        pickup,
        dropoff,
        vehicle_category: category,
        pickup_address: pickupAddress,
        dropoff_address: dropoffAddress,
        gender_preference: preference,
        // **بمنطقةٍ زمنية**: `datetime-local` يعطي وقتاً محلياً بلا منطقة،
        // و`new Date(value)` يقرؤه بمنطقة الجهاز — فيصل الموعدُ كما رآه صاحبُه
        scheduled_at: new Date(when).toISOString(),
      });
      setPhase("idle");
      setDropoff(null);
      setDropoffAddress(null);
      navigate("/account/bookings");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تثبيت الحجز",
      );
    } finally {
      setRequesting(false);
    }
  }

  async function submit(
    category: VehicleCategory,
    preference: GenderPreference,
    promoCode?: string,
    sharing?: { share: boolean; shareGenderConfirmed: boolean },
  ) {
    if (!pickup || !dropoff) return;
    setRequesting(true);
    setError(null);
    try {
      const created = await requestRide({
        pickup,
        dropoff,
        vehicle_category: category,
        pickup_address: pickupAddress,
        dropoff_address: dropoffAddress,
        gender_preference: preference,
        // **الرمزُ يُرسل مع الطلب** (12-ز): الخلفيةُ تُجمّد قاعدتَه على الرحلة،
        // ورمزٌ خاطئ يرفض الطلبَ كلَّه بدل أن يمرّ بلا خصمٍ في صمت
        promo_code: promoCode,
        // **المشاركةُ حقلان لا واحد** (12-ي): الثاني موافقةٌ صريحةٌ على أن
        // تشاركها راكبةٌ أخرى، والخلفيةُ **ترفض** طلباً مجنَّساً بلا موافقة ولا
        // تُسقطها بصمت — فالتطبيقُ يرسل ما اختارته لا ما يُريحه
        share: sharing?.share,
        share_gender_confirmed: sharing?.shareGenderConfirmed,
        stops: stops.map((stop) => ({
          lat: stop.lat,
          lng: stop.lng,
          address: stop.address,
        })),
      });
      // الرحلة تعود `requested`؛ انتقالها إلى `searching` يصل عبر المقبس
      setRide(created);
      setPhase("idle");
      setDropoff(null);
      setDropoffAddress(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إرسال الطلب");
      // **رفضٌ بلا مخرجٍ ليس رفضاً**: تفضيلٌ نسائيٌّ بقي في ملفها من سوقٍ
      // الخدمةُ فيه مشتعلة يجعل كلَّ طلبٍ يرتدّ، والمفتاحُ لا يظهر لتغيّره
      // (لأن الخدمة مطفأة). فيُعرض هنا زرٌّ يعيده إلى `any` — والسببُ مكتوب
      setBlockedByPreference(
        caught instanceof ApiError &&
          caught.code === "women_service_unavailable",
      );
    } finally {
      setRequesting(false);
    }
  }

  /** يعيد التفضيل المخزَّن إلى «أي كبتن» ثم يفتح الطريق للطلب من جديد.
   *
   * ويكتب في الملف لا في هذه الشاشة وحدها: التفضيلُ عمودٌ على الحساب، وقيمةٌ
   * تُتجاوَز محلياً تعود بأول شاشةٍ أخرى تقرؤها.
   */
  async function clearGenderPreference() {
    setError(null);
    try {
      await updateMe({ ride_gender_preference: "any" });
      await refreshUser();
      setBlockedByPreference(false);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تعديل التفضيل",
      );
    }
  }

  /** «أقبل أي كبتن» — **طلبٌ جديد بنفس النقطتين لا توسيعُ بحثٍ منتهٍ**.
   *
   * `no_driver_found` حالةٌ نهائية في الخلفية (القسم 4)، فلا شيء يُستأنف؛
   * والسعرُ يُعاد حسابه لأن الرحلة الجديدة رحلةٌ جديدة — وذلك أصدق من إيهامها
   * أن الطلب الأول ما زال حياً.
   */
  async function acceptAnyDriver(previous: Ride) {
    setError(null);
    try {
      const created = await requestRide({
        pickup: previous.pickup,
        dropoff: previous.dropoff,
        vehicle_category: previous.vehicle_category,
        pickup_address: previous.pickup_address,
        dropoff_address: previous.dropoff_address,
        gender_preference: "any",
      });
      setDismissed(null);
      setRide(created);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إرسال الطلب");
    }
  }

  const picking =
    phase === "pick-pickup" || phase === "pick-dropoff" || phase === "pick-stop";

  return (
    <div className="relative h-full w-full overflow-hidden bg-bg">
      <MapView
        ref={map}
        token={token}
        center={center}
        // أثناء الرحلة يرى الراكب كبتنه وحده (SPEC القسم 10)
        drivers={tracking ? [] : drivers}
        pickup={tracking ? ride!.pickup : pickup}
        dropoff={tracking ? ride!.dropoff : dropoff}
        driverLocation={driverPing}
        // **مسارُ الرحلة على الطرق بعد القبول** (البند ٨) — ويتقلّص خلف الكبتن
        routePoints={routeLine}
        trimAt={driverPing}
        // **نبضةُ الموقع الحالي** — لونُها `--brand` فتتبع الوضعَ والسِمة.
        // وتختفي أثناء الرحلة: الانتباهُ حينها لسيارة الكبتن لا لموقعي
        showMyLocation={tracking || picking ? null : pickup}
        // **ونبضةٌ حول الانطلاق ما دام البحثُ جارياً** — تتوقف عند القبول،
        // فنبضٌ يبقى بعد الإسناد يقول «ما زلنا نبحث» وقد وُجد
        searching={ride?.status === "searching" || ride?.status === "requested"}
        onMoveEnd={(point) => {
          setCenter(point);
          // بلا رمزٍ لا نداء — كما في `describe` بالضبط
          if (!picking || !token) return;
          setPinLoading(true);
          setPinAddress(null);
          void reverseGeocode(token, point)
            .then((address) => setPinAddress(address))
            .catch(() => setPinAddress(null))
            .finally(() => setPinLoading(false));
        }}
      />

      {/* دبوسٌ ثابت في المركز: الخريطة تتحرك تحته لا هو فوقها */}
      {picking ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center pb-40">
          <motion.div initial={{ y: -8 }} animate={{ y: 0 }} className="text-38">
            📍
          </motion.div>
        </div>
      ) : null}

      {/* رأسُ الخريطة كما في النموذج بعد الحزمة (أ): **حرفُ الحساب** في طرفٍ،
          والجرسُ ومبدّلُ السِمة في الآخر. وسقط منه زرّا «القائمة» و«المحفظة»:
          الأولُ صار الشريطَ السفليَّ كلَّه (فحُذفت `/menu`)، والثاني تبويباً
          فيه — واختصارٌ فوق الخريطة إلى تبويبٍ ظاهرٍ أسفلَها بابان لشيءٍ واحد */}
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between gap-8 px-16 pt-safe">
        <button
          type="button"
          onClick={() => navigate("/account")}
          className="ctl size-44 text-14 font-bold"
          aria-label="حسابي"
        >
          {user?.name.slice(0, 1) ?? "؟"}
        </button>
        <div className="flex items-center gap-8">
          <button
            type="button"
            onClick={() => navigate("/account/notifications")}
            aria-label="الإشعارات"
            // **`pointer-events-auto` لا زينة**: الحاويةُ `pointer-events-none`
            // كي تمرّ إيماءاتُ الخريطة من حولها، فكلُّ زرٍّ فيها يُعيد تمكينَ
            // نفسه. وبغيره يُرسم الزرُّ ويُقاس ويبدو سليماً **ولا يُنقر** —
            // والقياسُ وحده يكشفه: `elementFromPoint` يعيد canvas الخريطة
            className="ctl relative size-44"
          >
            <Bell className="size-20" />
            {/* **نقطةٌ لا رقم** كما في التصميم (`unreadShow`): الرقمُ يحتاج قراءةً
                ثانيةً كلَّ فتحةٍ للرئيسية، والنقطةُ تجيب السؤالَ الوحيد الذي
                يُسأل هنا — «هل ثمّ جديد؟». والعددُ نفسُه في الشاشة */}
            {unreadNotifications ? (
              <span className="absolute end-8 top-8 size-8 rounded-full bg-danger" />
            ) : null}
          </button>
          <button
            type="button"
            onClick={() => setChoice(dark ? "light" : "dark")}
            aria-label={dark ? "الوضع النهاري" : "الوضع الليلي"}
            className="ctl size-44"
          >
            {dark ? <Sun className="size-20" /> : <Moon className="size-20" />}
          </button>
        </div>
      </div>

      <button
        type="button"
        onClick={async () => {
          const position = await currentPosition();
          if (position) map.current?.flyTo(position, 15);
        }}
        className="ctl absolute bottom-[42%] end-16 size-44"
        aria-label="موقعي الحالي"
      >
        <Crosshair className="size-20" />
      </button>

      {/* **الأوراقُ تنتهي فوق الشريط** (`bottom:66px` في النموذج): ورقةٌ تلتصق
          بأسفل الشاشة تحت شريطٍ ثابتٍ تُخفي سطرَها الأخير — وهو زرُّ الطلب */}
      <div className="pointer-events-none absolute inset-x-0 bottom-nav mx-auto max-w-lg">
        <AnimatePresence mode="wait">
          <motion.div
            key={tracking || outcome ? `ride-${ride!.status}` : phase}
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 340, damping: 32 }}
            className="pointer-events-auto"
          >
            {tracking ? (
              <TrackingSheet ride={ride!} onChanged={() => void refresh()} />
            ) : outcome ? (
              <OutcomeSheet
                ride={outcome}
                onDismiss={() => setDismissed(outcome.id)}
                onAcceptAnyDriver={() => acceptAnyDriver(outcome)}
              />
            ) : picking ? (
              <Sheet>
                <div className="space-y-12 pb-16">
                  <p className="text-center text-14 text-muted">
                    حرّك الخريطة حتى يقف الدبوس على{" "}
                    {phase === "pick-pickup" ? "نقطة الانطلاق" : "وجهتك"}
                  </p>
                  {/* **العنوانُ المعكوس جغرافياً** كما في التصميم: تأكيدُ نقطةٍ
                      بلا اسمها تأكيدٌ على العمى. و«نقرأ العنوان…» أثناء النداء
                      لأن صمتاً ثم ظهورَ نصٍّ يُقرأ وميضاً */}
                  <p className="rounded-12 border border-line bg-bg px-14 py-12 text-13.5 text-ink">
                    {pinLoading
                      ? "نقرأ العنوان…"
                      : (pinAddress ?? "حرّك الخريطة لقراءة العنوان")}
                  </p>
                  <Button size="lg" onClick={confirmPin}>
                    تأكيد الموقع
                  </Button>
                  <Button
                    variant="ghost"
                    className="w-full"
                    onClick={() => setPhase(dropoff ? "confirm" : "idle")}
                  >
                    إلغاء
                  </Button>
                </div>
              </Sheet>
            ) : phase === "confirm" && pickup && dropoff ? (
              <ConfirmRide
                pickup={pickup}
                pickupAddress={pickupAddress}
                dropoff={dropoff}
                dropoffAddress={dropoffAddress}
                categories={countryConfig?.vehicle_categories ?? ["economy"]}
                onEditDestination={() => setSearchOpen(true)}
                onRequest={submit}
                onSchedule={schedule}
                requesting={requesting}
                requestError={error}
                stops={stops}
                onStopsChange={setStops}
                onAddStop={() => setPhase("pick-stop")}
                blockedByPreference={blockedByPreference}
                onClearPreference={() => void clearGenderPreference()}
                countryConfig={countryConfig}
                // «رجوع» (الحزمة ب): يترك التخطيطَ كلَّه ويعود إلى «إلى أين؟».
                // ويمسح الوجهةَ لأن بقاءها يترك الشاشةَ في حالٍ لا زرَّ يعيدها
                // منه إلى ورقة التأكيد — أما المحطاتُ فمعها، إذ لا معنى
                // لمحطاتٍ بلا وجهة
                onBack={() => {
                  setPhase("idle");
                  setDropoff(null);
                  setDropoffAddress(null);
                  setStops([]);
                }}
              />
            ) : (
              <Sheet>
                <div className="space-y-12 pb-8">
                  <p className="text-18 font-semibold text-ink">إلى أين؟</p>
                  {/* **حقلٌ لا زرٌّ بشكل حقل**: ارتفاعٌ لا ينزل عن 48 (هدفُ لمسٍ
                      مريح)، وتعبئةُ `--sur2` فوق سطح الورقة `--sur` فيُقرأ حدُّه
                      من الفرق لا من خطٍّ باهت، و`rounded-13` نصفُ قطر «حقل
                      الإدخال في المحمول» (`DESIGN.md` §1.3).
                      **وحالةُ التركيز تتبع `--brand`** فتتبدّل مع السِمة الوردية
                      بلا شرطٍ في هذا الملف. */}
                  <button
                    type="button"
                    onClick={() => setSearchOpen(true)}
                    className="pressable flex min-h-48 w-full items-center gap-12 rounded-13 border border-line bg-bg px-16 text-start transition focus-visible:border-brand active:border-brand"
                  >
                    <Search className="size-20 shrink-0 text-muted" />
                    <span className="truncate text-14.5 text-muted">
                      ابحث عن وجهتك أو حدّدها بالدبوس
                    </span>
                  </button>
                  {/* اختصارا «المنزل» و«العمل» — أولُ مكانين محفوظين
                      (`FUTURE-FEATURES` بند 1). ولا يظهر الصفُّ بلا أماكن:
                      صفٌّ فارغٌ دائمٌ لأجل حالةٍ لم تقع بعد */}
                  {places.length > 0 ? (
                    <div className="flex gap-8">
                      {places.slice(0, 2).map((place) => (
                        <button
                          key={place.id}
                          type="button"
                          onClick={() =>
                            pickPlace({
                              id: `place:${place.id}`,
                              name: place.label,
                              address: place.address ?? "",
                              coordinates: { lat: place.lat, lng: place.lng },
                            })
                          }
                          className="pressable min-w-0 flex-1 rounded-12 border border-line bg-surface px-12 py-10 text-start transition hover:bg-surface-2"
                        >
                          <span className="block truncate font-medium text-ink">
                            {place.label}
                          </span>
                          <span className="block truncate text-12 text-muted">
                            {place.address ?? "نقطة محفوظة"}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : null}

                  {/* **صفٌّ لا سطرٌ معلّق**: كان نصّاً عارياً تحت الحقل يُقرأ
                      زائدةً لا عنصراً — بلا أيقونةٍ تقول «مكان»، وبلا حدٍّ يربطه
                      بما فوقه، وبلا ما يقول إنه **يُضغط**. وهو يُضغط: منه يدخل
                      طورُ `pick-pickup`. فصار صفاً بأيقونة موقعٍ بلون `--brand`
                      (فيتبع السِمة)، وتسميةٍ فوق القيمة، وكلمةِ «تغيير» تقول
                      وظيفتَه — بنفس ارتفاع الحقل ونصفِ قطره، فيُقرأ الاثنان
                      عائلةً واحدة. */}
                  <button
                    type="button"
                    onClick={() => setPhase("pick-pickup")}
                    className="pressable flex min-h-48 w-full items-center gap-12 rounded-13 border border-line px-16 text-start transition focus-visible:border-brand active:border-brand"
                  >
                    <MapPin className="size-18 shrink-0 text-brand" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-11.5 text-muted">نقطة الانطلاق</span>
                      <span className="block truncate text-14 text-ink">
                        {pickupAddress ?? (pickup ? "الموقع المحدد" : "موقعي الحالي")}
                      </span>
                    </span>
                    <span className="shrink-0 text-12 text-muted">تغيير</span>
                  </button>
                </div>
              </Sheet>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <DestinationSearch
        open={searchOpen}
        onOpenChange={setSearchOpen}
        token={token}
        country={user?.country_code ?? "JO"}
        near={pickup ?? center}
        onPick={pickPlace}
        onPickOnMap={() => setPhase("pick-dropoff")}
      />

    </div>
  );
}

/** خاتمةُ رحلة: الدفع بعد الإنهاء، وخبرٌ يُقرأ بعد الإلغاء (SPEC القسم 5). */
function OutcomeSheet({
  ride,
  onDismiss,
  onAcceptAnyDriver,
}: {
  ride: Ride;
  onDismiss: () => void;
  onAcceptAnyDriver: () => Promise<void>;
}) {
  const navigate = useNavigate();
  const [retrying, setRetrying] = useState(false);
  const completed = ride.status === "completed";
  // طلبٌ مجنَّس لم يجد كبتناً: هنا وحده يُعرض التنازل عن الشرط
  const missedGendered =
    ride.status === "no_driver_found" && ride.gender_preference !== "any";

  return (
    <Sheet>
      <div className="space-y-12 pb-16">
        <p className="text-18 font-semibold text-ink">{RIDE_STATUS_LABEL[ride.status]}</p>

        {completed ? (
          <>
            <p className="text-14 text-muted">
              الأجرة النهائية{" "}
              <span className="font-semibold text-ink">
                {formatMoney(ride.final_fare ?? ride.estimated_fare, ride.currency)}
              </span>
            </p>
            <Button size="lg" onClick={() => navigate(`/rides/${ride.id}/pay`)}>
              الانتقال إلى الدفع
            </Button>
          </>
        ) : missedGendered ? (
          <>
            {/* **تخييرٌ لا رفض**: الطلبُ سقط لأن الشرط لم يتحقق، والقرارُ في
                التنازل عنه قرارُها هي — ونعرضه مرةً هنا لا نطبّقه عنها.
                و«أنتظر كبتنة» ليس زراً بعد: لا مسارَ في الخلفية يواصل بحثاً
                انتهى، فوعدٌ بلا مسارٍ أسوأ من غيابه (`FUTURE-FEATURES`) */}
            <p className="text-14 leading-relaxed text-muted">
              لا كبتنة متاحة قريبة الآن. يمكنك طلب رحلةٍ جديدة بعد قليل، أو
              قبول أي كبتن متاح الآن — الاختيار لكِ.
            </p>
            <Button
              size="lg"
              loading={retrying}
              onClick={async () => {
                setRetrying(true);
                try {
                  await onAcceptAnyDriver();
                } finally {
                  setRetrying(false);
                }
              }}
            >
              أقبل أي كبتن متاح
            </Button>
          </>
        ) : (
          <p className="text-14 text-muted">
            {ride.cancelled_reason ?? "يمكنك طلب رحلة جديدة الآن."}
          </p>
        )}

        <Button variant="ghost" className="w-full" onClick={onDismiss}>
          {completed ? "لاحقاً" : "حسناً"}
        </Button>
      </div>
    </Sheet>
  );
}
