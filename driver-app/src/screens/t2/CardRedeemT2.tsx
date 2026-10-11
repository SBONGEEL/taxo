/** **بطاقةُ TAXO للكبتن** — رمزٌ مطبوعٌ يشحن محفظتَه مرّةً واحدة (SPEC §٧٣-هـ المرحلة ٢)، **بقطع شاشات مال الكبتن** (رأسُ C10،
 * وحقلُ C18، وزرُّ C21).
 *
 * **ستّةَ عشرَ حرفاً أربعاً أربعاً** — والخادمُ يقبلها بمسافاتٍ وحروفٍ صغيرة. **والرصيدُ لمحفظة الكبتن** (`wallet=driver`): سياقُ الفعل لا
 * دورُ الفاعل (SPEC §22). **والمحاولاتُ الخاطئةُ مسقوفة** — والخادمُ يقول متى يُعاد.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { redeemTaxoCard } from "@/api/endpoints";
import type { TaxoCardRedeemed } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./fields.css";
import "./money.css";
import "./payrequest.css";

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
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر استعمال البطاقة — أعد المحاولة");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2 t2-clq-page scr">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">بطاقة TAXO</h1>
      </div>

      {done ? (
        <div className="t2-wdl-card t2-pr-done">
          <Icon name="check_circle" />
          <h2 className="t2-pr-done-title">شُحن رصيدك</h2>
          <p className="t2-pr-done-text">
            أُضيف {digits(done.amount)} {CURRENCY_LABEL[done.currency]} من البطاقة <span dir="ltr">{done.serial}</span>.
          </p>
          <button type="button" className="t2-clq-cta t2-pr-gap" onClick={() => navigate("/wallet")}>
            إلى المحفظة
          </button>
        </div>
      ) : (
        <>
          <label className="t2-fld-label" htmlFor="taxo-card-code">
            رمز البطاقة
          </label>
          <input
            id="taxo-card-code"
            className="t2-fld"
            dir="ltr"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            value={code}
            onChange={(event) => setCode(grouped(event.target.value))}
          />
          <p className="t2-fld-hint">ستّةَ عشرَ حرفاً كما تحت الطبقة الفضيّة</p>
          {error ? (
            <p className="t2-note danger" role="alert">
              <Icon name="error" fill />
              {error}
            </p>
          ) : null}
          <button
            type="button"
            className="t2-clq-cta t2-pr-gap-lg"
            disabled={busy || !ready}
            aria-busy={busy}
            onClick={submit}
          >
            {busy ? "يُشحن…" : "اشحن"}
          </button>
        </>
      )}
    </div>
  );
}
