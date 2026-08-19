/** صفحتا التبديل: «غير مثبَّت» وصفحةُ استقبال الجلسة.
 *
 * **و«غير مثبَّت» صفحةٌ لا رسالةُ خطأ**: من ضغط «تبديل» يريد شيئاً، وقولُ
 * «تعذّر» يتركه بلا خطوةٍ تالية. فتُشرح الحالُ ويُعطى مدخلُ التثبيت.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { exchangeHandoff } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";

const DRIVER_STORE_URL = "https://driver.tajora.ly";

export function DriverNotInstalledScreen() {
  const goBack = useGoBack();
  return (
    <div className="h-full bg-bg px-16 pb-nav pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">تطبيق السائق</h1>
      </div>

      <section className="card p-16">
        <p className="text-13.5 font-semibold text-ink">
          تطبيق السائق غير مثبَّت على هذا الجهاز
        </p>
        <p className="mt-8 text-12 leading-note text-muted">
          حسابك واحد، وتدخل به التطبيقين بلا تسجيلٍ جديد. ثبّت تطبيق السائق ثم
          عد إلى هنا واضغط «تبديل» — تنتقل جلستك وحدها.
        </p>
        <Button
          className="mt-14"
          onClick={() => {
            window.location.href = DRIVER_STORE_URL;
          }}
        >
          احصل على تطبيق السائق
        </Button>
      </section>
    </div>
  );
}

/** يستقبل رمزَ التسليم ويبادله بجلسة — **ثم يمحو الرمزَ من العنوان**. */
export function HandoffLandingScreen() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // الرمزُ يصل في الجزء (`#`) لا في الاستعلام: الجزءُ لا يُرسل إلى خادمٍ
    // ولا يدخل سجلَّ وسيط
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = params.get("token");
    if (!token) {
      setError("رابط التبديل غير مكتمل");
      return;
    }
    exchangeHandoff(token)
      .then(() => {
        // **يُمحى من العنوان فوراً**: رمزٌ مستهلَكٌ يبقى في شريط العنوان يُعاد
        // إرساله بمشاركةِ رابطٍ أو لقطةِ شاشة
        window.history.replaceState({}, "", "/");
        window.location.replace("/");
      })
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر التبديل"),
      );
  }, [navigate]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-12 bg-bg px-16">
      {error ? (
        <>
          <ErrorNote message={error} />
          <Button variant="secondary" onClick={() => navigate("/login")}>
            سجّل الدخول
          </Button>
        </>
      ) : (
        <p className="text-13 text-muted">جارٍ نقل جلستك…</p>
      )}
    </div>
  );
}
