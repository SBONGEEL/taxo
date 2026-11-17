# أمرُ المالك ٢٠٢٦-١١-١٧ — صوتُ «بيب بيب TAXO» (النصُّ كما قاله)

> **كُتب لحظةَ وروده.** يجري موازياً و**لا يؤخّر افتتاح ليبيا**. الأصواتُ الجديدةُ **مطفأةٌ حتى يختار المالك**؛ ويُشحن مع تحديث التطبيق القادم (مع المرحلة A).
> وإرسالُ الخيارات (MP3 لكلِّ خيار + تسجيلُ شاشة) **رسالةٌ مسموحة** قبل التقرير الأخير، كلوحة الأيقونات.

New task: create a beautiful custom notification sound for TAXO, a «بيب بيب TAXO» sound that is modern, fresh and professional. Do not stop until it is finished, and do not delay the Libya launch for it.

1. Two sounds, one family (same style, same brand feel):
   A. Driver, new ride request: a clear, attention-grabbing ringtone built on «بيب بيب» plus a short TAXO sound signature. It loops like an incoming call until the driver accepts, declines or the request expires. It must be heard in a car with traffic noise and the radio on, but never harsh or annoying.
   B. Rider, «الكابتن وصل»: a short, friendly «بيب بيب» with the same TAXO signature, about 1 to 2 seconds, pleasant and premium.
   Also make a matching soft sound for other ride updates (driver accepted, ride started, ride ended), so the whole app sounds like one brand.

2. Make 3 different style options for each sound, for me to choose:
   - Option 1: clean electronic «بيب بيب» with a short musical chime (modern, minimal).
   - Option 2: «بيب بيب» with a spoken or sung «TAXO» at the end (a sonic logo).
   - Option 3: a warmer musical version, like the sounds of top ride and delivery apps in quality, but original.
   All original. Do not copy or imitate the sound of any other app or brand. If you use any sound tool or library, it must allow commercial use; write the license in the repo.

3. Technical quality:
   - Clean mix, no clipping, normalized loudness, clear on cheap phone speakers and in a car.
   - Formats: Android (OGG or WAV in res/raw) and iOS (CAF or AIFF, under 30 seconds as Apple requires). Give the iOS files to the iOS agent through HANDOFF.md; do not touch its folder.
   - A matching vibration pattern for each sound (the driver one strong, like a call; the rider one short).

4. Send me the options to listen to: one short MP3 per option, labeled clearly (driver 1, 2, 3; rider 1, 2, 3), plus a short recording of each playing on the phone screen. Keep the new sounds OFF until I choose.

5. After I choose, build it:
   - Android: new notification channels with the chosen sounds (a channel's sound cannot change after it is created, so use new channel IDs and keep the old ones working for old app versions). The driver request rings on the locked screen as in the Kotlin stage A.
   - Web and the apps loaded from the server: play the same sounds where the browser allows.
   - iOS: the same sounds through the iOS agent.
   - Panel: a switch per country for the new sounds, and a volume note in the driver app («ارفع صوت الرنين»).
   - Settings in both apps: the user can turn the sound off or keep vibration only, except the driver ride request, which always rings while the driver is online.
6. Release with the next app update (with Kotlin stage A for Android), and include it in the final report.

Conditions: no change to fares, pricing or money tables. Never skip a deploy gate. No heavy local work; check the heavy lock first.
«اكمل ولا تتوقف ايضا»
