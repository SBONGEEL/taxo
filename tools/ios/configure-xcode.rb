# frozen_string_literal: true
#
# **يُكمل مشروعَ Xcode عند البناء** (أمرُ المالك ٢٠٢٦-١١-١٧) — `ruby tools/ios/configure-xcode.rb <customer-app|driver-app>`
#
# **ولمَ عند البناء لا في الإيداع**: `project.pbxproj` يكتبه Xcode، وتحريرُه بيدٍ نصّاً يُتلفه (معرّفاتٌ عشوائيّةٌ وأقسامٌ
# مترابطة). فهذا يستعمل `xcodeproj` — المكتبةَ نفسَها التي يكتب بها CocoaPods المشروعَ — **ومكرَّرُه لا يضيف شيئاً**:
# كلُّ خطوةٍ تسأل أهي قائمةٌ قبل أن تضيف.
#
# ويضيف ثلاثة:
#   1) **نصوصَ الأذونات بالفرنسيّة** (`fr.lproj/InfoPlist.strings`) — والعربيّةُ في `Info.plist` نفسِه (لغةُ التطوير `ar`).
#   2) **امتدادَ الأدوات `TaxoWidgets`** — أداةُ الشاشة الرئيسيّة والنشاطُ الحيُّ للرحلة (iOS 16.2+)، مضمَّناً في التطبيق.
#   3) **اللغاتِ المعروفة** `ar` و`fr` في المشروع.
#
# **ولا يمسّ أندرويد**، ولا يُشغَّل إلا على macOS من `tools/build-ios.mjs`.
require 'xcodeproj'

app_name = ARGV[0]
kinds = { 'customer-app' => 'rider', 'driver-app' => 'driver' }
kind = kinds[app_name] or abort("الاستعمال: ruby tools/ios/configure-xcode.rb <customer-app|driver-app>")

root = File.expand_path('../..', __dir__)
ios = File.join(root, app_name, 'ios', 'App')
project = Xcodeproj::Project.open(File.join(ios, 'App.xcodeproj'))
app = project.targets.find { |t| t.name == 'App' } or abort('✗ لا هدفَ App في المشروع')
changed = []

# ── ٣) اللغات ─────────────────────────────────────────────────────────────
regions = project.root_object.known_regions
%w[ar fr].each do |lang|
  next if regions.include?(lang)
  regions << lang
  changed << "لغة #{lang}"
end

# ── ١) نصوصُ الأذونات بالفرنسيّة ─────────────────────────────────────────
app_group = project.main_group.children.find { |g| g.respond_to?(:path) && g.path == 'App' } or abort('✗ لا مجموعةَ App')
variant = app_group.children.find { |c| c.isa == 'PBXVariantGroup' && c.name == 'InfoPlist.strings' }
unless variant
  variant = app_group.new_variant_group('InfoPlist.strings')
  Dir[File.join(ios, 'App', '*.lproj', 'InfoPlist.strings')].sort.each do |file|
    lang = File.basename(File.dirname(file), '.lproj')
    ref = variant.new_reference("#{lang}.lproj/InfoPlist.strings")
    ref.name = lang
  end
  app.resources_build_phase.add_file_reference(variant)
  changed << 'InfoPlist.strings'
end

# ── ٢) امتدادُ الأدوات ───────────────────────────────────────────────────
EXT = 'TaxoWidgets'
unless project.targets.any? { |t| t.name == EXT }
  ext = project.new_target(:app_extension, EXT, :ios, '16.2', nil, :swift)
  group = project.main_group.new_group(EXT)
  sources = [
    File.join(root, 'ios-native', 'TaxoWidgets', 'TaxoWidgets.swift'),
    File.join(root, 'ios-native', 'TaxoNative', 'Sources', 'Shared', 'TaxoRideAttributes.swift'),
  ]
  refs = sources.map do |file|
    abort("✗ غائب: #{file}") unless File.exist?(file)
    ref = group.new_file(file)
    ref.source_tree = '<absolute>'
    ref
  end
  ext.add_file_references(refs)

  app_settings = app.build_configurations.first.build_settings
  ext.build_configurations.each do |config|
    s = config.build_settings
    s['INFOPLIST_FILE'] = File.join(root, 'ios-native', 'TaxoWidgets', 'Info.plist')
    s['GENERATE_INFOPLIST_FILE'] = 'NO'
    s['PRODUCT_BUNDLE_IDENTIFIER'] = '$(TAXO_APP_ID).widgets'
    s['PRODUCT_NAME'] = '$(TARGET_NAME)'
    s['TAXO_APP_KIND'] = kind
    s['SWIFT_VERSION'] = '5.0'
    s['TARGETED_DEVICE_FAMILY'] = '1'
    s['IPHONEOS_DEPLOYMENT_TARGET'] = '16.2'
    s['SKIP_INSTALL'] = 'YES'
    s['CODE_SIGN_STYLE'] = 'Automatic'
    s['MARKETING_VERSION'] = app_settings['MARKETING_VERSION'] || '1.0'
    s['CURRENT_PROJECT_VERSION'] = app_settings['CURRENT_PROJECT_VERSION'] || '1'
    s['LD_RUNPATH_SEARCH_PATHS'] = ['$(inherited)', '@executable_path/Frameworks', '@executable_path/../../Frameworks']
    s['SWIFT_EMIT_LOC_STRINGS'] = 'YES'
  end

  app.add_dependency(ext)
  embed = app.copy_files_build_phases.find { |p| p.name == 'Embed Foundation Extensions' } ||
          app.new_copy_files_build_phase('Embed Foundation Extensions')
  embed.symbol_dst_subfolder_spec = :plug_ins
  file = embed.add_file_reference(ext.product_reference, true)
  file.settings = { 'ATTRIBUTES' => ['RemoveHeadersOnCopy'] }
  changed << EXT
end

if changed.empty?
  puts "✓ #{app_name}: المشروعُ مكتملٌ سلفاً"
else
  project.save
  puts "✓ #{app_name}: أُضيف — #{changed.join(' · ')}"
end
