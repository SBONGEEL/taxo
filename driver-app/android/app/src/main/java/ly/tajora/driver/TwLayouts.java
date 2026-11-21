package ly.tajora.driver;

/** تخطيطُ كلِّ ودجةٍ بحجمها — مولَّدٌ من tools/gen-android-widgets.py — لا يُحرَّر باليد. */
final class TwLayouts {
    private TwLayouts() {}

    static int of(String kind, int size) {
        switch (kind) {
            case "status": return size == 2 ? R.layout.tw_status_l : size == 1 ? R.layout.tw_status_m : R.layout.tw_status_s;
            case "goal": return size == 2 ? R.layout.tw_goal_l : size == 1 ? R.layout.tw_goal_m : R.layout.tw_goal_s;
            case "subscription": return size == 2 ? R.layout.tw_subscription_l : size == 1 ? R.layout.tw_subscription_m : R.layout.tw_subscription_s;
            case "busy": return size == 2 ? R.layout.tw_busy_l : size == 1 ? R.layout.tw_busy_m : R.layout.tw_busy_s;
            case "ride": return size == 2 ? R.layout.tw_ride_l : size == 1 ? R.layout.tw_ride_m : R.layout.tw_ride_s;
            default: return R.layout.tw_signed_out;
        }
    }
}
