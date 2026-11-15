/** **«وجهتي» بالبحث** (أمرُ المالك ٢٠٢٦-١١-١٦ الثالث، SPEC §١٠٤/١٦) — قائمةُ البحث نفسُها التي في تطبيق الراكب، خلف
 *  `places_search_v2`: أيقونةُ الصنف، والحروفُ المظلَّلة، والمسافةُ من الكبتن، و«الأخيرة» تُحذف، والهيكلُ وعدمُ النتيجة وانقطاعُ
 *  الشبكة بـ«أعد المحاولة»، و«حدّد على الخريطة» آخراً — **وهو يعيده إلى الخريطة الموسَّعة لينقر نقطتَه كما كان**.
 *
 *  **وما ليس هنا عمداً**: النجمةُ و«البيت/العمل» — الأماكنُ المحفوظةُ بابُ الراكب (`/me/places`)، ولا مكانَ محفوظاً للكبتن يُعرض.
 *  **والاختيارُ يمرّ بـ«اجعلها وجهتي» نفسِه** (`setDestination`) بحدوده اليوميّة، فلا يتغيّر شيءٌ في التوزيع ولا في الأجرة.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { placeSearch } from "@/api/endpoints";
import type { Coordinates } from "@/api/types";
import { useBackLayer } from "@/lib/back-layers";
import { metersBetween } from "@/lib/eta";
import { tr } from "@/lib/i18n";
import {
  browserStore,
  categoryIcon,
  distanceLabel,
  forgetRecent,
  hiddenRecents,
  highlightRange,
  latestOnly,
  MIN_QUERY,
  pointKey,
  recentPicks,
  rememberPick,
  SEARCH_DEBOUNCE_MS,
} from "@/lib/place-search";
import { Icon } from "@/taxo2";

interface Row {
  id: string;
  name: string;
  address: string;
  at: Coordinates;
  category: string | null;
  distance: number | null;
}

type Status = "idle" | "loading" | "done" | "empty" | "offline";

export function DestinationSearchT2({
  userId,
  position,
  onChoose,
  onPickOnMap,
  onClose,
  error,
}: {
  userId: string | null;
  position: Coordinates | null;
  onChoose: (at: Coordinates, label: string) => void;
  onPickOnMap: () => void;
  onClose: () => void;
  error: string | null;
}) {
  useBackLayer(true, onClose);
  const store = useMemo(() => browserStore(), []);
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [credit, setCredit] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [storeVersion, setStoreVersion] = useState(0);
  const order = useRef(latestOnly());
  const input = useRef<HTMLInputElement>(null);
  const typing = query.trim().length >= MIN_QUERY;

  useEffect(() => {
    const text = query.trim();
    if (text.length < MIN_QUERY) {
      order.current.next();
      setRows([]);
      setStatus("idle");
      setCredit(null);
      return;
    }
    const ticket = order.current.next();
    const controller = new AbortController();
    setStatus((current) => (current === "done" ? "done" : "loading"));
    const timer = window.setTimeout(async () => {
      try {
        const answer = await placeSearch(text, position ?? undefined, controller.signal);
        if (controller.signal.aborted || !order.current.isCurrent(ticket)) return;
        const found = answer.items
          .filter((item) => item.lat !== null && item.lng !== null)
          .map((item) => ({
            id: item.id,
            name: item.name,
            address: item.address,
            at: { lat: item.lat as number, lng: item.lng as number },
            category: item.category ?? null,
            distance: item.distance_m,
          }));
        setRows(found);
        setCredit(answer.attribution === "open" ? answer.attribution_text : null);
        setStatus(found.length ? "done" : "empty");
      } catch {
        if (controller.signal.aborted || !order.current.isCurrent(ticket)) return;
        setRows([]);
        setStatus("offline");
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [query, position, retry]);

  const lately = useMemo(() => {
    void storeVersion;
    const hidden = new Set(hiddenRecents(store, userId));
    return recentPicks(store, userId)
      .filter((pick) => !hidden.has(pointKey(pick)))
      .slice(0, 5)
      .map<Row>((pick) => ({
        id: `pick:${pointKey(pick)}`, name: pick.name, address: pick.address, at: { lat: pick.lat, lng: pick.lng },
        category: "recent", distance: position ? metersBetween(position, pick) : null,
      }));
  }, [store, userId, position, storeVersion]);

  const choose = (row: Row) => {
    rememberPick(store, userId, { name: row.name, address: row.address, lat: row.at.lat, lng: row.at.lng, category: row.category });
    onChoose(row.at, row.name);
  };

  return (
    <div className="t2-ds" role="dialog" aria-label={tr("ابحث عن وجهتك")}>
      <div className="t2-ds-head">
        <button type="button" className="t2-ps-icon-btn" aria-label={tr("إغلاق")} onClick={onClose}>
          <Icon name="arrow_forward" />
        </button>
        <label className="t2-ds-field">
          <Icon name="search" />
          <input
            ref={input}
            autoFocus
            enterKeyHint="search"
            placeholder={tr("ابحث عن وجهتك")}
            aria-label={tr("ابحث عن وجهتك")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query ? (
            <button
              type="button"
              className="t2-ps-icon-btn"
              aria-label={tr("امسح البحث")}
              onClick={() => {
                setQuery("");
                input.current?.focus();
              }}
            >
              <Icon name="close" />
            </button>
          ) : null}
        </label>
      </div>
      {error ? (
        <p className="t2-ds-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="t2-ds-body">
        {!typing ? (
          lately.length > 0 ? (
            <Section title={tr("عمليات البحث الأخيرة")}>
              {lately.map((row) => (
                <ResultRow
                  key={row.id}
                  row={row}
                  query=""
                  onChoose={choose}
                  trailing={
                    <button
                      type="button"
                      className="t2-ps-icon-btn"
                      aria-label={tr("احذف من الأخيرة")}
                      onClick={() => {
                        forgetRecent(store, userId, row.at);
                        setStoreVersion((version) => version + 1);
                      }}
                    >
                      <Icon name="close" />
                    </button>
                  }
                />
              ))}
            </Section>
          ) : (
            <p className="t2-ds-hint">{tr("اكتب اسم مكانٍ أو شارعٍ أو حيّ — وتصلك الطلباتُ في طريقك إليه")}</p>
          )
        ) : status === "loading" && rows.length === 0 ? (
          <div className="t2-ds-list" aria-busy="true" aria-label={tr("جارٍ البحث")}>
            {[0, 1, 2, 3].map((index) => (
              <div key={index} className="t2-ps-skeleton">
                <span className="dot" />
                <span className="lines">
                  <span />
                  <span />
                </span>
              </div>
            ))}
          </div>
        ) : status === "offline" ? (
          <div className="t2-ds-state">
            <Icon name="cloud_off" />
            <p className="title">{tr("لا اتصال بالإنترنت")}</p>
            <p className="hint">{tr("تحقّق من الاتصال ثمّ أعد المحاولة — أو حدّد المكان على الخريطة")}</p>
            <button type="button" className="t2-button t2-ps-retry" onClick={() => setRetry((count) => count + 1)}>
              <Icon name="refresh" />
              <span>{tr("أعد المحاولة")}</span>
            </button>
          </div>
        ) : status === "empty" ? (
          <div className="t2-ds-state">
            <Icon name="search" />
            <p className="title">{tr("لم نجد هذا المكان")}</p>
            <p className="hint">{tr("تأكّد من الإملاء أو جرّب اسماً أقصر — أو حدّد المكان على الخريطة")}</p>
          </div>
        ) : (
          <div className={status === "loading" ? "t2-ds-list t2-ps-stale" : "t2-ds-list"}>
            {rows.map((row) => (
              <ResultRow key={row.id} row={row} query={query} onChoose={choose} />
            ))}
            {credit ? (
              <p className="t2-ps-credit" dir="ltr">
                {credit}
              </p>
            ) : null}
          </div>
        )}
      </div>

      <button type="button" className="t2-ps-map" onClick={onPickOnMap}>
        <Icon name="map" />
        <span className="t2-ds-map-label">{tr("حدّد على الخريطة")}</span>
        <Icon name="chevron_left" className="t2-chev" />
      </button>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <div className="t2-ds-group">{title}</div>
      <div className="t2-ds-list">{children}</div>
    </section>
  );
}

function ResultRow({
  row,
  query,
  onChoose,
  trailing,
}: {
  row: Row;
  query: string;
  onChoose: (row: Row) => void;
  trailing?: ReactNode;
}) {
  const range = query ? highlightRange(row.name, query) : null;
  const distance = distanceLabel(row.distance);
  return (
    <div className="t2-ps-row">
      <button type="button" className="t2-ps-pick" onClick={() => onChoose(row)}>
        <span className="t2-ps-mark">
          <Icon name={categoryIcon(row.category)} />
        </span>
        <span className="t2-ds-main">
          <span className="t2-ds-title">
            {range ? (
              <>
                {row.name.slice(0, range[0])}
                <mark>{row.name.slice(range[0], range[1])}</mark>
                {row.name.slice(range[1])}
              </>
            ) : (
              row.name
            )}
          </span>
          {row.address ? <span className="t2-ds-sub">{row.address}</span> : null}
        </span>
        {distance ? <span className="t2-ps-distance">{distance}</span> : null}
      </button>
      {trailing}
    </div>
  );
}
