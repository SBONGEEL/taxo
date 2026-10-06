import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// **ترتيبُ الأوراق مقصود** (§٦٢/١٦): رموزُ TAXO 2.0 وأوّلياتُها أوّلاً، ثمّ إطارُ اللوحة وعُدّتُها وشاشاتُها، **ثمّ Tailwind أخيراً**
// — فأصنافُ العُدّة بمحدِّدٍ واحد، **وصنفُ المستدعي يغلب عند التساوي** (`border-danger text-danger` على زرٍّ ثانويّ).
import "@/taxo2";
import "@/t2/frame.css";
import "@/t2/kit.css";
import "@/t2/screens.css";
import "@/index.css";

import App from "@/App";
import { installCrashReports } from "@/lib/crash-reports";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// **قبل أيِّ شاشة**: عطبٌ في الإقلاع نفسِه يقع قبل أن تُرسم أولُ ورقة،
// وتركيبٌ داخل مكوّنٍ يفوته ما سقط قبله.
installCrashReports("panel");
