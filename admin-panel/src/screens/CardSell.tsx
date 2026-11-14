/** **صفحةُ بائع البطاقات** (SPEC §١٠٠-ب/٥) — على الهاتف أو الحاسوب.
 *
 * يختار البائعُ الفئةَ ويضغط «بِع»، فتُولَّد بطاقةٌ واحدةٌ باسم محلّه **ويظهر رمزُها هنا مرّةً واحدة** في إيصالٍ يُطبع (طابعةٌ حراريّةٌ
 * ٨٠ مم أو ورقةٌ عاديّة) أو يُعرض للمشتري على الشاشة. **ولا يُخزَّن الرمزُ في أيِّ مكان**: يُمحى من الصفحة بزرّ «بيعٌ جديد»،
 * ومبيعاتُه تظهر تحته بالرقم التسلسليّ والحال وحدَهما.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { resellerMe, resellerSales, resellerSell } from "@/api/endpoints";
import type { ResellerMe, ResellerSale, ResellerSaleRow } from "@/api/types";
import { QrCode } from "@/components/QrCode";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { DISPLAY_LOCALE, cn, digits } from "@/lib/utils";

const REDEEM_URL = "https://app.tajora.ly/redeem#";

const STATE_LABEL: Record<ResellerSaleRow["state"], string> = {
  unused: "لم تُستعمل",
  redeemed: "استُعملت",
  expired: "انتهت",
  cancelled: "أُلغيت",
  not_started: "لم تبدأ",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString(DISPLAY_LOCALE, { dateStyle: "medium", timeStyle: "short" });
}

function errorText(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

/** الطباعةُ للإيصال وحدَه — ٨٠ مم للطابعة الحراريّة، وتصلح للورقة العاديّة */
const PRINT_CSS = `
@media print {
  @page { size: 80mm auto; margin: 3mm; }
  body * { visibility: hidden !important; }
  #pos-receipt, #pos-receipt * { visibility: visible !important; }
  #pos-receipt { position: absolute; inset: 0 auto auto 0; width: 74mm; border: 0 !important; box-shadow: none !important;
    background: #fff !important; color: #000 !important; }
  .no-print { display: none !important; }
}`;

export function CardSellScreen() {
  const [me, setMe] = useState<ResellerMe | null>(null);
  const [sales, setSales] = useState<ResellerSaleRow[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [sale, setSale] = useState<ResellerSale | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    const [mine, rows] = await Promise.all([resellerMe(), resellerSales()]);
    setMe(mine);
    setSales(rows);
  }, []);
  useEffect(() => {
    load().catch((caught) => setError(errorText(caught, "تعذّر فتح صفحة البيع")));
  }, [load]);

  async function sell() {
    if (!picked) return;
    setBusy(true);
    setError(null);
    try {
      setSale(await resellerSell(picked));
      setCopied(false);
      await load();
    } catch (caught) {
      setError(errorText(caught, "تعذّر البيع"));
    } finally {
      setBusy(false);
    }
  }

  const left = me ? Math.max(0, me.daily_cap - me.sold_today) : 0;

  return (
    <Shell title="بيع بطاقات TAXO" subtitle={me ? `${me.shop_name} · ${me.name}` : "صفحةُ البيع"}>
      <style>{PRINT_CSS}</style>
      <ErrorNote message={error} />
      {me && !me.enabled ? (
        <div className="rounded-card border border-line bg-surface p-16 text-13 text-ink">
          البيعُ في المحلّات غيرُ مفتوحٍ بعد. ستُفتح هذه الصفحةُ للبيع حين تفتحه الإدارة.
        </div>
      ) : null}

      {sale ? (
        <div className="mx-auto mt-8 max-w-[380px]">
          <div id="pos-receipt" className="rounded-card border border-line bg-white p-16 text-center text-black">
            <p className="text-15 font-bold">TAXO</p>
            <p className="text-12">بطاقةُ شحن · {sale.shop_name}</p>
            <p className="mt-10 text-30 font-bold" dir="ltr">
              {digits(sale.amount)} {sale.currency}
            </p>
            <p className="mt-10 text-11">الرمز</p>
            <p className="font-mono text-18 font-bold tracking-wider" dir="ltr">
              {sale.code}
            </p>
            <div className="mt-10 flex justify-center">
              <QrCode payload={`${REDEEM_URL}${sale.code.replace(/-/g, "")}`} size={150} alt="رمزُ شحن البطاقة" />
            </div>
            <p className="mt-8 text-11">امسح الرمزَ بكاميرا الهاتف، أو افتح التطبيق: المحفظة ← بطاقة TAXO</p>
            <p className="mt-8 text-10.5" dir="ltr">
              {sale.serial}
            </p>
            <p className="text-10.5">
              بيعت {when(sale.sold_at)} · تنتهي {when(sale.expires_at)}
            </p>
            <p className="mt-6 text-10.5">تُستعمل مرّةً واحدة — احفظ الإيصالَ حتى تشحن.</p>
          </div>
          <div className="no-print mt-12 grid grid-cols-2 gap-10">
            <Button size="md" onClick={() => window.print()}>
              اطبع الإيصال
            </Button>
            <Button
              size="md"
              variant="secondary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(sale.code);
                  setCopied(true);
                } catch {
                  setCopied(false);
                }
              }}
            >
              {copied ? "نُسخ الرمز" : "انسخ الرمز"}
            </Button>
          </div>
          <Button className="no-print mt-10" size="md" variant="ghost" onClick={() => setSale(null)}>
            بيعٌ جديد — ويُمحى الرمزُ من الشاشة
          </Button>
        </div>
      ) : me?.enabled ? (
        <div className="mx-auto mt-8 max-w-[480px]">
          <p className="text-12 text-muted">
            بقي لك {digits(String(left))} من {digits(String(me.daily_cap))} في آخر 24 ساعة. والبطاقةُ صالحةٌ{" "}
            {digits(String(me.validity_days))} يوماً من بيعها.
          </p>
          <div className="mt-12 grid grid-cols-2 gap-10">
            {me.denominations.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => setPicked(d.id)}
                className={cn(
                  "rounded-card border p-16 text-center text-20 font-bold transition",
                  picked === d.id ? "border-brand bg-brand/10 text-ink" : "border-line bg-surface text-ink",
                )}
              >
                <span dir="ltr">
                  {digits(d.amount)} {d.currency}
                </span>
              </button>
            ))}
          </div>
          {me.denominations.length === 0 ? <p className="mt-10 text-12 text-muted">لا فئاتٍ فعّالةً في سوقك بعد.</p> : null}
          <Button className="mt-14" size="lg" loading={busy} disabled={!picked || left === 0} onClick={() => void sell()}>
            بِع البطاقة
          </Button>
        </div>
      ) : null}

      <div className="no-print mx-auto mt-24 max-w-[480px]">
        <p className="text-13 font-semibold text-ink">مبيعاتي</p>
        {sales.length === 0 ? <p className="mt-6 text-12 text-muted">لا مبيعات بعد.</p> : null}
        <ul className="mt-8 grid gap-6">
          {sales.map((row) => (
            <li key={row.serial} className="flex items-center justify-between rounded-12 border border-line bg-surface px-12 py-10">
              <span className="min-w-0">
                <span dir="ltr" className="block text-12 font-semibold text-ink">
                  {row.serial}
                </span>
                <span className="block text-10.5 text-muted">{when(row.sold_at)}</span>
              </span>
              <span className="text-end">
                <span className="block text-12 text-ink" dir="ltr">
                  {digits(row.amount)} {row.currency}
                </span>
                <span className={cn("block text-10.5", row.state === "redeemed" ? "text-ok" : "text-muted")}>
                  {STATE_LABEL[row.state]}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Shell>
  );
}
