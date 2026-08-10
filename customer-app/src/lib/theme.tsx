/** الوضع الليلي: يتبع النظام ما لم يختر المستخدم صراحةً.
 *
 * SPEC القسم 2 يفرض الوضع الليلي على تطبيق **الكبتن**؛ وهنا يتبع تفضيل
 * النظام لأن الخريطة تُستعمل ليلاً في السيارة، وستايل Mapbox نفسه يتبدل معه
 * (`streets-v12` نهاراً و`dark-v11` ليلاً).
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

type ThemeChoice = "system" | "light" | "dark";

const KEY = "taxo.theme";

interface ThemeState {
  choice: ThemeChoice;
  dark: boolean;
  setChoice: (choice: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeState>({
  choice: "system",
  dark: false,
  setChoice: () => undefined,
});

function systemPrefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setStoredChoice] = useState<ThemeChoice>(
    () => (localStorage.getItem(KEY) as ThemeChoice | null) ?? "system",
  );
  const [systemDark, setSystemDark] = useState(systemPrefersDark);

  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);

  const dark = choice === "system" ? systemDark : choice === "dark";

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", dark ? "#0b0f14" : "#f7f8fa");
  }, [dark]);

  const setChoice = useCallback((next: ThemeChoice) => {
    localStorage.setItem(KEY, next);
    setStoredChoice(next);
  }, []);

  const value = useMemo<ThemeState>(
    () => ({ choice, dark, setChoice }),
    [choice, dark, setChoice],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
