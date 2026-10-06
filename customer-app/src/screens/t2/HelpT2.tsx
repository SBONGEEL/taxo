/** «المساعدة والدعم» — TAXO 2.0 «R30» (`design/t2-new/rider/R30-help.dc.html` · `R30b` · `R30c`)، **في المظهرين والنسائيّ** (§٦٢-ج/١٦).
 *
 * **المحتوى من اللوحة لا من التطبيق**: بريدُ الدعم والأسئلةُ الشائعةُ في إعدادات الموقع (`site_settings`) يكتبها المشرف، **ويقرؤها
 * التطبيقُ من البابِ العامِّ نفسِه الذي تقرؤه الصفحةُ التعريفية** (`GET /public/site`) — فلا نسخةَ ثانيةً للمحتوى تفترق عن الأولى،
 * ولا سؤالَ مكتوبٌ في الشيفرة.
 *
 * **ولا شيءَ يُرسم بلا مصدر**: بلا بريدٍ لا بطاقةَ بريد، وبلا أسئلةٍ منشورةٍ لا عنوانَ فوق قائمةٍ فارغة (R30b)، **وسببُ التعثّر يُقال
 * بنصّ الطلب نفسِه** ومعه «أعد المحاولة» يعيد الطلبَ نفسَه (R30c). **والسؤالُ زرٌّ يفتح جوابَه** (`aria-expanded`) — واحدٌ في المرّة،
 * والأوّلُ مفتوحٌ كما رُسم. **والبريدُ رابطٌ حقيقيّ** (`mailto:`) يفتحه الغلافُ بـ`AppLauncher` كما تُفتح صفحتا السياسات (`lib/legal`).
 */

import { AppLauncher } from "@capacitor/app-launcher";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getSiteHelp } from "@/api/endpoints";
import type { FaqItem } from "@/api/types";
import { useGoBack } from "@/lib/back";

import "@/taxo2";
import "./t2.css";
import "./help.css";

interface Help {
  email: string;
  faq: FaqItem[];
}

/** **الترتيبُ من الحقل لا من موضع العنصر** (`site_settings.faq`)، **ولا يُرسم سؤالٌ بلا جواب ولا جوابٌ بلا سؤال** — صفٌّ فارغٌ
 *  في اللوحة يُحذف بتفريغه (`Site.tsx`)، فلا يصير هنا زرّاً لا يفتح شيئاً. */
function readable(faq: FaqItem[]): FaqItem[] {
  return faq
    .filter((item) => item.q.trim() && item.a.trim())
    .map((item, index) => ({ item, index }))
    .sort((a, b) => (a.item.order ?? a.index) - (b.item.order ?? b.index) || a.index - b.index)
    .map(({ item }) => item);
}

export function HelpT2Screen() {
  // **من حيث جئت، و«حسابي» لمن دخل مباشرةً** (`lib/back.ts`)
  const goBack = useGoBack("/account");
  const [help, setHelp] = useState<Help | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // **سؤالٌ واحدٌ مفتوحٌ في المرّة — والأوّلُ كما رُسم**
  const [open, setOpen] = useState<number | null>(0);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getSiteHelp()
      .then((site) => setHelp({ email: site.support_email.trim(), faq: readable(site.faq) }))
      .catch((caught: unknown) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر تحميل المساعدة"),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const mail = help?.email ? `mailto:${help.email}` : null;

  return (
    <div className="t2 t2-page t2-account t2-help pb-nav" aria-busy={loading}>
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label="رجوع" onClick={goBack}>
          <span className="t2-icon" aria-hidden="true">arrow_forward</span>
        </button>
        <h1 className="t2-title">المساعدة والدعم</h1>
      </div>

      {error ? (
        <>
          <p className="t2-note danger" role="alert">
            <span className="t2-icon" aria-hidden="true">error</span>
            {error}
          </p>
          <button type="button" className="t2-button secondary t2-help-retry" onClick={load} disabled={loading}>
            أعد المحاولة
          </button>
        </>
      ) : null}

      {mail ? (
        <a
          className="t2-help-mail"
          href={mail}
          onClick={(event) => {
            // **الغلافُ يفتح تطبيقَ البريد** — والرابطُ يبقى رابطاً لقارئ الشاشة وللمتصفّح
            event.preventDefault();
            void AppLauncher.openUrl({ url: mail });
          }}
        >
          <span className="t2-help-mail-icon" aria-hidden="true">
            <span className="t2-icon fill">mail</span>
          </span>
          <span className="t2-help-mail-main">
            <span className="t2-help-mail-title">راسل فريق الدعم</span>
            {/* **العنوانُ لاتينيٌّ يُقرأ من اليسار** — ويُملى حرفاً بحرف */}
            <span dir="ltr" className="t2-help-mail-address">
              {help!.email}
            </span>
          </span>
          <span className="t2-icon t2-chev" aria-hidden="true">chevron_left</span>
        </a>
      ) : null}

      {help && help.faq.length > 0 ? (
        <>
          <h2 className="t2-section">الأسئلة الشائعة</h2>
          <div className="t2-list t2-help-faq">
            {help.faq.map((item, index) => {
              const expanded = open === index;
              const answerId = `t2-help-a-${index}`;
              return (
                <div key={`${index}-${item.q}`} className={expanded ? "t2-help-item open" : "t2-help-item"}>
                  <button
                    type="button"
                    className="t2-help-q"
                    aria-expanded={expanded}
                    aria-controls={answerId}
                    onClick={() => setOpen(expanded ? null : index)}
                  >
                    <span className="t2-help-q-text">{item.q}</span>
                    <span className="t2-icon t2-help-chev" aria-hidden="true">expand_more</span>
                  </button>
                  {/* **الجوابُ في الشجرة دائماً ومخفيٌّ حين يُطوى** — فيجد `aria-controls` ما يشير إليه */}
                  <p id={answerId} className="t2-help-a" hidden={!expanded}>
                    {item.a}
                  </p>
                </div>
              );
            })}
          </div>
        </>
      ) : null}
    </div>
  );
}
