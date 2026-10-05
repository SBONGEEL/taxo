/** ورقةُ الترحيب — **عند أول فتحٍ بعد الاعتماد**، مرةً واحدةً لكل جهاز — **بلغة TAXO 2.0** (§٦٢/١ و/٦: كانت بطراز الهوية القديمة
 * فرآها المالكُ «الترحيبَ القديم»؛ ولا لوحةَ لها فرُسمت من أوراق الكبتن، `welcome-sheet.css`).
 *
 * **ونصوصُها ليست هنا** بل في `lib/welcome.ts` — بيتٌ واحدٌ يُعدَّل مرةً، وهي
 * قاعدةُ §17.2 مطبَّقةً على غير الأخطاء.
 *
 * **ولا تُغلق بالنقر على الظلّ** — بخلاف كلِّ ورقةٍ أخرى في هذا التطبيق. وهي
 * مخالفةٌ مقصودة: ورقةُ السحب تُغلق بالنقر لأن من فتحها **يعرف ما فيها** وقد
 * يكون فتحها خطأً؛ وهذه تُعرض **مرةً واحدةً في عمر الحساب على هذا الجهاز**،
 * فنقرةٌ عارضةٌ خارجها تحذفها إلى الأبد. وهي علّةُ إشعار الوضع النسائيّ نفسُها:
 * ما يُعرض مرةً يُغلق بيدٍ قاصدة.
 *
 * **ولا تحجب قراراً**: تظهر على الرئيسية وليس فوق عرضِ رحلةٍ ولا رحلةٍ جارية —
 * الاعتمادُ يقع قبل أيِّ طلب، فلا تزاحمُ أصلاً. والقاعدةُ مكتوبةٌ كي لا يُنقل
 * موضعُها لاحقاً بلا انتباه.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getMySubscription } from "@/api/endpoints";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";
import {
  pickWelcomeOffer,
  WELCOME_CTA,
  WELCOME_LEAD,
  WELCOME_POINTS,
  WELCOME_SEEN_KEY,
  WELCOME_TITLE,
  type WelcomeOffer,
} from "@/lib/welcome";

import "./welcome-sheet.css";

export function WelcomeSheet() {
  const [open, setOpen] = useState(false);
  const [offer, setOffer] = useState<WelcomeOffer | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    // **القراءةُ في تأثيرٍ لا في التهيئة**: `localStorage` قد يكون ممنوعاً
    // (خصوصيةٌ مشدَّدة)، ورميُه أثناء الرسم يُفرِّغ الشاشة — والفشلُ هنا يعني
    // «لا تُعرض» لا «انكسر التطبيق»
    try {
      if (!localStorage.getItem(WELCOME_SEEN_KEY)) setOpen(true);
    } catch {
      /* لا تخزينَ متاح — لا ورقةَ، ولا عطب */
    }
  }, []);

  // **العرضُ يُقرأ لا يُكتب**: الخلفيةُ تحسبه لهذا الكبتن، فمن لا ينطبق عليه
  // شيءٌ يرى ورقةً بلا سطرِ عرض — ولا يعلم أن ثمّة عرضاً لغيره (الفرع و).
  // **والفشلُ صامت**: ورقةُ ترحيبٍ لا تُكسر لأن نداءً تعثّر
  useEffect(() => {
    if (!open) return;
    let alive = true;
    getMySubscription()
      .then((data) => {
        if (alive) setOffer(pickWelcomeOffer(data.plans));
      })
      .catch(() => {
        /* لا عرضَ يُعرض — وهو الافتراضُ الآمن */
      });
    return () => {
      alive = false;
    };
  }, [open]);

  function dismiss() {
    setOpen(false);
    // **يُكتب عند الإغلاق لا عند العرض**: من فتح التطبيقَ فقُتل قبل أن يقرأ
    // يستحق أن يراها مرةً أخرى — ووسمُها عند العرض يحرمه إياها بلا أن يقرأها
    try {
      localStorage.setItem(WELCOME_SEEN_KEY, "1");
    } catch {
      /* تعذّر الحفظ — تُعرض مرةً أخرى، وهو أهونُ من ألّا تُعرض أبداً */
    }
    // **الزرُّ يقود إلى الشاشة التي بلا اشتراكها لا تصل طلبات** — لا يودّع
    navigate("/subscription");
  }

  if (!open) return null;

  return (
    <div className="t2 t2-wsheet" role="dialog" aria-modal="true" aria-label={WELCOME_TITLE}>
      <div className="t2-wsheet-card">
        <div className="t2-wsheet-grab" aria-hidden="true" />
        <h2>{WELCOME_TITLE}</h2>
        <p className="t2-wsheet-lead">{WELCOME_LEAD}</p>

        {/* **أوّلُ ما تقرؤه العين، وأبرزُ سطر** — ويختفي وحدَه حين لا عرضَ ينطبق على هذا الكبتن */}
        {offer ? (
          <div className="t2-wsheet-offer">
            <strong>
              {offer.free
                ? `${offer.planName} مجاناً`
                : `${offer.planName} بـ${digits(offer.priceAfter)} ${CURRENCY_LABEL[offer.currency]}`}
            </strong>
            <p>
              {offer.name}
              {offer.free ? null : (
                <>
                  {" — "}
                  <s>
                    {digits(offer.price)} {CURRENCY_LABEL[offer.currency]}
                  </s>
                </>
              )}
            </p>
          </div>
        ) : null}

        <ul className="t2-wsheet-points">
          {WELCOME_POINTS.map((point) => (
            <li key={point.title}>
              <Icon name="check_circle" fill />
              <span>
                <strong>{point.title}</strong>
                <p>{point.body}</p>
              </span>
            </li>
          ))}
        </ul>

        <button type="button" className="t2-button action" onClick={dismiss}>
          {WELCOME_CTA}
        </button>
      </div>
    </div>
  );
}
