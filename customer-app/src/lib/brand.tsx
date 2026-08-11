/** السِمة الوردية — `design/DESIGN.md` §1.1-ب (المرحلة 10-ج).
 *
 * **رمزان لا لوحة**: `--brand` و`--brand-ink` وحدهما يتبدّلان، والتبديلُ صنفٌ
 * واحد (`.pink`) على الجذر. وهذا التطبيق مكتوبٌ بهما منذ اليوم الأول — الزرُّ
 * والحقلُ النشط والشارة — فتتحول واجهتُه كلُّها بلا لمس مكوّن واحد.
 *
 * **مفتوحةٌ افتراضاً لمن جنسُها أنثى، ومطفأةٌ بمفتاح.** والسببُ أن الشاشة
 * تُرى: هاتفٌ ورديُّ الواجهة في يدٍ أو على طاولة **يُعلن جنسَ صاحبته لمن ينظر
 * إليه**، وقد لا تريد ذلك في مكانٍ بعينه أو يومٍ بعينه. فالافتراضُ لطفٌ
 * والإطفاءُ حق.
 *
 * **والاختيار محليٌّ على الجهاز لا على الحساب**، وذلك من نفس السبب: من أطفأتها
 * لأن حولها من ينظر لا تريد أن تُطفأ على هاتفها الآخر في بيتها، ومن سلّمت
 * هاتفها لغيرها تُطفئها هنا وحدها. تفضيلٌ على الحساب كان سيجعل قراراً عن
 * **هذه اللحظة وهذا المكان** قراراً عن كل شاشاتها.
 *
 * **ولا تظهر ولا مفتاحُها حيث `women_service_enabled` مطفأ**: هويةٌ لخدمةٍ لم
 * تُفتح تُعلن عن غير موجود — وهي نفسُ قاعدة إخفاء مفتاح التفضيل.
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

import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

const KEY = "taxo.pink";

interface BrandState {
  /** هل السِمة مرسومةٌ الآن؟ */
  pink: boolean;
  /** هل لصاحبة الشاشة أن تختارها أصلاً؟ (الخدمة مفعّلة وجنسُها أنثى) */
  available: boolean;
  setPink: (next: boolean) => void;
}

const BrandContext = createContext<BrandState>({
  pink: false,
  available: false,
  setPink: () => undefined,
});

function storedChoice(): boolean | null {
  const raw = localStorage.getItem(KEY);
  return raw === null ? null : raw === "on";
}

export function BrandProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const enabled = useFeature(user?.country_code, "women_service_enabled");
  const available = enabled && user?.gender === "female";

  const [choice, setChoice] = useState<boolean | null>(storedChoice);

  // الاختيارُ الصريح يسبق الافتراض، والافتراضُ هو الإتاحة نفسها — فمن لم
  // تُتَح لها لا تُرسم لها ولو بقي في جهازها اختيارٌ من سوقٍ آخر
  const pink = available && (choice ?? true);

  useEffect(() => {
    document.documentElement.classList.toggle("pink", pink);
  }, [pink]);

  const setPink = useCallback((next: boolean) => {
    localStorage.setItem(KEY, next ? "on" : "off");
    setChoice(next);
  }, []);

  const value = useMemo<BrandState>(
    () => ({ pink, available, setPink }),
    [pink, available, setPink],
  );

  return (
    <BrandContext.Provider value={value}>{children}</BrandContext.Provider>
  );
}

export function useBrand() {
  return useContext(BrandContext);
}
