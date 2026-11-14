/** **بطاقةُ TAXO** — رمزٌ مطبوعٌ يشحن المحفظةَ مرّةً واحدة (SPEC §٧٣-هـ المرحلة ٢)، **بقطع شاشات المال نفسِها** (R16).
 *
 * **ستّةَ عشرَ حرفاً أربعاً أربعاً كما في البطاقة** — الحقلُ يرتّبها وأنت تكتب، والخادمُ يقبلها بمسافاتٍ وحروفٍ صغيرة. **ولا يُقال لماذا
 * رُفض رمزٌ أكثرَ ممّا يقوله الخادم**: «غيرُ صحيح» لا «غيرُ موجودٍ في سوقك» — فلا يُعرف من الردّ أين يوجد رمز. **والمحاولاتُ الخاطئةُ
 * مسقوفة** — والخادمُ يقول متى يُعاد.
 */

import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

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

/** **رمزٌ وصل من رابط** (`/redeem#<الرمز>`: QR البطاقة أو زرُّ «اشحن في التطبيق» في صفحة الهدية، SPEC §١٠٠).
 * ما بعد `#` لا يبلغ خادماً، فيُحفظ في الجلسة ويُفتح به حقلُ البطاقة، ثمّ يُمحى من شريط العنوان. */
const REDEEM_KEY = "taxo.redeem.code";

export function RedeemLink() {
  const raw = typeof window === "undefined" ? "" : window.location.hash.replace(/^#/, "");
  const plain = raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 16);
  try {
    if (plain) sessionStorage.setItem(REDEEM_KEY, plain);
  } catch {
    /* تخزينُ الجلسة ممنوع: يُكتب الرمزُ باليد */
  }
  return <Navigate to="/wallet/card" replace />;
}

function takeLinkedCode(): string {
  try {
    const saved = sessionStorage.getItem(REDEEM_KEY) ?? "";
    sessionStorage.removeItem(REDEEM_KEY);
    return grouped(saved);
  } catch {
    return "";
  }
}

/** **امسح QR البطاقة** (SPEC §١٠٠-ب/١١) — صورةٌ من الكاميرا تُقرأ **في الجهاز نفسِه** (`BarcodeDetector`) **ولا تُرفع إلى أيِّ خادم**.
 * والـQR يحمل `app.tajora.ly/redeem#<الرمز>`، فيُؤخذ ما بعد `#`. **وجهازٌ لا يملك القارئ لا يرى الزرّ** — وكاميرا الهاتف نفسُها تفتح الرابط. */
type Detector = { detect: (image: ImageBitmap) => Promise<{ rawValue: string }[]> };

function hasQrReader(): boolean {
  return typeof window !== "undefined" && "BarcodeDetector" in window && typeof createImageBitmap === "function";
}

async function readQr(file: File): Promise<string | null> {
  const Ctor = (window as unknown as { BarcodeDetector: new (options: { formats: string[] }) => Detector }).BarcodeDetector;
  const found = await new Ctor({ formats: ["qr_code"] }).detect(await createImageBitmap(file));
  const raw = found[0]?.rawValue ?? "";
  const tail = raw.includes("#") ? raw.slice(raw.indexOf("#") + 1) : raw;
  const plain = tail.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 16);
  return plain.length === 16 ? plain : null;
}

export function CardRedeemT2Screen() {
  const goBack = useGoBack("/wallet");
  const navigate = useNavigate();
  const [code, setCode] = useState(takeLinkedCode);
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
          {hasQrReader() ? (
            <label className="t2-button t2-m-cta t2-m-gap" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              <Icon name="qr_code_scanner" />
              {tr("امسح رمز QR")}
              <input
                type="file"
                accept="image/*"
                capture="environment"
                hidden
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (!file) return;
                  try {
                    const scanned = await readQr(file);
                    if (scanned) {
                      setCode(grouped(scanned));
                      setError(null);
                    } else setError(tr("لم يُقرأ رمزُ QR — قرّب الكاميرا أو اكتب الرمز"));
                  } catch {
                    setError(tr("لم يُقرأ رمزُ QR — قرّب الكاميرا أو اكتب الرمز"));
                  }
                }}
              />
            </label>
          ) : null}
        </>
      )}
    </div>
  );
}
