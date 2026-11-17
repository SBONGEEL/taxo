/** الوضع: **ليليٌّ افتراضاً** في تطبيق الكبتن (SPEC القسم 12.2).
 *
 * ولا يتبع النظام كما يفعل تطبيق الراكب: الكبتن يعمل ساعاتٍ متصلة والشاشة
 * أمامه في السيارة، فوضعٌ يتبدّل مع غروب الشمس يبيّض شاشته في نفق. التبديل
 * قرارٌ يتخذه هو من الإعدادات، ويُحفظ.
 *
 * والصنف على `<html>`: `.dark` معرّفٌ مع الجذر العاري في `index.css` فيعمل
 * التطبيق ليلياً حتى قبل أن يُقلع React.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

/** **و«تلقائي»** (SPEC §١٠٣ B/16، خلف `auto_night_keep_awake`): ليليٌّ من السادسة مساءً إلى السادسة صباحاً بساعة الهاتف —
 *  **بالساعة لا بضوء المكان ولا بوضع النظام**، فلا يبيضّ في نفقٍ ولا يسودّ تحت جسر (العلّةُ التي في رأس هذا الملفّ). */
type ThemeChoice = "dark" | "light" | "auto";

export function nightAt(hour: number): boolean {
  return hour >= 18 || hour < 6;
}

const KEY = "taxo.driver.theme";

interface ThemeState {
  choice: ThemeChoice;
  dark: boolean;
  setChoice: (choice: ThemeChoice) => void;
  toggle: () => void;
}

function storedChoice(): ThemeChoice {
  const raw = localStorage.getItem(KEY);
  return raw === "light" || raw === "auto" ? raw : "dark";
}

const ThemeContext = createContext<ThemeState>({
  choice: "dark",
  dark: true,
  setChoice: () => undefined,
  toggle: () => undefined,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setStoredChoice] = useState<ThemeChoice>(storedChoice);
  const [night, setNight] = useState(() => nightAt(new Date().getHours()));

  // **«تلقائي» يُراجَع كلَّ دقيقة** — والتطبيقُ مفتوحٌ ساعاتٍ متّصلة
  useEffect(() => {
    if (choice !== "auto") return;
    const check = () => setNight(nightAt(new Date().getHours()));
    check();
    const timer = window.setInterval(check, 60_000);
    return () => window.clearInterval(timer);
  }, [choice]);

  const dark = choice === "auto" ? night : choice === "dark";

  // **قبل أيِّ أثرٍ في الأبناء** (SPEC §١٠٥/٢، عطبٌ مقيس): الخريطةُ تبني نمطَها من رموز `html.dark` في أثرها هي — **وآثارُ الأبناء
  // تجري قبل آثار الآباء**، فكان الصنفُ يُبدَّل بعد أن بُنيت الخريطةُ بألوان المظهر السابق: نهاريّةٌ في الليل. و`useLayoutEffect`
  // يجري قبل كلِّ `useEffect` في الشجرة، ويجري قبل أوّل رسمٍ فلا تُرسم لوحةٌ بالمظهر الخطأ
  useLayoutEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", dark);
    root.classList.toggle("light", !dark);
    document
      .querySelector('meta[name="theme-color"]')
      // **أرضُ TAXO 2.0** (`taxo2/tokens.css`: `--t2-bg`) — كان `#14181d`/`#f2f0eb` من الهوية القديمة فيبقى خطٌّ غريبٌ أعلى الهاتف
      ?.setAttribute("content", dark ? "#0e1013" : "#f4f1ea");
  }, [dark]);

  const setChoice = useCallback((next: ThemeChoice) => {
    localStorage.setItem(KEY, next);
    setStoredChoice(next);
  }, []);

  const value = useMemo<ThemeState>(
    () => ({
      choice,
      dark,
      setChoice,
      toggle: () => setChoice(dark ? "light" : "dark"),
    }),
    [choice, dark, setChoice],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
