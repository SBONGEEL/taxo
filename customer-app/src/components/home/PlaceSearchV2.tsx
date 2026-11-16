/** **قائمةُ البحث عن الأماكن الجديدة** (أمرُ المالك ٢٠٢٦-١١-١٦ الثالث، SPEC §١٠٤) — خلف `places_search_v2`، **ومطفأً
 *  `DestinationSearch` القديمةُ كما هي حرفاً**. والقائمةُ نفسُها لكلِّ موضعٍ يُسأل فيه عن مكان: الوجهة، والانطلاق، والمحطات،
 *  والمشوار الثابت — **وما يتغيّر بينها العنوانُ والصفوفُ البديلة** («موقعي الحالي» للانطلاق، و«بلا وجهة» للساعات).
 *
 *  **ولا تمسّ النقطةَ ولا الأجرة**: ما يُختار إحداثيّاتُ النتيجة كما وصلت من `/places/search`، والمسارُ يُسعَّر في الخلفيّة كما كان.
 *  **والمحفوظُ والأخيرُ لكلِّ مستخدمٍ وحدَه**: المحفوظةُ من `/me/places` (بابُ الراكب)، وآخرُ ما اختاره وما أخفاه في جهازه بمفتاحٍ
 *  يحمل معرّفَه (`lib/place-search.ts`).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { CountryCode, Coordinates, SavedPlace } from "@/api/types";
import { createPlace, deletePlace, placeSearch, searchMapPlaces } from "@/api/endpoints";
import { mergeSearch, searchPlaces, type Place } from "@/lib/geocode";
import { useMapPlaces } from "@/lib/map-labels";
import { useFeature } from "@/lib/config";
import { listen, VOICE_FLAG, voiceAvailable } from "@/lib/voice-input";
import { usePlaces } from "@/lib/places";
import { useSession } from "@/lib/session";
import {
  browserStore,
  categoryIcon,
  distanceLabel,
  foldText,
  forgetRecent,
  hiddenRecents,
  highlightRange,
  latestOnly,
  MIN_QUERY,
  pointKey,
  recentPicks,
  rememberPick,
  samePoint,
  SEARCH_DEBOUNCE_MS,
} from "@/lib/place-search";
import { DrawerT2 } from "@/screens/t2/DrawerT2";
import { BlankT2 } from "@/screens/t2/KitT2";
import { Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/request.css";
import { tr } from "@/lib/i18n";

export interface PlaceSearchProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  token: string | null;
  country: CountryCode;
  near: Coordinates | null;
  onPick: (place: Place) => void;
  onPickOnMap?: () => void;
  onSkip?: () => void;
  title?: string;
  onHere?: () => void;
  airports?: Place[];
}

interface Row extends Place {
  category: string | null;
  distance: number | null;
}

type Status = "idle" | "loading" | "done" | "empty" | "offline";

/** المسافةُ بخطٍّ مستقيم (هافرساين) — **للعرض وحدَه** بجانب ما لا يحمل مسافتَه من الخادم */
function metersBetween(a: Coordinates, b: Coordinates): number {
  const r = 6_371_000;
  const p1 = (a.lat * Math.PI) / 180;
  const p2 = (b.lat * Math.PI) / 180;
  const dp = p2 - p1;
  const dl = ((b.lng - a.lng) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

/** **الورقةُ فوق لوحة المفاتيح لا تحتها** (§١٠٤/٩) — ارتفاعُ ما يُرى من الشاشة وما تغطّيه اللوحة، من `visualViewport` */
function useVisibleViewport(active: boolean): { height: number; covered: number } | null {
  const [size, setSize] = useState<{ height: number; covered: number } | null>(null);
  useEffect(() => {
    const viewport = typeof window === "undefined" ? undefined : window.visualViewport;
    if (!active || !viewport) {
      setSize(null);
      return;
    }
    const update = () =>
      setSize({
        height: viewport.height,
        covered: Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop),
      });
    update();
    viewport.addEventListener("resize", update);
    viewport.addEventListener("scroll", update);
    return () => {
      viewport.removeEventListener("resize", update);
      viewport.removeEventListener("scroll", update);
    };
  }, [active]);
  return size;
}

export function PlaceSearchV2({
  open,
  onOpenChange,
  token,
  country,
  near,
  onPick,
  onPickOnMap,
  onSkip,
  title = tr("إلى أين؟"),
  onHere,
  airports,
}: PlaceSearchProps) {
  const { user } = useSession();
  const { places, recents, refresh } = usePlaces();
  const { labels, places: spots } = useMapPlaces();
  const store = useMemo(() => browserStore(), []);
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [credit, setCredit] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [storeVersion, setStoreVersion] = useState(0);
  const [savingAs, setSavingAs] = useState<"home" | "work" | null>(null);
  const [busyStar, setBusyStar] = useState<string | null>(null);
  const order = useRef(latestOnly());
  const input = useRef<HTMLInputElement>(null);
  const typing = query.trim().length >= MIN_QUERY;
  const viewport = useVisibleViewport(open);

  const voiceOn = useFeature(country, VOICE_FLAG) && voiceAvailable();
  const [listening, setListening] = useState(false);
  const speak = async () => {
    setListening(true);
    try {
      const text = await listen(country, title);
      if (text) setQuery(text);
    } catch {
      // لا خدمةَ تعرّفٍ في الهاتف — الكتابةُ باقية
    } finally {
      setListening(false);
    }
  };

  useEffect(() => {
    if (!open) {
      setQuery("");
      setRows([]);
      setStatus("idle");
      setSavingAs(null);
    }
  }, [open]);

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
    // **النتائجُ السابقةُ تبقى ظاهرةً حتى يصل الجديد** (§١٠٤/٤) — الهيكلُ للأوّل وحدَه
    setStatus((current) => (current === "done" ? "done" : "loading"));
    const timer = window.setTimeout(async () => {
      let failed = false;
      const answer = await placeSearch(text, near ?? undefined, controller.signal).catch(() => {
        failed = true;
        return null;
      });
      if (controller.signal.aborted || !order.current.isCurrent(ticket)) return;
      if (answer) {
        const found: Row[] = answer.items
          .filter((item) => item.lat !== null && item.lng !== null)
          .map((item) => ({
            id: item.id,
            name: item.name,
            address: item.address,
            coordinates: { lat: item.lat as number, lng: item.lng as number },
            category: item.category ?? null,
            distance: item.distance_m,
          }));
        setRows(found);
        setCredit(answer.attribution === "open" ? answer.attribution_text : null);
        setStatus(found.length ? "done" : "empty");
        return;
      }
      // **فشلُ الخلفيّة يعيد الطريقَ القديمَ كما كان** (أماكنُ السوق + Mapbox)، وإن فشلا معاً فهو انقطاع
      const [own, provider] = await Promise.allSettled([
        labels ? searchMapPlaces(text, near ?? undefined, controller.signal) : Promise.resolve([]),
        token ? searchPlaces(token, text, country, near ?? undefined, controller.signal) : Promise.resolve([]),
      ]);
      if (controller.signal.aborted || !order.current.isCurrent(ticket)) return;
      const merged = mergeSearch(
        own.status === "fulfilled" ? own.value : [],
        provider.status === "fulfilled" ? provider.value : [],
        near,
      ).map((place) => ({ ...place, category: null, distance: near ? metersBetween(near, place.coordinates) : null }));
      setCredit(null);
      setRows(merged);
      const offline =
        (failed && typeof navigator !== "undefined" && navigator.onLine === false) ||
        (failed && own.status === "rejected" && provider.status === "rejected");
      setStatus(merged.length ? "done" : offline ? "offline" : "empty");
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [query, token, country, near, labels, retry]);

  const home = places.find((place) => place.icon === "home") ?? null;
  const work = places.find((place) => place.icon === "work") ?? null;
  const others = places.filter((place) => place !== home && place !== work);

  // **«الأخيرة»**: ما اختاره من البحث في هذا الجهاز، ثمّ وجهاتُ رحلاته — بلا المحفوظ ولا ما أخفاه ولا المكرَّر
  const lately = useMemo(() => {
    void storeVersion;
    const hidden = new Set(hiddenRecents(store, user?.id));
    const out: Row[] = [];
    const seen: Coordinates[] = places.map((place) => ({ lat: place.lat, lng: place.lng }));
    const add = (row: Row) => {
      if (hidden.has(pointKey(row.coordinates)) || seen.some((point) => samePoint(point, row.coordinates))) return;
      seen.push(row.coordinates);
      out.push(row);
    };
    for (const pick of recentPicks(store, user?.id)) {
      add({
        id: `pick:${pointKey(pick)}`, name: pick.name, address: pick.address, coordinates: { lat: pick.lat, lng: pick.lng },
        category: "recent", distance: near ? metersBetween(near, pick) : null,
      });
    }
    for (const recent of recents) {
      add({
        id: `recent:${recent.key}`, name: recent.address, address: "", coordinates: recent.point,
        category: "recent", distance: near ? metersBetween(near, recent.point) : null,
      });
    }
    return out.slice(0, 5);
  }, [store, user?.id, places, recents, near, storeVersion]);

  // **أماكنُ مشهورةٌ قريبة** (§١٠٤/١٠) — معالمُ السوق التي يحرّرها المالكُ في اللوحة، الأقربُ أوّلاً
  const popular = useMemo<Row[]>(() => {
    if (!labels || !near) return [];
    return spots
      .map((spot) => ({
        id: `spot:${spot.id}`, name: spot.name_ar, address: "", coordinates: { lat: spot.lat, lng: spot.lng },
        category: spot.category, distance: metersBetween(near, spot),
      }))
      .filter((row) => row.distance < 15_000)
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 5);
  }, [labels, spots, near]);

  // **النجمةُ لمكانٍ باسمه لا لنقطته**: محلٌّ داخل «مكة مول» على نقطته نفسِها لا يُضاء بحفظ المول، ولا تمحو نجمتُه
  // «البيت» إن وقع البيتُ على النقطة — البيتُ والعملُ يُغيَّران من خانتهما وحدَها
  const savedAt = (row: Row): SavedPlace | undefined =>
    places.find(
      (place) =>
        place.icon !== "home" &&
        place.icon !== "work" &&
        samePoint({ lat: place.lat, lng: place.lng }, row.coordinates) &&
        foldText(place.label) === foldText(row.name.slice(0, 60)),
    );

  async function choose(row: Row, remember: boolean) {
    if (savingAs) {
      // **«أضف البيت/العمل»**: الصفُّ المختارُ يُحفظ باسمه لهذا المستخدم، والقائمةُ تبقى مفتوحةً للوجهة
      try {
        await createPlace({
          label: savingAs === "home" ? tr("البيت") : tr("العمل"),
          lat: row.coordinates.lat, lng: row.coordinates.lng, address: row.address || row.name, icon: savingAs,
        });
        await refresh();
      } finally {
        setSavingAs(null);
        setQuery("");
      }
      return;
    }
    if (remember) {
      rememberPick(store, user?.id, {
        name: row.name, address: row.address, lat: row.coordinates.lat, lng: row.coordinates.lng, category: row.category,
      });
    }
    onPick({ id: row.id, name: row.name, address: row.address, coordinates: row.coordinates });
    onOpenChange(false);
  }

  async function toggleStar(row: Row) {
    if (busyStar) return;
    setBusyStar(row.id);
    try {
      const existing = savedAt(row);
      if (existing) await deletePlace(existing.id);
      else
        await createPlace({
          label: row.name.slice(0, 60), lat: row.coordinates.lat, lng: row.coordinates.lng,
          address: row.address || null, icon: "star",
        });
      await refresh();
    } catch {
      // الحفظُ تحسينٌ لا شرط — النتيجةُ تبقى قابلةً للاختيار
    } finally {
      setBusyStar(null);
    }
  }

  const savedRow = (place: SavedPlace): Row => ({
    id: `place:${place.id}`, name: place.label, address: place.address ?? "", coordinates: { lat: place.lat, lng: place.lng },
    category: "saved", distance: near ? metersBetween(near, { lat: place.lat, lng: place.lng }) : null,
  });

  const mapRow = onPickOnMap ? (
    <button
      type="button"
      className="t2-ps-map"
      onClick={() => {
        onOpenChange(false);
        onPickOnMap();
      }}
    >
      <Icon name="map" />
      <span className="t2-dest-pin-label">{tr("حدّد على الخريطة")}</span>
      <Icon name="chevron_left" className="t2-chev" />
    </button>
  ) : null;

  return (
    <DrawerT2
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      style={viewport ? { bottom: viewport.covered, maxHeight: Math.max(280, viewport.height - 24) } : undefined}
      className="t2-ps"
    >
      <div className="t2-ps-head">
        <label className="t2-dest-field">
          <Icon name="search" />
          <input
            ref={input}
            autoFocus
            enterKeyHint="search"
            placeholder={savingAs ? tr("ابحث عن المكان لحفظه") : tr("ابحث عن مكان أو شارع أو حي")}
            aria-label={tr("ابحث عن مكان أو شارع أو حي")}
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
          {voiceOn ? (
            <button
              type="button"
              className={listening ? "t2-ps-icon-btn on" : "t2-ps-icon-btn"}
              aria-label={listening ? tr("يستمع…") : tr("قل وجهتك بصوتك")}
              onClick={() => void speak()}
              disabled={listening}
            >
              <Icon name="mic" fill={listening} />
            </button>
          ) : null}
        </label>
        {savingAs ? (
          <p className="t2-ps-saving">
            <span>{savingAs === "home" ? tr("اختر مكانَ البيت من النتائج") : tr("اختر مكانَ العمل من النتائج")}</span>
            <button type="button" onClick={() => setSavingAs(null)}>
              {tr("إلغاء")}
            </button>
          </p>
        ) : null}
      </div>

      {!typing ? (
        <>
          {onHere || onSkip ? (
            <div className="t2-list t2-ps-section">
              {onHere ? (
                <button
                  type="button"
                  className="t2-dest-row"
                  onClick={() => {
                    onOpenChange(false);
                    onHere();
                  }}
                >
                  <Icon name="my_location" className="mark" />
                  <span className="t2-dest-main">
                    <span className="t2-dest-title">{tr("موقعي الحالي")}</span>
                  </span>
                </button>
              ) : null}
              {onSkip ? (
                <button
                  type="button"
                  className="t2-dest-row"
                  onClick={() => {
                    onOpenChange(false);
                    onSkip();
                  }}
                >
                  <Icon name="timer" className="mark" />
                  <span className="t2-dest-main">
                    <span className="t2-dest-title">{tr("بلا وجهة — تقولها للكبتن في الطريق")}</span>
                  </span>
                </button>
              ) : null}
            </div>
          ) : null}

          {/* **«البيت» و«العمل»** (§١٠٤/١٠) — مصدرٌ واحدٌ مع الأماكن المحفوظة (`/me/places` بأيقونتَي home/work)، وزرُّ إضافةٍ لما لم يُحفظ */}
          {!savingAs ? (
            <div className="t2-ps-quick">
              {[
                { kind: "home" as const, place: home, label: tr("البيت"), add: tr("أضف البيت") },
                { kind: "work" as const, place: work, label: tr("العمل"), add: tr("أضف العمل") },
              ].map(({ kind, place, label, add }) =>
                place ? (
                  <button key={kind} type="button" className="t2-ps-chip" onClick={() => void choose(savedRow(place), false)}>
                    <Icon name={kind} fill />
                    <span>{label}</span>
                  </button>
                ) : (
                  <button
                    key={kind}
                    type="button"
                    className="t2-ps-chip add"
                    onClick={() => {
                      setSavingAs(kind);
                      input.current?.focus();
                    }}
                  >
                    <Icon name="add" />
                    <span>{add}</span>
                  </button>
                ),
              )}
            </div>
          ) : null}

          {airports && airports.length > 0 ? (
            <Section title={tr("المطارات")}>
              {airports.map((airport) => (
                <ResultRow
                  key={airport.id}
                  row={{ ...airport, category: "airport", distance: near ? metersBetween(near, airport.coordinates) : null }}
                  query=""
                  onChoose={(row) => void choose(row, true)}
                />
              ))}
            </Section>
          ) : null}

          {others.length > 0 ? (
            <Section title={tr("أماكن محفوظة")}>
              {others.map((place) => (
                <ResultRow key={place.id} row={savedRow(place)} query="" onChoose={(row) => void choose(row, false)} />
              ))}
            </Section>
          ) : null}

          {lately.length > 0 ? (
            <Section title={tr("عمليات البحث الأخيرة")}>
              {lately.map((row) => (
                <ResultRow
                  key={row.id}
                  row={row}
                  query=""
                  onChoose={(picked) => void choose(picked, true)}
                  trailing={
                    <button
                      type="button"
                      className="t2-ps-icon-btn"
                      aria-label={tr("احذف من الأخيرة")}
                      onClick={() => {
                        forgetRecent(store, user?.id, row.coordinates);
                        setStoreVersion((version) => version + 1);
                      }}
                    >
                      <Icon name="close" />
                    </button>
                  }
                />
              ))}
            </Section>
          ) : null}

          {popular.length > 0 ? (
            <Section title={tr("أماكن مشهورة قريبة")}>
              {popular.map((row) => (
                <ResultRow key={row.id} row={row} query="" onChoose={(picked) => void choose(picked, true)} />
              ))}
            </Section>
          ) : null}
        </>
      ) : status === "loading" && rows.length === 0 ? (
        <div className="t2-list t2-ps-section" aria-busy="true" aria-label={tr("جارٍ البحث")}>
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
        <div className="t2-ps-state">
          <BlankT2 icon="cloud_off" title={tr("لا اتصال بالإنترنت")} hint={tr("تحقّق من الاتصال ثمّ أعد المحاولة — أو حدّد المكان على الخريطة")} />
          <button type="button" className="t2-button primary t2-ps-retry" onClick={() => setRetry((count) => count + 1)}>
            <Icon name="refresh" />
            <span>{tr("أعد المحاولة")}</span>
          </button>
        </div>
      ) : status === "empty" ? (
        <div className="t2-ps-state">
          <BlankT2
            icon="search"
            title={tr("لم نجد هذا المكان")}
            hint={tr("تأكّد من الإملاء أو جرّب اسماً أقصر أو جزءاً من الاسم — أو حدّد المكان على الخريطة")}
          />
        </div>
      ) : (
        <div className={status === "loading" ? "t2-list t2-ps-section t2-ps-stale" : "t2-list t2-ps-section"}>
          {rows.map((row) => {
            const saved = Boolean(savedAt(row));
            return (
              <ResultRow
                key={row.id}
                row={row}
                query={query}
                onChoose={(picked) => void choose(picked, row.category !== "saved")}
                trailing={
                  savingAs || row.category === "saved" ? null : (
                    <button
                      type="button"
                      className={saved ? "t2-ps-icon-btn star on" : "t2-ps-icon-btn star"}
                      aria-label={saved ? tr("أزل من المحفوظة") : tr("احفظ هذا المكان")}
                      aria-pressed={saved}
                      disabled={busyStar === row.id}
                      onClick={() => void toggleStar(row)}
                    >
                      <Icon name="star" fill={saved} />
                    </button>
                  )
                }
              />
            );
          })}
          {/* **شرطُ رخصة ODbL** — نسبةُ OpenStreetMap وOverture تحت ما جاء منهما */}
          {credit ? (
            <p className="t2-ps-credit" dir="ltr">
              {credit}
            </p>
          ) : null}
        </div>
      )}

      {/* **«حدّد على الخريطة» في آخر القائمة دائماً** (§١٠٤/١٢) — في كلِّ حال: قبل الكتابة، ومع النتائج، وبلا نتيجة، وبلا شبكة */}
      {savingAs ? null : mapRow}
    </DrawerT2>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <div className="t2-group t2-dest-group">{title}</div>
      <div className="t2-list">{children}</div>
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
          <Icon name={categoryIcon(row.category)} fill={row.category === "saved"} />
        </span>
        <span className="t2-dest-main">
          <span className="t2-dest-title">
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
          {row.address ? <span className="t2-dest-sub">{row.address}</span> : null}
        </span>
        {distance ? <span className="t2-ps-distance">{distance}</span> : null}
      </button>
      {trailing}
    </div>
  );
}
