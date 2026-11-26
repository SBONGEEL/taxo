// صورُ المتجر: لقطةٌ حقيقيّةٌ في إطار هاتف + عنوانٌ عربيّ/فرنسيّ بهويّة TAXO 2.0 (أسود/برتقاليّ #ff6a33) — node compose.mjs <out>
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
const require = createRequire('C:/Users/loly3/.claude/skills/video-studio/package.json');
const { chromium } = require('playwright');
const ROOT = path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Z]:)/, '$1');
const OUT = process.argv[2] || `${ROOT}/out`;
const ONLY = process.argv[3] || '';
const SW = 1082, SH = 2342; // أبعادُ اللقطة
const ACC = '#ff6a33';
const u = (p) => 'file:///' + `${ROOT}/${p}`.replace(/\\/g, '/');
const hl = (s) => s.replace(/\[\[(.+?)\]\]/g, '<span class="hl">$1</span>');

const FOOT = { ar: 'لقطاتٌ حقيقيّة من التطبيق ببيانات توضيحيّة', fr: 'Captures réelles de l’application, données de démonstration' };
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Readex+Pro:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=block');
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;background:#0c0e11}
body{font-family:'Readex Pro','IBM Plex Sans Arabic',sans-serif;color:#f2f0eb;position:relative;
 background:radial-gradient(900px 620px at 50% 8%,rgba(255,106,51,.20),transparent 70%),radial-gradient(700px 700px at 50% 100%,rgba(255,106,51,.10),transparent 70%),linear-gradient(180deg,#14171c 0%,#0b0d10 100%)}
.cap{position:absolute;left:70px;right:70px;text-align:center}
.logo{display:block;margin:0 auto 26px;height:64px}
h1{font-weight:700;font-size:80px;line-height:1.16;letter-spacing:-.5px}
[lang=fr] h1{font-size:64px;letter-spacing:-1px}
.hl{color:${ACC}}
p.sub{margin-top:22px;font-size:39px;line-height:1.38;color:#b9c0c8;font-weight:400}
[lang=fr] p.sub{font-size:34px}
.phone{position:absolute;left:50%;transform:translateX(-50%);width:640px;border-radius:66px;padding:12px;background:#22262c;
 box-shadow:0 50px 120px rgba(0,0,0,.65),0 0 0 2px rgba(255,255,255,.07),inset 0 0 0 2px rgba(0,0,0,.6)}
.phone img{display:block;width:616px;height:${Math.round(616 * SH / SW)}px;border-radius:54px}
.car{position:absolute;filter:drop-shadow(0 30px 40px rgba(0,0,0,.6))}
.callout{position:absolute;left:50%;transform:translateX(-50%);border:5px solid ${ACC};border-radius:34px;background-repeat:no-repeat;
 box-shadow:0 30px 90px rgba(0,0,0,.7),0 0 0 10px rgba(255,106,51,.14)}
.foot{position:absolute;left:0;right:0;bottom:34px;text-align:center;font-size:24px;color:#6f7781}
`;

function shotSlide(s, lang) {
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  const capTop = s.logo ? 92 : 128;
  const phoneTop = s.logo ? 470 : 486;
  let extra = '';
  if (s.car) extra += `<img class="car" src="${u(s.car)}" style="width:${s.carW || 560}px;${dir === 'rtl' ? 'left' : 'right'}:${s.carX ?? -10}px;top:${s.carY ?? 1440}px;${dir === 'ltr' ? 'transform:scaleX(-1)' : ''}">`;
  if (s.callout) {
    const [cx, cy, cw, ch] = s.callout; const W = 960, k = W / cw;
    extra += `<div class="callout" style="top:${s.calloutY}px;width:${W + 10}px;height:${Math.round(ch * k) + 10}px;background-image:url('${u(s.shot)}');background-size:${Math.round(SW * k)}px auto;background-position:${-Math.round(cx * k)}px ${-Math.round(cy * k)}px"></div>`;
  }
  return `<!doctype html><html lang="${lang}" dir="${dir}"><head><meta charset="utf-8"><style>${CSS}</style></head><body>
<div class="cap" style="top:${capTop}px">${s.logo ? `<img class="logo" src="${u('assets/taxo2-logo-cream.png')}">` : ''}<h1>${hl(s.title)}</h1><p class="sub">${s.sub}</p></div>
<div class="phone" style="top:${phoneTop}px"><img src="${u(s.shot)}"></div>${extra}
<div class="foot">${FOOT[lang]}</div><script>document.fonts.ready.then(()=>{const c=document.querySelector('.cap').getBoundingClientRect().bottom;const ph=document.querySelector('.phone');const top=Math.max(${phoneTop},Math.round(c+44));const H=1846-top;const w=Math.min(616,Math.floor((H-24)*${SW}/${SH}));ph.style.top=top+'px';ph.style.width=(w+24)+'px';const im=ph.querySelector('img');im.style.width=w+'px';im.style.height=Math.round(w*${SH}/${SW})+'px';document.body.dataset.ready='1'})</script></body></html>`;
}

// **الفقاعةُ والودجات** — من لقطات Note 20 (٢٢/١١): القائمةُ حادّةٌ وما خلفها من الشاشة الرئيسيّة مُغبَّشٌ مُعتَم (لا تطبيقات ولا خلفيّةُ المالك)
function bubbleSlide(s, lang) {
  const crop = { x: 0, y: 330, w: 720, h: 600 }; const k = 1.12; const W = Math.round(crop.w * k), H = Math.round(crop.h * k);
  const circles = [[90, 120, 84], [554, 104, 94], [490, 306, 94], [94, 360, 94], [304, 406, 96]];
  const ell = [[492, 435, 96, 32], [94, 493, 100, 30], [335, 540, 135, 32]];
  const layers = [...circles.map(([x, y, r]) => `radial-gradient(circle ${r * k}px at ${x * k}px ${y * k}px,#000 ${(r - 6) * k}px,transparent ${r * k}px)`),
    ...ell.map(([x, y, rx, ry]) => `radial-gradient(${rx * k}px ${ry * k}px at ${x * k}px ${y * k}px,#000 72%,transparent 100%)`)].join(',');
  const src = u('src/n20-bubble-tap.png');
  const bg = `background-image:url('${src}');background-size:${1080 * k}px auto;background-position:${-crop.x * k}px ${-crop.y * k}px;width:${W}px;height:${H}px`;
  const cards = ['wcrop/w-off.png', 'wcrop/w-hot.png', 'wcrop/w-ride.png', 'wcrop/w-sub.png'];
  return `<!doctype html><html lang="${lang}" dir="rtl"><head><meta charset="utf-8"><style>${CSS}
.panel{position:absolute;left:60px;width:960px;height:${H}px;top:440px;border-radius:48px;overflow:hidden;background:#0b0d10;box-shadow:0 40px 100px rgba(0,0,0,.6),0 0 0 2px rgba(255,255,255,.06)}
.blur{position:absolute;left:-20px;top:-20px;width:1000px;height:${H + 40}px;background-image:url('${src}');background-size:1000px auto;background-position:0 ${-crop.y * (1000 / 1080)}px;filter:blur(30px) brightness(.38) saturate(.5)}
.sharp{position:absolute;left:110px;top:0;${bg};-webkit-mask-image:${layers};-webkit-mask-repeat:no-repeat}
.tag{position:absolute;right:40px;bottom:36px;font-size:30px;color:#cfd5db;text-align:right;line-height:1.5;max-width:300px}
.tag b{color:${ACC};font-weight:600}
.grid{position:absolute;left:60px;width:960px;top:${440 + H + 26}px;display:grid;grid-template-columns:1fr 1fr;gap:22px}
.grid img{width:469px;height:${Math.round(469 * 640 / 900)}px;display:block;clip-path:inset(14px 14px 14px 14px round 38px)}
</style></head><body>
<div class="cap" style="top:110px"><h1>${hl(s.title)}</h1><p class="sub">${s.sub}</p></div>
<div class="panel"><div class="blur"></div><div class="sharp"></div></div>
<div class="grid">${cards.map((c) => `<img src="${u(c)}">`).join('')}</div>
<div class="foot">${FOOT[lang]}</div></body></html>`;
}

function featureGraphic(f, lang) {
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  return `<!doctype html><html lang="${lang}" dir="${dir}"><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Readex+Pro:wght@400;500;600;700&display=block');
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1024px;height:500px;overflow:hidden}
body{font-family:'Readex Pro',sans-serif;color:#f2f0eb;position:relative;
 background:radial-gradient(520px 380px at ${dir === 'rtl' ? '22%' : '78%'} 62%,rgba(255,106,51,.30),transparent 70%),linear-gradient(135deg,#171a1f 0%,#0b0d10 100%)}
.txt{position:absolute;top:0;bottom:0;${dir === 'rtl' ? 'right' : 'left'}:60px;width:440px;display:flex;flex-direction:column;justify-content:center}
.logo{height:58px;width:auto;align-self:flex-start;${dir === 'rtl' ? 'align-self:flex-start' : ''}}
h1{margin-top:22px;font-size:${f.big || 56}px;font-weight:700;line-height:1.12}
h1 .hl{color:${ACC}}
p{margin-top:16px;font-size:25px;line-height:1.45;color:#bcc3cb}
.road{position:absolute;${dir === 'rtl' ? 'left' : 'right'}:0;bottom:0;width:560px;height:150px;background:linear-gradient(180deg,transparent,rgba(255,106,51,.10));}
.car{position:absolute;filter:drop-shadow(0 26px 30px rgba(0,0,0,.65))}
</style></head><body>
${f.cars.map((c) => `<img class="car" src="${u(c.src)}" style="width:${c.w}px;${dir === 'rtl' ? 'left' : 'right'}:${c.x}px;top:${c.y}px;${dir === 'ltr' ? 'transform:scaleX(-1)' : ''}">`).join('')}
<div class="txt">${f.noLogo ? '' : `<img class="logo" src="${u('assets/taxo2-logo-cream.png')}">`}<h1>${hl(f.title)}</h1><p>${f.sub}</p></div>
</body></html>`;
}

const K_BANNER = [36, 1046, 1010, 244];
const SLIDES = {
  driver: {
    ar: [
      { id: '01', shot: 'cap-k-ar/k-home.png', logo: true, car: 'assets/economy-34-night-640.webp', title: 'يومك في [[شاشة واحدة]]', sub: 'ابدأ الاستقبال بلمسة — وسيارتك وصافي اليوم أمامك' },
      { id: '02', shot: 'cap-k-ar/k-banner.png', callout: K_BANNER, calloutY: 1130, title: 'حملة الإطلاق [[في الأردن]]', sub: 'سجّل قبل الإطلاق: 60 يوماً مجاناً بدون عمولة — وبعد الإطلاق 7 أيام فقط' },
      { id: '03', shot: 'cap-k-ar/k-offer.png', title: 'الطلب [[واضح]] قبل القبول', sub: 'الفئة والأجرة والمسافة إلى الراكب في بطاقة واحدة' },
      { id: '04', shot: 'cap-k-ar/k-nav.png', title: 'ملاحة [[حتى الراكب]]', sub: 'إرشادٌ خطوةً بخطوة داخل التطبيق' },
      { id: '05', shot: 'cap-k-ar/k-collect.png', title: '[[تم الاستلام]] بلمسة', sub: 'أكّد استلام الأجرة نقداً في نهاية الرحلة' },
      { id: '06', shot: 'cap-k-ar/k-earn-week.png', title: 'أرباحك [[بوضوح]]', sub: 'اليوم والأسبوع والشهر — والعمولة والبقشيش كلٌّ في سطره' },
      { id: '07', shot: 'cap-k-ar/k-wallet.png', title: 'اسحب أرباحك [[عبر كليك]]', sub: 'الرصيد القابل للسحب وكل حركة في محفظتك' },
      { id: '08', bubble: true, title: '[[الفقاعة]] والودجات', sub: 'تحكّم بالاستقبال من فوق أي تطبيق، وتابع حالتك من الشاشة الرئيسية', tagT: 'فقاعة TAXO', tagS: 'افتح TAXO · أوقف الاستقبال · بلاغ طريق' },
    ],
    fr: [
      { id: '01', shot: 'cap-k-fr/k-home.png', logo: true, car: 'assets/economy-34-night-640.webp', title: 'Votre journée sur [[un seul écran]]', sub: 'Passez en ligne d’un geste — votre voiture et votre net du jour sous les yeux' },
      { id: '02', shot: 'cap-k-fr/k-offer.png', title: 'Une demande [[claire]] avant d’accepter', sub: 'Catégorie, tarif et distance jusqu’au passager sur une seule carte' },
      { id: '03', shot: 'cap-k-fr/k-nav.png', title: 'Navigation [[jusqu’au passager]]', sub: 'Guidage pas à pas dans l’application' },
      { id: '04', shot: 'cap-k-fr/k-arrived.png', title: '[[Au point]] de prise en charge', sub: 'Message ou appel au passager, puis démarrez la course' },
      { id: '05', shot: 'cap-k-fr/k-trip.png', title: 'Fin de course [[d’un glissement]]', sub: 'Destination, distance restante et estimation à l’écran' },
      { id: '06', shot: 'cap-k-fr/k-collect.png', title: 'Paiement [[reçu]] d’un geste', sub: 'Confirmez l’encaissement en espèces en fin de course' },
      { id: '07', shot: 'cap-k-fr/k-earn-week.png', title: 'Vos gains [[en clair]]', sub: 'Jour, semaine, mois — commission et pourboires sur leur ligne' },
      { id: '08', shot: 'cap-k-fr/k-wallet.png', title: 'Portefeuille et [[retrait via CliQ]]', sub: 'Solde retirable et chaque mouvement au même endroit' },
    ],
  },
  rider: {
    ar: [
      { id: '01', shot: 'cap-r-ar/r-home.png', logo: true, car: 'assets/comfort-34-night-640.webp', title: '[[إلى أين؟]]', sub: 'اطلب رحلتك بلمسات قليلة' },
      { id: '02', shot: 'cap-r-ar/r-confirm.png', title: 'اختر الفئة و[[اعرف السعر]]', sub: 'تقدير الأجرة لكل فئة قبل أن تطلب' },
      { id: '03', shot: 'cap-r-ar/r-search.png', title: 'نبحث لك عن [[أقرب كابتن]]', sub: 'نعرض طلبك على الكباتن القريبين منك' },
      { id: '04', shot: 'cap-r-ar/r-found.png', title: 'الكابتن [[في الطريق إليك]]', sub: 'اسمه وسيارته ولوحتها وموقعه على الخريطة' },
      { id: '05', shot: 'cap-r-ar/r-trip.png', title: 'تابع [[رحلتك]] لحظةً بلحظة', sub: 'وشاركها مع شخصٍ تثق به' },
      { id: '06', shot: 'cap-r-ar/r-rate.png', title: 'قيّم وأضف [[بقشيشاً]]', sub: 'وتفصيل الأجرة أمامك عند الوصول' },
      { id: '07', shot: 'cap-r-ar/r-pay.png', title: 'ادفع [[عبر كليك]]', sub: 'الاسم المستعار والمرجع والمبلغ جاهزةٌ للنسخ' },
      { id: '08', shot: 'cap-r-ar/r-wallet.png', title: '[[محفظة TAXO]]', sub: 'اشحن رصيدك ببطاقات TAXO وحوّل لصديق' },
    ],
    fr: [
      { id: '01', shot: 'cap-r-fr/r-home.png', logo: true, car: 'assets/comfort-34-night-640.webp', title: '[[Où allez-vous ?]]', sub: 'Commandez votre course en quelques gestes' },
      { id: '02', shot: 'cap-r-fr/r-confirm.png', title: 'Choisissez et [[voyez le prix]]', sub: 'Le tarif estimé de chaque catégorie avant de commander' },
      { id: '03', shot: 'cap-r-fr/r-search.png', title: 'Nous cherchons [[un capitaine proche]]', sub: 'Votre demande est proposée aux capitaines à proximité' },
      { id: '04', shot: 'cap-r-fr/r-found.png', title: 'Votre capitaine [[arrive]]', sub: 'Nom, voiture, plaque et position sur la carte' },
      { id: '05', shot: 'cap-r-fr/r-trip.png', title: 'Suivez [[votre course]] en direct', sub: 'et partagez-la avec une personne de confiance' },
      { id: '06', shot: 'cap-r-fr/r-rate.png', title: 'Notez et [[laissez un pourboire]]', sub: 'Le détail du tarif dès l’arrivée' },
      { id: '07', shot: 'cap-r-fr/r-pay.png', title: 'Payez [[via CliQ]]', sub: 'Alias, référence et montant prêts à copier' },
      { id: '08', shot: 'cap-r-fr/r-wallet.png', title: 'Portefeuille et [[cartes TAXO]]', sub: 'Rechargez avec une carte TAXO et transférez à un ami' },
    ],
  },
};
const FG = {
  driver: {
    ar: { big: 84, title: '<span class="hl">Driver</span>', sub: 'تطبيق الكابتن: الطلبات والملاحة والمحفظة في مكانٍ واحد', cars: [{ src: 'assets/economy-34-night-640.webp', w: 450, x: 30, y: 140 }] },
    fr: { big: 84, title: '<span class="hl">Driver</span>', sub: 'L’application des capitaines : demandes, navigation et portefeuille au même endroit', cars: [{ src: 'assets/economy-34-night-640.webp', w: 450, x: 30, y: 140 }] },
  },
  rider: {
    ar: { title: 'رحلتك <span class="hl">بلمسة</span>', sub: 'اعرف السعر التقديريّ قبل الطلب، وتابع الكابتن على الخريطة', cars: [{ src: 'assets/comfort-34-night-640.webp', w: 360, x: 150, y: 90 }, { src: 'assets/economy-34-night-640.webp', w: 400, x: 10, y: 200 }] },
    fr: { title: 'Votre course <span class="hl">en un geste</span>', big: 46, sub: 'Le prix estimé avant de commander, le capitaine suivi sur la carte', cars: [{ src: 'assets/comfort-34-night-640.webp', w: 360, x: 150, y: 90 }, { src: 'assets/economy-34-night-640.webp', w: 400, x: 10, y: 200 }] },
  },
};

const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
const made = [];
async function render(html, file, w, h, type) {
  const tmp = `${ROOT}/compose-tmp.html`; fs.writeFileSync(tmp, html);
  await page.setViewportSize({ width: w, height: h });
  await page.goto(u('compose-tmp.html'), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready); await page.waitForFunction(() => !document.querySelector('.phone') || document.body.dataset.ready === '1');
  const ok = await page.evaluate(() => document.fonts.check('700 40px "Readex Pro"', document.querySelector('h1').innerText));
  if (!ok) throw new Error('FONT NOT LOADED ' + file);
  const bad = await page.evaluate(() => [...document.images].filter((i) => !i.complete || !i.naturalWidth).map((i) => i.src));
  if (bad.length) throw new Error('IMG ' + bad.join(','));
  fs.mkdirSync(path.dirname(file), { recursive: true });
  await page.screenshot({ path: file, type, ...(type === 'jpeg' ? { quality: 95 } : {}) });
  made.push(file);
}
for (const app of ['driver', 'rider']) for (const lang of ['ar', 'fr']) {
  for (const s of SLIDES[app][lang]) {
    const key = `${app}/${lang}/${s.id}`; if (ONLY && !key.startsWith(ONLY)) continue;
    await render(s.bubble ? bubbleSlide(s, lang) : shotSlide(s, lang), `${OUT}/${app}/${lang}/${app}-${lang}-${s.id}.png`, 1080, 1920, 'png');
  }
  const key = `${app}/${lang}/fg`; if (!ONLY || key.startsWith(ONLY)) await render(featureGraphic(FG[app][lang], lang), `${OUT}/${app}/${lang}/${app}-${lang}-feature-1024x500.jpg`, 1024, 500, 'jpeg');
}
await b.close();
console.log(made.length, 'files');
