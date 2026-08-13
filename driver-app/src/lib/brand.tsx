/** السِمة الوردية — `design/DESIGN.md` §1.1-ب (المرحلة 10-ج، وسلوكُها 2026-08-13).
 *
 * **رمزان لا لوحة**: `--brand` و`--brand-ink` وحدهما يتبدّلان، والتبديلُ صنفٌ
 * واحد (`.pink`) على الجذر. وهذا التطبيق مكتوبٌ بهما منذ اليوم الأول — الزرُّ
 * والحقلُ النشط والشارة — فتتحول واجهتُه كلُّها بلا لمس مكوّن واحد.
 *
 * **تُفعَّل تلقائياً بإقرارها الذاتي** (قرارُ المالك 2026-08-13): من أعلنت أنها
 * أنثى ترى السِمةَ من أول فتحةٍ بلا أن تبحث عن مفتاح، ولها إطفاؤها. والسببُ أن
 * الشاشة تُرى: هاتفٌ ورديُّ الواجهة **يُعلن جنسَ صاحبته لمن ينظر إليه**، وقد لا
 * تريد ذلك في مكانٍ بعينه أو يومٍ بعينه — فالافتراضُ لطفٌ والإطفاءُ حق.
 *
 * **والإقرارُ وحده يكفيها** (قرارُ المالك، البند 6): السِمةُ **عرضٌ بصريّ** لا
 * تَعِد بخدمةٍ ولا تفتح باباً، فلا تُعلَّق على `gender_verified_at` ولا على
 * `women_service_enabled`. أما **دخولُ المطابقة واستقبالُ الطلبات النسائية**
 * فيبقى على الختم كما هو مبنيّ — ولا يُخلط بينهما. (وهذا ينقض السطرَ الأخير من
 * القرار 47 في `DESIGN-DECISIONS.md`، وسببُ النقض مكتوبٌ هناك.)
 *
 * **والاختيار محليٌّ على الجهاز لا على الحساب**: من أطفأتها لأن حولها من ينظر
 * لا تريد أن تُطفأ على هاتفها الآخر في بيتها. فالافتراضُ يُطبَّق على جهازٍ لم
 * يُضبط فيه شيء، **ولا يُعيد تفعيلَ نفسه على جهازٍ أطفأته فيه**.
 *
 * **ويُلغى الوضعُ النسائيُّ عن الحساب** حين يخالف ما تثبّته الإدارةُ من الوثائق
 * ما أُقرّ: حينها `gender` لا يعود `female`، فتختفي السِمةُ ومفتاحُها معاً —
 * ويصلها إشعارٌ صريح من الخلفية، لأن اختفاءَ لونٍ وميزةٍ بلا تفسيرٍ تذكرةُ دعم.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import { WomenModeNotice } from "@/components/WomenModeNotice";
import { useSession } from "@/lib/session";

const KEY = "taxo.driver.pink";
// أثرُ «قيل لها مرةً» — مفتاحٌ منفصلٌ عن الاختيار: جهازٌ لم يُضبط فيه اختيارٌ
// وقد رأت الإشعارَ فيه حالةٌ قائمة، ودمجُهما يعيد الإشعارَ كلَّ فتحة
const NOTICE_KEY = "taxo.driver.pink.notice";
/** آخرُ قيمةٍ محسوبةٍ للسِمة — تقرؤها الشاشةُ الترحيبية وحدها (§7.6). */
const ACTIVE_KEY = "taxo.driver.pink.active";

interface BrandState {
  /** هل السِمة مرسومةٌ الآن؟ */
  pink: boolean;
  /** هل لصاحبة الشاشة أن تختارها أصلاً؟ (**إقرارُها وحده** — البند 6) */
  available: boolean;
  setPink: (next: boolean) => void;
  /** هل يُعرض إشعارُ «فُعِّل الوضع النسائي» الآن؟ مرةً واحدةً في عمر الجهاز. */
  showNotice: boolean;
  dismissNotice: () => void;
}

const BrandContext = createContext<BrandState>({
  pink: false,
  available: false,
  setPink: () => undefined,
  showNotice: false,
  dismissNotice: () => undefined,
});

function storedChoice(): boolean | null {
  const raw = localStorage.getItem(KEY);
  return raw === null ? null : raw === "on";
}

export function BrandProvider({ children }: { children: ReactNode }) {
  // **الإقرارُ وحده** لا مفتاحُ الخدمة معه: السِمةُ عرضٌ بصريٌّ لا يَعِد
  // بخدمةٍ ولا يفتح باباً (البند 6 من قرار المالك 2026-08-13). أما استقبالُ
  // الطلبات النسائية فيبقى على `gender_verified_at` في الخلفية كما هو مبنيّ
  const { user } = useSession();
  const available = user?.gender === "female";

  const [choice, setChoice] = useState<boolean | null>(storedChoice);

  // الاختيارُ الصريح يسبق الافتراض، والافتراضُ هو الإتاحة نفسها — فمن لم
  // تُتَح لها لا تُرسم لها ولو بقي في جهازها اختيارٌ من قبل
  const pink = available && (choice ?? true);

  // **إشعارُ مرةٍ واحدة**: يظهر لمن فُعِّلت لها بالافتراض ولم تُخبَر بعد. ويُطفأ
  // بإغلاقها أو بأول تغييرٍ للإعداد — فمن عرفت الطريقَ إلى المفتاح لا تُخبَر به
  const [noticeSeen, setNoticeSeen] = useState(
    () => localStorage.getItem(NOTICE_KEY) === "1",
  );
  const showNotice = pink && choice === null && !noticeSeen;
  const dismissNotice = useCallback(() => {
    localStorage.setItem(NOTICE_KEY, "1");
    setNoticeSeen(true);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("pink", pink);
    // **أثرٌ للرسم قبل الإقلاع لا مصدرٌ ثانٍ** (`DESIGN.md` §7.6): الشاشةُ
    // الترحيبية تُرسم قبل الحزمة، ولا سبيلَ لها إلى معرفة `available` — فهي
    // تنتظر الجلسة. فلو خمّنت من الاختيار وحده لصبغت شعارَ من لا تُتاح له.
    // ويُكتب من `pink` المحسوب نفسِه في نفس اللحظة، فلا يستطيع أن يخالفه:
    // ما يُقرأ في الفتحة القادمة هو ما وقع في هذه
    localStorage.setItem(ACTIVE_KEY, pink ? "1" : "0");
  }, [pink]);

  const setPink = useCallback((next: boolean) => {
    localStorage.setItem(KEY, next ? "on" : "off");
    // من ضبطت الإعدادَ بنفسها تعرف مكانَه — فلا يُعرض عليها إشعارُ التعريف به
    localStorage.setItem(NOTICE_KEY, "1");
    setNoticeSeen(true);
    setChoice(next);
  }, []);

  const value = useMemo<BrandState>(
    () => ({ pink, available, setPink, showNotice, dismissNotice }),
    [pink, available, setPink, showNotice, dismissNotice],
  );

  return (
    <BrandContext.Provider value={value}>
      {children}
      {/* داخل المزوّد لا في شاشةٍ بعينها: الإشعارُ يخصّ الجهازَ لا مساراً،
          وأول فتحةٍ قد تكون على أي شاشة */}
      <WomenModeNotice />
    </BrandContext.Provider>
  );
}

export function useBrand() {
  return useContext(BrandContext);
}
