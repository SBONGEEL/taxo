"""**فئةُ المكان** — بيتٌ واحدٌ يقرؤه `build_map_data.py` (الأيقونة) و`arabic_names.py` (ترتيبُ «أماكن بلا اسم عربي»).

نُقلت من `build_map_data.py` حرفاً (٢٠٢٦-١١-٢٠) لأنّ ذاك يقرأ `sys.argv` ويستورد `osmium` عند تحميله فلا يُستورد.
"""

# ── فئةُ المكان ⇐ أيقونته (الأسماءُ نفسُها في `customer-app/src/lib/open-places.ts`)
OSM_CATEGORY = [
    ("hospital", {"amenity=hospital", "healthcare=hospital"}),
    ("clinic", {"amenity=clinic", "amenity=doctors", "healthcare=clinic", "healthcare=doctor", "healthcare=centre", "amenity=dentist", "healthcare=dentist"}),
    ("pharmacy", {"amenity=pharmacy", "healthcare=pharmacy", "shop=chemist"}),
    ("university", {"amenity=university", "amenity=college"}),
    ("school", {"amenity=school", "amenity=kindergarten"}),
    ("mosque", {"amenity=place_of_worship"}),
    ("bank", {"amenity=bank", "amenity=atm", "amenity=bureau_de_change"}),
    ("government", {"office=government", "amenity=townhall", "amenity=courthouse", "amenity=police", "amenity=post_office", "amenity=embassy", "office=diplomatic", "amenity=fire_station"}),
    ("fuel", {"amenity=fuel", "amenity=charging_station"}),
    ("restaurant", {"amenity=restaurant", "amenity=fast_food", "amenity=food_court"}),
    ("cafe", {"amenity=cafe", "amenity=ice_cream", "shop=bakery", "shop=pastry"}),
    ("hotel", {"tourism=hotel", "tourism=motel", "tourism=guest_house", "tourism=hostel", "tourism=apartment"}),
    ("mall", {"shop=mall", "shop=department_store", "amenity=marketplace", "shop=supermarket"}),
    ("landmark", {"tourism=attraction", "tourism=museum", "historic=monument", "historic=memorial", "historic=castle", "historic=archaeological_site", "historic=ruins", "tourism=viewpoint", "leisure=stadium", "leisure=park", "aeroway=aerodrome", "aeroway=terminal"}),
    ("transport", {"amenity=bus_station", "public_transport=station", "railway=station", "amenity=taxi", "amenity=parking"}),
]
OSM_LOOKUP = {tag: cat for cat, tags in OSM_CATEGORY for tag in tags}
# Overture `categories.primary` ⇐ الفئة (كلماتٌ في الاسم الإنجليزيّ للفئة)
OVERTURE_WORDS = [
    ("hospital", ("hospital",)), ("pharmacy", ("pharmacy", "drugstore")),
    ("clinic", ("clinic", "doctor", "dentist", "medical", "health", "laboratory")),
    ("university", ("university", "college")), ("school", ("school", "kindergarten", "academy")),
    ("mosque", ("mosque", "religious", "church", "place_of_worship")), ("bank", ("bank", "atm", "currency")),
    ("government", ("government", "embassy", "police", "post_office", "court", "town_hall", "public_service", "municipal")),
    ("fuel", ("gas_station", "fuel", "ev_charging")), ("cafe", ("cafe", "coffee", "bakery", "dessert", "juice", "tea_room")),
    ("restaurant", ("restaurant", "food", "pizza", "burger", "grill", "shawarma", "sandwich")),
    ("hotel", ("hotel", "motel", "resort", "hostel", "guest_house", "lodging")),
    ("mall", ("shopping_center", "mall", "supermarket", "department_store", "grocery", "hypermarket")),
    ("landmark", ("landmark", "museum", "monument", "park", "stadium", "historic", "tourist", "airport")),
    ("transport", ("bus_station", "train_station", "transportation", "parking", "taxi")),
]

# **ترتيبُ الأهمّيّة** (أمرُ المالك ٢٠٢٦-١١-٢٠ الثاني، البند ٤): ما يقصده الراكبُ في حاجته أوّلاً — ثمّ الباقي
PRIORITY = ("hospital", "clinic", "pharmacy", "school", "university", "government", "mall", "mosque", "bank", "fuel")


def priority(cat: str) -> int:
    """موضعُ الفئة في الترتيب (٠ أهمُّها)، وما ليس في القائمة بعدها كلِّها."""
    return PRIORITY.index(cat) if cat in PRIORITY else len(PRIORITY)


def category(tag: str) -> str:
    base = tag.split(" ")[0]
    if base.startswith("overture="):
        words = base[len("overture="):].lower()
        for cat, marks in OVERTURE_WORDS:
            if any(m in words for m in marks):
                return cat
        return "place"
    if base in OSM_LOOKUP:
        return OSM_LOOKUP[base]
    if base.startswith("shop="):
        return "shop"
    return "place"
