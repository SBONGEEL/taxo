package ly.tajora.rider;

/** تخطيطُ كلِّ ودجةٍ بحجمها — مولَّدٌ من tools/gen-android-widgets.py — لا يُحرَّر باليد. */
final class TwLayouts {
    private TwLayouts() {}

    static int of(String kind, int size) {
        switch (kind) {
            case "request": return size == 2 ? R.layout.tw_request_l : size == 1 ? R.layout.tw_request_m : R.layout.tw_request_s;
            case "on_the_way": return size == 2 ? R.layout.tw_on_the_way_l : size == 1 ? R.layout.tw_on_the_way_m : R.layout.tw_on_the_way_s;
            case "quick": return size == 2 ? R.layout.tw_quick_l : size == 1 ? R.layout.tw_quick_m : R.layout.tw_quick_s;
            case "favorites": return size == 2 ? R.layout.tw_favorites_l : size == 1 ? R.layout.tw_favorites_m : R.layout.tw_favorites_s;
            case "wallet": return size == 2 ? R.layout.tw_wallet_l : size == 1 ? R.layout.tw_wallet_m : R.layout.tw_wallet_s;
            case "discount": return size == 2 ? R.layout.tw_discount_l : size == 1 ? R.layout.tw_discount_m : R.layout.tw_discount_s;
            case "schedule": return size == 2 ? R.layout.tw_schedule_l : size == 1 ? R.layout.tw_schedule_m : R.layout.tw_schedule_s;
            case "services": return size == 2 ? R.layout.tw_services_l : size == 1 ? R.layout.tw_services_m : R.layout.tw_services_s;
            case "current": return size == 2 ? R.layout.tw_current_l : size == 1 ? R.layout.tw_current_m : R.layout.tw_current_s;
            case "home": return size == 2 ? R.layout.tw_home_l : size == 1 ? R.layout.tw_home_m : R.layout.tw_home_s;
            case "work": return size == 2 ? R.layout.tw_work_l : size == 1 ? R.layout.tw_work_m : R.layout.tw_work_s;
            case "points": return size == 2 ? R.layout.tw_points_l : size == 1 ? R.layout.tw_points_m : R.layout.tw_points_s;
            case "recent": return size == 2 ? R.layout.tw_recent_l : size == 1 ? R.layout.tw_recent_m : R.layout.tw_recent_s;
            case "offers": return size == 2 ? R.layout.tw_offers_l : size == 1 ? R.layout.tw_offers_m : R.layout.tw_offers_s;
            case "nearest": return size == 2 ? R.layout.tw_nearest_l : size == 1 ? R.layout.tw_nearest_m : R.layout.tw_nearest_s;
            default: return R.layout.tw_signed_out;
        }
    }
}
