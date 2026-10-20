/** **الإشعارات** — كلُّ نشاطٍ في الأسواق الثلاثة (SPEC §٨١/١): مرشِّحاتٌ بالنوع والسوق والتاريخ، و«مقروء» لصفٍّ أو للكلّ.
 *
 * **والسطرُ سطرُ شاشة القفل حرفاً** (`title`/`body` من الخادم): نوعٌ وسوقٌ ومبلغٌ بلا اسمٍ ولا رقم — **والتفاصيلُ في سجلّها**،
 * ينقلك إليه النقرُ. **والصفُّ المجموعُ** («١٢ طلبَ رحلة») يفتح القائمةَ مرشَّحةً بنوعه.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { alertCatalog, listAlerts } from "@/api/endpoints";
import type { AdminAlert, AlertCatalog, AlertCategory, CountryCode } from "@/api/types";
import { AlertRow } from "@/components/AlertBell";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { DateInput, Select } from "@/components/ui/Field";
import { Segmented } from "@/components/ui/Segmented";
import { recordPath, useAlertFeed } from "@/lib/alerts";
import { useCountries } from "@/lib/countries";

const PAGE = 50;

type CategoryFilter = AlertCategory | "all";

export function AlertsScreen() {
  const navigate = useNavigate();
  const feed = useAlertFeed();
  const [params, setParams] = useSearchParams();
  const { rows: markets } = useCountries();
  const [catalog, setCatalog] = useState<AlertCatalog | null>(null);
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [country, setCountry] = useState<CountryCode | "">("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [items, setItems] = useState<AdminAlert[] | null>(null);
  const [more, setMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const kind = params.get("kind") ?? "";

  useEffect(() => {
    void alertCatalog().then(setCatalog).catch((cause) => setError((cause as Error).message));
  }, []);

  const query = useMemo(
    () => ({
      category: category === "all" ? undefined : category,
      kind: kind || undefined,
      country_code: country || undefined,
      // **يومُ البدء من أوّله ويومُ النهاية إلى آخره** — بتوقيت الجهاز الذي يقرأ
      since: since ? new Date(`${since}T00:00:00`).toISOString() : undefined,
      until: until ? new Date(`${until}T23:59:59`).toISOString() : undefined,
      unread: unreadOnly || undefined,
      limit: PAGE,
    }),
    [category, kind, country, since, until, unreadOnly],
  );

  const load = useCallback(
    async (before?: string) => {
      try {
        const page = await listAlerts({ ...query, before });
        setItems((current) => (before && current ? [...current, ...page.items] : page.items));
        setMore(page.items.length === PAGE);
      } catch (cause) {
        setError((cause as Error).message);
      }
    },
    [query],
  );

  useEffect(() => {
    setItems(null);
    void load();
  }, [load, feed?.summary?.unread]);

  const kinds = (catalog?.kinds ?? []).filter((spec) => category === "all" || spec.category === category);

  const openAlert = (alert: AdminAlert) => {
    if (!alert.read) void feed?.markRead([alert.id]);
    navigate(recordPath(alert));
  };

  return (
    <Shell
      title="الإشعارات"
      subtitle={`كلُّ نشاطٍ في الأسواق الثلاثة — غيرُ المقروء ${feed?.summary?.unread ?? 0}`}
      actions={
        <div className="flex flex-wrap gap-8">
          <Button size="sm" variant="secondary" onClick={() => void feed?.markRead("all")}>
            الكلُّ مقروء
          </Button>
          <Button size="sm" variant="secondary" onClick={() => navigate("/alerts/settings")}>
            الإعداد
          </Button>
        </div>
      }
    >
      <div className="ad-alert-page">
        <div className="ad-alert-filters">
          <Segmented
            label="النوع"
            value={category}
            onPick={(next) => {
              setCategory(next);
              if (kind) setParams({});
            }}
            options={[
              { key: "all", label: "الكلّ" },
              ...(catalog?.categories ?? []).map((item) => ({ key: item.key as CategoryFilter, label: item.label })),
            ]}
          />
          <Select
            label="الحدث"
            value={kind}
            onChange={(event) => setParams(event.target.value ? { kind: event.target.value } : {})}
          >
            <option value="">كلُّ الأحداث</option>
            {kinds.map((spec) => (
              <option key={spec.kind} value={spec.kind}>
                {spec.label}
              </option>
            ))}
          </Select>
          <Select label="السوق" value={country} onChange={(event) => setCountry(event.target.value as CountryCode | "")}>
            <option value="">كلُّ الأسواق</option>
            {(markets ?? []).map((market) => (
              <option key={market.country_code} value={market.country_code}>
                {market.name}
              </option>
            ))}
          </Select>
          <DateInput label="من" value={since} onChange={setSince} />
          <DateInput label="إلى" value={until} onChange={setUntil} />
          <Segmented
            label="الحال"
            value={unreadOnly ? "unread" : "all"}
            onPick={(next) => setUnreadOnly(next === "unread")}
            options={[
              { key: "all", label: "الكلّ" },
              { key: "unread", label: "غيرُ المقروء" },
            ]}
          />
        </div>
        <ErrorNote message={error} />
        {items === null ? (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        ) : null}
        {items !== null && items.length === 0 ? (
          <div className="ad-reports-empty">
            <p className="ad-empty-title">لا إشعاراتٍ بهذه المرشِّحات.</p>
          </div>
        ) : null}
        {items !== null && items.length > 0 ? (
          <div className="ad-alert-list">
            {items.map((alert) => (
              <AlertRow key={alert.id} alert={alert} onOpen={openAlert} />
            ))}
          </div>
        ) : null}
        {more && items ? (
          <div className="mt-12">
            <Button size="sm" variant="secondary" onClick={() => void load(items[items.length - 1].last_event_at)}>
              أقدم
            </Button>
          </div>
        ) : null}
      </div>
    </Shell>
  );
}
