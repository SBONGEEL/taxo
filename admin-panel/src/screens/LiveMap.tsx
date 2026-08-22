/** الخريطة الحيّة — SPEC القسم 13/1، و`DESIGN.md` §1.4 (عمودٌ جانبي 340px).
 *
 * **الشاشة الوحيدة في المنصة التي تقرن اسماً بموقع**، ولذلك ثلاثة أشياء فيها
 * مقصودة:
 *
 * 1. **`admin` وحده يفتحها**، والخلفية هي من ترفض غيره (403). وإخفاؤها من
 *    القائمة عن `support` رسمٌ لا حماية — كما في بقية اللوحة.
 * 2. **يظهر في أعلاها أن فتحها مُسجَّل.** لا لأن المشرف يحتاج التذكير، بل لأن
 *    صلاحيةً بهذا الاتساع يجب أن تُعلن عن نفسها لمن يستعملها؛ ورقابةٌ صامتة
 *    تُكتشف لاحقاً تُقرأ خيانةً لا انضباطاً.
 * 3. **ولا زرَّ «تعيين سائق».** الإسنادُ اليدوي بندٌ مؤجَّل في
 *    `FUTURE-FEATURES` (27): الرحلةُ تُعرض على كبتنٍ واحدٍ في كل لحظة عبر
 *    `services/dispatch.py`، وزرٌّ يتخطاه من اللوحة يكسر العرضَ الجاري ويسند
 *    رحلةً لكبتنٍ لم يقبلها. فما هنا مراقبةٌ خالصة.
 *
 * **والتحديث بالاستعلام لا بمقبس**: مقبسُ `ws/` يبثّ لصاحب الرحلة وللكبتن
 * المسنَد، ولا قناةَ فيه تجمع دولةً كاملة — وإضافتها تعني بثَّ مواقع الجميع
 * إلى اتصالٍ مفتوح. واستعلامٌ كل خمس ثوانٍ يكفي سؤالاً عن «أين هم الآن».
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { getLiveMap } from "@/api/endpoints";
import type { LiveDriver, LiveMap, LivePendingRide } from "@/api/types";
import { LiveCanvas } from "@/components/LiveCanvas";
import { Shell } from "@/components/Shell";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { useSession } from "@/lib/session";
import { digits, cn,
  DISPLAY_LOCALE,
} from "@/lib/utils";
import type { CountryCode } from "@/api/types";

/** مركزُ البداية قبل أن يظهر أحد — العاصمة، كما في تطبيق الراكب. */
const CENTER: Record<CountryCode, { lat: number; lng: number }> = {
  JO: { lat: 31.9539, lng: 35.9106 },
  LY: { lat: 32.8872, lng: 13.1913 },
};

const REFRESH_MS = 5_000;

const CATEGORY_LABEL: Record<string, string> = {
  economy: "اقتصادية",
  comfort: "مريحة",
};

export function LiveMapScreen() {
  const { country } = useCountry();
  const { config } = useConfig();
  const { isAdmin } = useSession();
  const token = config?.providers.mapbox?.public_token ?? null;

  const [data, setData] = useState<LiveMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  // آخرُ لحظةِ وصولِ إجابة — «قبل ثانيتين» أصدقُ من صمتٍ يوحي بأن الشاشة حيّة
  const [freshAt, setFreshAt] = useState<Date | null>(null);
  const timer = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await getLiveMap(country));
      setFreshAt(new Date());
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تحديث الخريطة",
      );
    }
  }, [country]);

  useEffect(() => {
    setData(null);
    setSelected(null);
    void load();
    timer.current = window.setInterval(() => void load(), REFRESH_MS);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [load]);

  if (!isAdmin) {
    return (
      <Shell title="الخريطة الحيّة">
        <ErrorNote message="هذه الشاشة لمالك الحساب وحده." />
      </Shell>
    );
  }

  const drivers = data?.drivers ?? [];
  const pending = data?.pending_rides ?? [];
  const free = drivers.filter((row) => !row.on_ride).length;

  return (
    <Shell
      title="الخريطة الحيّة"
      subtitle="من في الشارع الآن، والطلبات التي لم يأخذها أحد"
    >
      <div className="mb-14 flex flex-wrap items-center gap-x-16 gap-y-6 rounded-13 border border-line bg-surface-2 px-14 py-10 text-11.5 text-muted">
        <span>
          فتحُ هذه الشاشة مُسجَّلٌ في سجل التدقيق باسمك — فهي تعرض أسماء
          السائقين وأرقامهم ومواقعهم الآنية.
        </span>
        <span className="ms-auto">
          {freshAt
            ? `آخر تحديث ${digits(
                digits(freshAt.toLocaleTimeString(DISPLAY_LOCALE, {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })),
              )}`
            : "…"}
        </span>
      </div>

      <ErrorNote message={error} />

      {data === null ? (
        <Spinner className="mx-auto" />
      ) : (
        <div className="flex flex-col gap-14 lg:flex-row">
          <div className="h-live flex-1 overflow-hidden rounded-16 border border-line bg-surface">
            <LiveCanvas
              token={token}
              center={CENTER[country]}
              drivers={drivers}
              pendingRides={pending}
              selected={selected}
              onSelect={(id) => setSelected(id === selected ? null : id)}
            />
          </div>

          <aside className="flex h-live flex-col gap-12 overflow-y-auto lg:w-side">
            <div className="grid grid-cols-3 gap-8">
              <Tally label="متصلون" value={drivers.length} />
              <Tally label="متفرّغون" value={free} />
              <Tally
                label="بانتظار سائق"
                value={pending.length}
                tone={pending.length > 0 ? "text-warn" : undefined}
              />
            </div>

            <Section title="طلبات بانتظار سائق">
              {pending.length === 0 ? (
                <Empty text="لا طلب معلّق الآن." />
              ) : (
                pending.map((ride) => <PendingRow key={ride.ride_id} ride={ride} />)
              )}
            </Section>

            <Section title="السائقون المتصلون">
              {drivers.length === 0 ? (
                <Empty text="لا أحد متصلٌ في هذه الدولة الآن." />
              ) : (
                drivers.map((driver) => (
                  <DriverRow
                    key={driver.driver_id}
                    driver={driver}
                    selected={selected === driver.driver_id}
                    onPick={() =>
                      setSelected(
                        selected === driver.driver_id ? null : driver.driver_id,
                      )
                    }
                  />
                ))
              )}
            </Section>
          </aside>
        </div>
      )}
    </Shell>
  );
}

function Tally({
  label,
  value,
  tone = "text-ink",
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="rounded-13 border border-line bg-surface p-12 text-center">
      <div className={cn("text-20 font-bold", tone)}>
        {digits(String(value))}
      </div>
      <div className="mt-3 text-10.5 text-muted">{label}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-16 border border-line bg-surface p-14">
      <h2 className="mb-10 text-12.5 font-bold text-ink">{title}</h2>
      <div className="flex flex-col gap-8">{children}</div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="text-11.5 text-muted">{text}</p>;
}

function DriverRow({
  driver,
  selected,
  onPick,
}: {
  driver: LiveDriver;
  selected: boolean;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onPick}
      className={cn(
        "rounded-13 border p-11 text-start",
        selected ? "border-ink bg-stripe-a" : "border-line",
      )}
    >
      <div className="flex items-baseline justify-between gap-8">
        <span className="text-12.5 font-semibold text-ink">{driver.name}</span>
        <span
          className={cn(
            "text-10.5 font-semibold",
            driver.state === "on_ride"
              ? "text-ok"
              : driver.state === "stale"
                ? "text-warn"
                : "text-muted",
          )}
        >
          {driver.state === "on_ride"
            ? "في رحلة"
            : driver.state === "stale"
              ? "بثُّه توقّف"
              : "متفرّغ"}
        </span>
      </div>
      {/* الرقمُ كما هو: المشرف يطلبه أو يقارنه بما يقوله الكبتن، وتعريبُ
          خاناته يجعله يطابق سلسلةً بشكلٍ آخر — الأرقام الهندية للكميّات لا
          للمعرّفات، كما في `Cards.tsx` و`Vehicle.tsx` عند الكبتن */}
      <div className="mt-3 text-11 text-muted" dir="ltr">
        {driver.phone}
      </div>
      {/* **«منذ كم» لا «متى»**: اللوحةُ تُستفتى كلَّ خمس ثوانٍ، والمشرفُ
          يسأل عن الطزاجة لا عن التوقيت. و`null` تُقرأ «غيرُ معلوم» */}
      <div className="mt-3 text-10.5 text-muted">
        {driver.seconds_since_update === null
          ? "آخر بثّ: غير معلوم"
          : `آخر بثّ منذ ${digits(String(driver.seconds_since_update))} ثانية`}
      </div>
      <div className="mt-3 text-10.5 text-muted">
        {CATEGORY_LABEL[driver.vehicle_category] ?? driver.vehicle_category}
        {driver.plate_number ? ` · ${driver.plate_number}` : ""}
      </div>
    </button>
  );
}

function PendingRow({ ride }: { ride: LivePendingRide }) {
  return (
    <div className="rounded-13 border border-warn bg-surface-2 p-11">
      <div className="flex items-baseline justify-between gap-8">
        <span className="text-11.5 font-semibold text-ink">
          {ride.status === "searching" ? "يُعرض على سائق" : "طلبٌ جديد"}
        </span>
        <span className="text-10.5 text-muted">{sinceLabel(ride.created_at)}</span>
      </div>
      <div className="mt-3 text-10.5 text-muted" dir="ltr">
        {ride.lat.toFixed(4)}, {ride.lng.toFixed(4)}
      </div>
    </div>
  );
}

/** «منذ كم» بالدقائق — والرقمُ من فرقٍ زمنيّ لا مالٍ، فتعريبُه عرضٌ لا حساب. */
function sinceLabel(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `منذ ${digits(String(Math.floor(seconds)))} ث`;
  return `منذ ${digits(String(Math.floor(seconds / 60)))} د`;
}
