<#
.SYNOPSIS
  يسحب نسخةً احتياطيةً من الخادم إلى هذا الجهاز (`design/BACKUP-AND-RESTORE.md` §٥).

.DESCRIPTION
  **SSH و rsync فقط — لا نداءَ HTTP ولا رمزَ جلسة.** وهذا هو السبب لا التبسيط:
  اللحظةُ التي تحتاج فيها نسخةً هي اللحظةُ التي يكون فيها التطبيقُ ساقطاً،
  فسحبٌ يمرّ بالـAPI هو بابٌ يُغلق مع ما تريد إنقاذه.

.EXAMPLE
  .\pull-backup.ps1                     # آخرُ نسخةٍ موجودة
  .\pull-backup.ps1 -Date 2026-08-14    # نسخةُ يومٍ بعينه
  .\pull-backup.ps1 -Now                # يُشغّل نسخةً جديدةً على الخادم ثم يسحبها
#>
[CmdletBinding()]
param(
  # مضيفُ SSH كما في `~/.ssh/config` أو `user@host`
  [string]$Server = $env:TAXO_BACKUP_SERVER,
  # مسارُ المشروع على الخادم (حيث `docker-compose.yml`)
  [string]$RemoteProject = $(if ($env:TAXO_REMOTE_PROJECT) { $env:TAXO_REMOTE_PROJECT } else { "/opt/taxo" }),
  # وجهةُ الحفظ على هذا الجهاز
  [string]$Destination = $(if ($env:TAXO_BACKUP_DEST) { $env:TAXO_BACKUP_DEST } else { "D:\taxo-backups" }),
  [string]$Date,
  [switch]$Now
)

$ErrorActionPreference = "Stop"

if (-not $Server) {
  throw "حدّد -Server أو اضبط TAXO_BACKUP_SERVER (مثال: taxo@1.2.3.4)"
}

$RemoteRoot = "$RemoteProject/backend/var/backups"

function Invoke-Remote([string]$Command) {
  # `ssh` يعيد رقمَ خروج الأمر البعيد، و PowerShell لا يرفع عليه — فيُفحص يدوياً
  $output = & ssh $Server $Command
  if ($LASTEXITCODE -ne 0) { throw "فشل أمرٌ على الخادم: $Command" }
  return $output
}

if ($Now) {
  Write-Host "==> تشغيل نسخةٍ جديدة على الخادم" -ForegroundColor Cyan
  # **نفسُ السكربت الذي تناديه المهمّةُ المجدولة** — فلا مسارَ ثانٍ يُنتج نسخةً
  # بشكلٍ مختلف، وهو شرطُ الخطة
  Invoke-Remote "cd $RemoteProject && docker compose exec -T backend bash /app/scripts/backup.sh" | Out-Host
}

if ($Date) {
  $stamp = ($Date -replace '-', '')
  $name = Invoke-Remote "ls -1 $RemoteRoot | grep -E '^taxo-$stamp' | tail -1"
  if (-not $name) { throw "لا توجد نسخةٌ بتاريخ $Date" }
} else {
  $name = Invoke-Remote "ls -1 $RemoteRoot | grep -E '^taxo-' | tail -1"
  if (-not $name) { throw "لا توجد نسخٌ على الخادم" }
}
$name = $name.Trim()
Write-Host "==> النسخة: $name" -ForegroundColor Cyan

$local = Join-Path $Destination $name
New-Item -ItemType Directory -Force -Path $local | Out-Null

Write-Host "==> النقل" -ForegroundColor Cyan
# `--partial` كي لا يُعاد نقلُ جيجابايتٍ من الصفر بعد انقطاع
& rsync -az --partial --info=progress2 "${Server}:${RemoteRoot}/${name}/" "$local/"
if ($LASTEXITCODE -ne 0) { throw "فشل rsync" }

Write-Host "==> التحقق من البصمات" -ForegroundColor Cyan
# **نقلٌ مبتورٌ يصمت، ونسخةٌ نصفُها لا تُكتشف إلا يومَ الاستعادة** — فتُفحص هنا،
# على الملفات **كما هي مخزَّنة** (مشفَّرةً كانت أو لا): البيانُ يحمل بصماتِ ما
# يُنقل فعلاً، فلا يحتاج الفحصُ عبارةَ المرور على هذا الجهاز
$manifest = Get-Content (Join-Path $local "manifest.json") -Raw | ConvertFrom-Json
$bad = @()
foreach ($entry in $manifest.files.PSObject.Properties) {
  $file = Join-Path $local $entry.Name
  if (-not (Test-Path $file)) { $bad += "$($entry.Name): مفقود"; continue }
  $actual = (Get-FileHash -Algorithm SHA256 -Path $file).Hash.ToLower()
  if ($actual -ne $entry.Value.sha256) { $bad += "$($entry.Name): بصمةٌ مختلفة" }
}
if ($bad.Count -gt 0) {
  # **ولا تُوسَم «سُحبت»**: الوسمُ يجعل الخادمَ يعدّها محفوظةً فيحذفها يوماً،
  # وما بيدك نصفُ ملف
  Write-Host "✗ النسخةُ مبتورة:" -ForegroundColor Red
  $bad | ForEach-Object { Write-Host "   $_" -ForegroundColor Red }
  throw "فشل التحقق — لم تُوسَم النسخةُ مسحوبةً"
}
Write-Host "✓ البصمات مطابقة" -ForegroundColor Green

Write-Host "==> وسمُ «سُحبت» على الخادم" -ForegroundColor Cyan
# **علامةٌ على القرص لا صفٌّ في القاعدة**: اللوحةُ تقرؤها من القرص، ويبقى
# السحبُ مستقلاً عن عمل التطبيق تماماً
$marker = "{`"pulled_at`": `"$((Get-Date).ToUniversalTime().ToString('o'))`", `"host`": `"$env:COMPUTERNAME`"}"
Invoke-Remote "printf '%s' '$marker' > $RemoteRoot/$name/.pulled" | Out-Null

Write-Host ""
Write-Host "تمّت: $local" -ForegroundColor Green
Write-Host "تذكير: عبارةُ فكِّ التشفير ومفتاحُ Fernet ليسا في هذا الأرشيف — وبغيرهما لا تُفتح النسخة." -ForegroundColor Yellow
