import streamlit as st
import swisseph as swe
import datetime
import pytz
from timezonefinder import TimezoneFinder
import geonamescache

# إعداد واجهة التطبيق
st.set_page_config(page_title="حاسبة احتمالات سنوات الارتباط العاطفي ", layout="wide", page_icon="💍")

# 1. تهيئة قاعدة بيانات الدول والمدن العالمية
@st.cache_data
def load_geo_data():
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    cities = gc.get_cities()
    
    country_map = {c['name']: code for code, c in countries.items()}
    sorted_countries = sorted(list(country_map.keys()))
    
    cities_by_country = {}
    for c_code in country_map.values():
        c_cities = [city for city in cities.values() if city['countrycode'] == c_code]
        c_cities_sorted = sorted(c_cities, key=lambda x: x['population'], reverse=True)
        cities_by_country[c_code] = c_cities_sorted
        
    return gc, country_map, sorted_countries, cities_by_country

gc, country_map, country_list, cities_by_country = load_geo_data()
tf = TimezoneFinder()

# ثوابت فلكية
PLANETS = {
    'Sun': swe.SUN, 'Moon': swe.MOON, 'Mercury': swe.MERCURY, 
    'Venus': swe.VENUS, 'Mars': swe.MARS, 'Jupiter': swe.JUPITER, 
    'Saturn': swe.SATURN, 'Uranus': swe.URANUS, 'Neptune': swe.NEPTUNE, 
    'Pluto': swe.PLUTO, 'Rahu': swe.TRUE_NODE
}

# الكواكب التي لها أورب 3 درجات فقط
OUTER_PLANETS = ['Uranus', 'Neptune', 'Pluto']

ZODIAC_NAMES = [
    "الحمل", "الثور", "الجوزاء", "السرطان", 
    "الأسد", "العذراء", "الميزان", "العقرب", 
    "القوس", "الجدي", "الدلو", "الحوت"
]

def get_utc_julian_day(date_obj, time_obj, tz_str):
    local_tz = pytz.timezone(tz_str)
    dt = datetime.datetime.combine(date_obj, time_obj)
    local_dt = local_tz.localize(dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)

def find_exact_solar_return(target_year, natal_sun_lon, birth_month, birth_day, birth_time, b_tz):
    guess_dt = datetime.datetime(target_year, birth_month, birth_day, birth_time.hour, birth_time.minute)
    local_tz = pytz.timezone(b_tz)
    utc_dt = local_tz.localize(guess_dt).astimezone(pytz.utc)
    jd_guess = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0)
    
    for _ in range(15):
        sun_lon = swe.calc_ut(jd_guess, swe.SUN)[0][0]
        diff = (natal_sun_lon - sun_lon)
        if diff > 180: diff -= 360
        if diff < -180: diff += 360
        jd_guess += diff / 0.985647
        if abs(diff) < 0.000001:
            break
    return jd_guess

def get_house_of_planet(p_lon, cusps):
    """حساب رقم البيت المنزلي (من 1 إلى 12) بناءً على خطوط بداية البيوت"""
    for i in range(12):
        c1 = cusps[i]
        c2 = cusps[(i + 1) % 12]
        if c1 < c2:
            if c1 <= p_lon < c2: return i + 1
        else:
            if p_lon >= c1 or p_lon < c2: return i + 1
    return 1

def check_midpoint_activation(sr_planets, midpoint_lon):
    """
    التحقق الدقيق من تفعيل كواكب السنوية لمحور الميد بوينت.
    - +/- 3 درجات لكواكب أورانوس، نبتون، وبلوتو.
    - +/- 2 درجة لجميع الكواكب الأخرى والنقاط (شاملة راهو وكيتو).
    """
    axis_longitudes = [(midpoint_lon + k * 90) % 360 for k in range(4)]
    
    activated_planets = []
    for p_name, p_data in sr_planets.items():
        p_lon = p_data['lon']
        
        # تحديد الأورب المسموح
        orb = 3.0 if p_name in OUTER_PLANETS else 2.0
        
        for target_lon in axis_longitudes:
            diff = abs(p_lon - target_lon)
            if diff > 180: diff = 360 - diff
            if diff <= orb:
                sign_idx = int(p_lon / 30)
                deg_in_sign = p_lon % 30
                p_label = "أورانوس/نبتون/بلوتو" if p_name in OUTER_PLANETS else "كواكب/نقاط أخرى"
                activated_planets.append(f"{p_name} ({p_label}) في {deg_in_sign:.1f}° {ZODIAC_NAMES[sign_idx]} [فرق: {diff:.1f}°]")
                break
    return activated_planets

def is_before_cusp(p_lon, cusp_lon, orb=6):
    diff = (cusp_lon - p_lon) % 360
    return diff <= orb

# --- واجهة المستخدم التفاعلية ---
st.title("حاسبة احتمالات سنوات الارتباط العاطفي: الميد بوينت الميلادية و العودة الشمسية")
st.caption("برمجة الفلكي و المبرمج استرو رادار")
st.markdown("---")

col1, col2, col3 = st.columns(3)

default_b_country_idx = country_list.index("Syria") if "Syria" in country_list else 0
default_sr_country_idx = country_list.index("United Arab Emirates") if "United Arab Emirates" in country_list else 0

with col1:
    name = st.text_input("الاسم", "New Name")
    birth_date = st.date_input("تاريخ الميلاد", value=datetime.date(2005, 1, 1), min_value=datetime.date(1960, 1, 1))
    birth_time = st.time_input("ساعة الميلاد", value=datetime.time(12, 0), step=datetime.timedelta(minutes=1))

with col2:
    st.markdown("### مكان الميلاد")
    b_country_name = st.selectbox("دولة الميلاد", country_list, index=default_b_country_idx, key="b_country_select")
    b_c_code = country_map[b_country_name]
    b_city_objects = cities_by_country.get(b_c_code, [])
    b_city_names = [c['name'] for c in b_city_objects] if b_city_objects else [b_country_name]
    b_city_name = st.selectbox("مدينة الميلاد", b_city_names, index=0, key="b_city_select")

with col3:
    st.markdown("### مكان السنوية (المكان الحالي)")
    sr_country_name = st.selectbox("دولة السنوية", country_list, index=default_sr_country_idx, key="sr_country_select")
    sr_c_code = country_map[sr_country_name]
    sr_city_objects = cities_by_country.get(sr_c_code, [])
    sr_city_names = [c['name'] for c in sr_city_objects] if sr_city_objects else [sr_country_name]
    sr_city_name = st.selectbox("مدينة السنوية", sr_city_names, index=0, key="sr_city_select")

submit = st.button("حساب سنوات الزواج المحتملة", type="primary")

if submit:
    b_city_obj = next((c for c in b_city_objects if c['name'] == b_city_name), None)
    sr_city_obj = next((c for c in sr_city_objects if c['name'] == sr_city_name), None)
    
    b_lat, b_lon = (b_city_obj['latitude'], b_city_obj['longitude']) if b_city_obj else (25.2048, 55.2708)
    sr_lat, sr_lon = (sr_city_obj['latitude'], sr_city_obj['longitude']) if sr_city_obj else (25.2048, 55.2708)
        
    b_tz = tf.timezone_at(lng=b_lon, lat=b_lat) or "UTC"
    sr_tz = tf.timezone_at(lng=sr_lon, lat=sr_lat) or "UTC"
    
    jd_birth = get_utc_julian_day(birth_date, birth_time, b_tz)
    natal_sun = swe.calc_ut(jd_birth, swe.SUN)[0][0]
    natal_moon = swe.calc_ut(jd_birth, swe.MOON)[0][0]
    
    # حساب بيوت الخريطة الميلادية (نظام ريجومونتانوس)
    natal_cusps, _ = swe.houses(jd_birth, b_lat, b_lon, b'R')
    
    # حساب الميد بوينت (شمس / قمر)
    midpoint_lon = (natal_sun + natal_moon) / 2.0
    if abs(natal_sun - natal_moon) > 180:
        midpoint_lon = (midpoint_lon + 180) % 360
        
    midpoint_sign_idx = int(midpoint_lon / 30)
    midpoint_deg = midpoint_lon % 30
    
    st.info(f"**نتائج الحسابات الميلادية لـ ({name}):**\n"
            f"* موقع الشمس: `{natal_sun%30:.2f}°` {ZODIAC_NAMES[int(natal_sun/30)]}\n"
            f"* موقع القمر: `{natal_moon%30:.2f}°` {ZODIAC_NAMES[int(natal_moon/30)]}\n"
            f"* **الميد بوينت (شمس/قمر):** `{midpoint_deg:.2f}°` **{ZODIAC_NAMES[midpoint_sign_idx]}**\n"
            f"* **محور الميد بوينت النشط (درجة {midpoint_deg:.1f}° من):** {ZODIAC_NAMES[midpoint_sign_idx]}، {ZODIAC_NAMES[(midpoint_sign_idx+6)%12]}، {ZODIAC_NAMES[(midpoint_sign_idx+3)%12]}، {ZODIAC_NAMES[(midpoint_sign_idx+9)%12]}\n"
            f"* **ضوابط الأورب للميد بوينت:** ±3° لأورانوس ونبتون وبلوتو | ±2° لباقي الكواكب والنقاط (شاملة راهو وكيتو)")
    
    start_year = birth_date.year + 18
    end_year = birth_date.year + 60
    years_list = list(range(start_year, end_year + 1))
    total_years = len(years_list)
    
    marriage_years = []
    progress_bar = st.progress(0.0)
    
    for i, target_year in enumerate(years_list):
        progress_val = min(1.0, (i + 1) / total_years)
        
        jd_sr = find_exact_solar_return(target_year, natal_sun, birth_date.month, birth_date.day, birth_time, b_tz)
        
        # بيوت العودة الشمسية (ريجومونتانوس)
        sr_cusps, _ = swe.houses(jd_sr, sr_lat, sr_lon, b'R')
        sr_asc = sr_cusps[0] # طالع العودة الشمسية
        
        sr_planets = {}
        for p_name, p_id in PLANETS.items():
            lon = swe.calc_ut(jd_sr, p_id)[0][0]
            sr_planets[p_name] = {
                'lon': lon, 
                'sign': int(lon / 30), 
                'deg_in_sign': lon % 30, 
                'house': get_house_of_planet(lon, sr_cusps)
            }

        # إضافة كيتو (العقدة الجنوبية) تلقائياً كمقابل لراهو (180 درجة)
        rahu_lon = sr_planets['Rahu']['lon']
        ketu_lon = (rahu_lon + 180) % 360
        sr_planets['Ketu'] = {
            'lon': ketu_lon,
            'sign': int(ketu_lon / 30),
            'deg_in_sign': ketu_lon % 30,
            'house': get_house_of_planet(ketu_lon, sr_cusps)
        }

        # 1. شرط أساسي: تفعيل الميد بوينت بالأورب المسموح (+/- 3 لأورانوس/نبتون/بلوتو و +/- 2 لغيرهم)
        activated_midpoint_planets = check_midpoint_activation(sr_planets, midpoint_lon)
        if not activated_midpoint_planets:
            progress_bar.progress(progress_val)
            continue

        # 2. تقييم دلالات الزواج السنوية الشاملة (10 دلالات)
        dallalat_details = []
        dallalat_count = 0
        
        # دلالة 1: طالع السنوية في بيوت الزواج/الأوتاد الميلادية (1، 4، 5، 7، 10)
        sr_asc_in_natal = get_house_of_planet(sr_asc, natal_cusps)
        if sr_asc_in_natal in [1, 4, 5, 7, 10]:
            dallalat_count += 1
            dallalat_details.append(f"1. طالع العودة الشمسية يقع في **البيت {sr_asc_in_natal} الميلادي** (بيت وتدي/ارتباط)")

        # دلالة 2: موقع شمس السنوية في بيوت الأوتاد/الارتباط السنوية (1، 4، 5، 7، 10)
        if sr_planets['Sun']['house'] in [1, 4, 5, 7, 10]:
            dallalat_count += 1
            dallalat_details.append(f"2. الشمس السنوية في **البيت {sr_planets['Sun']['house']} السنوي**")
            
        # دلالة 3: موقع قمر السنوية في بيوت الأوتاد/الارتباط السنوية (1، 4، 5، 7، 10)
        if sr_planets['Moon']['house'] in [1, 4, 5, 7, 10]:
            dallalat_count += 1
            dallalat_details.append(f"3. القمر السنوي في **البيت {sr_planets['Moon']['house']} السنوي**")

        # دلالة 4: تواجد كواكب في البيت السابع السنوي (بيت الزواج والشراكة)
        planets_in_7th = [p_name for p_name, p_data in sr_planets.items() if p_data['house'] == 7]
        if len(planets_in_7th) >= 1:
            dallalat_count += 1
            dallalat_details.append(f"4. تواجد كواكب بالبيت السابع السنوي: ({', '.join(planets_in_7th)})")

        # دلالة 5: هيمنة أو كثرة الكواكب بالبيت السابع السنوي (3 كواكب فما فوق)
        if len(planets_in_7th) >= 3:
            dallalat_count += 1
            dallalat_details.append(f"5. هيمنة البيت السابع السنوي بـ ({len(planets_in_7th)}) كواكب")

        # دلالة 6: تواجد أدلة عاطفية بالبيت الخامس السنوي (الزهرة، المشتري، الشمس، القمر)
        planets_in_5th = [p_name for p_name in ['Venus', 'Jupiter', 'Sun', 'Moon'] if sr_planets[p_name]['house'] == 5]
        if len(planets_in_5th) >= 1:
            dallalat_count += 1
            dallalat_details.append(f"6. تواجد أدلة عاطفية في البيت الخامس السنوي: ({', '.join(planets_in_5th)})")

        # دلالة 7: وضعية الزهرة السنوية (بالبيوت 1، 4، 5، 7، 10 أو بأبراج الثور، السرطان، الميزان، الجدي، الحوت)
        if sr_planets['Venus']['house'] in [1, 4, 5, 7, 10] or sr_planets['Venus']['sign'] in [1, 3, 6, 9, 11]:
            dallalat_count += 1
            dallalat_details.append(f"7. الزهرة في موقع قوي إما بالبيت {sr_planets['Venus']['house']} السنوي أو برج مستجيب للزواج")

        # دلالة 8: وضعية المريخ السنوي (في أبراج الحمل، الجدي أو في بيوت الأوتاد/الارتباط)
        if sr_planets['Mars']['sign'] in [0, 9] or sr_planets['Mars']['house'] in [1, 4, 5, 7, 10]:
            dallalat_count += 1
            dallalat_details.append(f"8. المريخ في موقعه الأصلي/شرفه أو بالبيت {sr_planets['Mars']['house']} السنوي")

        # دلالة 9: وضعية المشتري السنوي (في بيوت الأوتاد/الارتباط السنوية 1، 4، 5، 7، 10)
        if sr_planets['Jupiter']['house'] in [1, 4, 5, 7, 10]:
            dallalat_count += 1
            dallalat_details.append(f"9. المشتري (كوكب السعادة والاتساع) في البيت {sr_planets['Jupiter']['house']} السنوي")

        # دلالة 10: اتصال كواكب رئيسية بأوتاد السنوية (قبل أوتاد 1، 4، 5، 7، 10 السنوية بـ 6 درجات فأقل)
        target_planets = ['Uranus', 'Venus', 'Jupiter', 'Sun', 'Rahu', 'Ketu', 'Mars', 'Moon']
        target_cusps = [sr_cusps[0], sr_cusps[3], sr_cusps[4], sr_cusps[6], sr_cusps[9]] # 1, 4, 5, 7, 10
        
        cusp_contacts = []
        for p_name in target_planets:
            p_lon = sr_planets[p_name]['lon']
            for cusp_idx, cusp in enumerate(target_cusps):
                if is_before_cusp(p_lon, cusp, orb=6):
                    house_num = 1 if cusp_idx==0 else (4 if cusp_idx==1 else (5 if cusp_idx==2 else (7 if cusp_idx==3 else 10)))
                    cusp_contacts.append(f"{p_name} قبل وتد البيت {house_num}")
                    break
                    
        if cusp_contacts:
            dallalat_count += 1
            dallalat_details.append(f"10. اتصال أدلة الزواج بأوتاد السنوية: ({', '.join(cusp_contacts)})")

        # 3. الشرط القاطع للمخرجات: تحقق الميد بوينت + توفر من 3 إلى 10 دلالات
        if 3 <= dallalat_count <= 10:
            marriage_years.append({
                "year": target_year, 
                "age": target_year - birth_date.year, 
                "dallalat_count": dallalat_count,
                "midpoint_activators": activated_midpoint_planets,
                "details": dallalat_details
            })
            
        progress_bar.progress(progress_val)

    # طباعة السنوات المستخرجة
    st.subheader("السنوات المتحققة (شرط الميد بوينت + تحقق من 3 إلى 10 دلالات زواج):")
    
    if marriage_years:
        for m in marriage_years:
            with st.expander(f"سنة {m['year']} (العمر: {m['age']} سنة) - تحقق ({m['dallalat_count']} من 10) دلالات زواج"):
                st.write(f"**الكواكب المفعلة للميد بوينت:**")
                for act in m['midpoint_activators']:
                    st.write(f"  * {act}")
                    
                st.write("**تفاصيل الدلالات السنوية المتحققة:**")
                for d in m['details']:
                    st.write(f"- {d}")
    else:
        st.warning("لم يتم العثور على سنوات تطابق الشروط الدقيقة (شرط الميد بوينت + تحقق 3 دلالات فأكثر من أصل 10).")
