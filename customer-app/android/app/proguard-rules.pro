# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
#-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile

# **R8 مفعَّلٌ في الإصدار** (ملاحظةُ Google على 960: إخفاءُ الرموز ٢٪ والحدُّ ٢٥٪، الموعدُ فبراير ٢٠٢٧ — design/CODE-HEALTH-2026-10.md ٤-١).
# **ما يُنادى بالانعكاس يبقى باسمه**: الجسرُ يجد الإضافاتِ ودوالَّها بأسمائها، والنظامُ يجد خدماتِنا ومستقبلاتِنا من البيان —
# فتُبقى Capacitor وإضافاتُه وشيفرتُنا كلُّها، **ويُصغَّر ويُخفى ما سواها** (androidx · Firebase · Material · Kotlin) وهو جُلُّ الملفّ.
-keep class com.getcapacitor.** { *; }
-keep @com.getcapacitor.annotation.CapacitorPlugin class * { *; }
-keep class * extends com.getcapacitor.Plugin { *; }
-keep class com.capacitorjs.plugins.** { *; }
-keep class com.aparajita.** { *; }
-keep class ly.tajora.** { *; }
-keepclassmembers class * { @android.webkit.JavascriptInterface <methods>; }
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod,Exceptions
# **أسطرُ تقارير الأعطال تبقى مقروءة** — ويُرفع `mapping.txt` مع الحزمة
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
