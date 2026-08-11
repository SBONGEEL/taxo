// منقولٌ حرفاً بحرف من `design/DESIGN.md` §6 — وهو المصدر لا هذا الملف.
// أيُّ قيمةٍ تُعدَّل هنا وحدها تصير انحرافاً صامتاً عن نظام التصميم.
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // استبدالٌ كامل لا توسيع: سلالم Tailwind لا تشبه هذا التصميم، وتركُ
    // الافتراضيات متاحةً يعني أن أوّل `text-sm` يكتبها أحدُنا تُخرج المشروع
    // من النظام بلا إنذار. والمفاتيح **بالبكسل** فالصنفُ يشهد على قيمته.
    fontFamily: {
      sans: ['"IBM Plex Sans Arabic"', "system-ui", "sans-serif"],
      mono: ["ui-monospace", "Menlo", "monospace"],
    },
    fontSize: {
      "8.5": "8.5px", "9": "9px", "9.5": "9.5px", "10": "10px", "10.5": "10.5px",
      "11": "11px", "11.5": "11.5px", "12": "12px", "12.5": "12.5px",
      "13": "13px", "13.5": "13.5px", "14": "14px", "14.5": "14.5px",
      "15": "15px", "16": "16px", "17": "17px", "18": "18px", "19": "19px",
      "20": "20px", "21": "21px", "22": "22px", "23": "23px", "24": "24px",
      "25": "25px", "26": "26px", "30": "30px", "32": "32px", "34": "34px",
      "38": "38px", "44": "44px",
    },
    fontWeight: {
      light: "300", normal: "400", medium: "500", semibold: "600", bold: "700",
    },
    letterSpacing: {
      tighter: "-0.02em", tight: "-0.01em", normal: "0",
      brand: "0.04em", map: "0.08em", paper: "0.12em",
      wordmark: "0.14em", code: "0.42em",
    },
    lineHeight: {
      hero: "1.1", header: "1.25", tight: "1.5", snug: "1.6", note: "1.7",
      relaxed: "1.8", loose: "1.9", kv: "2.1", legal: "2.3",
    },
    borderRadius: {
      none: "0",
      "2": "2px",   // نقطة الوجهة المربّعة
      "3": "3px",
      "4": "4px",   // أعلى أعمدة الرسوم
      "5": "5px",
      "6": "6px",   // ورقة العقد
      "7": "7px", "8": "8px", "9": "9px",
      "10": "10px", // حقل اللوحة وأزرارها
      "11": "11px", "12": "12px",
      "13": "13px", // حقل المحمول
      "14": "14px", "15": "15px",
      "16": "16px", // البطاقات والزرّ الأساسي
      "18": "18px", "20": "20px",
      "22": "22px", // الورقة المدمجة
      "24": "24px", // الورقة المنبثقة
      "38": "38px",
      full: "99px",
    },
    spacing: {
      "0": "0", px: "1px",
      "2": "2px", "3": "3px", "4": "4px", "5": "5px", "6": "6px", "7": "7px",
      "8": "8px", "9": "9px", "10": "10px", "11": "11px", "12": "12px",
      "13": "13px", "14": "14px", "15": "15px", "16": "16px", "17": "17px",
      "18": "18px", "19": "19px", "20": "20px", "21": "21px", "22": "22px",
      "24": "24px", "26": "26px", "27": "27px",
      "28": "28px", "30": "30px", "32": "32px", "33": "33px", "34": "34px",
      "36": "36px", "38": "38px", "40": "40px", "42": "42px", "44": "44px",
      "46": "46px", "48": "48px", "52": "52px", "54": "54px", "58": "58px", "60": "60px",
      "62": "62px", "64": "64px", "66": "66px", "82": "82px",
      "150": "150px", // ارتفاع رسم أعمدة الساعات (§3.4)
      "170": "170px", // شريط الخريطة في تفاصيل الرحلة
      // بنيةٌ ثابتة
      status: "34px", nav: "66px", header: "58px",
    },
    extend: {
      colors: {
        // كل لون متغيّرُ CSS ليتبدّل الوضعان بلا شرطٍ في أيّ مكوّن.
        // الصيغة hex-في-متغيّر لا rgb-مفكوكة: التصميم يعرّفها hex،
        // وتفكيكُها إلى ثلاثة أعداد يفتح باب انحرافها عن المصدر.
        bg: "var(--bg)",
        surface: "var(--sur)",
        "surface-2": "var(--sur2)",
        line: "var(--brd)",
        ink: "var(--tx)",
        muted: "var(--mut)",
        accent: "var(--acc)",
        "accent-ink": "var(--inv)",
        ok: "var(--ok)",
        warn: "var(--warn)",
        danger: "var(--dng)",
        // رمزُ السِمة الوردية — افتراضُه `--tx`/`--inv` فلا أثر له مطفأً
        // (DESIGN.md §1.1-ب)
        brand: "var(--brand)",
        "brand-ink": "var(--brand-ink)",
        "brand-soft": "var(--brand-soft)",
        "brand-brd": "var(--brand-brd)",
        "stripe-a": "var(--sa)",
        "stripe-b": "var(--sb)",
        dim: "var(--dim)",
      },
      width: { device: "390px", drawer: "440px", side: "340px", "side-sm": "290px" },
      maxWidth: {
        modal: "560px", doc: "720px", paper: "620px", panel: "1780px", prose: "70ch",
      },
      minWidth: { menu: "236px" },
      boxShadow: {
        menu: "0 16px 44px rgba(0,0,0,.3)",
        toast: "0 10px 30px rgba(0,0,0,.3)",
        paper: "0 6px 26px rgba(0,0,0,.18)",
        sheet: "0 -6px 24px rgba(0,0,0,.07)",
      },
      backgroundImage: {
        // الخريطة النائبة — نفس الزاوية والعرض في التصميمات الثلاثة
        stripe:
          "repeating-linear-gradient(45deg, var(--sa), var(--sa) 10px, var(--sb) 10px, var(--sb) 20px)",
      },
      keyframes: {
        pulse: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".45" } },
        pulseSoft: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".35" } },
        slideup: {
          from: { transform: "translateY(30px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        fadein: { from: { opacity: "0" }, to: { opacity: "1" } },
        spin: { to: { transform: "rotate(360deg)" } },
        sweep: {
          "0%": { transform: "scale(.4)", opacity: ".55" },
          "100%": { transform: "scale(1.5)", opacity: "0" },
        },
        slidein: {
          from: { transform: "translateX(0) scale(.98)", opacity: "0" },
          to: { transform: "none", opacity: "1" },
        },
        rise: {
          from: { transform: "translateY(10px)", opacity: "0" },
          to: { transform: "none", opacity: "1" },
        },
      },
      animation: {
        pulse: "pulse 1.8s infinite",
        "pulse-fast": "pulse 1.2s infinite",
        "pulse-live": "pulseSoft 1.6s infinite",
        slideup: "slideup .3s",
        "slideup-fast": "slideup .25s",
        fadein: "fadein .25s",
        "fadein-slow": "fadein .3s",
        "fadein-fast": "fadein .2s",
        spin: "spin 1s linear infinite",
        "spin-slow": "spin 2.4s linear infinite",
        sweep: "sweep 2.2s ease-out infinite",
        "sweep-delayed": "sweep 2.2s ease-out infinite 1.1s",
        slidein: "slidein .22s",
        rise: "rise .22s",
        "rise-fast": "rise .14s",
      },
    },
  },
  plugins: [],
};
