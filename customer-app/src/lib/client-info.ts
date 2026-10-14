/** **ما يرافق ملاحظةَ المستخدم ليُعرف ما كان يشغّل** (SPEC §٧٦/٤) — إصدارُ الغلاف وحزمةُ الشاشات والمنصّةُ والمسار.
 *
 * **والإصدارُ إصداران** لأن الشاشاتِ تُحمَّل من الخادم (`server.url`): **الغلافُ** المثبَّت من المتجر (`App.getInfo`) **وحزمةُ الشاشات**
 * (اسمُ ملفِّ الدخول الذي حمّلته الصفحة) — والخللُ يُصلَح في الثانية. **والمسارُ قالبُه لا معرّفاتُه** (`maskPath`)، كتقارير الأعطال.
 */

import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

import { maskPath } from "@/lib/breadcrumbs";

export interface ClientInfo {
  app_version?: string;
  web_build?: string;
  platform: string;
  route: string;
}

export async function clientInfo(): Promise<ClientInfo> {
  let appVersion: string | undefined;
  if (Capacitor.isNativePlatform()) {
    try {
      const info = await App.getInfo();
      appVersion = `${info.version}+${info.build}`.slice(0, 40);
    } catch {
      appVersion = undefined;
    }
  }
  const entry = document.querySelector<HTMLScriptElement>('script[type="module"][src*="/assets/"]');
  const webBuild = entry?.src.split("/").pop()?.slice(0, 80) || undefined;
  let route = "/";
  try {
    route = maskPath(window.location.pathname).slice(0, 120);
  } catch {
    route = "/";
  }
  return { app_version: appVersion, web_build: webBuild, platform: Capacitor.getPlatform(), route };
}
