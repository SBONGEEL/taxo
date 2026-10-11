/** **بطاقةُ TAXO** — رمزٌ مطبوعٌ يشحن المحفظةَ مرّةً واحدة (SPEC §٧٣-هـ المرحلة ٢)، **بقطع شاشات المال نفسِها** (R16).
 *
 * **ستّةَ عشرَ حرفاً أربعاً أربعاً كما في البطاقة** — الحقلُ يرتّبها وأنت تكتب، والخادمُ يقبلها بمسافاتٍ وحروفٍ صغيرة. **ولا يُقال لماذا
 * رُفض رمزٌ أكثرَ ممّا يقوله الخادم**: «غيرُ صحيح» لا «غيرُ موجودٍ في سوقك» — فلا يُعرف من الردّ أين يوجد رمز. **والمحاولاتُ الخاطئةُ
 * مسقوفة** — والخادمُ يقول متى يُعاد.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { redeemTaxoCard } from "@/api/endpoints";
import type { TaxoCardRedeemed } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { play } from "@/lib/sound";
import { formatMoney } from "@/lib/utils";
import { AuthBlock, AuthInput, Icon } from "@/taxo2";

import { BannerT2, BusyLabel, HeadT2 } from "./MoneyT2";
import "./payrequest.css"; import { tr } from "@/lib/i18n";

/** **الرمزُ كما يُطبع** — حروفٌ وأرقامٌ كبيرة، أربعاً أربعاً، ستّةَ عشرَ على الأكثر */
function grouped(raw: string): string {
  const plain = raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 16);
  return plain.replace(/(.{4})(?=.)/g, "$1-");
}

export function CardRedeemT2Screen() {
  const goBack = useGoBack("/wallet");
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<TaxoCardRedeemed | null>(null);
  const ready = code.replace(/-/g, "").length === 16;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      setDone(await redeemTaxoCard(code));
      // **الصوتُ مع «شُحن» لا قبله** — المالُ قُيّد في الردّ نفسِه
      play("topup");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر استعمال البطاقة — أعد المحاولة"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2 t2-m-page">
      <HeadT2 title={tr("بطاقة TAXO")} onBack={goBack} />
      {done ? (
        <section className="t2-m-card t2-pr-done">
          <Icon name="check_circle" />
          <h2 className="t2-pr-done-title">{tr("شُحن رصيدك")}</h2>
          <p className="t2-pr-done-text">
            {tr("أُضيف")}{" "}{formatMoney(done.amount, done.currency)}{" "}{tr("من البطاقة")}{" "}
            <span dir="ltr">{done.serial}</span>.
          </p>
          <button type="button" className="t2-button primary t2-m-cta t2-m-gap" onClick={() => navigate("/wallet")}>
            {tr("إلى المحفظة")}
          </button>
        </section>
      ) : (
        <>
          <AuthBlock label={tr("رمز البطاقة")} htmlFor="taxo-card-code" hint={tr("ستّةَ عشرَ حرفاً كما تحت الطبقة الفضيّة")}>
            <AuthInput
              id="taxo-card-code"
              dir="ltr"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              value={code}
              onChange={(event) => setCode(grouped(event.target.value))}
            />
          </AuthBlock>
          <BannerT2 tone="danger" message={error} />
          <div className="t2-m-actions">
            <button
              type="button"
              className="t2-button primary t2-m-cta"
              disabled={busy || !ready}
              aria-busy={busy}
              onClick={submit}
            >
              <BusyLabel busy={busy}>{tr("اشحن")}</BusyLabel>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
