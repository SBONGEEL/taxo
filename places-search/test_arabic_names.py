"""**الأسماءُ العربيّة** (SPEC §١٠٩-ب) — بلا شبكة: المطابقةُ بالاسم نفسِه في المكان نفسِه، ولا اسمَ مزدوجٌ ولا عامّيٌّ ولا تاريخيّ،
ومدنُ القياس نسخةُ `build_map_data.py` حرفاً.

usage: python3 -I places-search/test_arabic_names.py
"""
import ast
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("arabic_names", os.path.join(HERE, "arabic_names.py"))
an = importlib.util.module_from_spec(spec)
spec.loader.exec_module(an)

failures = []


def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


check("اسمٌ عربيٌّ خالصٌ يُقبل", an.usable_arabic("  مستشفى   العبدلي ") == "مستشفى العبدلي")
check("والمزدوجُ لا يُقبل", an.usable_arabic("Sharia Amr - شارع الوادي") is None)
check("واللاتينيُّ لا يُقبل", an.usable_arabic("Abdali Hospital") is None)
check("ومفتاحُ المطابقة بلا علاماتٍ ولا حالة", an.latin_key("Hôpital  d'Oran") == an.latin_key("hopital d oran"))

features = [("1", "Abdali Hospital", "Abdali Hospital", "31.9600", "35.9100"),
            ("2", "Oran", "Oran", "35.6969", "-0.6331"),
            ("3", "Old Souk", "Old Souk", "32.0", "35.0")]
alternates = [
    ("1", "ar", "مستشفى العبدلي", "1", "", "", ""),
    ("1", "en", "Al-Abdali Hospital", "", "", "", ""),
    ("2", "ar", "وهران", "", "", "", ""),
    ("2", "ar", "الباهية", "", "", "1", ""),          # عامّيّ ⇐ لا
    ("3", "ar", "السوق القديم", "", "", "", "1"),     # تاريخيّ ⇐ لا
]
index = an.geonames_index(features, alternates)
check("بالاسم نفسِه في المكان نفسِه", an.geonames_match(index, ["Abdali Hospital"], 31.9601, 35.9102, "poi") == "مستشفى العبدلي")
check("وباسمٍ بديلٍ لاتينيّ", an.geonames_match(index, ["Al-Abdali Hospital"], 31.9601, 35.9102, "poi") == "مستشفى العبدلي")
check("وبعيداً ⇐ لا", an.geonames_match(index, ["Abdali Hospital"], 31.99, 35.95, "poi") is None)
check("والمدينةُ بمسافتها الأوسع، والعامّيُّ لا يغلب", an.geonames_match(index, ["Oran"], 35.71, -0.62, "city") == "وهران")
check("والتاريخيُّ وحدَه لا يُعطي اسماً", an.geonames_match(index, ["Old Souk"], 32.0, 35.0, "poi") is None)
check("ولا مطابقةَ بالشبه", an.geonames_match(index, ["Abdali Hospita"], 31.9601, 35.9102, "poi") is None)

with open(os.path.join(HERE, "build_map_data.py"), encoding="utf-8") as handle:
    tree = ast.parse(handle.read())
boxes = next(ast.literal_eval(node.value) for node in tree.body
             if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "CITY_BOXES")
check("مدنُ القياس نسخةُ build_map_data حرفاً", boxes == an.CITY_BOXES)
check("ولكلِّ مدينةٍ دولتها", set(an.CITY_OF_CC) == set(an.CITY_BOXES))
check("ونقطةٌ في عمّان مدينتُها عمّان", an.city_of(31.96, 35.91) == "عمّان")

sys.exit(1 if failures else 0)
