# جردُ بند اللوحة ٤ — «تعديلُ/حذفُ أيِّ عنصر» (قائمةُ المالك ٢٠٢٦-١١-١٠، مقيسٌ بالكود ٢٠٢٦-١١-١٧)

**الطريقة**: لكلِّ ملفٍّ فيه `<Table>` في `admin-panel/src`، تُعدّ نداءاتُ الخادم المستوردةُ من `@/api` بأسمائها: تعديل
(`update/edit/patch/set/save/review/approve/reject/resolve/mark…`) · إيقاف/حذف (`delete/remove/cancel/revoke/suspend…`) · إنشاء.
**وحدُّها مكتوب**: العدُّ بالاسم المستورد — شاشةٌ تفتح ملفّاً (الكبتن/الراكب) يُعدَّل من داخله تُعدّ صفراً هنا وتعديلُها في `Profile`؛
والعددُ أبوابٌ لا أزرارٌ مقيسةٌ في متصفّح.

**والحذفُ ليس هدفاً في كلِّ صنف — بقاعدةٍ مكتوبة** (`CLAUDE.md`، «الثانية»): **لا حذفَ صفٍّ على الإنتاج**، والإيقافُ تعليق.
فالمالُ والمستخدمون والرحلاتُ **تُوقَف أو تُلغى بقيدٍ مقابل** ولا تُحذف؛ **وعناصرُ الإعداد** (لافتات، بلاطات، باقات، مسوّداتُ سياسات، إصدارات)
**تُحذف**؛ **والأماكنُ والمرافقُ ومساراتُ المدن** «أخفِه/عطّل» بدل الحذف.

| الملف | تعديل | إيقاف/حذف | إنشاء | أبوابُ الإيقاف/الحذف |
|---|---:|---:|---:|---|
| `components/Advances.tsx` | 0 | 0 | 0 |  |
| `components/CancellationCharges.tsx` | 0 | 0 | 0 |  |
| `components/Deactivations.tsx` | 0 | 0 | 0 |  |
| `components/DriverDebts.tsx` | 0 | 0 | 0 |  |
| `components/PendingDeletions.tsx` | 0 | 0 | 0 |  |
| `components/Referrals.tsx` | 0 | 0 | 0 |  |
| `components/Storefront.tsx` | 2 | 3 | 3 | deleteBannerImage deletePromoBanner deleteServiceTile |
| `components/VerificationCampaign.tsx` | 0 | 1 | 1 | cancelVerificationCampaign |
| `screens/Audit.tsx` | 0 | 0 | 0 |  |
| `screens/Campaigns.tsx` | 1 | 1 | 1 | cancelCampaign |
| `screens/CardPay.tsx` | 2 | 0 | 0 |  |
| `screens/ChatReports.tsx` | 0 | 0 | 0 |  |
| `screens/ChatRooms.tsx` | 0 | 0 | 0 |  |
| `screens/Disputes.tsx` | 1 | 0 | 0 |  |
| `screens/Drivers.tsx` | 5 | 2 | 0 | revokeIntercityPermit suspendDriver |
| `screens/Errors.tsx` | 1 | 0 | 0 |  |
| `screens/Facilities.tsx` | 1 | 0 | 1 |  |
| `screens/Finance.tsx` | 4 | 0 | 0 |  |
| `screens/FinanceSummary.tsx` | 0 | 0 | 0 |  |
| `screens/Intercity.tsx` | 1 | 0 | 1 |  |
| `screens/PaymentProtection.tsx` | 0 | 0 | 0 |  |
| `screens/PaymentSystem.tsx` | 3 | 1 | 2 | cancelPaymentRequest |
| `screens/Payments.tsx` | 0 | 0 | 0 |  |
| `screens/Places.tsx` | 1 | 0 | 1 |  |
| `screens/Policies.tsx` | 1 | 1 | 2 | deletePolicyDraft |
| `screens/Releases.tsx` | 1 | 1 | 1 | deleteRelease |
| `screens/Reports.tsx` | 0 | 0 | 0 |  |
| `screens/Riders.tsx` | 0 | 0 | 0 |  |
| `screens/Rides.tsx` | 0 | 0 | 0 |  |
| `screens/SkinPurchases.tsx` | 0 | 0 | 0 |  |
| `screens/Subscriptions.tsx` | 1 | 2 | 1 | cancelSubscription deletePlan |
| `screens/TaxoCards.tsx` | 8 | 3 | 5 | cancelCardBatch cancelGift cancelTaxoCard |
| `screens/Transfers.tsx` | 3 | 0 | 0 |  |
| `screens/UnconfirmedPayments.tsx` | 1 | 0 | 0 |  |
| `screens/Users.tsx` | 1 | 0 | 0 |  |
| `screens/WhopPay.tsx` | 2 | 0 | 0 |  |

## الفجوات — تُقاس قبل أن تُبنى

1. **قوائمُ قراءةٍ بلا فعل** (`Audit` · `Reports` · `FinanceSummary` · `Payments` · `Rides` · `SkinPurchases` · `PaymentProtection`): سجلّاتٌ وتقارير — **الصحيحُ ألّا تُعدَّل**.
2. **`ChatReports`/`ChatRooms`** — **قِيس ٢٠٢٦-١١-١٨: ليس نقصاً**. `ChatReports.tsx` يستورد `handleChatReport`
   (`POST /admin/chat-reports/{id}/handle` بملاحظة)، **والطريقةُ لم تعدّه لأن «handle» ليس في قائمة الأفعال** — حدُّ العدِّ بالاسم بعينه.
3. **`Users` (الموظفون)** — **قِيس ٢٠٢٦-١١-١٨: نقصٌ حقيقيّ، ومقصودٌ في أصله**. تعديلُ الصلاحيّات قائم (`setAdminPermissions`)،
   **ولا بابَ لإيقاف موظّف**: `_set_blocked` (`routers/admin_users.py`) يرفض حسابَ `admin`/`support` بنصّه — «بابٌ يُغلق به مشرفٌ على
   زملائه». **والأثرُ**: موظّفٌ يترك العمل يبقى حسابُه يدخل اللوحة، ونزعُ صلاحيّاته كلِّها يُفرغه ولا يمنع دخوله.
   **والتوصية**: بابٌ **للمالك وحدَه** (`owner`) — `POST /admin/staff/{id}/suspend` و`/unsuspend` على `is_blocked` القائم (بلا ترحيلة)،
   **لا على نفسه ولا على مالكٍ آخر**، بسببٍ مكتوبٍ وقيدِ تدقيق، وزرٌّ في `Users.tsx` يظهر للمالك وحدَه. فتبقى العلّةُ الأصليّة قائمة
   (لا مشرفَ يغلق زميلاً) ويُسدّ الفراغ. **لم يُبنَ بعد** — يُبنى في دفعة اللوحة التالية خلف اختبارٍ يحاول بحسابِ `admin` فيُرفض.
4. **`Riders`/`Drivers`/`Advances`/`DriverDebts`/`Deactivations`**: أفعالُها من الملفّ الشخصيّ ومن مكوّناتٍ مستوردةٍ بغير `@/api` — صفرُها هنا حدُّ الطريقة لا نقص.
