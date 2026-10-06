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
 *
 * **وبلغة TAXO 2.0** (A03 — `design/t2-new/admin/A03-live-map.dc.html`): الخريطةُ بطاقةٌ بلغة «TaxoMap»، والعمودُ إلى جانبها
 * بثلاثة أعدادٍ بخطّ Unbounded ثمّ القائمتين — **والمنطقُ كما كان حرفاً**: الاستطلاعُ والاختيارُ والتوسيطُ مرّةً عند الاختيار.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { getLiveMap } from "@/api/endpoints";
import type { LiveDriver, LiveMap, LivePendingRide } from "@/api/types";
import { LiveCanvas } from "@/components/LiveCanvas";
import { Shell } from "@/components/Shell";
import { Badge } from "@/components/ui/Badge";
import type { Tone } from "@/components/ui/Badge";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { useSession } from "@/lib/session";
import { digits, cn,
  DISPLAY_LOCALE,
} from "@/lib/utils";
import { Icon } from "@/taxo2";
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
      {/* **فتحُها مُسجَّل — ويُقال ذلك أعلاها** (رأسُ الملفّ): صلاحيةٌ بهذا الاتساع تُعلن عن نفسها لمن يستعملها */}
      <div className="ad-live-note">
        <Icon name="visibility" />
        <span className="ad-live-note-text">
          فتحُ هذه الشاشة مُسجَّلٌ في سجل التدقيق باسمك — فهي تعرض أسماء
          السائقين وأرقامهم ومواقعهم الآنية.
        </span>
        <span className="ad-live-note-time">
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
        error ? null : (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        )
      ) : (
        <div className="ad-live">
          <div className="ad-live-map">
            <LiveCanvas
              token={token}
              center={CENTER[country]}
              drivers={drivers}
              pendingRides={pending}
              selected={selected}
              onSelect={(id) => setSelected(id === selected ? null : id)}
            />
          </div>

          <aside className="ad-live-side" aria-label="القائمتان">
            <div className="ad-tallies">
              <Tally label="متصلون" value={drivers.length} />
              <Tally label="متفرّغون" value={free} />
              <Tally label="بانتظار سائق" value={pending.length} warn={pending.length > 0} />
            </div>

            <Section title="طلبات بانتظار سائق">
              {pending.length === 0 ? (
                <Empty text="لا طلب معلّق الآن." />
              ) : (
                pending.map((ride) => <PendingRow key={ride.ride_id} ride={ride} />)
              )}
            </Section>

            {/* **يملأ العمودَ حين يحمل صفوفاً** فتُمرَّر داخله — وفارغاً بطاقةٌ بسطرها لا لوحٌ أجوف بطول الخريطة */}
            <Section title="السائقون المتصلون" grow={drivers.length > 0}>
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
  warn = false,
}: {
  label: string;
  value: number;
  warn?: boolean;
}) {
  return (
    <div className={warn ? "ad-tally warn" : "ad-tally"}>
      <span className="ad-num">{digits(String(value))}</span>
      <span className="ad-tally-label">{label}</span>
    </div>
  );
}

function Section({
  title,
  children,
  grow = false,
}: {
  title: string;
  children: React.ReactNode;
  grow?: boolean;
}) {
  return (
    <section className={grow ? "ad-live-sec grow" : "ad-live-sec"}>
      <h2 className="ad-live-sec-title">{title}</h2>
      <div className="ad-live-list">{children}</div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="ad-mini-empty">{text}</p>;
}

const STATE_LABEL: Record<LiveDriver["state"], string> = {
  on_ride: "في رحلة",
  stale: "بثُّه توقّف",
  available: "متفرّغ",
};
const STATE_TONE: Record<LiveDriver["state"], Tone> = {
  on_ride: "ok",
  stale: "warn",
  available: "muted",
};

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
      className={cn("ad-live-row", selected && "on")}
    >
      <span className="ad-live-row-top">
        <span className="ad-live-row-name">{driver.name}</span>
        <Badge tone={STATE_TONE[driver.state]}>{STATE_LABEL[driver.state]}</Badge>
      </span>
      {/* الرقمُ كما هو: المشرف يطلبه أو يقارنه بما يقوله الكبتن، وتعريبُ
          خاناته يجعله يطابق سلسلةً بشكلٍ آخر — الأرقام الهندية للكميّات لا
          للمعرّفات، كما في `Cards.tsx` و`Vehicle.tsx` عند الكبتن */}
      <span className="ad-live-row-line ad-ltr" dir="ltr">
        {driver.phone}
      </span>
      {/* **«منذ كم» لا «متى»**: اللوحةُ تُستفتى كلَّ خمس ثوانٍ، والمشرفُ
          يسأل عن الطزاجة لا عن التوقيت. و`null` تُقرأ «غيرُ معلوم» */}
      <span className="ad-live-row-line">
        {driver.seconds_since_update === null
          ? "آخر بثّ: غير معلوم"
          : `آخر بثّ منذ ${digits(String(driver.seconds_since_update))} ثانية`}
        {" · "}
        {CATEGORY_LABEL[driver.vehicle_category] ?? driver.vehicle_category}
        {driver.plate_number ? ` · ${driver.plate_number}` : ""}
      </span>
    </button>
  );
}

function PendingRow({ ride }: { ride: LivePendingRide }) {
  return (
    <div className="ad-live-row wait">
      <span className="ad-live-row-top">
        <span className="ad-live-row-name">
          {ride.status === "searching" ? "يُعرض على سائق" : "طلبٌ جديد"}
        </span>
        <span className="ad-live-row-since">{sinceLabel(ride.created_at)}</span>
      </span>
      <span className="ad-live-row-line ad-ltr" dir="ltr">
        {ride.lat.toFixed(4)}, {ride.lng.toFixed(4)}
      </span>
    </div>
  );
}

/** «منذ كم» بالدقائق — والرقمُ من فرقٍ زمنيّ لا مالٍ، فتعريبُه عرضٌ لا حساب. */
function sinceLabel(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `منذ ${digits(String(Math.floor(seconds)))} ث`;
  return `منذ ${digits(String(Math.floor(seconds / 60)))} د`;
}
