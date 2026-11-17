# **ملحقاتُ iOS الأصليّة للتطبيقين** (أمرُ المالك ٢٠٢٦-١١-١٧) — نظائرُ إضافات Java في أندرويد، **بالأسماء نفسِها**
# التي تناديها شيفرةُ الويب (`registerPlugin("Permissions")` …)، فلا يتغيّر في الويب إلا ما لا بدّ منه.
#
# **ولمَ حزمةٌ محلّيّةٌ لا ملفّاتٌ في هدف App**: ملفُّ Swift في الهدف يحتاج تحريرَ `project.pbxproj` بيد —
# وهو ملفٌّ يكتبه Xcode ويُتلفه التحريرُ النصّيّ. والحزمةُ يقرؤها CocoaPods من هذا المجلّد بنمطٍ واحد.
# **ولا تمسّ أندرويد**: لا `package.json` ولا `capacitor.config` يذكرها، فـ`cap sync android` لا يراها.
#
# **و`resources` لا `resource_bundles` بقصد**: أصواتُ الإشعار ونصوصُ `InfoPlist.strings` يجب أن تقع في
# الحزمة الرئيسيّة (`App.app/`) — فالنظامُ يبحث عن صوت الإشعار هناك وحدَه.
Pod::Spec.new do |s|
  s.name             = 'TaxoNative'
  s.version          = '1.0.0'
  s.summary          = 'TAXO native iOS plugins (rider and driver).'
  s.license          = { :type => 'Proprietary' }
  s.homepage         = 'https://taxo.tajora.ly'
  s.author           = 'TAXO'
  s.source           = { :path => '.' }
  s.ios.deployment_target = '15.0'
  s.swift_version    = '5.9'
  s.source_files     = 'Sources/**/*.swift'
  s.resources        = ['Resources/sounds/*.caf']
  s.dependency 'Capacitor'
  s.frameworks       = 'CoreLocation', 'UserNotifications', 'AVFoundation', 'Vision', 'Speech', 'StoreKit', 'CallKit'
end
