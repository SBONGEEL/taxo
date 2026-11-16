package ly.tajora.driver;

import android.app.PendingIntent;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/**
 * <b>بلاطةُ «متّصل / غير متّصل»</b> في الإعدادات السريعة (SPEC §١٠٣ المرحلة A/4).
 *
 * <p><b>تقرأ ولا تقرّر</b>: حالُها ما كتبه الويبُ في {@code online} (يكتبه حين يتّصل أو ينفصل، والخدمةُ تمحوه حين تموت)، ولمسُها
 * <b>يفتح التطبيقَ بفعل {@code go_online}/{@code go_offline}</b> فينفّذه الويبُ بمساره القائم — فحصُ الاشتراك والأذونات والموقع كما هو.
 * ومطفأةً لدولته ({@code tile=false}) تبقى «غيرَ متاحة» بلا لمسة.
 */
public class OnlineTileService extends TileService {

    @Override
    public void onStartListening() {
        super.onStartListening();
        refresh();
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(LauncherPlugin.PREFS, MODE_PRIVATE);
    }

    private void refresh() {
        Tile tile = getQsTile();
        if (tile == null) return;
        boolean enabled = prefs().getBoolean("tile", false);
        boolean online = prefs().getBoolean("online", false);
        tile.setState(!enabled ? Tile.STATE_UNAVAILABLE : online ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE);
        tile.setLabel(online ? "متّصل" : "غير متّصل");
        tile.updateTile();
    }

    @Override
    public void onClick() {
        super.onClick();
        if (!prefs().getBoolean("tile", false)) return;
        boolean online = prefs().getBoolean("online", false);
        Intent open = new Intent(this, MainActivity.class)
            .putExtra(LauncherPlugin.EXTRA, online ? "go_offline" : "go_online")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (Build.VERSION.SDK_INT >= 34) {
            startActivityAndCollapse(PendingIntent.getActivity(this, 41, open,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
        } else {
            startActivityAndCollapse(open);
        }
    }
}
