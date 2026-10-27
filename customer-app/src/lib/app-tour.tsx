/** جولةُ التطبيق — **أوّلَ فتحةٍ بعد التثبيت، مرّةً واحدة** (اقتراحُ Testers Community وأمرُ المالك ٢٠٢٦-١٠-٢٧، `design/PLAY-TEST-LOG.md`).
 *
 * **أربعُ بطاقاتٍ تقول ما يفعله التطبيقُ لا كيف رُسم**، وزرُّ «تخطٍّ» في كلِّ بطاقة، **وتُفتح ثانيةً** من «حسابي/الإعدادات» و«المساعدة»
 * (`openAppTour`). **وتظهر للضيف كما تظهر للداخل** — وضعُ الضيف جلسةٌ بحسابٍ تجريبيّ، فشرطُها «جلسةٌ قائمة» لا «حسابٌ حقيقيّ».
 *
 * **«أوّلَ فتحةٍ» تُحسم عند تحميل الوحدة لا عند الرسم**: جهازٌ عليه أثرُ ترحيبٍ سابق (`taxo.welcome.seen` · `taxo.driver.welcome.seen`)
 * **ثبّت التطبيقَ قبل الجولة** فلا تُفرض عليه في منتصف عمله — كبتنٌ في نوبته لا تحجب بطاقةٌ عرضاً وصله. والجهازُ الجديدُ يُعلَّم
 * «تنتظر» فتبقى حتى يدخل أو يبدأ الضيافة، **ولو أُغلق التطبيقُ قبلها**.
 *
 * **ونسخةٌ واحدةٌ في التطبيقين، متطابقةٌ بايتاً** (ومعها `app-tour.css`) — والتطبيقُ يُمرَّر لا يُكتب فيها.
 * **وتحت بوّابتَي التحديث وإعادة القبول** (`z-index` ٥٥ < ٥٨ < ٦٠): من عليه موافقةٌ يوافق أوّلاً ثمّ يرى الجولة.
 */
import { useEffect, useState, useSyncExternalStore } from "react";

import { tr } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import { Icon } from "@/taxo2";
import "./app-tour.css";

type App = "rider" | "driver";

interface Card {
  icon: string;
  title: string;
  body: string;
}

const CARDS: Record<App, readonly Card[]> = {
  rider: [
    {
      icon: "location_on",
      title: tr("اطلب رحلتك بلمسة"),
      body: tr("اختر وجهتك، وثبّت نقطة الالتقاط على الخريطة، وأقربُ كبتن يصلك."),
    },
    {
      icon: "sell",
      title: tr("السعر قبل التأكيد"),
      body: tr("ترى الأجرة قبل أن تطلب، ولا مفاجآت في نهاية الرحلة."),
    },
    {
      icon: "share_location",
      title: tr("تابع كبتنك وشارك رحلتك"),
      body: tr("ترى السيارة على الخريطة لحظةً بلحظة، وتراسل الكبتن أو تتصل به بلا كشف رقمك، وترسل رابط رحلتك لمن تحب."),
    },
    {
      icon: "account_balance_wallet",
      title: tr("ادفع كما يناسبك"),
      body: tr("نقداً أو من محفظتك أو بالطرق المتاحة في بلدك، وإيصالٌ لكل رحلة."),
    },
  ],
  driver: [
    {
      icon: "power_settings_new",
      title: tr("ابدأ الاستقبال متى شئت"),
      body: tr("اضغط «استقبال» فتصلك الطلبات القريبة، و«إيقاف» حين تنهي نوبتك."),
    },
    {
      icon: "sell",
      title: tr("الأجرة قبل القبول"),
      body: tr("كل عرضٍ يحمل الأجرة والمسافة ونقطة الالتقاط، وتقرّر أنت."),
    },
    {
      icon: "navigation",
      title: tr("الطريق والراكب أمامك"),
      body: tr("إرشادٌ إلى الراكب ثمّ إلى وجهته، ومحادثةٌ ومكالمةٌ بلا كشف الأرقام."),
    },
    {
      icon: "payments",
      title: tr("أرباحك ومحفظتك"),
      body: tr("ترى ما كسبته رحلةً رحلة، وتسحب من محفظتك، وتختار خطة الاشتراك التي تناسبك."),
    },
  ],
};

const STORE_KEY = "taxo.tour.v1";
/** أثرُ ترحيبٍ سابقٍ على الجهاز — **التثبيتُ أقدمُ من الجولة** */
const EARLIER = ["taxo.welcome.seen", "taxo.driver.welcome.seen"];

function read(): string | null {
  try {
    return localStorage.getItem(STORE_KEY);
  } catch {
    return "done";
  }
}

function write(value: "pending" | "done"): void {
  try {
    localStorage.setItem(STORE_KEY, value);
  } catch {
    /* تخزينٌ محجوب: لا جولةَ تُفرض في كلِّ فتحة — تُطلب من الإعدادات */
  }
}

// **يُحسم مرّةً عند تحميل الوحدة** — قبل أن يعلّم الترحيبُ نفسَه «رُئي» في هذه الفتحة
(function settleFirstOpen() {
  if (read() !== null) return;
  let earlier = false;
  try {
    earlier = EARLIER.some((key) => localStorage.getItem(key) !== null);
  } catch {
    earlier = true;
  }
  write(earlier ? "done" : "pending");
})();

// ── «افتح الجولة» من أيِّ شاشة ───────────────────────────────────────────────
let requests = 0;
const listeners = new Set<() => void>();

export function openAppTour(): void {
  requests += 1;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function current(): number {
  return requests;
}

/** **`held`**: ما يمنعها الآن — جولةُ أذونات الكبتن، أو عرضٌ أو رحلةٌ جارية (`App.tsx`). تنتظر ولا تُلغى. */
export function AppTour({ app, held = false }: { app: App; held?: boolean }) {
  const { user } = useSession();
  const asked = useSyncExternalStore(subscribe, current);
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const cards = CARDS[app];

  // **أوّلَ فتحة**: جلسةٌ قائمةٌ (داخلٌ أو ضيف) والجولةُ تنتظر
  useEffect(() => {
    if (user && !held && read() === "pending") {
      setIndex(0);
      setOpen(true);
    }
  }, [user, held]);

  // **وبطلبٍ من الإعدادات أو المساعدة** — في أيِّ وقت
  useEffect(() => {
    if (asked === 0) return;
    setIndex(0);
    setOpen(true);
  }, [asked]);

  // **وما يمنعها يُخفيها ولا يُغلقها**: عرضٌ يصل الكبتنَ وهي مفتوحةٌ يُرى فوراً، وتعود بعده من حيث كانت
  if (!open || held) return null;
  const close = () => {
    write("done");
    setOpen(false);
  };
  const last = index === cards.length - 1;
  const card = cards[index];
  return (
    <div className="t2 t2-tour" role="dialog" aria-modal="true" aria-labelledby="t2-tour-title">
      <div className="t2-tour-card">
        <button type="button" className="t2-tour-skip" onClick={close}>
          {tr("تخطٍّ")}
        </button>
        <span className="t2-tour-mark" aria-hidden="true">
          <Icon name={card.icon} />
        </span>
        <h1 id="t2-tour-title" className="t2-tour-title">
          {card.title}
        </h1>
        <p className="t2-tour-text">{card.body}</p>
        <div className="t2-tour-dots" aria-label={tr("{0} من {1}", { 0: index + 1, 1: cards.length })}>
          {cards.map((_, dot) => (
            <span key={dot} className={dot === index ? "on" : undefined} />
          ))}
        </div>
        <div className="t2-tour-actions">
          {index > 0 ? (
            <button type="button" className="t2-tour-back" onClick={() => setIndex(index - 1)}>
              {tr("السابق")}
            </button>
          ) : null}
          <button type="button" className="t2-button action t2-tour-next" onClick={last ? close : () => setIndex(index + 1)}>
            {last ? tr("ابدأ") : tr("التالي")}
          </button>
        </div>
      </div>
    </div>
  );
}
