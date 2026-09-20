import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "@/App";
import "@/index.css";
import { installCrashReports } from "@/lib/crash-reports";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// **قبل أيِّ شاشة**: عطبٌ في الإقلاع نفسِه يقع قبل أن تُرسم أولُ ورقة،
// وتركيبٌ داخل مكوّنٍ يفوته ما سقط قبله.
installCrashReports("panel");
