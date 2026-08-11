/** الوضع: **ليليٌّ افتراضاً** في اللوحة كذلك، كما يبدأ نموذجُ التصميم.
 *
 * ولا يتبع النظام: من يقرأ جداولَ مالٍ ساعاتٍ متصلة لا تتبدّل شاشتُه تحت
 * عينيه مع غروب الشمس. التبديل قرارُه من زرّ الرأس، ويُحفظ.
 *
 * والصنف على `<html>`: `.dark` معرّفٌ مع الجذر العاري في `index.css` فيعمل
 * التطبيق ليلياً حتى قبل أن يُقلع React.
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

type ThemeChoice = "dark" | "light";

const KEY = "taxo.admin.theme";

interface ThemeState {
  choice: ThemeChoice;
  dark: boolean;
  setChoice: (choice: ThemeChoice) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeState>({
  choice: "dark",
  dark: true,
  setChoice: () => undefined,
  toggle: () => undefined,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setStoredChoice] = useState<ThemeChoice>(
    () => (localStorage.getItem(KEY) as ThemeChoice | null) ?? "dark",
  );

  const dark = choice === "dark";

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", dark);
    root.classList.toggle("light", !dark);
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", dark ? "#14181d" : "#f2f0eb");
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
