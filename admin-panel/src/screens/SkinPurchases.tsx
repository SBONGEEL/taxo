/** **مشترياتُ المركبات** — سجلُّ ما خرج من محافظ الكباتن (2026-08-27).
 *
 * **وشاشةٌ مستقلّةٌ لا لوحٌ في «مركبات المتجر»** (قرارُ المالك: «مالٌ يخرج من
 * محافظ الكباتن له شاشتُه»). والكتالوجُ يجيب «**كم** بيعت من هذه المركبة»،
 * وهذه تجيب «**من** اشترى، و**متى**، و**بكم**، و**أيَّها يقود اليوم**» —
 * سؤالان مختلفان، وبطاقةٌ واحدةٌ تخدمهما تخدم أحدهما.
 *
 * **ولا رقمَ يُجمع هنا**: `total` و`revenue_by_currency` و«الموهوب» تصل
 * **مجموعةً من الخلفية على الجدول كلِّه**. والصفحةُ محدودةٌ بخمسين، فجمعُها
 * في المتصفّح يُخرج رقماً عنوانُه «الإيرادُ الكلي» وقيمتُه «إيرادُ ما ظهر»
 * — وهي قاعدةُ §14 مطبَّقةً على عدٍّ لا على مبلغ.
 *
 * **والإيرادُ بعملته لا مجموعاً**: دينارٌ أردنيٌّ وليبيٌّ لا يُجمعان، ورقمٌ
 * واحدٌ فوقهما كذبٌ صامت.
 *
 * **وثلاثةُ مصادرَ تُفرَّق ولا تُخلط**: شراءٌ بمالٍ، وهديةُ أوّلِ اشتراك،
 * ومنحةٌ إدارية. **والهديةُ والمنحةُ كلتاهما بلا سعر** — فمن قرأ «بلا مبلغ»
 * علامةً على الهدية عدّ المنحَ الإداريةَ هدايا، **وميزانيةُ الشهر المجاني
 * تُقرأ من عدد الهدايا وحدَها**.
 *
 * **ولا زرَّ يكتب هنا**: اللوحةُ تعرض ولا تخترع موضعاً ثانياً للقرار — إبطالُ
 * شراءٍ قرارٌ على صفِّ مِلكيّةٍ لا يُحذف (`RESTRICT` في النموذج)، ومنحُ مركبةٍ
 * بابُه شاشةُ الكبتن. وشاشةٌ للقراءة تُقال قراءةً ولا يُوضع فيها زرٌّ يُظنّ.
 */

import { useCallback, useEffect, useState } from "react";

import { listSkinPurchases } from "@/api/endpoints";
import type { SkinPurchaseRow, SkinPurchases } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Badge } from "@/components/ui/Badge";
import type { Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { currencyLabel, moment, money } from "@/lib/format";
import { digits } from "@/lib/utils";

const PAGE = 50;

/** **ندرةٌ ← نغمةُ شارة** — من `DESIGN.md` §2.6: النغمةُ لا اللون. */
const RARITY: Record<string, { label: string; tone: Tone }> = {
  common: { label: "عادية", tone: "muted" },
  premium: { label: "مميّزة", tone: "ink" },
  rare: { label: "نادرة", tone: "warn" },
  legendary: { label: "أسطورية", tone: "ok" },
};

const SOURCE: Record<string, { label: string; tone: Tone }> = {
  purchase: { label: "شراء", tone: "ok" },
  gift: { label: "هدية أول اشتراك", tone: "ink" },
  grant: { label: "منحة إدارية", tone: "muted" },
};

export function SkinPurchasesScreen() {
  const [data, setData] = useState<SkinPurchases | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (offset: number) => {
    setLoading(true);
    setError(null);
    try {
      setData(await listSkinPurchases({ limit: PAGE, offset }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "تعذّر قراءة السجل");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(page * PAGE);
  }, [load, page]);

  return (
    <Shell
      title="مشتريات المركبات"
      subtitle="مالٌ خرج من محافظ الكباتن — من اشترى، ومتى، وبكم."
    >
      {error ? <ErrorNote message={error} /> : null}

      {data ? (
        <div className="mt-16 grid gap-12 sm:grid-cols-2 lg:grid-cols-4">
          <Tile label="مِلكيّات مسجَّلة" value={digits(String(data.total))} />
          <Tile
            label="إيراد المبيعات"
            value={
              Object.keys(data.revenue_by_currency).length === 0
                ? "—"
                : Object.entries(data.revenue_by_currency)
                    .map(([code, amount]) => money(amount, code))
                    .join(" · ")
            }
          />
          <Tile
            label="هدايا أول اشتراك"
            value={digits(String(data.gifted_count))}
            note="وهي ميزانية الشهر المجاني المستهلكة"
          />
          <Tile label="منح إدارية" value={digits(String(data.granted_count))} />
        </div>
      ) : null}

      {loading && !data ? <Spinner className="mx-auto mt-24" /> : null}

      {data && data.rows.length === 0 ? (
        <EmptyNote
          title="لا مِلكيّةَ مسجَّلة"
          hint="لم يشترِ كبتنٌ مركبةً بعد، ولم تُمنح هديةُ أوّلِ اشتراك."
        />
      ) : null}

      {data && data.rows.length > 0 ? (
        <div className="mt-16 overflow-x-auto rounded-16 border border-line">
          <table className="w-full min-w-[46rem] text-13">
            <thead className="bg-surface-2 text-muted">
              <tr>
                <Th>الكبتن</Th>
                <Th>المركبة</Th>
                <Th>المصدر</Th>
                <Th>المبلغ</Th>
                <Th>التاريخ</Th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <Row key={row.id} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {data && data.total > PAGE ? (
        <div className="mt-16 flex items-center justify-between gap-12">
          <Button
            variant="ghost"
            disabled={page === 0 || loading}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
          >
            السابق
          </Button>
          <span className="text-12 text-muted">
            {digits(String(page * PAGE + 1))}–
            {digits(String(Math.min((page + 1) * PAGE, data.total)))} من{" "}
            {digits(String(data.total))}
          </span>
          <Button
            variant="ghost"
            disabled={(page + 1) * PAGE >= data.total || loading}
            onClick={() => setPage((current) => current + 1)}
          >
            التالي
          </Button>
        </div>
      ) : null}
    </Shell>
  );
}

function Tile({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="rounded-16 border border-line bg-surface p-16">
      <p className="text-12 text-muted">{label}</p>
      <p className="mt-6 text-20 font-semibold text-ink">{value}</p>
      {note ? <p className="mt-4 text-11 text-muted">{note}</p> : null}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="p-12 text-start font-medium">{children}</th>;
}

function Row({ row }: { row: SkinPurchaseRow }) {
  const rarity = RARITY[row.rarity] ?? { label: row.rarity, tone: "muted" as const };
  const source = SOURCE[row.source] ?? { label: row.source, tone: "muted" as const };
  return (
    <tr className="border-t border-line">
      <td className="p-12">
        <p className="text-ink">{row.driver_name}</p>
        {/* **الهاتفُ معرِّفٌ لا كمّية** — فلا تُحوَّل خاناتُه */}
        <p className="mt-2 text-11 text-muted" dir="ltr">
          {row.driver_phone}
        </p>
      </td>
      <td className="p-12">
        <div className="flex flex-wrap items-center gap-6">
          <span className="text-ink">{row.skin_name}</span>
          <Badge tone={rarity.tone}>{rarity.label}</Badge>
          {row.is_active_for_driver ? <Badge tone="ok">مفعَّلة الآن</Badge> : null}
        </div>
      </td>
      <td className="p-12">
        <Badge tone={source.tone}>{source.label}</Badge>
      </td>
      <td className="p-12">
        {/* **بلا مبلغٍ يُكتب شرطةً لا صفراً**: صفرٌ يقرأ «دُفع لا شيء» */}
        {row.price_paid === null ? (
          <span className="text-muted">—</span>
        ) : (
          <span className="text-ink">
            {money(row.price_paid, row.currency ?? undefined)}
            {row.currency ? (
              <span className="ms-4 text-11 text-muted">
                {currencyLabel(row.currency)}
              </span>
            ) : null}
          </span>
        )}
      </td>
      <td className="p-12 text-muted">{moment(row.created_at)}</td>
    </tr>
  );
}
