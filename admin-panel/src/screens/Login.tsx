/** دخول اللوحة — `DESIGN.md` §5.4، وSPEC القسم 13/8.
 *
 * **برقم الهاتف لا بالبريد.** النموذج يكتب «استخدم بريد العمل الخاص بك»، ولا
 * عمودَ بريدٍ في `users` أصلاً: الهوية في هذا النظام رقمُ هاتفٍ بصيغة E.164
 * لكل الأدوار، والدخولُ كلمةُ مرورٍ دائماً (`DESIGN-DECISIONS.md` بند 3).
 *
 * **ولا تحقّقَ ثنائي بعد.** النموذج يرسم شاشةً له ويعد بـ«جلسة تنتهي بعد ٣٠
 * دقيقة خمول»، ولا واحدةَ منهما مبنيّة — فلا تُكتب الجملتان: وعدُ أمانٍ لا
 * يقع أسوأ من غيابه، لأنه يجعل من يقرؤه أقلَّ حذراً لا أكثر
 * (`FUTURE-FEATURES.md` بند 26).
 *
 * وما يبقى من نصّ النموذج صادقٌ ويبقى: الدخول مقيّدٌ بالمصرّح لهم، وكلُّ
 * إجراءٍ يدخل سجل التدقيق — وهذان مبنيّان فعلاً (`services/audit.py`).
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { login } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote } from "@/components/ui/Feedback";
import { useConfig } from "@/lib/config";
import { useSession } from "@/lib/session";

/** الرقم الوطني كما يُكتب أمام بادئةٍ ثابتة — بلا صفرٍ بادئ. */
function toNational(input: string, dialCode: string): string {
  let digits = input.replace(/[^0-9]/g, "");
  if (digits.startsWith("00")) digits = digits.slice(2);
  if (digits.startsWith(dialCode)) digits = digits.slice(dialCode.length);
  return digits.replace(/^0+/, "");
}

export function LoginScreen() {
  const navigate = useNavigate();
  const { signIn } = useSession();
  const { config } = useConfig();

  const country = config?.countries.find(
    (entry) => entry.country_code === config.default_country_code,
  );
  // `dial_code` يصل بلا «+» (`core/phone.py`)، والعلامةُ تُرسم ولا تُخزَّن
  const dialCode = country?.dial_code ?? "";

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const response = await login(
        `+${dialCode}${toNational(phone, dialCode)}`,
        password,
        config?.default_country_code,
      );
      signIn(response);
      navigate("/drivers", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الدخول");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-24">
      <div className="w-modal max-w-full">
        <div className="mb-24 text-center">
          <div className="text-30 font-bold tracking-wordmark text-ink">
            TAXO
          </div>
          <h1 className="mt-10 text-21 font-bold text-ink">
            لوحة تحكم العمليات
          </h1>
          <p className="mt-6 text-12.5 leading-note text-muted">
            إدارة الأسطول والرحلات والمحافظ والعقود في الأردن وليبيا من مكان
            واحد.
          </p>
        </div>

        <form
          className="rounded-18 border border-line bg-surface p-24"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <label className="label" htmlFor="phone">
            رقم الهاتف
          </label>
          <div className="mb-16 flex items-stretch gap-8">
            <span
              dir="ltr"
              className="flex items-center rounded-13 border border-line bg-surface-2 px-14 text-14.5 text-muted"
            >
              +{dialCode || "…"}
            </span>
            <input
              id="phone"
              dir="ltr"
              inputMode="tel"
              autoComplete="username"
              className="fld"
              placeholder="7XXXXXXXX"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          </div>

          <Field
            label="كلمة المرور"
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          <div className="mt-16">
            <ErrorNote message={error} />
          </div>

          <Button
            className="mt-16"
            type="submit"
            loading={busy}
            disabled={!phone || !password}
          >
            متابعة
          </Button>
        </form>

        <p className="mt-16 text-center text-11.5 leading-note text-muted">
          الدخول مقيّد بالمستخدمين المصرّح لهم · كل إجراء يُسجَّل في سجل التدقيق
        </p>
      </div>
    </div>
  );
}
