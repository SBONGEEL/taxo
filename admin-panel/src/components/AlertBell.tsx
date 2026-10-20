/** **جرسُ المالك** في ترويسة اللوحة (SPEC §٨١/١) — عددُ غير المقروء، وآخرُ ثمانيةٍ بأيقونات فئاتها، و«الكلّ مقروء».
 *
 * **ولا يُرسم لمن لا يملك الصلاحية** — والإخفاءُ راحةٌ لا حماية: الخادمُ يردّ غيرَ حاملها. **وعلى الهاتف والحاسوب معاً**
 * (لا `ad-desk`): الجرسُ أداةُ عملٍ لا زرُّ حساب.
 */

import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import type { AdminAlert } from "@/api/types";
import { ACTIVITY_ALERTS, AlertGlyph, recordPath, useAlertFeed } from "@/lib/alerts";
import { sinceNow } from "@/lib/format";
import { useHolds } from "@/lib/permissions";
import { Icon } from "@/taxo2";

export function AlertRow({
  alert,
  onOpen,
  compact = false,
}: {
  alert: AdminAlert;
  onOpen: (alert: AdminAlert) => void;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      className={alert.read ? "ad-alert-row" : "ad-alert-row unread"}
      data-kind={alert.kind}
      onClick={() => onOpen(alert)}
    >
      <AlertGlyph tone={alert.tone} size={compact ? 36 : 44} />
      <span className="ad-alert-row-text">
        <span className="ad-alert-title">{alert.title}</span>
        <span className="ad-alert-body">{alert.body}</span>
      </span>
      <span className="ad-alert-row-side">
        <span className="ad-alert-time">{sinceNow(alert.last_event_at)}</span>
        {alert.read ? null : <span className="ad-alert-dot" aria-label="غير مقروء" />}
      </span>
    </button>
  );
}

export function AlertBell() {
  const holds = useHolds(ACTIVITY_ALERTS);
  const feed = useAlertFeed();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement | null>(null);

  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (holds !== true || !feed) return null;
  const unread = feed.summary?.unread ?? 0;
  const latest = feed.summary?.latest ?? [];

  const openAlert = (alert: AdminAlert) => {
    if (!alert.read) void feed.markRead([alert.id]);
    navigate(recordPath(alert));
  };

  return (
    <div className="ad-alert-bell" ref={box}>
      <button
        type="button"
        className="ad-round"
        aria-label={unread ? `الإشعارات — ${unread} غير مقروء` : "الإشعارات"}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="notifications" fill={unread > 0} />
        {unread > 0 ? <span className="ad-alert-count">{unread > 99 ? "99+" : unread}</span> : null}
      </button>
      {open ? (
        <div className="ad-alert-menu" role="dialog" aria-label="الإشعارات">
          <div className="ad-alert-menu-head">
            <p className="ad-alert-menu-title">الإشعارات</p>
            {unread > 0 ? (
              <button type="button" className="ad-link" onClick={() => void feed.markRead("all")}>
                الكلُّ مقروء
              </button>
            ) : null}
          </div>
          <div className="ad-alert-menu-list scr">
            {latest.length === 0 ? <p className="ad-alert-empty">لا إشعاراتٍ بعد.</p> : null}
            {latest.map((alert) => (
              <AlertRow key={alert.id} alert={alert} onOpen={openAlert} compact />
            ))}
          </div>
          <div className="ad-alert-menu-foot">
            <button type="button" className="ad-link" onClick={() => navigate("/alerts")}>
              كلُّ الإشعارات
            </button>
            <button type="button" className="ad-link" onClick={() => navigate("/alerts/settings")}>
              الإعداد
            </button>
            <button type="button" className="ad-link" onClick={() => navigate("/alerts/preview")}>
              المعاينة
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
