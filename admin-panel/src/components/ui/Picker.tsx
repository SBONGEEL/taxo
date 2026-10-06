/** **مُنتقٍ واحدٌ لكلِّ حقلٍ يشير إلى شيءٍ قائمٍ في النظام** (قرارُ المالك
 *  2026-09-01).
 *
 * **المبدأ بنصِّه**: «كلُّ ما يُكتب بيدٍ يُخطئ ويَبلى. فحيث تعرف الخلفيةُ
 * الجوابَ، لا تجعل المشرفَ يكتبه.»
 *
 * **والقاعدةُ الحاسمة**: **لا يُطلب من مشرفٍ أن يلصق UUID في أيِّ حقلٍ بعد
 * اليوم.** ومعرّفٌ يُلصق بيدٍ يُخطئ بحرفٍ فيصير الفعلُ على صفٍّ آخرَ **بلا أن
 * يصيح شيء** — الخلفيةُ تجد صفّاً صحيحاً، وهو صفُّ إنسانٍ غيرِ المقصود.
 *
 * ## وما يعرضه: الاسمُ والرقم لا المعرّف
 *
 * **«محمد» وحدَه لا يكفي** في قائمةٍ فيها ثلاثةُ محمّدين — **والرقمُ هو ما
 * يفرّق**. فكلُّ نتيجةٍ سطران: اسمٌ وتحته ما يميّزه (رقمُ هاتفٍ أو لوحةُ
 * مركبةٍ أو رمزُ خطّة).
 *
 * ## والبحثُ من الخادم بمهلةٍ لا عند كلِّ حرف
 *
 * **نداءٌ لكلِّ ضغطةِ مفتاحٍ يُغرق الخلفيةَ ويصل مبعثَراً**: الجوابُ الأبطأُ
 * لحرفين قد يصل بعد جواب ثلاثة، **فتُعرض نتائجُ بحثٍ سابق**. فمهلةُ ٢٥٠ملّي،
 * **وكلُّ جوابٍ يحمل نصَّه** فيُطرح ما لا يطابق آخرَ ما كُتب.
 *
 * ## ولا يعرض ما لا يملك المشرفُ صلاحيتَه
 *
 * **الترشيحُ في الخلفية لا هنا**: هذا المكوّنُ ينادي بابَ بحثٍ إدارياً،
 * **والبابُ يحرسه `require_permission`** — فمن لا يملك «قراءةَ الكباتن» يرى
 * قائمةً فارغةً لأن الخادمَ ردّ ٤٠٣، لا لأن الواجهةَ أخفت. **وإخفاءُ الواجهة
 * راحةٌ لا حماية** (SPEC §21).
 */

import { useEffect, useId, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { cn } from "@/lib/utils";
import { Icon } from "@/taxo2";

/** ما يعرضه سطرُ نتيجةٍ واحدة — **معرّفٌ للآلة، واسمٌ ووصفٌ للإنسان**. */
export interface PickerOption {
  id: string;
  /** السطرُ الأول — الاسمُ كما يعرفه المشرف. */
  label: string;
  /** السطرُ الثاني — ما يفرّق متشابهَي الاسم: رقمٌ أو لوحةٌ أو رمز. */
  hint?: string | null;
  /** **أيقونةُ الصنف** (Material Symbols) — زينةٌ في مربّعها بجانب السطرين، **والمعنى في السطرين لا فيها**. */
  icon?: string;
}

const DEBOUNCE_MS = 250;

export function Picker({
  label,
  value,
  onPick,
  search,
  placeholder = "اكتب للبحث…",
  error,
  disabled = false,
  /** **نصٌّ يُعرض حين لا نتيجة** — ولا يُخلط بـ«لا بيانات بعد». */
  emptyText = "لا نتائج لبحثك",
  /** اسمُ الحقل لقارئ الشاشة **حين لا تسميةَ مرئية** (البحثُ العامّ في الترويسة). */
  ariaLabel,
}: {
  label?: string;
  /** المختارُ الآن — **الكائنُ لا المعرّفُ وحدَه**: الشاشةُ تعرض اسمَه بلا
   *  نداءٍ ثانٍ يقرأ اسمَ معرّفٍ تحمله. */
  value: PickerOption | null;
  onPick: (option: PickerOption | null) => void;
  /** بابُ البحث — يُمرَّر من الشاشة، فالمكوّنُ لا يعرف أيَّ كيانٍ يبحث. */
  search: (query: string) => Promise<PickerOption[]>;
  placeholder?: string;
  error?: string | null;
  disabled?: boolean;
  emptyText?: string;
  ariaLabel?: string;
}) {
  const inputId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<PickerOption[] | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const box = useRef<HTMLDivElement | null>(null);
  // **آخرُ نصٍّ طُلب** — يُطرح به جوابٌ متأخّرٌ عن بحثٍ سابق
  const latest = useRef("");

  useEffect(() => {
    if (!open) return;
    const text = query.trim();
    latest.current = text;
    if (text.length < 2) {
      setRows(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void search(text)
        .then((found) => {
          if (latest.current !== text) return;
          setRows(found);
          setFailed(null);
        })
        .catch((caught) => {
          if (latest.current !== text) return;
          setRows([]);
          // **والسببُ من السجلِّ المركزيّ** — و«تعذّر البحث» وحدَها تُنتج
          // مشرفاً يظنّ أن لا نتائج وهو ممنوع
          setFailed(
            caught instanceof ApiError ? caught.message : "تعذّر البحث",
          );
        });
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query, open, search]);

  // **إغلاقٌ بالنقر خارجه** — قائمةٌ تبقى مفتوحةً فوق زرٍّ تجعل الضغطةَ تقع
  // على غير ما يُرى
  useEffect(() => {
    if (!open) return;
    function onDown(event: MouseEvent) {
      if (box.current && !box.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div ref={box} className="ad-pick">
      {label ? (
        <label className="label" htmlFor={inputId}>
          {label}
        </label>
      ) : null}

      {value ? (
        // **المختارُ يُعرض بطاقةً لا نصّاً في حقل**: حقلٌ فيه اسمٌ يُقرأ قابلاً
        // للتحرير، **وتحريرُه لا يغيّر المعرّفَ تحته** — فيصير المعروضُ غيرَ
        // المُرسَل، وهو أخطرُ من حقلٍ فارغ
        <div className={cn("ad-pick-chosen", error && "invalid")}>
          {value.icon ? (
            <span className="ad-tile">
              <Icon name={value.icon} />
            </span>
          ) : null}
          <span className="ad-pick-text">
            <span className="ad-pick-label">{value.label}</span>
            {value.hint ? (
              <span dir="auto" className="ad-pick-hint">
                {value.hint}
              </span>
            ) : null}
          </span>
          {disabled ? null : (
            <button
              type="button"
              className="ad-pick-change"
              onClick={() => {
                onPick(null);
                setQuery("");
                setRows(null);
              }}
            >
              غيّر
            </button>
          )}
        </div>
      ) : (
        <input
          id={inputId}
          type="search"
          value={query}
          disabled={disabled}
          placeholder={placeholder}
          aria-label={label ? undefined : ariaLabel}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          className={cn("fld", error && "invalid")}
          aria-invalid={error ? true : undefined}
        />
      )}

      {error ? (
        <p className="ad-err">
          <Icon name="error" fill />
          <span>{error}</span>
        </p>
      ) : null}

      {open && !value ? (
        <div className="ad-pick-menu scr">
          {query.trim().length < 2 ? (
            <p className="ad-pick-note">اكتب حرفين على الأقل</p>
          ) : rows === null ? (
            <p className="ad-pick-note">…يُبحث</p>
          ) : rows.length === 0 ? (
            <p className="ad-pick-note">{failed ?? emptyText}</p>
          ) : (
            rows.map((row) => (
              <button
                key={row.id}
                type="button"
                className="ad-pick-row"
                onClick={() => {
                  onPick(row);
                  setOpen(false);
                  setQuery("");
                  setRows(null);
                }}
              >
                {row.icon ? (
                  <span className="ad-tile">
                    <Icon name={row.icon} />
                  </span>
                ) : null}
                <span className="ad-pick-text">
                  <span className="ad-pick-label">{row.label}</span>
                  {/* **`auto` لا `ltr`**: رقمٌ وحدَه يبقى من اليسار، وسطرٌ يبدأ بالعربية يُقرأ من اليمين — **والقيمةُ فيه
                      معزولةٌ باتّجاهها** حيث تصوغه الشاشة (`GlobalSearch`) */}
                  {row.hint ? (
                    <span dir="auto" className="ad-pick-hint">
                      {row.hint}
                    </span>
                  ) : null}
                </span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
