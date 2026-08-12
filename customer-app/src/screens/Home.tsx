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
import { Crosshair, Menu, Search, Wallet } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { requestRide, updateMe } from "@/api/endpoints";
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

  const tracking = isActive(ride);
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

  async function submit(category: VehicleCategory, preference: GenderPreference) {
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
        onMoveEnd={setCenter}
      />

      {/* دبوسٌ ثابت في المركز: الخريطة تتحرك تحته لا هو فوقها */}
      {picking ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center pb-40">
          <motion.div initial={{ y: -8 }} animate={{ y: 0 }} className="text-38">
            📍
          </motion.div>
        </div>
      ) : null}

      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between gap-8 px-16 pt-safe">
        <button
          type="button"
          onClick={() => navigate("/menu")}
          className="pointer-events-auto rounded-full border border-line bg-surface p-12 shadow-sm backdrop-blur"
          aria-label="القائمة"
        >
          <Menu className="size-20 text-ink" />
        </button>
        <button
          type="button"
          onClick={() => navigate("/wallet")}
          className="pointer-events-auto rounded-full border border-line bg-surface p-12 shadow-sm backdrop-blur"
          aria-label="محفظتي"
        >
          <Wallet className="size-20 text-ink" />
        </button>
      </div>

      <button
        type="button"
        onClick={async () => {
          const position = await currentPosition();
          if (position) map.current?.flyTo(position, 15);
        }}
        className="absolute bottom-[42%] end-16 rounded-full border border-line bg-surface p-12 shadow-sm backdrop-blur"
        aria-label="موقعي الحالي"
      >
        <Crosshair className="size-20 text-ink" />
      </button>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 mx-auto max-w-lg">
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
                requesting={requesting}
                requestError={error}
                stops={stops}
                onStopsChange={setStops}
                onAddStop={() => setPhase("pick-stop")}
                blockedByPreference={blockedByPreference}
                onClearPreference={() => void clearGenderPreference()}
              />
            ) : (
              <Sheet>
                <div className="space-y-12 pb-16">
                  <p className="text-18 font-semibold text-ink">إلى أين؟</p>
                  <button
                    type="button"
                    onClick={() => setSearchOpen(true)}
                    className="flex w-full items-center gap-12 rounded-12 border border-line bg-bg px-16 py-14 text-start"
                  >
                    <Search className="size-20 text-muted" />
                    <span className="text-muted">ابحث عن وجهتك أو حدّدها بالدبوس</span>
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
                          className="min-w-0 flex-1 rounded-12 border border-line bg-surface px-12 py-10 text-start transition hover:bg-surface-2"
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

                  <button
                    type="button"
                    onClick={() => setPhase("pick-pickup")}
                    className="w-full truncate text-start text-14 text-muted"
                  >
                    نقطة الانطلاق:{" "}
                    <span className="text-ink">
                      {pickupAddress ?? (pickup ? "الموقع المحدد" : "موقعي الحالي")}
                    </span>
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
