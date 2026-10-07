/** **المشاويرُ الثابتة** (SPEC §٦٣-ج/٦) — «مشاويرُك» و«مشاويرُ تنتظر كبتناً» في صفحةٍ واحدة، **في المظهرين** — لا لوحةَ لها:
 * أختُ «الحجوز المضمونة» (`GuaranteesT2`) **بعُدّتها وأصنافها نفسِها** (`guarantees.css`): الرأس · عنوانُ القسم · بطاقةُ الحجز ·
 * الشارة · الأزرار · البلاغ · الفراغ — **بالرموز وحدَها**.
 *
 * **«مشاويرُك» أوّلاً وتُقرأ ولو أُطفئت الخدمة**: ما اعتمده قائمٌ يكمل شهرَه، ورحلاتُه تصله قبل غيره. **والعروضُ بعدها خلف
 * المفتاح.** والعرضُ **بلا اسم الراكب ولا رقمه** كما تنشره الخلفية.
 *
 * **والأفعالُ أبوابُ الخلفية بحرفها، ورسائلُها كما ردّتها** (`useCommuteBoard`): اعتمادٌ سبقه غيرُه ٤٠٩ برسالته فيُغلق زرُّه —
 * **لا نصَّ يُخترع مكانَ نصِّها**. **ولا مالَ يُحسب هنا** (§14): سعرُ الرحلة المجمَّدُ وعددُها كما وصلا، ولا يُضربان.
 */

import type { ReactNode } from "react";

import type { CommuteOffer } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useCommuteBoard } from "@/lib/guarantees";
import { currencyLabel, digits, DISPLAY_LOCALE } from "@/lib/utils";
import { Icon } from "@/taxo2";

import { countRides } from "./count";

import "./t2.css";
import "./guarantees.css";

/** أيامُ الأسبوع **الأحدُ أوّلاً** وبتُّ كلٍّ في قناع الخلفية (ترتيبُ `weekday()`: الإثنين 1 … الأحد 64). */
const DAYS: ReadonlyArray<{ bit: number; name: string }> = [
  { bit: 64, name: "الأحد" },
  { bit: 1, name: "الاثنين" },
  { bit: 2, name: "الثلاثاء" },
  { bit: 4, name: "الأربعاء" },
  { bit: 8, name: "الخميس" },
  { bit: 16, name: "الجمعة" },
  { bit: 32, name: "السبت" },
];

/** «الأحد · الثلاثاء · الخميس» — **والمتتاليةُ مدىً** «الأحد إلى الخميس» (خمسةُ أسماءٍ تلتفّ سطرين في رأس البطاقة، قِيس)، و«كلَّ
 *  يوم» للسبعة. والقاعدةُ قاعدةُ تطبيق الراكب (`commuteDaysText`) — فيقرأ الطرفان الأيامَ بنصٍّ واحد. */
function daysText(mask: number): string {
  const picked = DAYS.filter((day) => (mask & day.bit) !== 0);
  if (picked.length === DAYS.length) return "كلَّ يوم";
  const first = DAYS.indexOf(picked[0]);
  const run = picked.length >= 3 && picked.every((day, index) => DAYS[first + index] === day);
  return run ? `${picked[0].name} إلى ${picked[picked.length - 1].name}` : picked.map((day) => day.name).join(" · ");
}

/** «8 أكتوبر» — **يومٌ محلّيٌّ لا لحظةٌ بتوقيتٍ عالميّ** (`new Date("2026-10-08")` منتصفُ ليلٍ بتوقيت غرينتش). */
function dayShort(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return digits(new Date(year, month - 1, day).toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }));
}

export function CommutesT2Screen() {
  const goBack = useGoBack("/");
  const { enabled, lists, error, busy, notes, approve, release } = useCommuteBoard();

  return (
    <div className="t2 t2-gu">
      <div className="t2-gu-scroll scr">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
          <h1 className="t2-title">مشاويرُ ثابتة</h1>
        </div>
        <p className="t2-gu-lede">
          مشوارٌ يوميٌّ دفعه راكبُه مقدّماً لشهر. اعتمده فتصلك رحلاتُه قبل غيرك حين تكون متصلاً ومتاحاً — <b>وأجرتُها
          تُقيَّد في محفظتك من اشتراكه</b>، فلا تستلم من الراكب شيئاً.
        </p>

        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" />
            {error}
          </p>
        ) : null}

        {lists === null ? (
          error ? null : (
            <div className="t2-gu-wait" aria-busy="true">
              <Spinner />
            </div>
          )
        ) : (
          <>
            {lists.mine.length > 0 ? (
              <section>
                <div className="t2-section">
                  مشاويرُك
                  <span className="t2-section-aside" dir="ltr">
                    {digits(String(lists.mine.length))}
                  </span>
                </div>
                {lists.mine.map((row) => (
                  <CommuteCard key={row.id} row={row} mine note={notes[row.id]}>
                    <button
                      type="button"
                      className="t2-button secondary t2-gu-go"
                      disabled={busy !== null}
                      aria-busy={busy === row.id}
                      onClick={() => release(row)}
                    >
                      {busy === row.id ? "نرسل…" : "اعتذر عن المشوار"}
                    </button>
                  </CommuteCard>
                ))}
              </section>
            ) : null}

            {/* **العروضُ خلف المفتاح** — ومطفأً لا قسمَ يقول «لا عروض» عن خدمةٍ لا تعمل */}
            {enabled ? (
              <section>
                <div className="t2-section">مشاويرُ تنتظر كبتناً</div>
                {lists.offers.length === 0 ? (
                  <p className="t2-empty">لا مشاويرَ تنتظر الآن. تظهر هنا اشتراكاتُ الركّاب في سوقك حين لا يعتمدها أحد.</p>
                ) : (
                  lists.offers.map((row) => {
                    const note = notes[row.id];
                    return (
                      <CommuteCard key={row.id} row={row} note={note}>
                        <button
                          type="button"
                          className="t2-button action t2-gu-go"
                          disabled={busy !== null || note?.final === true}
                          aria-busy={busy === row.id}
                          onClick={() => approve(row)}
                        >
                          {busy === row.id ? "نرسل…" : "اعتمد المشوار"}
                        </button>
                      </CommuteCard>
                    );
                  })
                )}
              </section>
            ) : lists.mine.length === 0 ? (
              <p className="t2-empty">لا مشاويرَ معتمدةً لك.</p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

/** **بطاقةُ المشوار** — الأيامُ والمدّة، والمسارُ بنقطتيه، والوقتان، **والمالُ سطران**: سعرُ الرحلة المجمَّدُ وعددُها، وأنها مدفوعةٌ
 *  مقدّماً. **ولا يُضرب السعرُ في العدد** (§14) — الدخلُ يُقرأ رحلةً رحلةً في المحفظة. وما اعتمده بجمرٍ خافت. */
function CommuteCard({
  row,
  mine = false,
  note,
  children,
}: {
  row: CommuteOffer;
  mine?: boolean;
  note?: { tone: "ok" | "danger"; text: string };
  children: ReactNode;
}) {
  const cur = currencyLabel(row.currency);
  return (
    <article className={mine ? "t2-gu-card asking" : "t2-gu-card"}>
      <div className="t2-gu-top">
        <span className="t2-gu-when">
          <Icon name="event_repeat" />
          {daysText(row.weekdays)}
        </span>
        <span className="t2-chip">
          {dayShort(row.starts_on)} — {dayShort(row.ends_on)}
        </span>
      </div>
      <div className="t2-gu-route">
        <span className="t2-gu-dot" aria-hidden="true" />
        <span className="t2-gu-place">{row.pickup_address ?? "نقطة على الخريطة"}</span>
        <span className="t2-gu-dot to" aria-hidden="true" />
        <span className="t2-gu-place strong">{row.dropoff_address ?? "نقطة على الخريطة"}</span>
      </div>
      <div className="t2-gu-money">
        <span>
          ذهاب{" "}
          <b dir="ltr" className="t2-gu-time">
            {row.go_time.slice(0, 5)}
          </b>
          {row.return_time ? (
            <>
              {" "}
              · عودة{" "}
              <b dir="ltr" className="t2-gu-time">
                {row.return_time.slice(0, 5)}
              </b>
            </>
          ) : null}
        </span>
        <span className="t2-gu-fee">
          <b dir="ltr">{digits(row.price_per_ride)}</b> {cur} للرحلة · {countRides(row.rides_total)}
        </span>
      </div>
      {children}
      {note ? (
        <p className={note.tone === "ok" ? "t2-note t2-gu-done" : "t2-note danger"} role={note.tone === "ok" ? "status" : "alert"}>
          <Icon name={note.tone === "ok" ? "check_circle" : "error"} />
          {note.text}
        </p>
      ) : null}
    </article>
  );
}
