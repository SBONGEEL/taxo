/** **شريطُ الاتصال العائم** (أمرُ المالك ٢٠٢٦-١١-٠٦، البند ٥) — يظهر فوق كلِّ شاشةٍ حين لا يكون الاتصالُ سليماً، ويختفي وحدَه.
 *
 * **ويعيد المحاولةَ فعلاً** كما يَعِد نصُّه: كلَّ عشر ثوانٍ نداءٌ خفيفٌ لـ`/config` بلا مفتاح — فإن أجاب الخادمُ عاد الحالُ `ok`
 * (يضعه `api/client.ts` على كلِّ جواب) واختفى الشريط. **ولا يحاول وهو `offline`**: لا شبكةَ تُجرَّب، والعودةُ يقولها حدثُ `online`.
 */

import { useEffect } from "react";

import { api } from "@/api/client";
import { tr } from "@/lib/i18n";
import { useConnection } from "@/lib/connection";

const RETRY_MS = 10_000;

export function ConnectionBanner() {
  const state = useConnection();

  useEffect(() => {
    if (state === "ok" || state === "offline") return;
    const timer = window.setInterval(() => {
      api.get("/config", { anonymous: true }).catch(() => undefined);
    }, RETRY_MS);
    return () => window.clearInterval(timer);
  }, [state]);

  if (state === "ok") return null;

  const text =
    state === "offline"
      ? tr("لا يوجد اتصال بالإنترنت")
      : state === "down"
        ? tr("الخدمة متوقفة مؤقتاً، نعمل على إصلاحها")
        : tr("اتصالك بالإنترنت ضعيف أو غير مستقر — نعيد المحاولة تلقائياً");

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        insetInline: "12px",
        top: "calc(10px + env(safe-area-inset-top, 0px))",
        zIndex: 1000,
        display: "flex",
        flexDirection: "column",
        gap: "2px",
        padding: "10px 14px",
        borderRadius: "14px",
        background: state === "down" ? "#7a2e14" : "#1d2230",
        color: "#fff",
        fontSize: "13px",
        lineHeight: 1.5,
        boxShadow: "0 6px 20px rgba(0,0,0,0.35)",
        pointerEvents: "none",
      }}
    >
      <span style={{ fontWeight: 700 }}>{text}</span>
      {state === "weak" ? (
        <span style={{ opacity: 0.8, fontSize: "12px" }}>{tr("جرّب التبديل بين Wi-Fi وبيانات الهاتف")}</span>
      ) : null}
    </div>
  );
}
