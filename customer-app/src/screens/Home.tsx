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
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { requestRide } from "@/api/endpoints";
import type { Coordinates, Ride, VehicleCategory } from "@/api/types";
import { DestinationSearch } from "@/components/home/DestinationSearch";
import { ConfirmRide } from "@/components/home/ConfirmRide";
import { MapView, type MapHandle } from "@/components/map/MapView";
import { TrackingSheet } from "@/components/ride/TrackingSheet";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { useCountryConfig, useMapboxToken } from "@/lib/config";
import { DEFAULT_CENTER, currentPosition, reverseGeocode, type Place } from "@/lib/geocode";
import { RIDE_STATUS_LABEL } from "@/lib/labels";
import { isActive, useRide } from "@/lib/ride";
import { useSession } from "@/lib/session";
import { formatMoney } from "@/lib/utils";

type Phase = "idle" | "pick-pickup" | "pick-dropoff" | "confirm";

export function HomeScreen() {
  const navigate = useNavigate();
  const { user } = useSession();
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

  // مركز الخريطة يذهب للخلفية فترسل السيارات حوله — لا سياراتَ بلا مركز
  useEffect(() => {
    if (!tracking) setViewport(center);
  }, [center, tracking, setViewport]);

  // أثناء الرحلة: الإطار يضم الكبتن والوجهة معاً
  useEffect(() => {
    if (!ride || !tracking) return;
    const target = ride.status === "in_progress" ? ride.dropoff : ride.pickup;
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
    setDropoff(point);
    void describe(point, "dropoff");
    setPhase("confirm");
    if (pickup) map.current?.fitBounds(pickup, point);
  }

  async function submit(category: VehicleCategory) {
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
      });
      // الرحلة تعود `requested`؛ انتقالها إلى `searching` يصل عبر المقبس
      setRide(created);
      setPhase("idle");
      setDropoff(null);
      setDropoffAddress(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إرسال الطلب");
    } finally {
      setRequesting(false);
    }
  }

  const picking = phase === "pick-pickup" || phase === "pick-dropoff";

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
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center pb-10">
          <motion.div initial={{ y: -8 }} animate={{ y: 0 }} className="text-4xl">
            📍
          </motion.div>
        </div>
      ) : null}

      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between gap-2 px-4 pt-safe">
        <button
          type="button"
          onClick={() => navigate("/menu")}
          className="pointer-events-auto rounded-full border border-line bg-surface/95 p-3 shadow-sm backdrop-blur"
          aria-label="القائمة"
        >
          <Menu className="size-5 text-ink" />
        </button>
        <button
          type="button"
          onClick={() => navigate("/wallet")}
          className="pointer-events-auto rounded-full border border-line bg-surface/95 p-3 shadow-sm backdrop-blur"
          aria-label="محفظتي"
        >
          <Wallet className="size-5 text-ink" />
        </button>
      </div>

      <button
        type="button"
        onClick={async () => {
          const position = await currentPosition();
          if (position) map.current?.flyTo(position, 15);
        }}
        className="absolute bottom-[42%] end-4 rounded-full border border-line bg-surface/95 p-3 shadow-sm backdrop-blur"
        aria-label="موقعي الحالي"
      >
        <Crosshair className="size-5 text-ink" />
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
              <OutcomeSheet ride={outcome} onDismiss={() => setDismissed(outcome.id)} />
            ) : picking ? (
              <Sheet>
                <div className="space-y-3 pb-4">
                  <p className="text-center text-sm text-muted">
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
              />
            ) : (
              <Sheet>
                <div className="space-y-3 pb-4">
                  <p className="text-lg font-semibold text-ink">إلى أين؟</p>
                  <button
                    type="button"
                    onClick={() => setSearchOpen(true)}
                    className="flex w-full items-center gap-3 rounded-xl border border-line bg-bg px-4 py-3.5 text-start"
                  >
                    <Search className="size-5 text-muted" />
                    <span className="text-muted">ابحث عن وجهتك أو حدّدها بالدبوس</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setPhase("pick-pickup")}
                    className="w-full truncate text-start text-sm text-muted"
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
function OutcomeSheet({ ride, onDismiss }: { ride: Ride; onDismiss: () => void }) {
  const navigate = useNavigate();
  const completed = ride.status === "completed";

  return (
    <Sheet>
      <div className="space-y-3 pb-4">
        <p className="text-lg font-semibold text-ink">{RIDE_STATUS_LABEL[ride.status]}</p>

        {completed ? (
          <>
            <p className="text-sm text-muted">
              الأجرة النهائية{" "}
              <span className="font-semibold text-ink">
                {formatMoney(ride.final_fare ?? ride.estimated_fare, ride.currency)}
              </span>
            </p>
            <Button size="lg" onClick={() => navigate(`/rides/${ride.id}/pay`)}>
              الانتقال إلى الدفع
            </Button>
          </>
        ) : (
          <p className="text-sm text-muted">
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
