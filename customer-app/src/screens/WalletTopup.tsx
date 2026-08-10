/** شحن المحفظة بقنواته الثلاث (SPEC القسم 7).
 *
 * ثلاث قنوات وثلاثة ردود مختلفة — ولذلك ثلاثة مسارات في الخلفية لا مسارٌ
 * واحد بحقولٍ فارغة:
 *
 * | القناة | المسار | ما يعود |
 * |---|---|---|
 * | بطاقة | `POST /wallet/me/topups/card` | رابط صفحة الدفع (فوريٌّ آلي) |
 * | كليك الآلي | `POST /wallet/me/topups/cliq` | رمزٌ يُمسح وحسابُ التاجر يشهد |
 * | كليك اليدوي | `POST /wallet/me/topups` | طلبٌ ينتظر موظفاً — لا رصيد قبله |
 *
 * والقناة الآلية قد لا يكون لها عقد؛ حينها ترتدّ 503 وتبقى اليدوية قائمة —
 * «مزوّدٌ متوقف لا يقطع قناة شحنٍ كاملة» (القسم 15/أ). فالشاشة تعرض اليدوية
 * دائماً وتجرّب الآلية أولاً.
 */

import { CreditCard, Smartphone, Landmark } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import {
  checkCliqTopup,
  createCardTopup,
  createCliqTopup,
  createTopupRequest,
} from "@/api/endpoints";
import type { CliqTopup } from "@/api/types";
import { QrCode } from "@/components/QrCode";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { Screen } from "@/components/ui/Screen";
import { useCountryConfig } from "@/lib/config";
import { useSession } from "@/lib/session";
import { cn, formatMoney } from "@/lib/utils";

const QUICK_AMOUNTS = ["5", "10", "20", "50"];

type Channel = "card" | "cliq" | "manual";

export function WalletTopupScreen() {
  const { user } = useSession();
  const country = useCountryConfig(user?.country_code);

  const [amount, setAmount] = useState("10");
  const [channel, setChannel] = useState<Channel>("cliq");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [cliq, setCliq] = useState<CliqTopup | null>(null);

  const cardEnabled = country?.features.card_enabled === true;
  const cliqEnabled = country?.features.cliq_enabled === true;
  const currency = country?.currency;

  async function submit() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      if (channel === "card") {
        const order = await createCardTopup(amount);
        if (order.redirect_url) {
          window.location.assign(order.redirect_url);
          return;
        }
        setDone("تمت العملية — سيظهر الرصيد خلال لحظات.");
        return;
      }

      if (channel === "cliq") {
        setCliq(await createCliqTopup(amount));
        return;
      }

      await createTopupRequest(amount, reference.trim());
      setDone("سجّلنا طلبك — يظهر الرصيد بعد أن تؤكده الإدارة.");
      setReference("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إتمام الشحن");
    } finally {
      setBusy(false);
    }
  }

  /** يسأل حساب التاجر: الدفتر لا يتحرك إلا بجوابه للخلفية (القسم 7). */
  async function recheck() {
    if (!cliq) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await checkCliqTopup(cliq.cart_id);
      setCliq(updated);
      if (updated.status === "paid") setDone("وصلت الحوالة — شُحن رصيدك.");
      if (updated.status === "created") {
        setError("لم تصل الحوالة بعد — أعد المحاولة بعد لحظات.");
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الاستعلام");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="شحن الرصيد" back="/wallet">
      <div className="space-y-5">
        {cliq ? (
          <section className="card space-y-4 p-4">
            <h2 className="font-semibold text-ink">حوّل عبر كليك</h2>
            <p className="text-sm text-muted">
              امسح الرمز من تطبيق بنكك بمبلغ {formatMoney(cliq.amount, cliq.currency)}.
            </p>
            {cliq.qr_payload ? (
              <div className="flex justify-center">
                <QrCode payload={cliq.qr_payload} />
              </div>
            ) : null}
            {cliq.deep_link ? (
              <Button variant="secondary" className="w-full" asChild>
                <a href={cliq.deep_link}>افتح تطبيق البنك</a>
              </Button>
            ) : null}

            <ErrorNote message={error} />
            <SuccessNote message={done} />

            {cliq.status === "paid" ? null : (
              <Button className="w-full" loading={busy} onClick={recheck}>
                حوّلتُ — تحقّق الآن
              </Button>
            )}
            <Button variant="ghost" className="w-full" onClick={() => setCliq(null)}>
              رجوع
            </Button>
          </section>
        ) : (
          <>
            <div>
              <Field
                label="المبلغ"
                inputMode="decimal"
                dir="ltr"
                className="text-start"
                value={amount}
                onChange={(event) =>
                  setAmount(event.target.value.replace(/[^\d.]/g, ""))
                }
                suffix={currency}
              />
              <div className="mt-2 flex gap-2">
                {QUICK_AMOUNTS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setAmount(value)}
                    className={cn(
                      "flex-1 rounded-lg border px-2 py-2 text-sm transition",
                      amount === value
                        ? "border-brand bg-brand/10 text-ink"
                        : "border-line text-muted hover:bg-line/30",
                    )}
                  >
                    {value}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <p className="label">طريقة الشحن</p>

              {cliqEnabled ? (
                <ChannelOption
                  active={channel === "cliq"}
                  onSelect={() => setChannel("cliq")}
                  icon={Smartphone}
                  title="كليك — رمز فوري"
                  hint="امسح الرمز من تطبيق بنكك ويُشحن رصيدك آلياً"
                />
              ) : null}

              {cardEnabled ? (
                <ChannelOption
                  active={channel === "card"}
                  onSelect={() => setChannel("card")}
                  icon={CreditCard}
                  title="بطاقة"
                  hint="شحنٌ فوري عبر صفحة دفع آمنة"
                />
              ) : null}

              <ChannelOption
                active={channel === "manual"}
                onSelect={() => setChannel("manual")}
                icon={Landmark}
                title="حوالة يدوية"
                hint="حوّل ثم أدخل المرجع — تؤكده الإدارة"
              />
            </div>

            {channel === "manual" ? (
              <Field
                label="مرجع الحوالة"
                dir="ltr"
                className="text-start"
                value={reference}
                onChange={(event) => setReference(event.target.value)}
                hint="رقم الحوالة كما يظهر في تطبيق بنكك"
              />
            ) : null}

            <ErrorNote message={error} />
            <SuccessNote message={done} />

            <Button
              size="lg"
              loading={busy}
              disabled={
                Number(amount) <= 0 ||
                (channel === "manual" && reference.trim().length < 3)
              }
              onClick={submit}
            >
              متابعة
            </Button>
          </>
        )}
      </div>
    </Screen>
  );
}

function ChannelOption({
  active,
  onSelect,
  icon: Icon,
  title,
  hint,
}: {
  active: boolean;
  onSelect: () => void;
  icon: typeof CreditCard;
  title: string;
  hint: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-start transition",
        active ? "border-brand bg-brand/10" : "border-line bg-surface hover:bg-line/30",
      )}
    >
      <Icon className="size-5 text-ink" />
      <span>
        <span className="block font-medium text-ink">{title}</span>
        <span className="block text-xs text-muted">{hint}</span>
      </span>
    </button>
  );
}
