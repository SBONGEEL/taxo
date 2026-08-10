/** تحويل P2P بين محافظ الركاب (SPEC القسم 7) — خلف `wallet_transfer_enabled`.
 *
 * الترتيب الذي يصفه SPEC حرفياً: **رقم المستلم ← عرض الاسم للتأكيد ← تنفيذ**.
 * خطوة الاسم ليست زينة: تحويلٌ إلى رقمٍ أخطأ فيه صاحبُه لا يُسترد — الدفتر لا
 * يُعدَّل، وردُّه يحتاج موافقة من وصله.
 *
 * والحدود اليومية والشهرية تحكمها الخلفية (`wallet_settings`)، وصفرٌ فيها
 * يعني «لم يُضبط بعد» فترتدّ العملية برسالةٍ تقول ذلك — لا تخترع الواجهة حداً.
 */

import { ArrowLeftRight, UserCheck } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { lookupRecipient, transfer } from "@/api/endpoints";
import type { CountryCode, TransferRecipient } from "@/api/types";
import { PhoneInput } from "@/components/PhoneInput";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { Screen } from "@/components/ui/Screen";
import { useConfig, useCountryConfig } from "@/lib/config";
import { usePhoneCountry } from "@/lib/config";
import { looksComplete } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { formatMoney, newIdempotencyKey } from "@/lib/utils";

export function WalletTransferScreen() {
  const navigate = useNavigate();
  const { user } = useSession();
  const { config } = useConfig();
  const country = useCountryConfig(user?.country_code);

  const countries = config?.countries.map((entry) => entry.country_code) ?? [
    "JO",
  ];
  const [code, setCode] = useState<CountryCode>(user?.country_code ?? "JO");
  const { nationalLength } = usePhoneCountry(code);
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [recipient, setRecipient] = useState<TransferRecipient | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // مفتاحٌ واحد لهذه العملية: إعادة المحاولة بعد انقطاعٍ لا تحوّل مرتين
  const key = useRef<string | null>(null);

  async function findRecipient() {
    setBusy(true);
    setError(null);
    try {
      setRecipient(await lookupRecipient(phone));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر العثور على الحساب",
      );
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    if (!recipient) return;
    setBusy(true);
    setError(null);
    try {
      key.current ??= newIdempotencyKey("transfer");
      const entry = await transfer(recipient.phone, amount, key.current);
      setDone(
        `تم تحويل ${formatMoney(entry.amount.replace("-", ""), entry.currency)} إلى ${recipient.name}`,
      );
      key.current = null;
      setRecipient(null);
      setPhone("");
      setAmount("");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تنفيذ التحويل",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="تحويل رصيد" back="/wallet">
      <div className="space-y-5">
        {recipient ? (
          <div className="card flex items-center gap-3 p-4">
            <UserCheck className="size-6 text-success" />
            <div className="min-w-0">
              <p className="truncate font-semibold text-ink">
                {recipient.name}
              </p>
              <p dir="ltr" className="text-sm text-muted">
                {recipient.phone}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setRecipient(null)}
              className="ms-auto text-sm text-muted hover:text-ink"
            >
              تغيير
            </button>
          </div>
        ) : (
          <PhoneInput
            phone={phone}
            country={code}
            countries={countries}
            onPhoneChange={setPhone}
            onCountryChange={setCode}
            disabled={busy}
          />
        )}

        {recipient ? (
          <Field
            label="المبلغ"
            inputMode="decimal"
            dir="ltr"
            className="text-start"
            value={amount}
            onChange={(event) =>
              setAmount(event.target.value.replace(/[^\d.]/g, ""))
            }
            suffix={country?.currency}
            hint="الحدّان اليومي والشهري يضبطهما فريق TAXO"
          />
        ) : null}

        <ErrorNote message={error} />
        <SuccessNote message={done} />

        {recipient ? (
          <Button
            size="lg"
            loading={busy}
            disabled={Number(amount) <= 0}
            onClick={send}
          >
            <ArrowLeftRight className="size-4" />
            تأكيد التحويل
          </Button>
        ) : (
          <Button
            size="lg"
            loading={busy}
            disabled={!looksComplete(phone, nationalLength)}
            onClick={findRecipient}
          >
            متابعة
          </Button>
        )}

        {done ? (
          <Button
            variant="ghost"
            className="w-full"
            onClick={() => navigate("/wallet")}
          >
            العودة للمحفظة
          </Button>
        ) : null}
      </div>
    </Screen>
  );
}
