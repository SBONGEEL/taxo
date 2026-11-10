"""**دولُ مُنتقي الهاتف** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٥) — القائمةُ الثابتةُ التي يُرسم منها العلمُ والاسمُ والرمز.

**والأسواقُ الثلاثةُ منها** (الأردن · ليبيا · الجزائر) **وقواعدُ أرقامها في `core/phone.py` لا هنا**: هذه القائمةُ للعرض والحال
وحدَهما — **لا رقمَ يُطبَّع ولا رمزَ تحقّقٍ يُرسل لدولةٍ ليست سوقاً**، فالدولةُ غيرُ النشطة تُردّ قبل أيِّ رمز (`signup_countries`).

**والاختيار** (قراري، والمالكُ أذن «You choose the list»): الدولُ العربيّةُ الاثنتان والعشرون كلُّها، **وما يكثر فيه أهلُ المغرب
العربيّ والمشرق في المهجر** — تركيا وأوروبا الغربيّة وأمريكا الشماليّة. **ورمزُ الاتّصال نصُّ أرقامٍ بلا «+»** كما في `phone.py`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Country:
    code: str
    dial: str
    ar: str
    fr: str
    en: str

    def name(self, language: str | None) -> str:
        if language == "fr":
            return self.fr
        if language == "en":
            return self.en
        return self.ar


CATALOGUE: tuple[Country, ...] = (
    # ── الأسواق (حالُها من «الدول والحدود») ──
    Country("JO", "962", "الأردن", "Jordanie", "Jordan"),
    Country("DZ", "213", "الجزائر", "Algérie", "Algeria"),
    Country("LY", "218", "ليبيا", "Libye", "Libya"),
    # ── الدولُ العربيّة ──
    Country("BH", "973", "البحرين", "Bahreïn", "Bahrain"),
    Country("KM", "269", "جزر القمر", "Comores", "Comoros"),
    Country("DJ", "253", "جيبوتي", "Djibouti", "Djibouti"),
    Country("EG", "20", "مصر", "Égypte", "Egypt"),
    Country("IQ", "964", "العراق", "Irak", "Iraq"),
    Country("KW", "965", "الكويت", "Koweït", "Kuwait"),
    Country("LB", "961", "لبنان", "Liban", "Lebanon"),
    Country("MR", "222", "موريتانيا", "Mauritanie", "Mauritania"),
    Country("MA", "212", "المغرب", "Maroc", "Morocco"),
    Country("OM", "968", "عُمان", "Oman", "Oman"),
    Country("PS", "970", "فلسطين", "Palestine", "Palestine"),
    Country("QA", "974", "قطر", "Qatar", "Qatar"),
    Country("SA", "966", "السعودية", "Arabie saoudite", "Saudi Arabia"),
    Country("SO", "252", "الصومال", "Somalie", "Somalia"),
    Country("SD", "249", "السودان", "Soudan", "Sudan"),
    Country("SY", "963", "سوريا", "Syrie", "Syria"),
    Country("TN", "216", "تونس", "Tunisie", "Tunisia"),
    Country("AE", "971", "الإمارات", "Émirats arabes unis", "United Arab Emirates"),
    Country("YE", "967", "اليمن", "Yémen", "Yemen"),
    # ── المهجر ──
    Country("TR", "90", "تركيا", "Turquie", "Türkiye"),
    Country("FR", "33", "فرنسا", "France", "France"),
    Country("DE", "49", "ألمانيا", "Allemagne", "Germany"),
    Country("GB", "44", "المملكة المتحدة", "Royaume-Uni", "United Kingdom"),
    Country("IT", "39", "إيطاليا", "Italie", "Italy"),
    Country("ES", "34", "إسبانيا", "Espagne", "Spain"),
    Country("BE", "32", "بلجيكا", "Belgique", "Belgium"),
    Country("NL", "31", "هولندا", "Pays-Bas", "Netherlands"),
    Country("CH", "41", "سويسرا", "Suisse", "Switzerland"),
    Country("AT", "43", "النمسا", "Autriche", "Austria"),
    Country("SE", "46", "السويد", "Suède", "Sweden"),
    Country("NO", "47", "النرويج", "Norvège", "Norway"),
    Country("DK", "45", "الدنمارك", "Danemark", "Denmark"),
    Country("MT", "356", "مالطا", "Malte", "Malta"),
    Country("CY", "357", "قبرص", "Chypre", "Cyprus"),
    Country("CA", "1", "كندا", "Canada", "Canada"),
    Country("US", "1", "الولايات المتحدة", "États-Unis", "United States"),
)

BY_CODE: dict[str, Country] = {country.code: country for country in CATALOGUE}
