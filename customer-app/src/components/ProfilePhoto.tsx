/** **صورةُ الملفّ** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-هـ) — دائرةٌ تُلمس فتفتح ورقةً: «التقاط صورة» · «اختيار من المعرض» · «تعديل»
 *  (قصٌّ دائريّ) · «حذف». **منسوخةٌ بايتاً في التطبيقين** (`check:permissions-plugin`) — وما يفترق (البابُ، والحذفُ المسموح، وسطرُ
 *  المراجعة) يأتي من صاحب الشاشة.
 *
 *  * **بلا صورة**: أوّلُ حرفٍ من الاسم في دائرةٍ لونُها من الاسم (`letterColour`).
 *  * **قبل الرفع**: قصٌّ في دائرة، وتصغيرٌ إلى ٥١٢، وJPEG — **الرسمُ في `canvas` لا ينقل EXIF** (والخادمُ يعيد ترميزَها أيضاً).
 *  * **والإذنُ عند الضغط وحدَه**: الكاميرا يطلبها النظامُ حين يُضغط «التقاط صورة»، والورقةُ تقول لماذا قبلها بسطرٍ عربيّ. */
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import { clampCrop, drawnSize, INITIAL_CROP, initialOf, letterColour, OUTPUT_EDGE, sourceRect, type Crop } from "@/lib/photo-crop";
import { tr } from "@/lib/i18n";
import { Icon } from "@/taxo2";

import "./profile-photo.css";

const VIEW = 260;

export interface ProfilePhotoProps {
  name: string;
  /** الصورةُ الحاليّة كما يراها الآخرون — `null` ⇐ الحرف */
  load: () => Promise<Blob | null>;
  upload: (file: File) => Promise<void>;
  /** `null` ⇐ لا حذف (الكبتنُ الذي صورتُه مطلوبة) — ويُقال السببُ في `deleteNote` */
  remove: (() => Promise<void>) | null;
  deleteNote?: string | null;
  /** سطرٌ تحت الدائرة — «صورتك الجديدة قيد المراجعة…» */
  note?: string | null;
  /** يُنادى بعد كلِّ تغييرٍ ناجح (لتحديث الملاحظة من الخادم) */
  onChanged?: () => void;
  size?: number;
}

export function ProfilePhoto({ name, load, upload, remove, deleteNote, note, onChanged, size = 68 }: ProfilePhotoProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [current, setCurrent] = useState<Blob | null>(null);
  const [sheet, setSheet] = useState(false);
  const [editing, setEditing] = useState<{ src: string; w: number; h: number } | null>(null);
  const [crop, setCrop] = useState<Crop>(INITIAL_CROP);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const camera = useRef<HTMLInputElement>(null);
  const gallery = useRef<HTMLInputElement>(null);
  const drag = useRef<{ x: number; y: number } | null>(null);

  const refresh = () => {
    load()
      .then((blob) => {
        setCurrent(blob);
        setUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return blob ? URL.createObjectURL(blob) : null;
        });
      })
      .catch(() => undefined);
  };
  useEffect(refresh, []);
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);

  function edit(blob: Blob) {
    setError(null);
    const src = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => {
      setCrop(INITIAL_CROP);
      setEditing({ src, w: image.naturalWidth, h: image.naturalHeight });
      setSheet(false);
    };
    image.onerror = () => {
      URL.revokeObjectURL(src);
      setError(tr("تعذّرت قراءة الصورة — اختر صورةً أخرى"));
    };
    image.src = src;
  }

  function closeEditor() {
    if (editing) URL.revokeObjectURL(editing.src);
    setEditing(null);
  }

  async function save() {
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      const image = new Image();
      image.src = editing.src;
      await image.decode();
      const { sx, sy, size: side } = sourceRect(editing.w, editing.h, crop);
      const canvas = document.createElement("canvas");
      canvas.width = OUTPUT_EDGE;
      canvas.height = OUTPUT_EDGE;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("canvas");
      context.drawImage(image, sx, sy, side, side, 0, 0, OUTPUT_EDGE, OUTPUT_EDGE);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
      if (!blob) throw new Error("toBlob");
      await upload(new File([blob], "profile.jpg", { type: "image/jpeg" }));
      closeEditor();
      refresh();
      onChanged?.();
    } catch (caught) {
      setError(caught instanceof Error && caught.message && !["canvas", "toBlob"].includes(caught.message) ? caught.message : tr("تعذّر حفظ الصورة"));
    } finally {
      setBusy(false);
    }
  }

  async function destroy() {
    if (!remove) return;
    setBusy(true);
    setError(null);
    try {
      await remove();
      setConfirmDelete(false);
      setSheet(false);
      refresh();
      onChanged?.();
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : tr("تعذّر حذف الصورة"));
    } finally {
      setBusy(false);
    }
  }

  const pick = (file: File | undefined) => {
    if (file) edit(file);
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    drag.current = { x: event.clientX, y: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag.current || !editing) return;
    const dx = (event.clientX - drag.current.x) / VIEW;
    const dy = (event.clientY - drag.current.y) / VIEW;
    drag.current = { x: event.clientX, y: event.clientY };
    setCrop((value) => clampCrop({ ...value, x: value.x + dx, y: value.y + dy }, editing.w, editing.h));
  };
  const onPointerUp = () => {
    drag.current = null;
  };

  const drawn = editing ? drawnSize(editing.w, editing.h, crop.zoom) : null;

  return (
    <>
      <button
        type="button"
        className="pp-avatar"
        style={{ width: size, height: size, background: url ? undefined : letterColour(name) }}
        onClick={() => {
          setError(null);
          setSheet(true);
        }}
        aria-label={tr("صورة الملف")}
      >
        {url ? <img src={url} alt="" /> : <span className="pp-letter">{initialOf(name)}</span>}
        <span className="pp-badge" aria-hidden="true">
          <Icon name="photo_camera" />
        </span>
      </button>
      {note ? <p className="pp-note">{note}</p> : null}

      <input ref={camera} type="file" accept="image/*" capture="user" hidden onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
      <input ref={gallery} type="file" accept="image/*" hidden onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />

      {sheet ? (
        <div className="pp-scrim" role="presentation" onClick={() => !busy && setSheet(false)}>
          <div className="pp-sheet" role="dialog" aria-modal="true" aria-label={tr("صورة الملف")} onClick={(e) => e.stopPropagation()}>
            <p className="pp-title">{tr("صورة الملف")}</p>
            <button type="button" className="pp-row" onClick={() => camera.current?.click()}>
              <Icon name="photo_camera" />
              {tr("التقاط صورة")}
            </button>
            <button type="button" className="pp-row" onClick={() => gallery.current?.click()}>
              <Icon name="add_photo_alternate" />
              {tr("اختيار من المعرض")}
            </button>
            {current ? (
              <button type="button" className="pp-row" onClick={() => edit(current)}>
                <Icon name="edit" />
                {tr("تعديل")}
              </button>
            ) : null}
            {current && remove ? (
              confirmDelete ? (
                <div className="pp-confirm">
                  <p>{tr("ستُحذف صورتك، ويظهر حرفُ اسمك بدلاً منها.")}</p>
                  <button type="button" className="pp-row danger" disabled={busy} aria-busy={busy} onClick={() => void destroy()}>
                    {tr("نعم، احذفها")}
                  </button>
                  <button type="button" className="pp-row" onClick={() => setConfirmDelete(false)}>
                    {tr("تراجع")}
                  </button>
                </div>
              ) : (
                <button type="button" className="pp-row danger" onClick={() => setConfirmDelete(true)}>
                  <Icon name="delete" />
                  {tr("حذف")}
                </button>
              )
            ) : null}
            {current && !remove && deleteNote ? <p className="pp-hint">{deleteNote}</p> : null}
            <p className="pp-hint">{tr("نطلب إذنَ الكاميرا أو الصور عند الضغط فقط، ولا نستعمل الصورةَ إلا صورةً لملفّك.")}</p>
            {error ? <p className="pp-error" role="alert">{error}</p> : null}
          </div>
        </div>
      ) : null}

      {editing && drawn ? (
        <div className="pp-scrim pp-editor-scrim" role="presentation">
          <div className="pp-editor" role="dialog" aria-modal="true" aria-label={tr("تعديل الصورة")}>
            <p className="pp-title">{tr("حرّك الصورةَ وكبّرها لتملأ الدائرة")}</p>
            <div
              className="pp-view"
              style={{ width: VIEW, height: VIEW }}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={onPointerUp}
            >
              <img
                src={editing.src}
                alt=""
                draggable={false}
                style={{
                  width: drawn.w * VIEW,
                  height: drawn.h * VIEW,
                  left: VIEW / 2 + crop.x * VIEW - (drawn.w * VIEW) / 2,
                  top: VIEW / 2 + crop.y * VIEW - (drawn.h * VIEW) / 2,
                }}
              />
              <span className="pp-mask" aria-hidden="true" />
            </div>
            <input
              className="pp-zoom"
              type="range"
              min={1}
              max={4}
              step={0.01}
              value={crop.zoom}
              aria-label={tr("التكبير")}
              onChange={(e) => setCrop((value) => clampCrop({ ...value, zoom: Number(e.target.value) }, editing.w, editing.h))}
            />
            {error ? <p className="pp-error" role="alert">{error}</p> : null}
            <div className="pp-actions">
              <button type="button" className="pp-save" disabled={busy} aria-busy={busy} onClick={() => void save()}>
                {busy ? tr("جارٍ الحفظ…") : tr("حفظ")}
              </button>
              <button type="button" className="pp-cancel" disabled={busy} onClick={closeEditor}>
                {tr("إلغاء")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
