/** **مُختارُ السوق لحسابات التجربة وحدَها** (SPEC §٧٤-أ/١٠) — لا يُرسم لغيرها أبداً.
 *
 * **داخلَ دولةٍ سوقُها، وخارجَ كلِّ دولةٍ مُختار**: `TestMarketAuto` عند الإقلاع يقرأ الموقعَ (إن كان إذنُه ممنوحاً سلفاً) **فإن وقع في سوقٍ لحساب
 * التجربة أخٌ فيه انتقل إليه مرّةً واحدةً في الجلسة**؛ و`TestMarketSection` في الإعدادات يختار السوقَ بيده — ولو كان مغلقاً للعموم.
 *
 * **والانتقالُ دخولٌ إلى حسابٍ آخر** (`POST /auth/test-markets/{سوق}` — لكلِّ سوقٍ حسابُ تجربةٍ بمحفظته وعملته)، **ثمّ إعادةُ تحميلٍ كاملة**:
 * العملةُ والأسعارُ والخدماتُ وطرقُ الدفع كلُّها تُقرأ من سوق الحساب، فلا يبقى في الذاكرة شيءٌ من السوق السابق. **وكلُّ انتقالٍ سطرٌ في التدقيق.**
 */
import { useEffect, useState } from "react";

import { getTestMarkets, switchTestMarket } from "@/api/endpoints";
import type { CountryCode, TestMarket } from "@/api/types";
import { useConfig } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import { AuthCountrySheet, Flag, Icon } from "@/taxo2";

const AUTO_KEY = "taxo.test.market.auto";

function located(areas: Array<{ country_code: CountryCode; area: number[] }>): Promise<CountryCode | null> {
  return new Promise((resolve) => {
    void (async () => {
      try {
        const state = await navigator.permissions?.query({ name: "geolocation" as PermissionName });
        if (state?.state !== "granted") return resolve(null);
        navigator.geolocation.getCurrentPosition(
          (position) => {
            const { latitude, longitude } = position.coords;
            const hit = areas.find(({ area }) => latitude >= area[0] && latitude <= area[1] && longitude >= area[2] && longitude <= area[3]);
            resolve(hit?.country_code ?? null);
          },
          () => resolve(null),
          { timeout: 4000, maximumAge: 600_000 },
        );
      } catch {
        resolve(null);
      }
    })();
  });
}

async function moveTo(country: CountryCode, signIn: ReturnType<typeof useSession>["signIn"]): Promise<void> {
  const response = await switchTestMarket(country);
  signIn(response);
  // **إعادةُ تحميلٍ كاملة** — لا يبقى من السوق السابق شيءٌ في الذاكرة
  window.setTimeout(() => window.location.assign("/"), 50);
}

/** **داخلَ دولةٍ سوقُها** — مرّةً في الجلسة، ولحساب التجربة وحدَه. */
export function TestMarketAuto() {
  const { user, signIn } = useSession();
  const { config } = useConfig();
  useEffect(() => {
    if (!user?.is_test || !config) return;
    try {
      if (sessionStorage.getItem(AUTO_KEY)) return;
      sessionStorage.setItem(AUTO_KEY, "1");
    } catch {
      return;
    }
    void (async () => {
      const here = await located(config.countries);
      if (!here || here === user.country_code) return;
      const { markets } = await getTestMarkets();
      if (markets.some((market) => market.country_code === here)) await moveTo(here, signIn);
    })().catch(() => undefined);
  }, [user, config, signIn]);
  return null;
}

/** **قسمُ «سوق التجربة» في الإعدادات** — لا يُرسم لغير حساب التجربة. */
export function TestMarketSection() {
  const { user, signIn } = useSession();
  const { config } = useConfig();
  const [markets, setMarkets] = useState<TestMarket[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.is_test) return;
    getTestMarkets()
      .then((answer) => setMarkets(answer.markets))
      .catch(() => setMarkets([]));
  }, [user]);

  if (!user?.is_test || markets.length === 0) return null;
  const current = markets.find((market) => market.current);
  const dial = (code: CountryCode) => config?.countries.find((entry) => entry.country_code === code)?.dial_code ?? "";

  return (
    <section>
      <div className="t2-group">{tr("سوق التجربة")}</div>
      <div className="t2-list t2-sgroup">
        <button type="button" className="t2-srow" disabled={busy} onClick={() => setOpen(true)} aria-haspopup="dialog">
          {current ? <Flag code={current.country_code} label={current.name} size={26} /> : <Icon name="flag" className="t2-srow-icon" />}
          <span className="t2-srow-main">
            <span className="t2-srow-title">{current?.name ?? user.country_code}</span>
            <span className="t2-srow-hint">
              {tr("حسابُ تجربة — تصل كلَّ سوقٍ ولو كان مغلقاً، ورصيدُه «رصيد تجريبي» لا يغادر المنصّة")}
            </span>
          </span>
          <Icon name="expand_more" />
        </button>
        {error ? (
          <p className="t2-srow-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
      <AuthCountrySheet
        open={open}
        title={tr("سوق التجربة")}
        sub={tr("لكلِّ سوقٍ حسابُ تجربةٍ بمحفظته وعملته — والانتقالُ يُسجَّل.")}
        options={markets.map((market) => ({
          code: market.country_code,
          name: market.status === "closed" ? `${market.name} · ${tr("مغلقة للعموم")}` : market.name,
          dial: dial(market.country_code),
        }))}
        value={current?.country_code ?? user.country_code}
        onPick={(code) => {
          setOpen(false);
          if (code === current?.country_code) return;
          setBusy(true);
          setError(null);
          moveTo(code as CountryCode, signIn).catch((caught) => {
            setBusy(false);
            setError(caught instanceof Error && caught.message ? caught.message : tr("تعذّر الانتقال"));
          });
        }}
        onClose={() => setOpen(false)}
      />
    </section>
  );
}
