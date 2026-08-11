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

import { Bell, Moon, Sun } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  acceptRide,
  arriveRide,
  cancelRide,
  completeRide,
  declineRide,
  getDriverWallet,
  getMySubscription,
  startRide,
} from "@/api/endpoints";
import type { MySubscription, Ride, Wallet } from "@/api/types";
import { ActiveRide } from "@/components/ActiveRide";
import { CollectScreen } from "@/screens/Collect";
import { RateRiderScreen } from "@/screens/RateRider";
import { BottomNav } from "@/components/BottomNav";
import { MapView } from "@/components/map/MapView";
import { OfferSheet } from "@/components/OfferSheet";
import { ErrorNote } from "@/components/ui/Feedback";
import { useConfig, useMapboxToken } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { isActive, useRide } from "@/lib/ride";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { arabicDigits, cn } from "@/lib/utils";

const CURRENCY_LABEL: Record<string, string> = { JOD: "د.أ", LYD: "د.ل" };
const CURRENCY_FULL: Record<string, string> = {
  JOD: "دينار أردني",
  LYD: "دينار ليبي",
};
const CATEGORY_LABEL: Record<string, string> = {
  economy: "اقتصادي",
  comfort: "مريح",
};

export function HomeScreen() {
  const navigate = useNavigate();
  const { user } = useSession();
  const { config } = useConfig();
  const { profile } = useDriver();
  const { dark, toggle } = useTheme();
  const token = useMapboxToken();
  const {
    online,
    connecting,
    ride,
    offer,
    position,
    error,
    goOnline,
    goOffline,
    setRide,
    dismissOffer,
    clearError,
  } = useRide();

  // ما بعد الإنهاء: التحصيل ثم التقييم — رحلةٌ واحدة لا شاشتان مستقلتان،
  // فالخروجُ منهما بيد الكبتن لا بحدثٍ من الخلفية
  const [settling, setSettling] = useState<Ride | null>(null);
  const [rating, setRating] = useState<Ride | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [subscription, setSubscription] = useState<MySubscription | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const currencyCode =
    config?.countries.find((c) => c.country_code === user?.country_code)
      ?.currency ?? "JOD";
  const currency =
    CURRENCY_LABEL[
      config?.countries.find((c) => c.country_code === user?.country_code)
        ?.currency ?? "JOD"
    ] ?? "";

  useEffect(() => {
    getDriverWallet()
      .then(setWallet)
      .catch(() => undefined);
    getMySubscription()
      .then(setSubscription)
      .catch(() => undefined);
  }, []);

  const tracking = isActive(ride);
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
      else if (ride.status === "in_progress") {
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
          getDriverWallet()
            .then(setWallet)
            .catch(() => undefined);
        }}
      />
    );
  }
  if (rating) {
    return <RateRiderScreen ride={rating} onDone={() => setRating(null)} />;
  }

  return (
    <div className="relative h-full overflow-hidden bg-bg">
      <MapView
        token={token}
        center={position}
        pickup={tracking ? ride.pickup : null}
        dropoff={tracking ? ride.dropoff : null}
        fit={tracking}
        className="absolute inset-0"
      />

      {/* تدرّجٌ علوي 60px يفصل الشريط عن الخريطة (§2.9) */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-60 bg-gradient-to-b from-bg to-transparent" />

      {!tracking ? (
        <>
          <div className="absolute inset-x-16 top-12 flex items-center justify-between gap-8">
            <div className="flex items-center gap-8 rounded-full border border-line bg-surface px-13 py-8">
              <span
                className={cn(
                  "block size-8 rounded-full",
                  online ? "bg-ok" : "bg-muted",
                )}
              />
              <span className="text-12.5 font-semibold text-ink">
                {online ? "متصل" : "غير متصل"}
              </span>
            </div>

            <div className="flex gap-7">
              <button
                type="button"
                onClick={() => navigate("/account")}
                aria-label="الإشعارات"
                className="flex size-33 items-center justify-center rounded-full border border-line bg-surface text-ink"
              >
                <Bell className="size-16" />
              </button>
              <button
                type="button"
                onClick={toggle}
                aria-label="تبديل المظهر"
                className="flex size-33 items-center justify-center rounded-full border border-line bg-surface text-ink"
              >
                {dark ? (
                  <Sun className="size-16" />
                ) : (
                  <Moon className="size-16" />
                )}
              </button>
            </div>
          </div>

          {/* لافتةُ الاشتراك — تظهر إلا حين يكون سارياً بلا قرب انتهاء */}
          {subscription && !covered ? (
            <button
              type="button"
              onClick={() => navigate("/subscription")}
              className="absolute inset-x-16 top-62 flex animate-slideup items-center gap-10 rounded-14 border border-danger bg-surface px-13 py-11 text-start"
            >
              <span className="block h-36 w-6 shrink-0 rounded-4 bg-danger" />
              <span className="min-w-0 flex-1">
                <span className="block text-12.5 font-bold text-ink">
                  لا اشتراك ساري
                </span>
                <span className="block text-11 text-muted">
                  اشترك لتبدأ استقبال الطلبات.
                </span>
              </span>
              <span className="shrink-0 rounded-9 bg-accent px-12 py-7 text-11.5 font-bold text-accent-ink">
                اشترك
              </span>
            </button>
          ) : null}

          {online && !offer ? (
            <div className="absolute inset-x-0 top-62 flex justify-center">
              <span className="flex animate-pulse items-center gap-9 rounded-full border border-line bg-surface px-18 py-9 text-12.5 font-semibold text-ink">
                <span className="block size-8 rounded-full bg-ok" />
                {position ? "بانتظار الطلبات…" : "بانتظار إشارة الموقع…"}
              </span>
            </div>
          ) : null}

          <div className="absolute inset-x-0 bottom-nav bg-gradient-to-t from-bg from-55% to-transparent px-16 pb-12 pt-14">
            <div className="mb-10 flex gap-8">
              {[
                {
                  label: "المحفظة",
                  value: wallet ? arabicDigits(wallet.balance) : "—",
                },
                { label: "رحلات اليوم", value: "—" },
                {
                  label: "التقييم",
                  value: profile
                    ? arabicDigits(Number(profile.driver.rating_avg).toFixed(1))
                    : "—",
                },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="flex-1 rounded-14 border border-line bg-surface px-12 py-10"
                >
                  <div className="text-10 text-muted">{stat.label}</div>
                  <div className="text-15 font-bold text-ink">{stat.value}</div>
                </div>
              ))}
            </div>

            {error || actionError ? (
              <div className="mb-10">
                <ErrorNote message={error ?? actionError} />
              </div>
            ) : null}

            <button
              type="button"
              disabled={connecting}
              onClick={() => {
                clearError();
                if (!covered) navigate("/subscription");
                else if (online) goOffline();
                else goOnline();
              }}
              className={cn(
                "w-full rounded-16 border border-line p-16 text-center text-15 font-bold",
                !covered
                  ? "bg-surface-2 text-muted"
                  : online
                    ? "bg-surface text-ink"
                    : "bg-accent text-accent-ink",
              )}
            >
              {goLabel}
            </button>
          </div>

          <BottomNav />
        </>
      ) : (
        <ActiveRide
          ride={ride}
          currencyLabel={currency}
          busy={busy}
          onAdvance={() => void advance()}
          onCancel={() =>
            void run(async () =>
              setRide(await cancelRide(ride.id, "إلغاء من الكبتن")),
            )
          }
        />
      )}

      {offer ? (
        <OfferSheet
          offer={offer}
          currencyLabel={currency}
          categoryLabel={CATEGORY_LABEL[offer.ride.vehicle_category] ?? ""}
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
    </div>
  );
}
