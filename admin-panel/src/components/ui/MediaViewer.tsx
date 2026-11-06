/** **عارضُ الوثائق والصور** — ملءَ الشاشة على خلفيّةٍ داكنة (أمرُ المالك ٢٠٢٦-١١-٠٦، البند ٠).
 *
 * كانت الوثيقةُ تُعرض صورةً بارتفاع ١٧٠ داخل الدرج، والإيصالُ في حوارٍ بعرض ٩٨٠، والـPDF رابطاً إلى تبويبٍ آخر —
 * **والمشرفُ يقرأ رقماً صغيراً على رخصةٍ مصوَّرةٍ مائلة**. فصار لكلِّ ملفٍّ مرفوعٍ عارضٌ واحد:
 * تكبيرٌ (أزرار، عجلة، نقرٌ مزدوج، قرصٌ بإصبعين) وسحبٌ، وتدويرُ 90°، والتالي والسابق داخل المجموعة نفسِها
 * بعدّادٍ «2 من 5»، وفتحُ الأصل في تبويبٍ وتنزيلُه، والـPDF داخله. ويُغلق بـ✕ وبـEsc وبالنقر خارج الملف.
 *
 * **والأمانُ ليس طبقةً هنا بل ما تحتها**: الملفُّ يُجلب بمفتاح الجلسة إلى `blob:` (لا عنوانَ عامّاً يُنسخ)،
 * والخلفيّةُ تردّ `private, no-store` فلا يُخزَّن في وسيطٍ ولا في ذاكرة المتصفّح على جهازٍ مشترك،
 * **ومن فتح يُحرِّر**: `useMediaCache` يُلغي كلَّ `blob:` حين تُغلق الشاشةُ التي فتحته.
 *
 * **والأرقامُ لاتينيّة** («2 من 5») كبقيّة اللوحة — قاعدةُ `check:digits`.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
  ReactNode,
  WheelEvent as ReactWheelEvent,
} from "react";
import { createPortal } from "react-dom";

import { Icon } from "@/taxo2";

export type LoadedMedia = { url: string; type: string };

export type MediaItem = {
  /** مفتاحٌ ثابتٌ للملفّ — به يُخبَّأ فلا يُجلب مرّتين بين المصغَّرة والعارض. */
  key: string;
  label: string;
  load: () => Promise<LoadedMedia>;
  /** ما يُرسم تحت الملفّ في العارض — حقلُ تاريخ الانتهاء للوثيقة: يُقرأ الرقمُ ويُكتب في نظرةٍ واحدة. */
  extra?: ReactNode;
};

export type MediaCache = { get: (item: MediaItem) => Promise<LoadedMedia> };

/** خبيئةُ ملفّاتٍ **يملكها من فتحها**: تُحرِّر كلَّ `blob:` حين تُغلق الشاشة أو الدرج. */
export function useMediaCache(): MediaCache {
  const store = useRef<Map<string, Promise<LoadedMedia>>>(new Map());
  useEffect(() => {
    const map = store.current;
    return () => {
      map.forEach((pending) => {
        pending.then((media) => URL.revokeObjectURL(media.url)).catch(() => undefined);
      });
      map.clear();
    };
  }, []);
  return useMemo(
    () => ({
      get(item: MediaItem) {
        const map = store.current;
        let pending = map.get(item.key);
        if (!pending) {
          pending = item.load();
          map.set(item.key, pending);
          // **فشلٌ لا يُخبَّأ**: ضغطةٌ ثانيةٌ تحاول من جديد بدل أن تعيد الخطأ نفسَه
          pending.catch(() => map.delete(item.key));
        }
        return pending;
      },
    }),
    [],
  );
}

type Loaded = { state: "loading" } | { state: "ready"; media: LoadedMedia } | { state: "failed"; message: string };

/** **والحالُ موسومةٌ بمفتاحها**: بعد «التالي» يبقى حالُ الملفّ السابق رسمةً واحدةً قبل أن يبدأ الجلب —
 *  وحالٌ لا يطابق مفتاحُه البندَ الحاليَّ «جارٍ» لا «جاهز»، وإلا عُدَّت الوثيقةُ التاليةُ مرئيّةً بصورةِ سابقتها. */
function useLoaded(cache: MediaCache, item: MediaItem | undefined): Loaded {
  const [tagged, setTagged] = useState<{ key: string; loaded: Loaded } | null>(null);
  useEffect(() => {
    if (!item) return;
    let alive = true;
    const key = item.key;
    const setLoaded = (loaded: Loaded) => alive && setTagged({ key, loaded });
    cache
      .get(item)
      .then((media) => setLoaded({ state: "ready", media }))
      .catch((caught: unknown) =>
        setLoaded({ state: "failed", message: caught instanceof Error ? caught.message : "تعذّر فتح الملف" }),
      );
    return () => {
      alive = false;
    };
    // المفتاحُ هو الهويّة — كائنُ البند يُبنى من جديد في كلِّ رسم
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cache, item?.key]);
  return tagged && item && tagged.key === item.key ? tagged.loaded : { state: "loading" };
}

const isPdf = (media: LoadedMedia) => media.type === "application/pdf";

/** مصغَّرةٌ تُفتح بنقرة — صورةٌ أو بطاقةُ PDF. تجلب ملفَّها من الخبيئة نفسِها التي يقرأ منها العارض. */
export function MediaThumb({
  cache,
  item,
  onOpen,
  className,
}: {
  cache: MediaCache;
  item: MediaItem;
  onOpen: () => void;
  className?: string;
}) {
  const loaded = useLoaded(cache, item);
  return (
    <button
      type="button"
      className={["ad-mv-thumb", className].filter(Boolean).join(" ")}
      onClick={onOpen}
      aria-label={`اعرض ${item.label} ملءَ الشاشة`}
    >
      {loaded.state === "ready" ? (
        isPdf(loaded.media) ? (
          <span className="ad-mv-thumb-pdf">
            <Icon name="picture_as_pdf" />
            PDF
          </span>
        ) : (
          <img src={loaded.media.url} alt={item.label} />
        )
      ) : loaded.state === "failed" ? (
        <span className="ad-mv-thumb-pdf">
          <Icon name="hide_image" />
        </span>
      ) : (
        <span className="ad-mv-thumb-pdf">
          <Icon name="image" />
        </span>
      )}
      <span className="ad-mv-thumb-zoom">
        <Icon name="zoom_in" />
      </span>
    </button>
  );
}

const MIN_SCALE = 1;
const MAX_SCALE = 8;
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

const EXTENSION: Record<string, string> = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/webp": ".webp",
  "application/pdf": ".pdf",
};

type View = { scale: number; x: number; y: number; turn: number };
const RESET: View = { scale: 1, x: 0, y: 0, turn: 0 };

export function MediaViewer({
  cache,
  items,
  index,
  onIndex,
  onClose,
  onShown,
}: {
  cache: MediaCache;
  items: MediaItem[];
  index: number;
  onIndex: (next: number) => void;
  onClose: () => void;
  /** **يقع حين يصل الملفُّ مفتوحاً لا حين يُضغط** — نداءٌ فشل ليس معاينة (الاعتمادُ الجماعيُّ يقرؤه). */
  onShown?: (key: string) => void;
}) {
  const item = items[index];
  const loaded = useLoaded(cache, item);
  const [view, setView] = useState<View>(RESET);
  const [stage, setStage] = useState({ width: 0, height: 0 });
  const stageRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{ distance: number; scale: number; startX: number; startY: number; moved: boolean } | null>(null);
  const justDragged = useRef(false);
  // **أين بدأت الضغطة** — الالتقاطُ يجعل هدفَ النقرة المسرحَ أيّاً كان ما ضُغط، فيُقرأ المنشأُ لا الهدف
  const pressedBackdrop = useRef(false);
  const count = items.length;

  const go = useCallback(
    (step: number) => {
      if (count < 2) return;
      onIndex((index + step + count) % count);
    },
    [count, index, onIndex],
  );

  useEffect(() => {
    if (loaded.state === "ready" && item) onShown?.(item.key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.state, item?.key]);

  // كلُّ ملفٍّ يبدأ بحجمه واستقامته — تكبيرُ رخصةٍ لا يُورَث إلى صورةِ السيّارة بعدها
  useEffect(() => setView(RESET), [index]);

  // **يُغلق بـEsc وحدَه لا ما تحته معه**: الالتقاطُ على النافذة يسبق مستمعَ الدرج فيُوقَف عنده
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement;
      if (event.key === "Escape") {
        event.stopImmediatePropagation();
        event.preventDefault();
        onClose();
        return;
      }
      if (typing) return;
      // **الاتّجاهُ عربيّ**: التالي إلى اليسار
      if (event.key === "ArrowLeft") go(1);
      else if (event.key === "ArrowRight") go(-1);
      else if (event.key === "+" || event.key === "=") zoomBy(1.4);
      else if (event.key === "-") zoomBy(1 / 1.4);
      else if (event.key === "r" || event.key === "R") rotate();
      else if (event.key === "0") setView(RESET);
      else return;
      event.stopImmediatePropagation();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [go, onClose]);

  // الصفحةُ تحته لا تتمرّر، والتركيزُ على زرّ الإغلاق ثم يعود حيث كان
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
      before?.focus?.();
    };
  }, []);

  useEffect(() => {
    const node = stageRef.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      setStage({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  /** تكبيرٌ حول نقطة — **ما تحت المؤشّر يبقى تحته**، وإلا قفزت الورقةُ بعيداً عمّا يُقرأ. */
  function zoomAt(factor: number, pointX = 0, pointY = 0) {
    setView((current) => {
      const scale = clamp(current.scale * factor, MIN_SCALE, MAX_SCALE);
      if (scale === MIN_SCALE) return { ...current, scale, x: 0, y: 0 };
      const ratio = scale / current.scale;
      return { ...current, scale, x: pointX - (pointX - current.x) * ratio, y: pointY - (pointY - current.y) * ratio };
    });
  }
  function zoomBy(factor: number) {
    zoomAt(factor);
  }
  function rotate() {
    setView((current) => ({ ...current, turn: (current.turn + 90) % 360, x: 0, y: 0 }));
  }

  /** موضعُ نقطةٍ نسبةً إلى مركز المسرح — مركزُ التحويل */
  function local(clientX: number, clientY: number) {
    const box = stageRef.current?.getBoundingClientRect();
    if (!box) return { x: 0, y: 0 };
    return { x: clientX - box.left - box.width / 2, y: clientY - box.top - box.height / 2 };
  }

  const ready = loaded.state === "ready" ? loaded.media : null;
  const pdf = ready ? isPdf(ready) : false;
  const canTransform = Boolean(ready) && !pdf;

  function onWheel(event: ReactWheelEvent<HTMLDivElement>) {
    if (!canTransform) return;
    const point = local(event.clientX, event.clientY);
    zoomAt(event.deltaY < 0 ? 1.15 : 1 / 1.15, point.x, point.y);
  }

  function onPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    pressedBackdrop.current = event.target === event.currentTarget;
    if (!canTransform) return;
    // **ضغطةٌ على زرٍّ ليست إيماءة** (قِيس ٢٠٢٦-١١-٠٦): الالتقاطُ على المسرح يحوّل نقرةَ «التالي» إلى نقرةٍ على
    // المسرح نفسِه — فتُقرأ «نقرةً خارج الملف» ويُغلق العارض، ثم تصيب النقرةُ التاليةُ ظلَّ الدرج فيُغلق هو أيضاً
    if ((event.target as Element).closest("button, a, iframe")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const points = [...pointers.current.values()];
    gesture.current = {
      distance: points.length === 2 ? Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y) : 0,
      scale: view.scale,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
  }

  function onPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const previous = pointers.current.get(event.pointerId);
    if (!previous || !gesture.current) return;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const points = [...pointers.current.values()];
    if (Math.abs(event.clientX - gesture.current.startX) + Math.abs(event.clientY - gesture.current.startY) > 6) {
      gesture.current.moved = true;
    }
    if (points.length === 2 && gesture.current.distance > 0) {
      // **قرصٌ بإصبعين** حول منتصفهما
      const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      const target = clamp(gesture.current.scale * (distance / gesture.current.distance), MIN_SCALE, MAX_SCALE);
      const middle = local((points[0].x + points[1].x) / 2, (points[0].y + points[1].y) / 2);
      zoomAt(target / view.scale, middle.x, middle.y);
      return;
    }
    if (points.length === 1 && view.scale > 1) {
      setView((current) => ({ ...current, x: current.x + event.clientX - previous.x, y: current.y + event.clientY - previous.y }));
    }
  }

  function onPointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    const start = gesture.current;
    justDragged.current = Boolean(start?.moved);
    pointers.current.delete(event.pointerId);
    if (pointers.current.size > 0) {
      // بقي إصبعٌ بعد القرص: يبدأ منه سحبٌ جديد لا قفزة
      const [rest] = [...pointers.current.values()];
      gesture.current = { distance: 0, scale: view.scale, startX: rest.x, startY: rest.y, moved: true };
      return;
    }
    gesture.current = null;
    // **سحبٌ أفقيٌّ على الهاتف بلا تكبير = التالي/السابق** — والعربيّةُ تقلب الاتّجاه
    if (start && view.scale === 1 && event.pointerType !== "mouse") {
      const dx = event.clientX - start.startX;
      const dy = event.clientY - start.startY;
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) go(dx < 0 ? 1 : -1);
    }
  }

  function onDoubleClick(event: ReactMouseEvent<HTMLDivElement>) {
    if (!canTransform) return;
    const point = local(event.clientX, event.clientY);
    if (view.scale > 1) setView((current) => ({ ...current, scale: 1, x: 0, y: 0 }));
    else zoomAt(2.5, point.x, point.y);
  }

  // **ورقةٌ مدوَّرةٌ ربعاً تُقاس بعرضها لا بطولها**: حدودُ الملاءمة تتبادل
  const sideways = view.turn % 180 !== 0;
  const fit = {
    maxWidth: `${Math.max(0, sideways ? stage.height : stage.width)}px`,
    maxHeight: `${Math.max(0, sideways ? stage.width : stage.height)}px`,
  };
  const pdfInline = typeof navigator !== "undefined" && (navigator as Navigator & { pdfViewerEnabled?: boolean }).pdfViewerEnabled !== false;
  const fileName = item ? `${item.label}${ready ? EXTENSION[ready.type] ?? "" : ""}` : "";

  return createPortal(
    <div className="ad-mv" role="dialog" aria-modal="true" aria-label={item?.label ?? "عارض الملفات"}
      onClick={(event) => {
        // **البوّابةُ تنقل الرسمَ لا شجرةَ الأحداث**: نقرةٌ هنا تصعد في React إلى الحوار أو الدرج تحته فتغلقه معه
        event.stopPropagation();
        onClose();
      }}
    >
      <div className="ad-mv-bar" onClick={(event) => event.stopPropagation()}>
        <button ref={closeRef} type="button" className="ad-mv-btn" onClick={onClose} aria-label="إغلاق">
          <Icon name="close" />
        </button>
        <div className="ad-mv-title">
          <span className="ad-mv-name">{item?.label}</span>
          {count > 1 ? (
            <span className="ad-mv-count">
              {index + 1} من {count}
            </span>
          ) : null}
        </div>
        <div className="ad-mv-tools">
          {canTransform ? (
            <>
              <button type="button" className="ad-mv-btn" onClick={() => zoomBy(1 / 1.4)} disabled={view.scale <= MIN_SCALE} aria-label="تصغير">
                <Icon name="zoom_out" />
              </button>
              <button type="button" className="ad-mv-pct" onClick={() => setView(RESET)} aria-label="الحجم الأصلي">
                {Math.round(view.scale * 100)}%
              </button>
              <button type="button" className="ad-mv-btn" onClick={() => zoomBy(1.4)} disabled={view.scale >= MAX_SCALE} aria-label="تكبير">
                <Icon name="zoom_in" />
              </button>
              <button type="button" className="ad-mv-btn" onClick={rotate} aria-label="تدوير 90 درجة">
                <Icon name="rotate_right" />
              </button>
            </>
          ) : null}
          {ready ? (
            <>
              <a className="ad-mv-btn" href={ready.url} target="_blank" rel="noopener" aria-label="افتح الأصل في تبويبٍ جديد" title="افتح الأصل في تبويبٍ جديد">
                <Icon name="open_in_new" />
              </a>
              <a className="ad-mv-btn" href={ready.url} download={fileName} aria-label="تنزيل" title="تنزيل">
                <Icon name="download" />
              </a>
            </>
          ) : null}
        </div>
      </div>

      <div
        ref={stageRef}
        className={["ad-mv-stage", view.scale > 1 ? "zoomed" : null].filter(Boolean).join(" ")}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={onDoubleClick}
        onClick={(event) => {
          // النقرُ على الفراغ حول الملفّ يُغلق؛ على الملفّ نفسِه أو بعد سحبٍ لا
          const dragged = justDragged.current;
          const backdrop = pressedBackdrop.current;
          justDragged.current = false;
          pressedBackdrop.current = false;
          if (event.target === event.currentTarget && backdrop && !dragged) onClose();
          else event.stopPropagation();
        }}
      >
        {loaded.state === "loading" ? <span className="ad-mv-note">جارٍ الفتح…</span> : null}
        {loaded.state === "failed" ? <span className="ad-mv-note danger">{loaded.message}</span> : null}
        {ready && pdf ? (
          pdfInline ? (
            <iframe className="ad-mv-pdf" src={ready.url} title={item?.label} />
          ) : (
            // **متصفّحُ الهاتف لا يرسم PDF داخل إطار** (Chrome أندرويد) — فلا مربّعَ فارغاً يُقرأ «لا ملف»
            <div className="ad-mv-pdf-card" onClick={(event) => event.stopPropagation()}>
              <Icon name="picture_as_pdf" />
              <p>هذا المتصفّح لا يعرض PDF داخل الصفحة.</p>
              <a className="ad-mv-open" href={ready.url} target="_blank" rel="noopener">
                افتح الملف
              </a>
              <a className="ad-mv-open ghost" href={ready.url} download={fileName}>
                نزّل الملف
              </a>
            </div>
          )
        ) : null}
        {ready && !pdf ? (
          <img
            className="ad-mv-img"
            src={ready.url}
            alt={item?.label}
            draggable={false}
            style={{
              ...fit,
              transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale}) rotate(${view.turn}deg)`,
            }}
            onClick={(event) => event.stopPropagation()}
          />
        ) : null}

        {count > 1 ? (
          <>
            <button
              type="button"
              className="ad-mv-nav prev"
              onClick={(event) => {
                event.stopPropagation();
                go(-1);
              }}
              aria-label="السابق"
            >
              <Icon name="chevron_right" />
            </button>
            <button
              type="button"
              className="ad-mv-nav next"
              onClick={(event) => {
                event.stopPropagation();
                go(1);
              }}
              aria-label="التالي"
            >
              <Icon name="chevron_left" />
            </button>
          </>
        ) : null}
      </div>

      {item?.extra ? (
        <div className="ad-mv-extra" onClick={(event) => event.stopPropagation()}>
          {item.extra}
        </div>
      ) : null}
    </div>,
    document.body,
  );
}
