/** **الطرود للكبتن** (§٦٣-ج/٤، بلاطةُ «طرود» — أمرُ المالك ٢٠٢٦-١٠-١٠): **ما يفعله بها** — كيف تصله، وما سلّمه منها.
 *
 * **لا لوحةَ لها في Claude Design** — فتُركَّب من عُدّة الهوية القائمة (رأسُ الشاشة وصفوفُ «رحلاتي» وملاحظةُ `t2-note`).
 * **والقائمةُ من «رحلاتي» نفسِها** (`GET /rides/me?side=driver`) مصفّاةً بنوع الطرد — لا بابٌ ثانٍ ولا رقمُ مالٍ يُحسب هنا.
 * **والعنوانُ والمستلمُ لا يظهران هنا**: بياناتُ المستلم تُنشر من القبول حتى الانتهاء وحدَه، وتُحذف بعده (سياسةُ الخصوصية).
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listMyRides } from "@/api/endpoints";
import type { RideListItem } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { RIDE_STATUS_LABEL } from "@/lib/rideFormat";

import { startOfToday, whenParts } from "./when";

import "./t2.css";
import "./ride.css";

/** «سُلِّم» للطرد بدل «مكتملة» — وما سواه حالُ الرحلة كما يقوله «رحلاتي» (`RIDE_STATUS_LABEL`). */
const DELIVERED = "سُلِّم";

export function ParcelsT2Screen() {
  const navigate = useNavigate();
  const goBack = useGoBack("/");
  const [rows, setRows] = useState<RideListItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  const today = startOfToday();

  useEffect(() => {
    listMyRides(50, 0)
      .then((items) => setRows(items.filter((item) => item.ride.ride_type === "parcel")))
      .catch(() => setFailed(true));
  }, []);

  return (
    <div className="t2 t2-svc">
      <div className="t2-svc-scroll scr">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <span className="t2-icon" aria-hidden="true">
              arrow_forward
            </span>
          </button>
          <h1 className="t2-title">الطرود</h1>
        </div>

        <p className="t2-note">
          <span className="t2-icon" aria-hidden="true">
            package_2
          </span>
          تصلك الطرودُ عرضاً كأيِّ رحلةٍ وعليها شارةُ «طرد». بعد القبول ترى اسمَ المستلم وعنوانَه وتتصل به، وتسلّمه الطردَ في الوجهة.
          وإن وجدتَ عند الاستلام ما لا تقبل نقلَه فارفض الطردَ من شاشة الرحلة — بلا مالٍ على أحد.
        </p>

        <div className="t2-group">ما نقلتَه</div>
        {rows === null ? (
          failed ? (
            <p className="t2-note danger" role="alert">
              <span className="t2-icon" aria-hidden="true">
                error
              </span>
              تعذّر قراءة رحلاتك
            </p>
          ) : (
            <div className="t2-svc-wait" aria-busy="true">
              <Spinner />
            </div>
          )
        ) : rows.length === 0 ? (
          <p className="t2-empty">لم تنقل طرداً بعد.</p>
        ) : (
          <div className="t2-list t2-sgroup">
            {rows.map(({ ride }) => (
              <button
                key={ride.id}
                type="button"
                className="t2-srow"
                onClick={() => navigate(`/rides/${ride.id}`)}
              >
                <span className="t2-icon t2-srow-icon" aria-hidden="true">
                  package_2
                </span>
                <span className="t2-srow-main">
                  <span className="t2-srow-title">
                    {ride.status === "completed" ? DELIVERED : (RIDE_STATUS_LABEL[ride.status] ?? "طرد")}
                  </span>
                  <span className="t2-srow-hint">
                    {whenParts(ride.created_at, today).day} · {whenParts(ride.created_at, today).time}
                  </span>
                </span>
                <span className="t2-icon" aria-hidden="true">
                  chevron_left
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
