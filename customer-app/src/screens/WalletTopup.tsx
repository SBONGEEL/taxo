/** شحن المحفظة بقنواته الثلاث (SPEC القسم 7) — **بلغة TAXO 2.0** (لوحتا `design/t2-new/rider/R16` · `R16b`).
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
 *
 * **وما تغيّر طبقةُ العرض وحدَها** — النداءاتُ والقواعدُ وشروطُ تعطيل الزرّ حرفاً: بطاقةُ المبلغ بخطِّ الأرقام (R10)، والقنواتُ
 * بطاقاتُ «اختر الفئة» (R06)، وصفحةُ الرمز بطاقةٌ بيضاء، **والشريطُ باقٍ** كما كان (القرار 53: صفحاتُ المحفظة الداخلية بشريطها).
 */

import { useState } from "react";
import { useLocation } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  checkCliqTopup,
  createCardTopup,
  createCliqTopup,
  createTopupRequest,
} from "@/api/endpoints";
import type { CliqTopup } from "@/api/types";
import { QrCode } from "@/components/QrCode";
import { useGoBack } from "@/lib/back";
import { useCountryConfig } from "@/lib/config";
import { notMultipleMessage, roundingUnit, unitHint } from "@/lib/rounding";
import { useSession } from "@/lib/session";
import { play } from "@/lib/sound";
import { QUICK_TOPUP_AMOUNTS } from "@/lib/wallet";
import { formatMoney } from "@/lib/utils";
import { AuthBlock, AuthInput, Icon } from "@/taxo2";
import { AmountCardT2, BannerT2, BusyLabel, HeadT2, QuickAmountsT2, UnitNoteT2 } from "@/screens/t2/MoneyT2";

// **بيتٌ واحدٌ للورقة والشاشة** — وثلاثةٌ لا أربعة (قرار 20 والتصميم)
const QUICK_AMOUNTS = QUICK_TOPUP_AMOUNTS;

type Channel = "card" | "cliq" | "manual";

export function WalletTopupScreen() {
  const { user } = useSession();
  const country = useCountryConfig(user?.country_code);
  // **من حيث جئت، والمحفظةُ لمن دخل مباشرةً** (`lib/back.ts`) — كما كان رأسُ الشاشة
  const goBack = useGoBack("/wallet");

  // **اختيارُ الورقة يصل في حالة المسار** (تصميمُ `topupShow`): الورقةُ تجمع
  // المبلغَ والقناةَ والشاشةُ تنفّذ — فلا منطقَ قناةٍ في مكانين. والدخولُ
  // المباشر إلى `/wallet/topup` (رابطٌ محفوظ) يبقى عاملاً بقيمه الافتراضية
  const handoff = (useLocation().state ?? null) as {
    amount?: string;
    channel?: Channel;
  } | null;
  const [amount, setAmount] = useState(handoff?.amount ?? "10");
  const [channel, setChannel] = useState<Channel>(handoff?.channel ?? "cliq");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [cliq, setCliq] = useState<CliqTopup | null>(null);

  const cardEnabled = country?.features.card_enabled === true;
  const cliqEnabled = country?.features.cliq_enabled === true;
  const currency = country?.currency;
  // **المبلغُ مضاعفٌ لوحدة التقريب حين تكون مشتعلة** (SPEC §٧٠-ج/٦) — في القنوات الثلاث: البطاقةُ وكليك الآليُّ يُفحصان قبل فتح
  // الطلب، واليدويُّ عند تسجيله. **والخلفيةُ هي التي تردّ**؛ وهذا يمنع الوصولَ إلى الردّ ويقول الخطوات قبله
  const unit = roundingUnit(country);
  const unitError = notMultipleMessage(amount, unit, currency);

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
      // **الصوتُ مع «شُحن» لا قبله** (§٦١-ي/١٠): البطاقةُ بلا صفحةٍ تقول «سيظهر
      // خلال لحظات» فلا تُعلَن، والطلبُ اليدويُّ ينتظر الإدارة — **ونغمةُ نجاحٍ
      // قبل أن يُقيَّد المالُ تَعِد بما لم يقع**
      if (updated.status === "paid") {
        setDone("وصلت الحوالة — شُحن رصيدك.");
        play("topup");
      }
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
    <div className="t2 t2-m-page">
      <HeadT2 title="شحن الرصيد" onBack={goBack} />

      {cliq ? (
        // **صفحةُ الرمز** (R16b) — بطاقةٌ بيضاء: الرمزُ أسودُ على أبيضَ في كلِّ سِمة، ثمّ تطبيقُ البنك، ثمّ «تحقّق الآن»
        <section className="t2-m-card">
          <h2 className="t2-m-cliq-title">حوّل عبر كليك</h2>
          <p className="t2-m-cliq-text">
            امسح الرمز من تطبيق بنكك بمبلغ {formatMoney(cliq.amount, cliq.currency)}.
          </p>
          {cliq.qr_payload ? <QrCode payload={cliq.qr_payload} /> : null}
          {cliq.deep_link ? (
            <a href={cliq.deep_link} className="t2-button secondary t2-m-open">
              <Icon name="open_in_new" />
              افتح تطبيق البنك
            </a>
          ) : null}

          <BannerT2 tone="danger" message={error} />
          <BannerT2 tone="ok" message={done} />

          {cliq.status === "paid" ? null : (
            <button
              type="button"
              className="t2-button primary t2-m-cta t2-m-gap"
              disabled={busy}
              aria-busy={busy}
              onClick={recheck}
            >
              <BusyLabel busy={busy}>حوّلتُ — تحقّق الآن</BusyLabel>
            </button>
          )}
          <button type="button" className="t2-m-link" onClick={() => setCliq(null)}>
            رجوع
          </button>
        </section>
      ) : (
        <>
          <AmountCardT2 id="topup-amount" label="المبلغ" value={amount} onChange={setAmount} currency={currency}>
            <QuickAmountsT2 amounts={QUICK_AMOUNTS} value={amount} onPick={setAmount} label={(value) => formatMoney(value)} />
          </AmountCardT2>
          <UnitNoteT2 hint={unitHint(unit, currency)} error={unitError} />

          <h2 className="t2-section">طريقة الشحن</h2>
          <div className="t2-m-chans" role="radiogroup" aria-label="طريقة الشحن">
            {cliqEnabled ? (
              <ChannelOption
                active={channel === "cliq"}
                onSelect={() => setChannel("cliq")}
                icon="smartphone"
                title="كليك — رمز فوري"
                hint="امسح الرمز من تطبيق بنكك ويُشحن رصيدك آلياً"
              />
            ) : null}

            {cardEnabled ? (
              <ChannelOption
                active={channel === "card"}
                onSelect={() => setChannel("card")}
                icon="credit_card"
                title="بطاقة"
                hint="شحنٌ فوري عبر صفحة دفع آمنة"
              />
            ) : null}

            <ChannelOption
              active={channel === "manual"}
              onSelect={() => setChannel("manual")}
              icon="account_balance"
              title="حوالة يدوية"
              hint="حوّل ثم أدخل المرجع — تؤكده الإدارة"
            />
          </div>

          {channel === "manual" ? (
            <div className="t2-m-gap-lg">
              <AuthBlock label="مرجع الحوالة" htmlFor="topup-reference" hint="رقم الحوالة كما يظهر في تطبيق بنكك">
                <AuthInput
                  id="topup-reference"
                  dir="ltr"
                  autoComplete="off"
                  value={reference}
                  onChange={(event) => setReference(event.target.value)}
                />
              </AuthBlock>
            </div>
          ) : null}

          <BannerT2 tone="danger" message={error} />
          <BannerT2 tone="ok" message={done} />

          <div className="t2-m-actions">
            <button
              type="button"
              className="t2-button primary t2-m-cta"
              disabled={
                busy ||
                Number(amount) <= 0 ||
                unitError !== null ||
                (channel === "manual" && reference.trim().length < 3)
              }
              aria-busy={busy}
              onClick={submit}
            >
              <BusyLabel busy={busy}>متابعة</BusyLabel>
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/** قناةُ شحن — بطاقةُ «اختر الفئة» في R06: المختارةُ بحافّةٍ مزدوجةٍ بالحبر. */
function ChannelOption({
  active,
  onSelect,
  icon,
  title,
  hint,
}: {
  active: boolean;
  onSelect: () => void;
  icon: string;
  title: string;
  hint: string;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onSelect}
      className={active ? "t2-m-chan on" : "t2-m-chan"}
    >
      <span className="t2-m-chan-icon">
        <Icon name={icon} />
      </span>
      <span className="t2-m-chan-main">
        <span className="t2-m-chan-title">{title}</span>
        <span className="t2-m-chan-hint">{hint}</span>
      </span>
    </button>
  );
}
