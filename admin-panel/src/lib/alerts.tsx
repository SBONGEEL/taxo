/** **إشعاراتُ المالك في اللوحة** (SPEC §٨١) — الفئاتُ بأيقوناتها وألوانها وأصواتها، والجرسُ الحيّ، والنافذةُ المنبثقة.
 *
 * **الفئةُ واحدةٌ في كلِّ مكان**: أيقونتُها ولونُها هنا هما ما يرسمه الهاتفُ (`res/drawable-nodpi/alert_large_*.png`) والمتصفّحُ
 * (`public/icons/alerts/*.png`) — **من مصدرٍ واحد** (`design/admin-alerts/`). **والصوتُ يُعزف واللوحةُ مفتوحة** (بإعداد كلِّ فئة)،
 * ومغلقةً يعزف المتصفّحُ صوتَ النظام — وتقوله صفحةُ الإعداد (شرطُ المالك ١٢).
 *
 * **ولا مسارَ يصل من الخادم**: السجلُّ نوعٌ ومعرّف، والمسارُ يُشتقّ هنا (`recordPath`) — فإشعارٌ مزوَّرٌ لا يفتح بابَ شيء.
 */

import {
  Banknote,
  Car,
  MessageSquareText,
  TriangleAlert,
  UserPlus,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";

import { alertSettings, alertSummary, markAlertsRead } from "@/api/endpoints";
import type { AdminAlert, AlertSettings, AlertSummary, AlertTone } from "@/api/types";
import { recordPath } from "@/lib/alert-paths";
import { enableBrowserAlerts } from "@/lib/alert-push";
import { useConfig } from "@/lib/config";
import { useHolds } from "@/lib/permissions";
import { useSession } from "@/lib/session";

import "./alerts.css";

/** **صلاحيةُ الاستلام** — مرآةُ `AdminPermission.ACTIVITY_ALERTS_RECEIVE`: المالكُ يملكها، وغيرُه بمنحٍ بالاسم. */
export const ACTIVITY_ALERTS = "activity_alerts.receive";

export interface ToneMeta {
  icon: LucideIcon;
  color: string;
  /** ملفُّ الصوت — **مولَّدٌ لا منسوخ** (`design/admin-alerts/README.md`) */
  sound: string;
  /** أيقونةُ إشعار المتصفّح بلون الفئة */
  image: string;
}

export const TONE_META: Record<AlertTone, ToneMeta> = {
  money_in: { icon: Banknote, color: "#1F9D55", sound: "/sounds/alerts/alert_money_in.mp3", image: "/icons/alerts/alert_money_in.png" },
  money_out: { icon: Wallet, color: "#2B6CB0", sound: "/sounds/alerts/alert_money_out.mp3", image: "/icons/alerts/alert_money_out.png" },
  account: { icon: UserPlus, color: "#6B46C1", sound: "/sounds/alerts/alert_account.mp3", image: "/icons/alerts/alert_account.png" },
  problem: { icon: TriangleAlert, color: "#E03E3E", sound: "/sounds/alerts/alert_problem.mp3", image: "/icons/alerts/alert_problem.png" },
  ride: { icon: Car, color: "#F05A28", sound: "/sounds/alerts/alert_ride.mp3", image: "/icons/alerts/alert_ride.png" },
  feedback: { icon: MessageSquareText, color: "#C88A12", sound: "/sounds/alerts/alert_feedback.mp3", image: "/icons/alerts/alert_feedback.png" },
};

/** **أيُّ صوتٍ يُسمع حين تصل فئاتٌ معاً** — المشكلةُ أوّلاً، والرحلاتُ آخراً فلا تغطّي الذروةُ ما يهمّ. */
const TONE_PRIORITY: AlertTone[] = ["problem", "money_in", "account", "feedback", "money_out", "ride"];

export { recordPath };

const players = new Map<AlertTone, HTMLAudioElement>();

/** **يعزف صوتَ الفئة** — ومتصفّحٌ يمنع العزفَ قبل لمسةٍ يُسكت بلا خطأ: الإشعارُ نفسُه وصل. */
export function playTone(tone: AlertTone): void {
  try {
    let player = players.get(tone);
    if (!player) {
      player = new Audio(TONE_META[tone].sound);
      player.preload = "auto";
      players.set(tone, player);
    }
    player.currentTime = 0;
    void player.play().catch(() => undefined);
  } catch {
    // لا صوتَ في هذه البيئة — ولا يُسقط ذلك شيئاً
  }
}

// ═════════════════════════ الجرسُ الحيّ

interface Feed {
  /** `null` لمن لا يملك الصلاحية أو قبل أوّل جواب */
  summary: AlertSummary | null;
  settings: AlertSettings | null;
  refresh: () => void;
  setSettings: (next: AlertSettings) => void;
  markRead: (ids: string[] | "all") => Promise<void>;
  /** **ما وصل الآن** — النوافذُ المنبثقة */
  toasts: AdminAlert[];
  dismiss: (id: string) => void;
}

const FeedContext = createContext<Feed | null>(null);

const VISIBLE_MS = 10_000;
const HIDDEN_MS = 30_000;
const TOAST_MS = 9_000;

export function AlertFeedProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const { config } = useConfig();
  const holds = useHolds(ACTIVITY_ALERTS);
  const [summary, setSummary] = useState<AlertSummary | null>(null);
  const [settings, setSettings] = useState<AlertSettings | null>(null);
  const [toasts, setToasts] = useState<AdminAlert[]>([]);
  const [nonce, setNonce] = useState(0);
  const newest = useRef<string | null>(null);
  const settingsRef = useRef<AlertSettings | null>(null);
  settingsRef.current = settings;

  const refresh = useCallback(() => setNonce((value) => value + 1), []);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  // **دفعٌ وصل واللوحةُ مفتوحة** (`alert-push.ts → onMessage`) — يُسأل الجرسُ الآن لا بعد دورته
  useEffect(() => {
    window.addEventListener("taxo:admin-alert", refresh);
    return () => window.removeEventListener("taxo:admin-alert", refresh);
  }, [refresh]);

  // **من منح المتصفّحَ الإذنَ من قبل يُسجَّل بصمت** عند كلِّ فتح — والطلبُ نفسُه بزرٍّ في صفحة الإعداد
  useEffect(() => {
    if (!user || holds !== true || !config) return;
    void enableBrowserAlerts(config.providers.fcm, { ask: false }).catch(() => undefined);
  }, [user, holds, config]);

  // **الإعدادُ مرّةً** — الأصواتُ تُقرأ منه، ويُعاد بعد كلِّ حفظ
  useEffect(() => {
    if (!user || holds !== true) {
      setSettings(null);
      return;
    }
    let live = true;
    void alertSettings()
      .then((value) => {
        if (live) setSettings(value);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [user, holds]);

  useEffect(() => {
    if (!user || holds !== true) {
      setSummary(null);
      newest.current = null;
      return;
    }
    let live = true;
    let timer: number | undefined;

    const tick = async () => {
      try {
        const answer = await alertSummary();
        if (!live) return;
        const previous = newest.current;
        const top = answer.latest[0]?.last_event_at ?? null;
        // **أوّلُ قراءةٍ لا تُصدر صوتاً** — ما كان قبل فتح اللوحة ليس «وصل الآن»
        if (previous !== null) {
          const arrived = answer.latest.filter((item) => !item.read && item.last_event_at > previous);
          if (arrived.length) announce(arrived);
        }
        if (top && (previous === null || top > previous)) newest.current = top;
        else if (previous === null) newest.current = "";
        setSummary(answer);
      } catch {
        // تعذّرٌ عابر — الجرسُ يبقى على آخر ما عرف، والدورةُ التالية تسأل
      } finally {
        if (live) {
          timer = window.setTimeout(tick, document.visibilityState === "visible" ? VISIBLE_MS : HIDDEN_MS);
        }
      }
    };

    const announce = (arrived: AdminAlert[]) => {
      const sounds = settingsRef.current?.sounds;
      const tone = TONE_PRIORITY.find((candidate) => arrived.some((item) => item.tone === candidate));
      if (tone && document.visibilityState === "visible" && sounds?.[tone] !== false) playTone(tone);
      // **صفٌّ مجموعٌ يكبر يعود بمعرّفه نفسِه** — فيحلّ محلَّ نافذته لا يُضاف فوقها
      const shown = arrived.slice(0, 3);
      setToasts((current) => [...shown, ...current.filter((item) => !shown.some((fresh) => fresh.id === item.id))].slice(0, 4));
      for (const item of arrived.slice(0, 3)) {
        window.setTimeout(() => dismiss(item.id), TOAST_MS);
      }
    };

    void tick();
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        window.clearTimeout(timer);
        void tick();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      live = false;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [user, holds, nonce, dismiss]);

  const markRead = useCallback(
    async (ids: string[] | "all") => {
      await markAlertsRead(ids === "all" ? { all: true } : { ids });
      refresh();
    },
    [refresh],
  );

  const value = useMemo<Feed>(
    () => ({ summary, settings, refresh, setSettings, markRead, toasts, dismiss }),
    [summary, settings, refresh, markRead, toasts, dismiss],
  );

  return (
    <FeedContext.Provider value={value}>
      {children}
      <AlertToasts />
    </FeedContext.Provider>
  );
}

export function useAlertFeed(): Feed | null {
  return useContext(FeedContext);
}

// ═════════════════════════ القطعةُ الواحدة — الجرسُ والقائمةُ والنافذةُ والمعاينةُ ترسم منها

export function AlertGlyph({ tone, size = 40 }: { tone: AlertTone; size?: number }) {
  const meta = TONE_META[tone];
  const Glyph = meta.icon;
  return (
    <span className="ad-alert-glyph" style={{ background: meta.color, width: size, height: size }} aria-hidden="true">
      <Glyph size={Math.round(size * 0.55)} strokeWidth={2} color="#FFFFFF" />
    </span>
  );
}

function AlertToasts() {
  const feed = useAlertFeed();
  const navigate = useNavigate();
  if (!feed || feed.toasts.length === 0) return null;
  return (
    <div className="ad-alert-toasts" role="status" aria-live="polite">
      {feed.toasts.map((item) => (
        <div key={item.id} className="ad-alert-toast" data-tone={item.tone}>
          <AlertGlyph tone={item.tone} size={40} />
          <div className="ad-alert-toast-text">
            <p className="ad-alert-title">{item.title}</p>
            <p className="ad-alert-body">{item.body}</p>
            <div className="ad-alert-toast-actions">
              <button
                type="button"
                className="ad-btn ad-btn-primary ad-btn-sm"
                onClick={() => {
                  feed.dismiss(item.id);
                  void feed.markRead([item.id]);
                  navigate(recordPath(item));
                }}
              >
                افتح
              </button>
              <button
                type="button"
                className="ad-btn ad-btn-secondary ad-btn-sm"
                onClick={() => {
                  feed.dismiss(item.id);
                  void feed.markRead([item.id]);
                }}
              >
                مقروء
              </button>
            </div>
          </div>
          <button type="button" className="ad-alert-x" aria-label="إغلاق" onClick={() => feed.dismiss(item.id)}>
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
