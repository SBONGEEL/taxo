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
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  createBooking,
  getMyReferrals,
  getRouteLine,
  getStorefront,
  getWallet,
  listMyRides,
  requestRide,
  unreadCount,
  updateMe,
} from "@/api/endpoints";
import type {
  Coordinates,
  GenderPreference,
  MyReferrals,
  Ride,
  Storefront,
  VehicleCategory,
  Wallet,
} from "@/api/types";
import { DestinationSearch } from "@/components/home/DestinationSearch";
import type { RiderHomeProps } from "@/screens/t2/RiderHomeT2";
import type { ConfirmRideProps } from "@/components/home/useConfirmRide";
import { MapView, type MapHandle } from "@/components/map/MapView";
import type { DraftStop } from "@/components/home/StopsEditor";
import { useCountryConfig, useMapboxToken } from "@/lib/config";
import { DEFAULT_CENTER, currentPosition, reverseArea, reverseGeocode, type Place } from "@/lib/geocode";
import { isActive, useRide } from "@/lib/ride";
import { useCoverNav } from "@/lib/navCover";
import { usePlaces } from "@/lib/places";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { RiderHomeT2 } from "@/screens/t2/RiderHomeT2";
import { ConfirmRideT2 } from "@/screens/t2/ConfirmRideT2";
import {
  LocateButtonT2,
  MapHeaderT2,
  PickingSheetT2,
  PinT2,
  WhereToSheetT2,
} from "@/screens/t2/HomeMapT2";
import { ApproachChipT2, ThemeButtonT2, TrackingSheetT2, TripCardT2 } from "@/screens/t2/TrackingT2";
import { OutcomeSheetT2 } from "@/screens/t2/OutcomeT2";

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
  // **أبوابُ الرئيسيةِ الجديدة** (تصميمُ `home Rider`): الرصيدُ، والبلاطاتُ
  // واللافتاتُ معاً في نداءٍ واحد، وجائزةُ الإحالة، وآخرُ رحلاته.
  //
  // **وكلُّها `null` حتى تصل** — **ولا يُرسم صفرٌ مكانَ «لم يُعرف بعد»**، ولا
  // عنوانٌ فوق قائمةٍ فارغة.
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [storefront, setStorefront] = useState<Storefront | null>(null);
  const [referrals, setReferrals] = useState<MyReferrals | null>(null);
  const [recent, setRecent] = useState<Ride[]>([]);
  useEffect(() => {
    let cancelled = false;
    unreadCount()
      .then((body) => !cancelled && setUnreadNotifications(body.unread > 0))
      .catch(() => undefined); // جرسٌ بلا نقطةٍ أهونُ من شاشةِ خطأ
    getWallet()
      .then((body) => !cancelled && setWallet(body))
      .catch(() => undefined);
    getStorefront()
      .then((body) => !cancelled && setStorefront(body))
      .catch(() => undefined);
    getMyReferrals()
      .then((body) => !cancelled && setReferrals(body))
      .catch(() => undefined);
    // **ثلاثٌ لا عشرون**: الشريطُ أفقيٌّ وثلاثُ بطاقاتٍ تملؤه، **وزرُّ «الكل»
    // هو البابُ إلى الباقي** — فقراءةُ عشرين لعرض ثلاثٍ حملٌ بلا قارئ
    listMyRides(3, 0)
      .then(
        (body) =>
          !cancelled &&
          // **الغلافُ لا الرحلة**: `RideListItem` يحمل معها النزاعَ والمدفوع
          setRecent(body.map((row) => row.ride).filter((row) => !isActive(row))),
      )
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const tracking = isActive(ride);

  // **شارةُ الموقع في رأس رئيسية TAXO 2.0** (§٦١-د): اسمُ منطقة نقطة الانطلاق — **من Mapbox لا تخميناً**، ونقطتُها هي هي
  // (موقعُ الجهاز أو ما وضعه بالدبوس). **وبلا نقطةٍ أو بلا جوابٍ لا شارة.**
  const [area, setArea] = useState<string | null>(null);
  // **ومن النداء نفسِه عنوانُها كاملاً** — سطرُ «من» في «R06» حين لا عنوانَ غيرُه (موقعُ الجهاز لا يُسمّى)، **للنهاريّ وحدَه**:
  // الورقةُ القائمةُ تقرأ `pickupAddress` كما كانت
  const [pickupLine, setPickupLine] = useState<string | null>(null);
  useEffect(() => {
    if (!token || !pickup) return;
    const controller = new AbortController();
    void reverseArea(token, pickup, controller.signal).then((reading) => {
      if (controller.signal.aborted) return;
      setArea(reading.area);
      setPickupLine(reading.address);
    });
    return () => controller.abort();
    // النقطةُ بإحداثيّتيها لا بهويّة الكائن: كائنٌ جديدٌ للنقطة نفسِها لا يعيد السؤال
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, pickup?.lat, pickup?.lng]);

  // **«نسائية» تبدأ هذا الطلبَ بـ«كبتنة فقط»** (§٦١-د/ج) — والراكبةُ تغيّره بنفسها في ورقة الطلب، ولا شيءَ آليّ
  const [presetPreference, setPresetPreference] = useState<GenderPreference | undefined>();
  // **و«جدولي الرحلة لوقت لاحق» (RW3، §٦٢-ج/٢٣) تفتحها بفئة تلك الرحلة ومنتقي الموعد مفتوحاً** — `null` في كلِّ طلبٍ غيرِه
  const [presetSchedule, setPresetSchedule] = useState<VehicleCategory | null>(null);

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

  /** **سياراتٌ حولك أثناء البحث** (R07، §٦٢-ج/٢٧) — والمقبسُ يبثّها أصلاً ما لم يُسنَد كبتن (`ws/routes.py`: «أثناء الرحلة يرى
   *  الراكب كبتنه وحده»)، **وكانت الخريطةُ ترمي ما يصل**. **ولا تُرسم سيارةٌ لن تأتي**: ما يُرسم من صنف الرحلة وحدَه كما يوزّع
   *  التوزيعُ (`presence.vehicle_category == ride.vehicle_category`). **والطلبُ المفتوحُ وحدَه** («أي كبتن» في الرحلة وفي الملفّ):
   *  الخلفيةُ ترشّح القائمةَ بتفضيل الملفّ لا الرحلة (`drivers.nearby_available`)، **وعدُّ الكبتنات المتاحات بندٌ غيرُه** (§٦٢-ج/٢٨،
   *  مطفأٌ يتبع الخدمةَ النسائية) — فطلبُ «كبتنة فقط» يبقى بالرادار وحده كما كان. **و`null` = لا شيءَ يُرسم ولا يُعدّ**. */
  const searchingNow = ride?.status === "searching" || ride?.status === "requested";
  const carsWhileSearching =
    ride && searchingNow && ride.gender_preference === "any" && (user?.ride_gender_preference ?? "any") === "any"
      ? drivers.filter((driver) => driver.vehicle_category === ride.vehicle_category)
      : null;
  // **والبحثُ يسأل حول نقطة انطلاقه** لا حول آخر ما كانت عليه الكاميرا قبل الطلب — منها يقع التوزيع ومنها يتّسع الرادار
  const searchFrom = carsWhileSearching !== null && ride ? ride.pickup : null;
  useEffect(() => {
    if (searchFrom) setViewport(searchFrom);
    // النقطةُ بإحداثيّتيها لا بهويّة الكائن — كلُّ إطارٍ يحمل رحلةً بكائنٍ جديد
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchFrom?.lat, searchFrom?.lng, setViewport]);

  // **أثناء الرحلة يؤطّر مراقبُ الورقة الملتصقة** (R07–R09، أدناه) — فوقها لا تحتها، **في المظهرين** (§٦٢/٣ و/٨). وكان هنا إطارٌ
  // ثانٍ بالحشو الثابت لليليّ وحدَه، حين كان الليليُّ يرسم الشاشةَ القديمة

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

  /** **«أعِد الرحلة»** (تصميمُ `home Rider`) — **وجهةُ رحلةٍ ماضيةٍ في ورقة
   *  التأكيد**، لا طلبٌ يُرسل بلمسة.
   *
   *  **وثلاثةٌ لا تُنسخ من الرحلة القديمة**:
   *  1. **نقطةُ الانطلاق**: أين هو **الآن** لا أين كان — ونسخُها تضع كبتناً
   *     على رصيفٍ غادره الراكبُ منذ يومين.
   *  2. **الأجرة**: تُحسب في الخلفية لحظتَها (§14)، **والقديمةُ تعريفةُ يومها**.
   *  3. **المحطاتُ الوسيطة**: مسارٌ يُعاد بمحطاتٍ لم يطلبها **أغلى بلا إذنه**.
   *
   *  **فالمنسوخُ الوجهةُ وحدَها** — ومنها إلى الورقة التي يراجعها ويضغط. */
  function repeatRide(past: Ride) {
    pickPlace({
      id: `ride:${past.id}`,
      name: past.dropoff_address ?? "الوجهة",
      address: past.dropoff_address ?? "",
      coordinates: past.dropoff,
    });
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
      setPresetSchedule(null);
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
      setPresetPreference(undefined);
      setPresetSchedule(null);
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

  /** **«جدولي الرحلة لوقت لاحق»** (RW3، §٦٢-ج/٢٣) — **ورقةُ الطلب نفسُها لا بابٌ ثانٍ**: نقطتا الرحلة التي لم تجد كبتنة وعنواناهما،
   *  **وتفضيلُها هي** (لا يُبدَّل) **وفئتُها**، ومنتقي الموعد مفتوحاً — **والحجزُ يمرّ بـ`schedule` القائم** بموعده وفحوصه. **ولا محطات**:
   *  الحجزُ لا يحملها (`createBooking`). وتُطوى الخاتمة؛ فمن عادت بالسهم عادت إلى الرئيسية. */
  function scheduleAgain(previous: Ride) {
    setPickup(previous.pickup);
    setPickupAddress(previous.pickup_address);
    setDropoff(previous.dropoff);
    setDropoffAddress(previous.dropoff_address);
    setStops([]);
    setPresetPreference(previous.gender_preference);
    setPresetSchedule(previous.vehicle_category);
    setError(null);
    setDismissed(previous.id);
    setPhase("confirm");
  }

  const picking =
    phase === "pick-pickup" || phase === "pick-dropoff" || phase === "pick-stop";

  /** **الرئيسيةُ صفحةٌ لا خريطة** (تصميمُ `home Rider`) — **وطورُ الطلب لا
   *  يتغيّر**: من ضغط «إلى أين؟» عاد إلى الخريطة ملءَ الشاشة كما كانت.
   *
   *  **والشرطُ يجمع الأطوارَ الأربعةَ صراحةً** — لا `phase === "idle"` وحدَه:
   *  رحلةٌ جاريةٌ أو خاتمةٌ تُنتظر تسبقان الصفحةَ كلَّها، **وطورٌ رابعٌ
   *  يُضاف غداً يقع في الفرع الصحيح لأن الشرطَ يسمّي ما يقبله لا ما يرفضه**. */
  const browsing = !tracking && outcome === null && phase === "idle";

  /** ارتفاعُ الورقة الملتصقة في أطوار الطلب نهاراً — شعارُ الخريطة ونسبتُها فوقها (`controlsInset`). */
  const [sheetInset, setSheetInset] = useState(0);

  const mapNode = (
    <MapView
        ref={map}
        token={token}
        center={center}
        // أثناء الرحلة يرى الراكب كبتنه وحده (SPEC القسم 10) — **وقبل أن يُسنَد يرى ما حوله** ممّا قد يأتيه (R07)
        drivers={tracking ? carsWhileSearching ?? [] : drivers}
        // **ونهارُ TAXO 2.0 في الرئيسية يرسم «أنت هنا» وحدَها** (R05) — نقطةُ الانطلاق هي هي، فدبوسُها فوقها نقطتان لشيءٍ واحد
        pickup={tracking ? ride!.pickup : browsing ? null : pickup}
        dropoff={tracking ? ride!.dropoff : dropoff}
        driverLocation={driverPing}
        // **مركبةُ الكبتن بعد القبول وحدَه** — وقبله لا تتغيّر الخريطةُ في
        // شيء: `ride` نفسُه لا يوجد، والكباتنُ القريبون يظلّون كما هم
        driverSkin={ride?.driver?.skin ?? null}
        // **مسارُ الرحلة على الطرق بعد القبول** (البند ٨) — ويتقلّص خلف الكبتن
        routePoints={routeLine}
        trimAt={driverPing}
        // **نبضةُ الموقع الحالي** — لونُها `--brand` فتتبع الوضعَ والسِمة.
        // وتختفي أثناء الرحلة: الانتباهُ حينها لسيارة الكبتن لا لموقعي
        // **وفي ورقة الطلب نهاراً دائرةُ الانطلاق ومربّعُ الوجهة وحدهما** (R06) — بلا هالةٍ فوق الدائرة
        showMyLocation={tracking || picking || !browsing ? null : pickup}
        // **ونبضةٌ حول الانطلاق ما دام البحثُ جارياً** — تتوقف عند القبول،
        // فنبضٌ يبقى بعد الإسناد يقول «ما زلنا نبحث» وقد وُجد
        searching={ride?.status === "searching" || ride?.status === "requested"}
        // **شعارُ Mapbox ونسبتُه فوق الورقة الملتصقة لا عليها** — شرطُ الرخصة يبقى مرئيّاً على الخريطة
        controlsInset={sheetInset}
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
  );

  /** **ما يُمرَّر للصفحة — كائنٌ واحدٌ للوجهين**: صفحةُ TAXO 2.0 «R05» في النهاريّ المرسوم، والقائمةُ في الليليّ
   *  (§61-ب). فلا يفترق ما تقرؤه الصفحتان ولا أين يذهب زرٌّ فيهما. */
  const homeProps: RiderHomeProps = {
    name: user?.name ?? "بك",
    // **عنوانُ موقعه حين يُعرف** — ولا مدينةَ تُخمَّن من إحداثيّة
    place: pickupAddress,
    unread: unreadNotifications,
    wallet,
    currency: countryConfig?.currency ?? "JOD",
    nearby: drivers.length,
    onOpenNotifications: () => navigate("/account/notifications"),
    onOpenWallet: () => navigate("/wallet"),
    onOpenAccount: () => navigate("/account"),
    onAskDestination: () => {
      setPresetPreference(undefined);
      setPresetSchedule(null);
      setSearchOpen(true);
    },
    places,
    onPickPlace: (saved) =>
      pickPlace({
        id: `place:${saved.id}`,
        name: saved.label,
        address: saved.address ?? "",
        coordinates: { lat: saved.lat, lng: saved.lng },
      }),
    tiles: storefront?.tiles ?? [],
    banners: storefront?.banners ?? [],
    referrals,
    onOpenReferrals: () => navigate("/account/referrals"),
    recent,
    onOpenRides: () => navigate("/rides"),
    onRepeat: repeatRide,
    map: mapNode,
    area,
    onChangePickup: () => setPhase("pick-pickup"),
    onWomenRide: () => {
      setPresetPreference("female");
      setSearchOpen(true);
    },
  };

  // «رجوع» (الحزمة ب): يترك التخطيطَ كلَّه ويعود إلى «إلى أين؟».
  // ويمسح الوجهةَ لأن بقاءها يترك الشاشةَ في حالٍ لا زرَّ يعيدها
  // منه إلى ورقة التأكيد — أما المحطاتُ فمعها، إذ لا معنى
  // لمحطاتٍ بلا وجهة. **وفعلٌ واحدٌ للوجهين**: زرُّ الورقة القائمة وسهمُ الخريطة في TAXO 2.0
  const leaveConfirm = () => {
    setPhase("idle");
    setDropoff(null);
    setDropoffAddress(null);
    setStops([]);
    setPresetPreference(undefined);
    setPresetSchedule(null);
  };

  const locateMe = async () => {
    const position = await currentPosition();
    if (position) map.current?.flyTo(position, 15);
  };

  /** **ورقةُ التأكيد — خصائصُ واحدةٌ للوجهين** (القائمُ في الليليّ، و«R06» في النهاريّ المرسوم). */
  const confirmProps: ConfirmRideProps | null =
    pickup && dropoff
      ? {
          pickup,
          pickupAddress,
          dropoff,
          dropoffAddress,
          categories: countryConfig?.vehicle_categories ?? ["economy"],
          onEditDestination: () => setSearchOpen(true),
          onRequest: submit,
          onSchedule: schedule,
          requesting,
          requestError: error,
          stops,
          onStopsChange: setStops,
          onAddStop: () => setPhase("pick-stop"),
          blockedByPreference,
          onClearPreference: () => void clearGenderPreference(),
          countryConfig,
          onBack: leaveConfirm,
          initialPreference: presetPreference,
          initialCategory: presetSchedule ?? undefined,
          initialScheduling: presetSchedule !== null,
          pickupLine,
        }
      : null;

  /** **ورقةُ التأكيد كما رسمتها «R06»** — ورقةُ الطلب نفسُها لا «إلى أين؟» بلا انطلاق. */
  const confirming = phase === "confirm" && confirmProps !== null;
  /** **أطوارُ الطلب بلا شريط تبويب** كما رُسمت (R06، §٦١-د) — الدبوسُ وورقةُ التأكيد، **ولكلٍّ منهما مخرجُه إلى الرئيسية
   *  وشريطِها** (السهمُ و«إلغاء»). **و«إلى أين؟» بلا انطلاقٍ يُبقيه**: لا سهمَ فيها يعيد. **وفي المظهرين** (§٦٢/٣) — كان
   *  الليليُّ يرسم الشريطَ والورقةَ القديمين. */
  const requestT2 = !tracking && outcome === null && (picking || confirming);
  useCoverNav(requestT2);
  /** **والتتبّعُ «R07–R09»** — بلا شريطٍ أصلاً (الرحلةُ الجاريةُ تخفيه، `App.tsx::NavBar`) والورقةُ ملتصقةٌ كما رُسمت. */
  const trackingT2 = tracking;
  /** **وخاتمةُ الرحلة «R29» ملتصقةٌ كذلك** — لا شريطَ تحتها أصلاً (`NavBar` يُخفيه ما دامت رحلةٌ معروضة)، وكانت ورقتُها القديمةُ
   *  تطفو فوق مكانه فارغاً. */
  const sheetAttached = requestT2 || trackingT2 || outcome !== null;

  // آخرُ ما يُؤطَّر به — يُقرأ داخل المراقب بلا أن يعيد كلُّ بثٍّ إنشاءَه
  const rideNow = useRef(ride);
  rideNow.current = ride;
  const pingNow = useRef(driverPing);
  pingNow.current = driverPing;

  /** **إطارُ «R06–R09» فوق ورقته** — الحشوُ الثابتُ (٣٢٠) لورقةٍ فوق الشريط، والملتصقةُ أطولُ منه فيغيب الطريقُ تحتها.
   *  فيُقاس ارتفاعُها ويُعاد الإطارُ حين يتغيّر بما يُرى (يصل السعرُ · يُفتح الكوبون · تتبدّل الحال)، والرأسُ فوقه محفوظ.
   *  **والارتفاعُ نفسُه يرفع شعارَ الخريطة** في الأطوار كلِّها (الدبوسُ أيضاً). */
  const sheetBox = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const box = sheetBox.current;
    if (!sheetAttached || !box) {
      setSheetInset(0);
      return;
    }
    const frame = (): [Coordinates, Coordinates, number] | null => {
      if (confirming && pickup && dropoff) return [pickup, dropoff, 120];
      const current = rideNow.current;
      if (!trackingT2 || !current) return null;
      const riding = current.status === "in_progress" || current.status === "at_stop";
      const target = riding ? current.dropoff : current.pickup;
      // **وبطاقةُ الطريق في R09 أطولُ من حبّة R08** — فالإطارُ يبدأ تحتها
      const top = riding ? 170 : 120;
      const ping = pingNow.current;
      if (ping) return [{ lat: ping.lat, lng: ping.lng }, target, top];
      // **بلا موقعٍ للكبتن** (البحث): مربّعٌ صغيرٌ حول النقطة — فتُؤطَّر فوق الورقة لا تحتها
      return [
        { lat: target.lat - 0.004, lng: target.lng - 0.004 },
        { lat: target.lat + 0.004, lng: target.lng + 0.004 },
        top,
      ];
    };
    let last = 0;
    const observer = new ResizeObserver(() => {
      const height = Math.round(box.getBoundingClientRect().height);
      setSheetInset(height);
      if (Math.abs(height - last) < 24) return;
      last = height;
      const view = frame();
      if (view) map.current?.fitBounds(view[0], view[1], { top: view[2], bottom: height + 40 });
    });
    observer.observe(box);
    return () => observer.disconnect();
  }, [sheetAttached, trackingT2, confirming, pickup, dropoff, ride?.status]);

  return (
    <div className="relative h-full w-full overflow-hidden bg-bg">
      {browsing ? (
        <RiderHomeT2 {...homeProps} />
      ) : (
        <>
      {mapNode}

      {/* **ما فوق الخريطة — TAXO 2.0 في المظهرين** (§٦٢/٣): كان الليليُّ يرسم الرأسَ والدبوسَ القديمين، بالأفعال نفسِها */}
      {trackingT2 ? (
        // **التتبّعُ كما رُسم** (R07–R09): لا رأسَ ولا «موقعي» — «الكبتن على بعد…» أو بطاقةُ الطريق، **ومبدّلُ السِمة باقٍ**
        // (قرارُ المالك ٢٥ — وفي الرحلة لا شريطَ ولا «إعدادات» يُبلغان)
        <>
          {ride!.status === "in_progress" || ride!.status === "at_stop" ? (
            <TripCardT2 ride={ride!} driverPing={driverPing} routePoints={routeLine} />
          ) : (
            <ApproachChipT2 ride={ride!} driverPing={driverPing} />
          )}
          <ThemeButtonT2
            dark={dark}
            low={ride!.status === "in_progress" || ride!.status === "at_stop"}
            onToggle={() => setChoice(dark ? "light" : "dark")}
          />
        </>
      ) : (
        <>
          {picking ? <PinT2 target={phase === "pick-pickup" ? "pickup" : "dropoff"} /> : null}
          <MapHeaderT2
            initial={user?.name.slice(0, 1) ?? "؟"}
            unread={unreadNotifications}
            dark={dark}
            onBack={confirming ? leaveConfirm : null}
            onOpenAccount={() => navigate("/account")}
            onOpenNotifications={() => navigate("/account/notifications")}
            onToggleTheme={() => setChoice(dark ? "light" : "dark")}
          />
          {/* **ولا زرَّ «موقعي» في ورقة الطلب** كما رُسمت — النقطتان محدّدتان، والدبوسُ وحدَه يحتاجه */}
          {confirming ? null : <LocateButtonT2 onLocate={() => void locateMe()} />}
        </>
      )}

      {/* **الأوراقُ تنتهي فوق الشريط** (`bottom:66px` في النموذج): ورقةٌ تلتصق
          بأسفل الشاشة تحت شريطٍ ثابتٍ تُخفي سطرَها الأخير — وهو زرُّ الطلب */}
      {/* **وفي أطوار الطلب نهاراً لا شريطَ** (`requestT2`) — فالورقةُ ملتصقةٌ بأسفل الشاشة كما رُسمت */}
      <div
        ref={sheetBox}
        className={`pointer-events-none absolute inset-x-0 ${sheetAttached ? "bottom-0" : "bottom-nav"} mx-auto max-w-lg`}
      >
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
              <TrackingSheetT2
                ride={ride!}
                onChanged={() => void refresh()}
                driverPing={driverPing}
                routePoints={routeLine}
                nearby={carsWhileSearching === null ? null : carsWhileSearching.length}
                pickupLine={
                  pickup && pickup.lat === ride!.pickup.lat && pickup.lng === ride!.pickup.lng ? pickupLine : null
                }
              />
            ) : outcome ? (
              <OutcomeSheetT2
                ride={outcome}
                onDismiss={() => setDismissed(outcome.id)}
                onAcceptAnyDriver={() => acceptAnyDriver(outcome)}
                onScheduleAgain={() => scheduleAgain(outcome)}
                error={error}
              />
            ) : picking ? (
              <PickingSheetT2
                targetLabel={phase === "pick-pickup" ? "نقطة الانطلاق" : "وجهتك"}
                address={pinAddress}
                loading={pinLoading}
                onConfirm={confirmPin}
                onCancel={() => setPhase(dropoff ? "confirm" : "idle")}
              />
            ) : phase === "confirm" && confirmProps ? (
              <ConfirmRideT2 {...confirmProps} />
            ) : (
              <WhereToSheetT2
                places={places}
                pickupLabel={pickupAddress ?? (pickup ? "الموقع المحدد" : "موقعي الحالي")}
                onSearch={() => setSearchOpen(true)}
                onPickPlace={(place) =>
                  pickPlace({
                    id: `place:${place.id}`,
                    name: place.label,
                    address: place.address ?? "",
                    coordinates: { lat: place.lat, lng: place.lng },
                  })
                }
                onChangePickup={() => setPhase("pick-pickup")}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

        </>
      )}

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
