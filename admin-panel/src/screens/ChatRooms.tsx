/** **غرفُ المحادثة** (أمرُ المالك ١٦/١١، بندُ اللوحة ٧) — كلُّ رحلةٍ فيها رسائل: طرفاها، وكم رسالة، وآخرُها، وبلاغاتُها المفتوحة.
 *
 * **بلا نصوص**: القائمةُ تقول من حادث من، والنصُّ يُقرأ بفتح الغرفة في شاشة الرحلة (`/rides?open=…`) — وذلك سطرُ تدقيقٍ مستقلّ.
 * **وبصلاحية `trip_chats.read`**، **وفتحُ القائمة نفسِه يُسجَّل** (الخادمُ يكتبه). ما فيه بلاغٌ مفتوحٌ أوّلاً ثمّ الأحدث.
 * والبحثُ باسم الراكب أو الكبتن أو بأوّل رقم الرحلة، وتتبع مبدّلَ السوق كبقية اللوحة.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listChatRooms } from "@/api/endpoints";
import type { AdminChatRoom } from "@/api/types";
import { TripChatsRefusal } from "@/components/RideComms";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Field } from "@/components/ui/Field";
import { ErrorNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { moment } from "@/lib/format";
import { TRIP_CHATS_READ, useMyPermissions } from "@/lib/permissions";

import "@/t2/comms.css";

const COLUMNS = "1.2fr 1.2fr 0.6fr 1fr 0.8fr 0.8fr";

export function ChatRoomsScreen() {
  const held = useMyPermissions();
  const { country } = useCountry();
  const navigate = useNavigate();
  const [scope, setScope] = useState<"all" | "reported">("all");
  const [query, setQuery] = useState("");
  const [applied, setApplied] = useState("");
  const [rows, setRows] = useState<AdminChatRoom[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refused, setRefused] = useState(false);
  const allowed = held?.has(TRIP_CHATS_READ) === true;

  // **البحثُ بعد توقّف الكتابة** — كلُّ طلبٍ سطرٌ في التدقيق، فلا يُطلب مع كلِّ حرف
  useEffect(() => {
    const timer = window.setTimeout(() => setApplied(query.trim()), 400);
    return () => window.clearTimeout(timer);
  }, [query]);

  const load = useCallback(async () => {
    setRows(null);
    setError(null);
    try {
      setRows(
        await listChatRooms({
          country_code: country,
          q: applied || undefined,
          only_reported: scope === "reported" ? true : undefined,
          limit: 200,
        }),
      );
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 403) setRefused(true);
      else setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الغرف");
    }
  }, [applied, country, scope]);

  useEffect(() => {
    if (allowed) void load();
  }, [allowed, load]);

  return (
    <Shell title="غرف المحادثة" subtitle="كلُّ رحلةٍ دارت فيها رسائل — بلا نصوص هنا، والنصُّ يُفتح من الرحلة، وكلُّ فتحٍ يُسجَّل باسمك">
      {held === null ? null : !allowed || refused ? (
        <TripChatsRefusal />
      ) : (
        <>
          <Pills
            value={scope}
            onPick={(key) => setScope(key)}
            options={[
              { key: "all", label: "الكل" },
              { key: "reported", label: "فيها بلاغٌ مفتوح" },
            ]}
          />
          <Field
            label="بحث"
            name="room_search"
            placeholder="اسمُ الراكب أو الكابتن، أو أوّلُ رقم الرحلة"
            value={query}
            maxLength={80}
            onChange={(event) => setQuery(event.target.value)}
          />
          <ErrorNote message={error} />
          <Table
            columns={COLUMNS}
            headers={["الراكب", "الكابتن", "الرسائل", "آخر رسالة", "الرحلة", "البلاغات"]}
            rows={rows}
            keyOf={(row) => row.ride_id}
            empty={{
              title: applied ? "لا غرفةَ تطابق البحث" : scope === "reported" ? "لا غرفةَ فيها بلاغٌ مفتوح" : "لا محادثاتٍ بعد",
              hint: "تظهر الغرفةُ هنا حين يرسل الراكبُ أو الكابتن أوّلَ رسالةٍ في رحلة.",
            }}
            render={(row) => (
              <>
                <button type="button" className="text-start font-semibold text-ink" onClick={() => navigate(`/rides?open=${row.ride_id}`)}>
                  {row.rider_name ?? "—"}
                </button>
                <span>{row.driver_name ?? "—"}</span>
                <span>{row.message_count}</span>
                <span className="text-muted">{moment(row.last_message_at)}</span>
                <span dir="ltr" className="text-start text-muted">
                  #{row.ride_id.slice(0, 8)}
                </span>
                <span>{row.open_reports > 0 ? <Badge tone="danger">{row.open_reports} مفتوح</Badge> : <span className="text-muted">—</span>}</span>
              </>
            )}
          />
        </>
      )}
    </Shell>
  );
}
