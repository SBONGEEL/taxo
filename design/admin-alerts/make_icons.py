"""أيقوناتُ إشعارات المالك (SPEC §٨١/٦–٩) — SVG يُكتب هنا ثمّ يُرسَم PNG بـffmpeg (librsvg).

* **الكبيرةُ لكلِّ فئة** (٢٥٦): مربّعٌ مدوَّرٌ بلون الفئة وعلامةٌ بيضاء — **علاماتُ Lucide** (رخصة ISC، حرّةٌ للاستعمال التجاريّ، وهي
  `lucide-react` نفسُها في اللوحة) فتتّحد العلامةُ في الهاتف والمتصفّح والجرس.
* **الشارةُ** (٩٦، أحاديّةُ اللون): الـX من علامة TAXO بالأبيض على شفافيّة — المتصفّحُ يرسمها قناعاً كما يرسم أندرويد أيقونةَ الشريط.
"""

from __future__ import annotations

import sys
from pathlib import Path

TONES = {
    # الفئة: (اللون، علامةُ Lucide)
    "money_in": ("#1F9D55", '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>'),
    "money_out": ("#2B6CB0", '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>'),
    "account": ("#6B46C1", '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>'),
    "problem": ("#E03E3E", '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>'),
    "ride": ("#F05A28", '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>'),
    "feedback": ("#C88A12", '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M13 8H7"/><path d="M17 12H7"/>'),
}


def large(color: str, glyph: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">'
        f'<rect width="256" height="256" rx="60" fill="{color}"/>'
        '<g transform="translate(52 52) scale(6.333)" fill="none" stroke="#FFFFFF" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>'
    )


# **الـX من علامة TAXO** (`ic_stat_taxo.xml`): قضيبان مدوَّرا الطرفين على ‎-50° و‎+50° — بالأبيض وحدَه
BADGE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">'
    '<g fill="#FFFFFF">'
    '<rect x="14" y="39" width="68" height="18" rx="9" transform="rotate(-50 48 48)"/>'
    '<rect x="14" y="39" width="68" height="18" rx="9" transform="rotate(50 48 48)"/>'
    "</g></svg>"
)

if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    for tone, (color, glyph) in TONES.items():
        (target / f"alert_{tone}.svg").write_text(large(color, glyph), encoding="utf-8")
    (target / "alert_badge.svg").write_text(BADGE, encoding="utf-8")
    print("\n".join(f"{tone} {color}" for tone, (color, _) in TONES.items()))
