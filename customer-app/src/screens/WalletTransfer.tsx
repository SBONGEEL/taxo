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
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getWallet, lookupRecipient, transfer } from "@/api/endpoints";
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
import {
  currencyLabel,
  formatMoney,
  newIdempotencyKey,
  subtractMoney,
} from "@/lib/utils";

export function WalletTransferScreen() {
  const navigate = useNavigate();
  const { user } = useSession();
  const { config } = useConfig();
  const country = useCountryConfig(user?.country_code);

  // **ولا سوقٌ مكتوبٌ هنا** (SPEC §24): القائمةُ من `/config`، فالمخفيُّ لا
  // يُعرض ولو كان لصاحب الحساب — والتحويلُ إليه بابٌ يفتحه إشعالُ المفتاح
  const countries =
    config?.countries.map((entry) => entry.country_code) ?? [];
  const [code, setCode] = useState<CountryCode>(user?.country_code ?? "JO");
  const { nationalLength } = usePhoneCountry(code);
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [recipient, setRecipient] = useState<TransferRecipient | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // **ورقةُ تأكيدٍ قبل تحويلٍ لا رجعةَ فيه** (قرارُ المالك 2026-08-19): المالُ
  // يذهب إلى **شخصٍ آخر** ويُختار **برقمٍ يُكتب باليد** — ورقمٌ واحدٌ خاطئ
  // يرسل المال إلى غريبٍ بلا استرداد. فالورقةُ تقول ثلاثة: **اسمَ** المستقبِل
  // لا رقمَه وحدَه، والمبلغ، والرصيدَ بعده.
  const [confirming, setConfirming] = useState(false);
  const [balance, setBalance] = useState<string | null>(null);

  // الرصيدُ يُقرأ ليُعرض «رصيدك بعده» — ولا يُحسب في المتصفح إلا للعرض:
  // الخلفيةُ ترفض ما يتجاوز الرصيد على أي حال (§14)
  useEffect(() => {
    getWallet()
      .then((wallet) => setBalance(wallet.balance))
      .catch(() => setBalance(null));
  }, [done]);
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
    <Screen title="تحويل رصيد" back="/wallet" nav>
      <div className="space-y-20">
        {recipient ? (
          <div className="card flex items-center gap-12 p-16">
            <UserCheck className="size-24 text-ok" />
            <div className="min-w-0">
              <p className="truncate font-semibold text-ink">
                {recipient.name}
              </p>
              <p dir="ltr" className="text-14 text-muted">
                {recipient.phone}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setRecipient(null)}
              className="pressable ms-auto text-14 text-muted hover:text-ink"
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
            // **الرمزُ لا الكود**: كلُّ سطحٍ ماليٍّ آخر يقول «د.أ»، وهذا وحدَه
            // كان يقول «JOD» — نفسُ شكلِ حقلِ الشحن الذي أُصلح في 2026-08-13
            suffix={currencyLabel(country?.currency)}
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
            onClick={() => setConfirming(true)}
          >
            <ArrowLeftRight className="size-16" />
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

      {confirming ? (
        <div
          className="fixed inset-0 z-50 flex items-end bg-dim"
          onClick={() => setConfirming(false)}
        >
          {/* **سقفٌ وتمريرٌ وقدمٌ ثابتة** (عطبٌ مقيسٌ 2026-08-23): كانت الورقةُ
              مثبَّتةً من الأسفل (`items-end`) بلا `max-height` وبلا تمرير، فتنمو
              صعوداً ويقصّها الإطار. **وهذه الشاشةُ أخطرُ ما يقع فيه**: لوحةُ
              المفاتيح مفتوحةٌ بالضرورة — المستخدمُ لتوّه كتب المبلغ — والإطارُ
              يتقلّص معها (قِيس في هذا المشروع ٨٢٠ ⇐ ٤٦٢). فالمبلغُ و«رصيدك
              بعده» في **قدمٍ لا تُمرَّر**، والعنوانُ وحدَه يُمرَّر. */}
          <div
            className="flex max-h-[calc(var(--vvh,100dvh)-76px)] mb-[var(--vv-bottom,0px)] w-full flex-col rounded-t-24 border-t border-line bg-surface pt-20"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="scr min-h-0 flex-1 px-18">
              <h2 className="mb-4 text-16 font-bold text-ink">تأكيد التحويل</h2>
              <p className="mb-14 text-12 leading-snug text-muted">
                لا يمكن التراجع بعد الإرسال — راجعِ الاسمَ لا الرقم وحدَه.
              </p>
            </div>

            <div className="shrink-0 px-18 pb-24">
            <div className="rounded-14 border border-line bg-surface-2 px-14 py-12">
              {/* **الاسمُ أولاً وأكبر**: الرقمُ ما كُتب، والاسمُ ما يُتحقَّق به */}
              <div className="flex items-baseline justify-between">
                <span className="text-12.5 text-muted">إلى</span>
                <span className="text-15 font-bold text-ink">
                  {recipient?.name}
                </span>
              </div>
              <div className="mt-6 flex items-baseline justify-between">
                <span className="text-12.5 text-muted">رقمه</span>
                <span dir="ltr" className="text-12.5 text-muted">
                  {recipient?.phone}
                </span>
              </div>
              <div className="mt-10 flex items-baseline justify-between border-t border-line pt-10">
                <span className="text-12.5 text-muted">المبلغ</span>
                <span className="text-17 font-bold text-ink">
                  {formatMoney(amount, country?.currency ?? "JOD")}
                </span>
              </div>
              {balance ? (
                <div className="mt-6 flex items-baseline justify-between">
                  <span className="text-12.5 text-muted">رصيدك بعده</span>
                  <span className="text-13 text-ink">
                    {formatMoney(
                      subtractMoney(balance, amount),
                      country?.currency ?? "JOD",
                    )}
                  </span>
                </div>
              ) : null}
            </div>

            <div className="mt-16 flex flex-col gap-9">
              <Button
                size="lg"
                loading={busy}
                onClick={() => {
                  setConfirming(false);
                  void send();
                }}
              >
                أرسل الآن
              </Button>
              <Button
                size="lg"
                variant="ghost"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                رجوع
              </Button>
            </div>
            </div>
          </div>
        </div>
      ) : null}

    </Screen>
  );
}
