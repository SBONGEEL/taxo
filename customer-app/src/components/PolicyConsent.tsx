/** موافقةُ التسجيل — **زرّان يفتحان الوثيقتين، ومربّعٌ يُضغط بيدٍ** (البند ١٠).
 *
 * **والمواصفةُ جدولت هذا اليومَ بنصِّها** (§45): «لا شاشةَ قبولٍ في تطبيقٍ…
 * **ويُبنى يومَ يعتمد المالكُ النصوص**، ومعه شاشتان في التطبيقين».
 *
 * ## ولمَ مربّعٌ يُضغط، لا جملةٌ تحت الزرّ
 *
 * **كان تحت زرِّ التسجيل سطرٌ يقول «بالمتابعة أنت توافق على شروط الاستخدام»**
 * — **بلا رابطٍ ولا نصٍّ ولا صفٍّ يُكتب**. فهي موافقةٌ **مُفترَضةٌ لا
 * معطاة**: لا يستطيع أحدٌ أن يقرأ ما وافق عليه، **ولا نعرف نحن أنه وافق**.
 * **والفرقُ ليس شكلياً**: يومَ يُسأل «أوافق هذا على النسخة الأولى؟» لا جواب.
 *
 * ## والنصُّ يُفتح في مكانه لا في صفحةٍ أخرى
 *
 * **نموذجٌ نصفُ مملوءٍ لا يُترك**: الانتقالُ إلى صفحةٍ ثمّ الرجوعُ يفقد ما
 * كُتب، **فمن قرأ الشروطَ يُعاقَب بإعادة الكتابة** — وهو يعلّم ألّا يقرأ.
 *
 * ## وحالةُ «لا وثيقةَ منشورة» تمرّ صامتة
 *
 * **سوقٌ لم تُنشر فيه وثيقةٌ لا يُسأل مستخدموه عن شيء** — فلا يُرسم شيءٌ،
 * **ولا يُمنع تسجيل**. وهي الحالُ التي كانت قائمةً حتى ٢٠٢٦-٠٩-٠٥،
 * **والبوّابةُ في الخلفية تُشتقّ من المنشور لا من ثابتٍ مكتوب** — فيومَ
 * يُنشر نصٌّ جديدٌ يعمل الطرفان وحدَهما.
 */

import { useEffect, useState } from "react";

import { requiredPolicies } from "@/api/endpoints";
import type { CountryCode, RequiredPolicy } from "@/api/types";

const TITLE: Record<string, string> = {
  privacy_policy: "سياسة الخصوصية",
  terms_of_use: "شروط الاستخدام",
};

export function PolicyConsent({
  country,
  checked,
  onChange,
  onLoaded,
}: {
  country: CountryCode;
  checked: boolean;
  onChange: (next: boolean) => void;
  /** يُبلّغ الشاشةَ بالمعرّفات — **وبقائمةٍ فارغةٍ حين لا وثيقةَ منشورة**. */
  onLoaded: (ids: string[]) => void;
}) {
  const [docs, setDocs] = useState<RequiredPolicy[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    requiredPolicies(country)
      .then((rows) => {
        if (!alive) return;
        setDocs(rows);
        onLoaded(rows.map((row) => row.id));
      })
      // **والصمتُ مقصود**: تعذُّرُ القراءة ليس رفضاً — والخلفيةُ هي التي
      // ترفض التسجيل إن لزمت موافقةٌ ولم تصل. **فلا يُمنع أحدٌ بخطأ شبكة.**
      .catch(() => {
        if (alive) setDocs([]);
      });
    return () => {
      alive = false;
    };
  }, [country, onLoaded]);

  if (docs === null || docs.length === 0) return null;

  return (
    <div className="rounded-14 border border-line bg-surface-2 p-12">
      <button
        type="button"
        role="checkbox"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className="flex w-full items-start gap-10 text-start"
      >
        <span
          aria-hidden
          className={
            "mt-2 flex size-20 flex-none items-center justify-center rounded-6 border text-12 font-bold " +
            (checked
              ? "border-accent bg-accent text-accent-ink"
              : "border-line text-transparent")
          }
        >
          ✓
        </span>
        <span className="text-12.5 leading-note text-ink">
          قرأتُ ووافقتُ على الوثيقتين أدناه.
        </span>
      </button>

      <div className="mt-10 flex flex-wrap gap-8">
        {docs.map((doc) => (
          <button
            key={doc.id}
            type="button"
            onClick={() => setOpen(open === doc.id ? null : doc.id)}
            aria-expanded={open === doc.id}
            className="min-h-44 rounded-10 border border-line px-12 text-12 font-semibold text-ink"
          >
            {TITLE[doc.doc_type] ?? doc.doc_type}
          </button>
        ))}
      </div>

      {docs.map((doc) =>
        open === doc.id ? (
          <div
            key={`${doc.id}-body`}
            className="mt-10 max-h-list overflow-y-auto rounded-10 border border-line bg-surface p-12 text-12 leading-note text-ink"
          >
            {/* **فقرةٌ فقرةً لا نصٌّ واحدٌ ملتصق** — النصُّ القانونيُّ يُقرأ
                بفواصله، **وسطرٌ واحدٌ طويلٌ لا يُقرأ فلا يُوافَق عليه بعلم** */}
            {doc.body_ar.split(/\n{2,}/).map((para, i) =>
              para.trim() ? <p key={i} className="mb-8">{para.trim()}</p> : null,
            )}
          </div>
        ) : null,
      )}
    </div>
  );
}
