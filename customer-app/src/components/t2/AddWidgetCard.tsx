/** **«أضف ودجت TAXO لشاشتك»** (أمرُ المالك ٢١/١١ الثالث، البند ٣) — **منسوخٌ بايتاً في التطبيقين** (`check:storefront-card`).
 *
 * **بطاقةٌ هادئةٌ في الرئيسيّة مرّةً واحدة** (`variant="card"`)، **وصفٌّ في الإعدادات** (`variant="row"`) — **لا نافذةَ تحجب أبداً**،
 * **وفي الهواتف والمشغّلات التي تدعم التثبيت وحدَها** (`usePinWidget`). واللمسةُ تطلب من المشغِّل، **وهو يسأل المستخدم**.
 */
import { useState } from "react";

import { tr } from "@/lib/i18n";
import { markPinCardSeen, pinCardSeen, usePinWidget } from "@/lib/pin-widget";
import { Icon } from "@/taxo2";

import "./add-widget.css";

export function AddWidgetCard({
  kind,
  enabled,
  body,
  variant,
}: {
  /** الودجةُ التي تُثبَّت — `request` للراكب و`status` للكبتن */
  kind: string;
  /** مفتاحُ الودجات لدولته — مطفأً لا بطاقة */
  enabled: boolean;
  /** سطرٌ صادقٌ عمّا تعرضه الودجة */
  body: string;
  variant: "card" | "row";
}) {
  const { supported, pin } = usePinWidget(kind, enabled);
  const [hidden, setHidden] = useState(() => variant === "card" && pinCardSeen());
  const [refused, setRefused] = useState(false);
  if (!supported || hidden) return null;

  function close() {
    markPinCardSeen();
    setHidden(true);
  }

  function add() {
    void pin().then((requested) => {
      if (variant === "card") close();
      setRefused(!requested);
    });
  }

  if (variant === "row") {
    return (
      <>
        <button type="button" className="t2-srow" onClick={add}>
          <Icon name="grid_view" className="t2-srow-icon" />
          <span className="t2-srow-main">
            <span className="t2-srow-title">{tr("أضف ودجت TAXO لشاشتك")}</span>
            <span className="t2-srow-hint">{body}</span>
          </span>
          <Icon name="add" className="aw-row-go" />
        </button>
        {refused ? (
          <p className="t2-srow-error" role="status">
            {tr("لم يقبل المشغِّلُ الطلب — أضفها من قائمة الودجات في هاتفك")}
          </p>
        ) : null}
      </>
    );
  }

  return (
    <section className="aw-card" aria-label={tr("أضف ودجت TAXO لشاشتك")}>
      <span className="aw-icon" aria-hidden="true">
        <Icon name="grid_view" fill />
      </span>
      <span className="aw-text">
        <span className="aw-title">{tr("أضف ودجت TAXO لشاشتك")}</span>
        <span className="aw-body">{body}</span>
      </span>
      <button type="button" className="aw-add" onClick={add}>
        {tr("أضف")}
      </button>
      <button type="button" className="aw-close" onClick={close} aria-label={tr("إغلاق")}>
        <Icon name="close" />
      </button>
    </section>
  );
}
