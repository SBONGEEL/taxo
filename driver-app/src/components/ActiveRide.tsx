/** الرحلة النشطة — SPEC القسم 12/4، وشكلُها من `DESIGN.md` §5.3.
 *
 * ثلاثةُ أطوارٍ بزرٍّ واحد يتبدّل نصُّه: «وصلتُ إلى الراكب» ← «بدء الرحلة»
 * ← «إنهاء الرحلة». **وطوران خامسٌ وسادس مع المحطات** (المرحلة 12-ب):
 * «وصلتُ المحطة» ثم «استئناف». والانتقالُ يُطلب من الخلفية وحدها
 * (`services/rides.py::ALLOWED_TRANSITIONS`) — الزرُّ يسأل ولا يقرّر، والحالةُ
 * الجديدة تأتي من ردّها لا من افتراضٍ محلي.
 *
 * ولون النقطتين يحمل الطور: قبل الركوب الانطلاقُ حيٌّ والوجهةُ خافتة، وبعد
 * `in_progress` ينعكسان (`DESIGN.md` §2.8).
 *
 * **ولا شاشةَ تحصيلٍ هنا**: `POST /rides/{id}/complete` يُنهي الرحلة،
 * وتحصيلُ الأجرة شاشةٌ مستقلة على `payments` تأتي في الجلسة التالية —
 * فالزرُّ الأخير ينهي الرحلة ويعود بالكبتن إلى الرئيسية حتى تُبنى.
 */

import { useEffect, useState } from "react";
import { Navigation } from "lucide-react";

import type { GenderPreference, Ride } from "@/api/types";
import { openIn, targetFor } from "@/lib/external-maps";
import type { NextInstruction } from "@/lib/next-instruction";
import { digits, cn } from "@/lib/utils";

export interface CancelReason {
  label: string;
  /** `undefined` = نصٌّ حرّ؛ والمصنَّف يُسقط الرسوم ويُدخل بلاغاً. */
  code?: "gender_mismatch";
}

/** أسبابُ إلغاء الكبتن كما في التصميم النسائي. */
const CANCEL_REASONS: CancelReason[] = [
  { label: "الراكب غير موجود" },
  { label: "الراكب ليس أنثى — عدم تطابق", code: "gender_mismatch" },
  { label: "سلوك غير لائق" },
];

const PHASES = {
  accepted: { title: "في الطريق إلى الراكب", action: "وصلتُ إلى الراكب" },
  arrived: { title: "بانتظار الراكب", action: "بدء الرحلة" },
  in_progress: { title: "الرحلة جارية", action: "إنهاء الرحلة" },
  at_stop: { title: "وقوفٌ عند محطة", action: "استئناف الرحلة" },
} as const;

type Phase = keyof typeof PHASES;

interface Props {
  ride: Ride;
  currencyLabel: string;
  busy: boolean;
  onAdvance: () => void;
  /** يمرّر السببَ المصنَّف مع نصّه — الخلفية تفرّق بينهما (المرحلة 10-ج). */
  onCancel: (reason: CancelReason) => void;
  /** تفضيلُ الكبتن الدائم — به وحده يظهر سببُ «عدم التطابق». */
  genderPreference: GenderPreference;
  onPause: () => void;
  onResume: () => void;
  onArriveStop: (stopId: string) => void;
  onResumeStop: (stopId: string) => void;
  /** «التعليمةُ التالية» — و`null` **تعني لا شريط**، وهي حالٌ صحيحةٌ لا عطب:
   *  المفتاحُ مطفأٌ، أو الكبتنُ انحرف عن الخط. **ولا نصَّ يُكتب عن غيابها**
   *  (قرارُ المالك 2026-08-20). */
  instruction: NextInstruction | null;
}

export function ActiveRide({
  ride,
  currencyLabel,
  busy,
  instruction,
  onAdvance,
  onCancel,
  genderPreference,
  onPause,
  onResume,
  onArriveStop,
  onResumeStop,
}: Props) {
  const phase = PHASES[ride.status as Phase] ?? PHASES.accepted;
  const riding = ride.status === "in_progress" || ride.status === "at_stop";
  // المحطةُ التي يقف عندها الآن، وأولُ محطةٍ لم يصلها بعد
  const waiting = ride.stops.find(
    (stop) => stop.arrived_at !== null && stop.resumed_at === null,
  );
  const nextStop = ride.stops.find((stop) => stop.arrived_at === null);
  // **زرُّ «وصلتُ المحطة» يسبق «إنهاء الرحلة»**: ما دامت محطةٌ لم تُبلغ،
  // فالإنهاءُ ليس الفعلَ التالي — والزرُّ الأول هو ما يقع تسعاً من عشر
  const stopAction =
    ride.status === "in_progress" && nextStop !== undefined
      ? { label: `وصلتُ المحطة ${digits(String(nextStop.sequence))}`, stop: nextStop }
      : null;
  const [picking, setPicking] = useState(false);
  const [reason, setReason] = useState<CancelReason | null>(null);
  const reasons = CANCEL_REASONS.filter(
    (option) => option.code !== "gender_mismatch" || genderPreference !== "any",
  );

  const mapTarget = targetFor(ride);

  return (
    <>
      {/* شريطُ الطور أعلى الخريطة */}
      <div className="pointer-events-none absolute inset-x-0 top-14 z-10 flex justify-center">
        <span className="rounded-full border border-line bg-surface px-18 py-8 text-12.5 font-bold text-ink">
          {phase.title}
        </span>
      </div>

      {/* **«التعليمةُ التالية»** (البند ٧) — **تحت شريط الطور لا فوقه**: الطورُ
          يقول أين هو من الرحلة، وهذا يقول أين يتّجه. ومن يقرأ في ثانيةٍ وهو
          يقود يقرأ الأعلى أولاً.

          **وغيابُها لا يُعلَن**: لا «يُعاد الحساب…» ولا مكانٌ فارغٌ محجوز —
          الشريطُ **ليس هنا** حين لا تعليمة (قرارُ المالك 2026-08-20). ومكانٌ
          محجوزٌ فارغٌ يقول «شيءٌ انكسر»، وهو ما بُني هذا القرارُ لمنعه.

          **ولا يلتقط اللمس** (`pointer-events-none`): يعلو الخريطةَ، ولمسةٌ
          تذهب إليه بدل الخريطة تمنع الكبتنَ من تحريكها */}
      {instruction ? (
        <div className="pointer-events-none absolute inset-x-0 top-52 z-10 flex justify-center px-18">
          <span className="flex max-w-full items-center gap-8 rounded-13 border border-line bg-surface px-14 py-9 shadow-card">
            <span className="text-13 font-bold text-ink">
              {digits(instruction.meters)} م
            </span>
            <span className="truncate text-12.5 text-muted">
              {instruction.text}
            </span>
          </span>
        </div>
      ) : null}

      <div className="absolute inset-x-0 bottom-0 z-10 rounded-t-22 border-t border-line bg-surface px-18 pb-22 pt-16">
        <div className="mb-13 flex items-center gap-12">
          <div className="flex size-44 items-center justify-center rounded-full border border-line bg-surface-2 text-14 font-bold text-ink">
            ر
          </div>
          <div className="flex-1">
            <div className="text-14 font-bold text-ink">راكب TAXO</div>
            <div className="text-11 text-muted">
              {digits(ride.estimated_fare)} {currencyLabel}
            </div>
            {/* حالُ المشاركة (12-ي) — **حالتان لا واحدة**: «مجموعةٌ تكوّنت»
                غيرُ «قد ينضم أحد». والفرقُ عمليٌّ لا لفظي: الأولى تعني راكباً
                ينتظر في نقطةٍ أخرى، والثانيةُ تعني ألّا يفاجأ إن ظهر. ولو
                كتبنا نصّاً واحداً لصار أحدُهما كذباً في نصف الحالات */}
            {Number(ride.share_discount_percent) > 0 ? (
              <div className="mt-3 text-10.5 font-bold text-muted">
                {ride.share_group_id
                  ? "رحلة مشتركة — راكبان"
                  : "مشتركة — قد ينضم راكب ثانٍ"}
              </div>
            ) : null}
          </div>
          {/* الاتصال مسارٌ في النظام لا في التطبيق: رقمُ الراكب لا يصل
              الكبتن (القسم 14)، فالزرّ يُخفى حتى يُبنى الاتصال المُقنَّع */}
        </div>

        <StopStrip ride={ride} currencyLabel={currencyLabel} />
        <PauseStrip ride={ride} currencyLabel={currencyLabel} />

        <div className="mb-15 grid grid-cols-[12px_1fr] gap-x-10 gap-y-4">
          <span
            className={cn(
              "mx-auto mt-5 block size-8 rounded-full",
              riding ? "bg-muted" : "bg-ok",
            )}
          />
          <div className={cn("text-12.5", riding ? "text-muted" : "text-ink")}>
            {ride.pickup_address ?? "نقطة الانطلاق"}
          </div>
          <span className="mx-auto block h-12 w-2 bg-line" />
          <span />
          <span
            className={cn(
              "mx-auto mt-2 block size-8 rounded-2",
              riding ? "bg-ok" : "bg-muted",
            )}
          />
          <div className={cn("text-12.5", riding ? "text-ink" : "text-muted")}>
            {ride.dropoff_address ?? "الوجهة"}
          </div>
        </div>

        {/* **«افتح في الخرائط» فوق زرِّ الحالة لا مكانَه** (البند ١٦): الوجهةُ
            **واحدةٌ صحيحةٌ بحسب حال الرحلة** — نقطةُ الالتقاء، ثم المحطةُ
            التالية، ثم الوجهة — لا قائمةٌ يقرؤها الكبتنُ ويقرّر عند إشارةٍ
            خضراء. ويختفي حيث لا وجهة (`arrived`: هو واقفٌ عندها).
            **وتطبيقُ قوقل يعرف الزحامَ والطرقَ المغلقةَ أفضلَ مما سنعرف، ويعرفها
            الآن** — ومن لا يعرف طريقَه سيفتحه على أيّ حال، فإمّا أن يكتب
            العنوانَ بيده وهو يقود أو نسلّمه بضغطة */}
        {mapTarget ? (
          <button
            type="button"
            onClick={() => openIn(mapTarget)}
            className="pressable mb-11 flex w-full items-center justify-center gap-8 rounded-15 border border-line p-13 text-13.5 font-bold text-ink"
          >
            <Navigation size={16} />
            {mapTarget.cta}
          </button>
        ) : null}

        {/* **«نقطة توقف» بعد بدء الرحلة وحدَها** (§5.10-ب): وقفةٌ قبل أن يركب
            الراكبُ هي انتظارُ الوصول، وله عدّادُه الذي يبدأ بـ«وصلت». وزرٌّ
            يظهر حيث لا يعمل يُعلّم الضغطَ ثم الارتداد */}
        {ride.status === "in_progress" || ride.status === "at_stop" ? (
          <button
            type="button"
            onClick={() => (ride.open_pause ? onResume() : onPause())}
            disabled={busy}
            className={cn(
              "pressable mb-11 w-full rounded-15 border p-13 text-center text-13.5 font-bold disabled:opacity-50",
              ride.open_pause
                ? "border-ok text-ok"
                : "border-line text-ink",
            )}
          >
            {ride.open_pause ? "استئناف" : "نقطة توقف"}
          </button>
        ) : null}

        {stopAction ? (
          <button
            type="button"
            onClick={() => onArriveStop(stopAction.stop.id)}
            disabled={busy}
            className="pressable mb-11 w-full rounded-15 bg-brand p-15 text-center text-15 font-bold text-brand-ink disabled:opacity-50"
          >
            {stopAction.label}
          </button>
        ) : null}

        <button
          type="button"
          onClick={() =>
            waiting ? onResumeStop(waiting.id) : onAdvance()
          }
          disabled={busy}
          className={cn(
            "pressable w-full rounded-15 p-15 text-center text-15 font-bold disabled:opacity-50",
            stopAction
              ? "border border-line text-ink"
              : "bg-brand text-brand-ink",
          )}
        >
          {phase.action}
        </button>
        {/* **لا إلغاء بعد بدء الرحلة** — لا من `in_progress` ولا من
            `at_stop`: الراكب في السيارة، و`ALLOWED_TRANSITIONS` تجعل الإنهاء
            المخرجَ الوحيد (SPEC القسم 5). كان الزرُّ يظهر في `in_progress`
            **منذ المرحلة 10** فيرتدّ بـ409 — عطبٌ قديمٌ كشفه فحصُ المحطات.
            وزرٌّ يعمل ثم يرتدّ يعلّم الكبتن أن يجرّب؛ وغيابُه يقول إن الباب
            مغلق */}
        {riding ? null : (
          <button
            type="button"
            onClick={() => setPicking(true)}
            disabled={busy}
            className="pressable mt-11 w-full text-center text-12 font-semibold text-muted"
          >
            إلغاء الرحلة
          </button>
        )}
      </div>

      {/* ورقةُ أسباب الإلغاء — و«الراكب ليس أنثى» لا تُعرض إلا إن كان الكبتن
          قد قصر عمله على جنس: الخلفية ترفضها في غير ذلك (`CancelReasonNot
          Applicable`)، وزرٌّ يعمل ثم يرتدّ يعلّم إعادةَ المحاولة */}
      {picking ? (
        <div className="absolute inset-0 z-30 flex flex-col justify-end bg-dim">
          <div className="rounded-t-24 border-t border-line bg-surface px-20 pb-24 pt-18">
            <div className="mx-auto mb-16 h-4 w-38 rounded-full bg-line" />
            <div className="text-17 font-bold text-ink">سبب الإلغاء</div>
            <div className="mt-14 flex flex-col gap-9">
              {reasons.map((option) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => setReason(option)}
                  className={cn(
                    "pressable flex items-center gap-11 rounded-13 border p-13 text-start",
                    reason?.label === option.label
                      ? "border-brand-brd bg-brand-soft"
                      : "border-line",
                  )}
                >
                  <span
                    className={cn(
                      "block size-17 flex-none rounded-full border-2",
                      reason?.label === option.label
                        ? "border-5 border-brand"
                        : "border-line",
                    )}
                  />
                  <span
                    className={cn(
                      "text-13.5",
                      reason?.label === option.label
                        ? "font-bold text-brand"
                        : "text-ink",
                    )}
                  >
                    {option.label}
                  </span>
                </button>
              ))}
            </div>

            {reason?.code === "gender_mismatch" ? (
              <p className="mt-14 rounded-13 border border-line bg-surface-2 p-14 text-12.5 leading-relaxed text-muted">
                لن تُحتسب عليكِ رسوم إلغاء. ويُسجَّل بلاغٌ على حساب الراكب،
                وتكرارُ البلاغات يوسم الحساب للمراجعة.
              </p>
            ) : null}

            <button
              type="button"
              disabled={busy || reason === null}
              onClick={() => {
                setPicking(false);
                onCancel(reason!);
              }}
              className="pressable mt-16 w-full rounded-15 bg-danger p-15 text-center text-15 font-bold text-white disabled:opacity-50"
            >
              تأكيد الإلغاء
            </button>
            <button
              type="button"
              onClick={() => setPicking(false)}
              className="pressable w-full pt-10 text-center text-13 text-muted"
            >
              تراجع
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}


/** شريطُ تقدّم المحطات — `DESIGN.md` §2.8-ب/§5.3.
 *
 * حبّةٌ لكل محطة: المنتهيةُ `--ok`، والحاليةُ محدَّدةٌ بـ`--tx`، والقادمةُ
 * `--mut`. ومعها **رسمُ الانتظار محسوباً من الخلفية** أثناء الوقوف: الكبتن
 * يرى ما يتراكم لصالحه، فوقوفٌ طويل يصير قراراً لا خسارة صامتة.
 *
 * **ولا شريطَ لرحلةٍ بلا محطات**: صفٌّ فارغ فوق كل رحلةٍ عادية ضجيجٌ دائم
 * لأجل حالةٍ نادرة.
 */
/** دقائقُ الانتظار **تُحسب في الجهاز وتتقدّم من نفسها**.
 *
 * القاعدةُ من 12-ب: عرضُ الوقت حسابُ وقت، وعرضُ المال حسابُ مال — والقسم 14
 * يمنع الثاني وحدَه. فالدقائقُ هنا، و`waiting_charge` يبقى كما تحسبه الخلفية
 * بالأسعار المجمَّدة على الرحلة.
 *
 * **والعطبُ الذي وُجد لأجله** (تجربةُ المرحلة ١٣ على الهاتفين): كان الرقمُ
 * يُقرأ من `waited_minutes` الواصلِ مع الرحلة، فيقف على «انتظارٌ ٠ دقيقة» ولا
 * يتحرك حتى يصل إطارٌ جديد — وقد يتأخر دقائق. فكبتنٌ واقفٌ ينتظر يرى عدّاداً
 * لا يتقدّم، **فيظن أن وصولَه لم يُسجَّل** فيضغط «وصلتُ» ثانيةً أو يتصل
 * بالدعم. عدّادٌ جامدٌ أسوأُ من لا عدّاد: الأولُ يكذب والثاني يسكت.
 *
 * **وكل عشر ثوانٍ لا كل ثانية**: المعروضُ دقائقُ صحيحة، فتحديثٌ في الثانية
 * يوقظ الشاشةَ ستين مرةً ليكتب الرقمَ نفسَه — وبطاريةُ الكبتن تعمل ساعات.
 */
function useElapsedMinutes(since: string | null): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (since === null) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 10_000);
    return () => window.clearInterval(timer);
  }, [since]);

  if (since === null) return 0;
  const started = new Date(since).getTime();
  if (Number.isNaN(started)) return 0;
  return Math.max(0, Math.floor((now - started) / 60_000));
}

/** شريطُ الوقفة غير المخطَّطة (SPEC §5.10-ب).
 *
 * **والعدّادُ يمشي محلياً والمبلغُ يأتي من الخلفية** (§14) — وهو الدرسُ الذي
 * دفعته دفعةُ الإصلاحات: كبتنٌ كان يقرأ «٠ دقيقة» طوال وقوفه **فيظن أن وصولَه
 * لم يُسجَّل**، بينما يرى الراكبُ عقارباً تمشي.
 *
 * **والنصُّ يفرّق بين النوعين**: «بانتظار الراكب» عند الوصول، و«وقفة» في منتصف
 * الرحلة — والحالان مختلفان عند من يقرأ وإن تشابه الحساب.
 */
function PauseStrip({
  ride,
  currencyLabel,
}: {
  ride: Ride;
  currencyLabel: string;
}) {
  const pause = ride.open_pause;
  const minutes = useElapsedMinutes(pause?.started_at ?? null);
  if (!pause) return null;

  const free = pause.free_minutes;
  const billing = minutes >= free;

  return (
    <div
      className={cn(
        "mb-13 rounded-13 border px-13 py-11",
        pause.over_max ? "border-warn bg-warn-soft" : "border-line bg-surface-2",
      )}
    >
      <div className="flex flex-wrap items-center gap-6">
        <span className="text-12.5 font-bold text-ink">
          {pause.kind === "arrival" ? "بانتظار الراكب" : "وقفة"}
        </span>
        <span className="text-12.5 text-muted">
          {digits(String(minutes))} دقيقة
        </span>
        {/* **والمبلغُ من الخلفية لا محسوباً هنا** — والمهلةُ تُقال قبل أن تنتهي
            لا بعدها: كبتنٌ يرى «٠٫٠٠٠» ولا يعرف لماذا يظنّ العدّادَ معطوباً */}
        <span className="ms-auto text-12.5 font-bold text-ink">
          {billing
            ? `${digits(ride.pause_charge)} ${currencyLabel}`
            : `مهلة ${digits(String(free))} دقائق`}
        </span>
      </div>
      {pause.over_max ? (
        <p className="mt-6 text-11 text-warn">
          تجاوز الانتظارُ حدَّه — لك أن تستأنف أو تُنهي، والقرارُ قرارك.
        </p>
      ) : null}
    </div>
  );
}


function StopStrip({
  ride,
  currencyLabel,
}: {
  ride: Ride;
  currencyLabel: string;
}) {
  const waiting = ride.stops.find(
    (stop) => stop.arrived_at !== null && stop.resumed_at === null,
  );
  // **قبل الخروج المبكر**: خطّافٌ بعد `return` يكسر ترتيبَ الخطّافات
  const waitedMinutes = useElapsedMinutes(waiting?.arrived_at ?? null);

  if (ride.stops.length === 0) return null;

  return (
    <div className="mb-13 rounded-13 border border-line bg-surface-2 px-13 py-11">
      <div className="flex flex-wrap items-center gap-6">
        {ride.stops.map((stop) => {
          const done = stop.resumed_at !== null;
          const here = stop.arrived_at !== null && stop.resumed_at === null;
          return (
            <span
              key={stop.id}
              className={cn(
                "rounded-full px-10 py-4 text-11 font-semibold",
                done
                  ? "bg-ok text-inv"
                  : here
                    ? "border border-ink text-ink"
                    : "text-muted",
              )}
            >
              محطة {digits(String(stop.sequence))}
            </span>
          );
        })}
        <span className="rounded-full px-10 py-4 text-11 font-semibold text-muted">
          الوجهة
        </span>
      </div>

      {waiting ? (
        <div className="mt-8 flex items-center justify-between text-11.5">
          {/* **دقائقُ صحيحة لا ثلاثُ منازل**: `2.168` رقمٌ لا يقرؤه أحد،
              والكبتنُ يريد «كم وقفتُ» لا كسرَ الدقيقة. **والعدّادُ محليٌّ
              يتقدّم** (`useElapsedMinutes`) لا رقماً واصلاً مع الرحلة */}
          <span className="text-muted">
            انتظارٌ {digits(String(waitedMinutes))} دقيقة
          </span>
          <span className="font-semibold text-ink">
            {digits(ride.waiting_charge)} {currencyLabel}
          </span>
        </div>
      ) : null}

      {waiting?.over_max_wait ? (
        <p className="mt-6 text-11 leading-note text-warn">
          تجاوز الانتظارُ السقف — يمكنك إنهاء الرحلة عند هذه المحطة بدل
          الاستئناف.
        </p>
      ) : null}
    </div>
  );
}
