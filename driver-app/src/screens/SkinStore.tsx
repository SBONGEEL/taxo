/** **متجر المركبات** (2026-08-22).
 *
 * **والترتيبُ من الخلفية لا يُعاد هنا** (شرطُ العقد: «المتجرُ مقسوماً بندرته
 * — والترتيبُ عقدٌ لا ذوق»). فالأقسامُ تُرسم **حين تتبدّل الندرةُ في القائمة**
 * لا بفرزٍ من عندنا: فرزٌ في الشاشة يجعل بابين يرتّبان شيئاً واحداً اختلافاً،
 * ويُفرغ شرطَ العقد من معناه بلا سطرٍ يتغيّر في الخلفية.
 *
 * **والرصيدُ في الرأس** — لا في ورقة الدفع وحدَها: من يتصفّح ثمانيةَ أسعارٍ
 * يحتاج أن يعرف ما معه قبل أن يفتح واحداً منها.
 *
 * **وثلاثُ خطواتٍ إلى المال**: بطاقة ← ورقةُ منتج ← ورقةُ تأكيد. والأولَيان
 * يُرجَع عنهما، والثالثةُ وحدَها تدفع (`design/MONEY-STEPS-CHECKLIST.md`).
 */

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Navigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { buySkin, getSkinStore } from "@/api/endpoints";
import type { SkinStore as SkinStorePayload, VehicleSkin } from "@/api/types";
import { BuyConfirmSheet } from "@/components/skins/BuyConfirmSheet";
import { SkinCard } from "@/components/skins/SkinCard";
import { SkinDetailSheet } from "@/components/skins/SkinDetailSheet";
import { EmptyNote, ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useGarage } from "@/lib/garage";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { RARITY_CHIP, RARITY_LABEL, RARITY_NOTE } from "@/lib/skins";
import { digits, cn } from "@/lib/utils";

const PAGE = 48;

export function SkinStoreScreen() {
  const goBack = useGoBack();
  const { enabled, refresh: refreshGarage } = useGarage();
  const [store, setStore] = useState<SkinStorePayload | null>(null);
  /** **الصفحاتُ متراكمةٌ خارج `store`**: الأخيرُ يحمل الرصيدَ والمجموع، وهذه
   *  تحمل ما عُرض حتى الآن — وخلطُهما يجعل كلَّ صفحةٍ تمحو ما قبلها. */
  const [skins, setSkins] = useState<VehicleSkin[]>([]);
  const [paging, setPaging] = useState(false);
  const sentinel = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState<string | null>(null);

  const [open, setOpen] = useState<VehicleSkin | null>(null);
  const [confirming, setConfirming] = useState<VehicleSkin | null>(null);
  const [busy, setBusy] = useState(false);
  const [buyError, setBuyError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  /** **يُعاد من الصفر** — بعد شراءٍ مثلاً: الصفحاتُ المتراكمةُ تُستبدل ولا
   *  تُلحَق، وإلا ظهرت المركبةُ مرّتين (المشتراةُ ومكانُها القديم). */
  const load = useCallback(async () => {
    const first = await getSkinStore(PAGE, 0);
    setStore(first);
    setSkins(first.skins);
  }, []);

  /** **الصفحةُ التالية عند بلوغ القاع** — ولا تُطلب وهي جاريةٌ ولا بعد
   *  النهاية: `total` من الخلفية يقول متى نتوقّف بلا صفحةٍ فارغةٍ تُكتشف بها. */
  const more = useCallback(async () => {
    if (paging || !store || skins.length >= store.total) return;
    setPaging(true);
    try {
      const next = await getSkinStore(PAGE, skins.length);
      setSkins((current) => [...current, ...next.skins]);
    } catch {
      // **صمتٌ مقصود**: الصفحةُ الأولى معروضةٌ وتعمل، وشريطُ خطأٍ على تمريرةٍ
      // فاشلةٍ يُفزع بلا أن يمنع شيئاً. والمحاولةُ تتكرّر عند التمرير التالي.
    } finally {
      setPaging(false);
    }
  }, [paging, store, skins.length]);

  useEffect(() => {
    load()
      .catch((caught) =>
        setFailed(
          caught instanceof ApiError ? caught.message : "تعذّر فتح المتجر",
        ),
      )
      .finally(() => setLoading(false));
  }, [load]);

  // **مراقبُ القاع** — بديلُ زرِّ «المزيد»: التمريرُ هو الإيماءةُ الطبيعيةُ في
  // شبكةٍ طويلة، وزرٌّ في آخر ٤٨ بطاقةً يُضغط مرّةً كلَّ صفحة.
  useEffect(() => {
    const node = sentinel.current;
    if (!node) return;
    const watcher = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) void more();
      },
      { rootMargin: "600px" },
    );
    watcher.observe(node);
    return () => watcher.disconnect();
  }, [more]);

  async function confirm() {
    const skin = confirming;
    if (!skin) return;
    setBusy(true);
    setBuyError(null);
    try {
      const result = await buySkin(skin.id);
      setConfirming(null);
      setOpen(null);
      // **الرصيدُ بعده من الدفتر** — لا مطروحاً في الشاشة (§14)
      setDone(
        `صارت «${result.skin.name}» في كراجك — رصيدك ${digits(
          result.balance_after,
        )} ${CURRENCY_LABEL[result.currency]}`,
      );
      await Promise.all([load(), refreshGarage()]);
    } catch (caught) {
      // **نصُّ الخلفية كما هو** (§17): «رصيدٌ غيرُ كافٍ» و«نفدت الكمية»
      // و«مملوكةٌ سلفاً» و«مقفولةٌ بالمستوى» كلُّها تُسمّى هناك لا هنا
      setBuyError(
        caught instanceof ApiError ? caught.message : "تعذّر إتمام الشراء",
      );
    } finally {
      setBusy(false);
    }
  }

  // **مطفأً: رجوعٌ لا رسالةُ خطأ** — كالكراج سواءً
  if (!enabled) return <Navigate to="/account" replace />;

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }


  return (
    <div className="relative h-full bg-bg">
      <div className="scr h-full px-16 pb-nav pt-safe">
        <div className="mb-14 flex items-center gap-10">
          <button
            type="button"
            onClick={() => goBack()}
            aria-label="رجوع"
            className="pressable text-18 text-muted"
          >
            →
          </button>
          <h1 className="flex-1 text-20 font-bold text-ink">متجر المركبات</h1>
        </div>

        {store ? (
          <div className="mb-14 flex items-baseline justify-between rounded-14 border border-line bg-surface px-14 py-12">
            <span className="text-12 text-muted">رصيد محفظتك</span>
            <span className="text-15 font-bold text-ink">
              {digits(store.balance)}{" "}
              <span className="text-10.5 font-medium text-muted">
                {CURRENCY_LABEL[store.currency]}
              </span>
            </span>
          </div>
        ) : null}

        <ErrorNote message={failed} />
        <SuccessNote message={done} />

        {skins.length === 0 && !failed ? (
          <EmptyNote
            title="لا مركبات معروضةً الآن"
            hint="يُضاف إلى المتجر من وقتٍ لآخر — عُد لاحقاً."
          />
        ) : null}

        {skins.map((skin, index) => {
          const heads = index === 0 || skins[index - 1].rarity !== skin.rarity;
          const until = skins.findIndex(
            (later, at) => at > index && later.rarity !== skin.rarity,
          );
          const groupEnd = until === -1 ? skins.length : until;
          if (!heads) return null;
          const group = skins.slice(index, groupEnd);
          return (
            <Fragment key={skin.rarity}>
              <div className="mb-8 mt-14 flex items-center gap-8">
                <span
                  className={cn(
                    "rounded-full border px-10 py-4 text-10.5 font-bold",
                    RARITY_CHIP[skin.rarity],
                  )}
                >
                  {RARITY_LABEL[skin.rarity]}
                </span>
                <span className="min-w-0 flex-1 truncate text-11 text-muted">
                  {RARITY_NOTE[skin.rarity]}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-10">
                {group.map((item) => (
                  <SkinCard
                    key={item.id}
                    skin={item}
                    onOpen={() => setOpen(item)}
                  />
                ))}
              </div>
            </Fragment>
          );
        })}

        {/* **حارسُ القاع** — بلوغُه يطلب الصفحةَ التالية (`rootMargin` يسبقه
            بستّ مئةِ بكسل، فتصل الصفحةُ قبل أن يرى الكبتنُ فراغاً) */}
        <div ref={sentinel} aria-hidden className="h-px" />
        {paging ? <Spinner className="mx-auto my-14" /> : null}

        <p className="mt-16 text-11 leading-note text-muted">
          المركبةُ زينةٌ على الخريطة — لا تغيّر أجرتك ولا فئةَ سيارتك ولا
          أولويتَك في الطلبات.
        </p>
      </div>

      {open ? (
        <SkinDetailSheet
          skin={open}
          busy={busy}
          onActivate={null}
          onBuy={
            open.owned || open.blocked_reason || !open.price
              ? null
              : () => setConfirming(open)
          }
          onClose={() => setOpen(null)}
        />
      ) : null}

      {confirming && store ? (
        <BuyConfirmSheet
          skin={confirming}
          balance={store.balance}
          currency={store.currency}
          busy={busy}
          error={buyError}
          onConfirm={() => void confirm()}
          onClose={() => {
            setConfirming(null);
            setBuyError(null);
          }}
        />
      ) : null}
    </div>
  );
}
