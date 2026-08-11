import logging
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

logger = logging.getLogger(__name__)

# ==========================================
# 0. Setup & UI Styling (ตั้งค่าพื้นฐานและหน้าตา)
# ==========================================
st.set_page_config(page_title="BorderLoad AI", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")
FILE_NAME = "orders.csv"

# --- Custom CSS for Ultra Clean & Professional Look ---
st.markdown("""
    <style>
        /* ซ่อนเมนูพื้นฐานของ Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* บังคับพื้นหลังแอปพลิเคชันเป็นสีเทาอ่อนสุด เพื่อให้กล่องสีขาวเด่นขึ้นมา */
        .stApp {
            background-color: #F3F4F6;
        }
        
        /* ปรับฟอนต์ให้ดูโมเดิร์นและสะอาดตา */
        html, body, [class*="css"]  {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* ================= ตกแต่ง Card ของ Metric (KPIs) ================= */
        [data-testid="stMetric"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E5E7EB !important;
            padding: 24px 20px !important;
            border-radius: 16px !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03) !important;
            transition: transform 0.2s; /* เพิ่มลูกเล่นตอนเอาเมาส์ชี้ */
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06) !important;
        }
        
        /* บังคับสีตัวอักษรในกล่อง KPI ให้เข้มชัดเจนตัดกับพื้นหลังขาว */
        [data-testid="stMetricLabel"] > div, [data-testid="stMetricLabel"] p {
            color: #64748B !important; /* สีเทา Slate สบายตา สำหรับหัวข้อ */
            font-size: 16px !important;
            font-weight: 600 !important;
        }
        [data-testid="stMetricValue"] > div {
            color: #0F172A !important; /* สีดำ/น้ำเงินเข้มจัด สำหรับตัวเลข ให้เด่นชัด */
            font-weight: 800 !important;
            font-size: 32px !important;
        }
        
        /* ================= ปรับสีหัวข้อ (Headers) ================= */
        h1, h2, h3 {
            color: #1E3A8A !important; /* สีน้ำเงินกรมท่า (Navy Blue) */
            font-weight: 700 !important;
            padding-bottom: 10px;
        }
        
        /* ================= ตกแต่ง Container ปกติ ================= */
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background-color: #FFFFFF !important;
            border-radius: 16px !important;
            border: 1px solid #E5E7EB !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.02) !important;
            padding: 20px !important;
        }
        
        /* ปรับสไตล์ของ Expander ให้สะอาดขึ้น */
        .streamlit-expanderHeader {
            background-color: #F8FAFC !important;
            border-radius: 8px !important;
            color: #1E3A8A !important;
            font-weight: 600 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- Thailand Timezone (UTC+7) ---
tz_th = timezone(timedelta(hours=7))

# --- Translations Dictionary ---
langs = {
    "ไทย": {
        "menu_title": "เมนูระบบ (Main Menu)",
        "page_dashboard": "📊 ภาพรวมแดชบอร์ด (Overview)",
        "page_orders": "📦 จัดการคำสั่งซื้อ (Orders)",
        "page_status": "⚙️ ตั้งค่าพารามิเตอร์ (Parameters)",
    },
    "English": {
        "menu_title": "System Menu",
        "page_dashboard": "📊 Dashboard Overview",
        "page_orders": "📦 Order Management",
        "page_status": "⚙️ System Parameters",
    }
}

# --- State Initialization ---
if 'fuel_price' not in st.session_state: st.session_state.fuel_price = 32.5
if 'baseline_fuel' not in st.session_state: st.session_state.baseline_fuel = 30.0
if 'driver_count' not in st.session_state: st.session_state.driver_count = 5
if 'dispatch_hour' not in st.session_state: st.session_state.dispatch_hour = 8
if 'trucks_schedule' not in st.session_state: st.session_state.trucks_schedule = []
if 'ai_issues' not in st.session_state: st.session_state.ai_issues = []
if 'ai_rating' not in st.session_state: st.session_state.ai_rating = 0

# ข้อมูลด่าน
default_routes = pd.DataFrame({
    "Destination": ["Vientiane", "Penang", "Kuala Lumpur", "Kunming", "Guangzhou", "Hanoi", "Ho Chi Minh"],
    "Border_Name": ["Nong Khai", "Sadao", "Sadao", "Chiang Khong", "Mukdahan", "Nakhon Phanom", "Aranyaprathet"],
    "Distance_km": [650, 1100, 1450, 1200, 1800, 950, 900],
    "Congestion_hrs": [1.0, 2.5, 2.5, 4.0, 1.5, 1.0, 3.0],
    "Lat": [17.9757, 5.4141, 3.1390, 25.0400, 23.1291, 21.0285, 10.8231],
    "Lon": [102.6000, 100.3288, 101.6869, 102.7000, 113.2644, 105.8542, 106.6297]
})
if 'route_data' not in st.session_state: st.session_state.route_data = default_routes.copy()

origin_coords = [99.0084, 18.5733] # [Lon, Lat] Hana Lamphun
SPEED_LIMIT_KMH = 80.0 

if 'cargo_rules' not in st.session_state:
    st.session_state.cargo_rules = pd.DataFrame({
        "Cargo_1": ["Food (Dry)", "Medical Supplies", "Chemical"],
        "Cargo_2": ["Chemical", "Chemical", "Electronics"],
        "Can_Ship_Together": [False, False, True]
    })

truck_types = {
    "Small (4-Wheel)": {"cap_kg": 3000, "cap_cbm": 10.0, "base_km_l": 10.0, "loaded_km_l": 8.0},
    "Medium (6-Wheel)": {"cap_kg": 7000, "cap_cbm": 20.0, "base_km_l": 6.0, "loaded_km_l": 4.5},
    "Large (10-Wheel)": {"cap_kg": 15000, "cap_cbm": 35.0, "base_km_l": 4.0, "loaded_km_l": 2.5}
}

# ==========================================
# OSRM Free Routing API (ดึงข้อมูลถนนจริง)
# ==========================================
@st.cache_data(ttl=3600)
def get_real_route(lon1, lat1, lon2, lat2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        res = requests.get(url, timeout=5)
        data = res.json()
        if data['code'] == 'Ok':
            return data['routes'][0]['geometry']['coordinates']
    except Exception:
        logger.exception("Failed to fetch OSRM route")
    return [[lon1, lat1], [lon2, lat2]]

@st.cache_data
def load_data():
    if os.path.exists(FILE_NAME): return pd.read_csv(FILE_NAME)
    return pd.DataFrame(columns=["Order_ID", "Origin", "Destination", "Weight_kg", "Volume_cbm", "Deadline", "Cargo_Type"])

def save_data(new_data_df):
    global data
    try:
        data = pd.concat([data, new_data_df], ignore_index=True).drop_duplicates(subset=['Order_ID'], keep='last')
        data.to_csv(FILE_NAME, index=False)
        st.cache_data.clear()
        return True
    except PermissionError:
        st.error("⚠️ ไม่สามารถบันทึกข้อมูลได้ เนื่องจากไฟล์ 'orders.csv' กำลังถูกเปิดค้างไว้ในโปรแกรมอื่น (เช่น Excel) กรุณาปิดไฟล์นั้นก่อนทำการบันทึกครับ")
        return False

data = load_data()

# ==========================================
# Core AI Logic: Generate Schedule Function
# ==========================================
def generate_schedule(scenario="Normal", ai_priority="Minimum Cost"):
    df_process = data.copy()
    issues = []
    
    # --- จำลองปัญหาจากตัวเลือก Scenario ---
    if scenario == "Disruption":
        st.session_state.route_data.loc[st.session_state.route_data['Border_Name'].isin(['Mukdahan', 'Chiang Khong']), 'Congestion_hrs'] = 15.0
        issues.append("🌪️ [Disruption Scenario] พายุเข้าด่าน! ด่านมุกดาหารและเชียงของติดขัดหนัก (รอ 15 ชั่วโมง)")
    else:
        st.session_state.route_data['Congestion_hrs'] = default_routes['Congestion_hrs']
        
    if scenario == "Erroneous Data" and len(df_process) > 0:
        df_process.loc[df_process.index[0:2], 'Weight_kg'] = 0.0

    erroneous = df_process[df_process['Weight_kg'] <= 0]
    if not erroneous.empty:
        issues.append(f"⚠️ [Erroneous Data Scenario] ตรวจพบสินค้าน้ำหนัก 0 kg จำนวน {len(erroneous)} ชิ้น -> AI ทำการแทนที่ด้วยค่าเฉลี่ย 500 kg ป้องกันระบบล่ม")
        df_process.loc[df_process['Weight_kg'] <= 0, 'Weight_kg'] = 500

    # จัดการวันที่และเวลา
    df_process['Deadline_DT'] = pd.to_datetime(df_process['Deadline'], errors='coerce')
    if df_process['Deadline_DT'].dt.tz is None:
        df_process['Deadline_DT'] = df_process['Deadline_DT'].dt.tz_localize(tz_th)
    else:
        df_process['Deadline_DT'] = df_process['Deadline_DT'].dt.tz_convert(tz_th)
    df_process['Deadline_DT'] = df_process['Deadline_DT'].fillna(datetime.now(tz_th) + timedelta(days=7))
    
    if ai_priority == "Minimum Cost":
        df_process = df_process.sort_values(by=['Destination', 'Weight_kg'], ascending=[True, False])
    else:
        df_process = df_process.sort_values(by=['Destination', 'Deadline_DT'], ascending=[True, True])
    
    # การจัดกลุ่มและเลือกรถ
    trucks = []
    def check_conflict(existing_cargos, new_cargo):
        for ex_cargo in existing_cargos:
            for _, rule in st.session_state.cargo_rules.iterrows():
                if (not rule['Can_Ship_Together']) and (
                    (new_cargo == rule['Cargo_1'] and ex_cargo == rule['Cargo_2']) or
                    (new_cargo == rule['Cargo_2'] and ex_cargo == rule['Cargo_1'])
                ): return True
        return False

    for idx, row in df_process.iterrows():
        placed = False
        for t in trucks:
            if t['Destination'] == row['Destination']:
                type_specs = truck_types[t['Truck_Type']]
                if (t['Weight'] + row['Weight_kg'] <= type_specs['cap_kg']) and \
                   (t['Volume'] + row['Volume_cbm'] <= type_specs['cap_cbm']) and \
                   (not check_conflict(t['Cargo_Types'], row['Cargo_Type'])):
                    t['Orders'].append(row['Order_ID'])
                    t['Weight'] += row['Weight_kg']
                    t['Volume'] += row['Volume_cbm']
                    t['Cargo_Types'].add(row['Cargo_Type'])
                    placed = True
                    break
        
        if not placed:
            selected_type = "Small (4-Wheel)"
            if row['Weight_kg'] > truck_types["Small (4-Wheel)"]["cap_kg"] or row['Volume_cbm'] > truck_types["Small (4-Wheel)"]["cap_cbm"]:
                selected_type = "Medium (6-Wheel)"
            if row['Weight_kg'] > truck_types["Medium (6-Wheel)"]["cap_kg"] or row['Volume_cbm'] > truck_types["Medium (6-Wheel)"]["cap_cbm"]:
                selected_type = "Large (10-Wheel)"
            
            trucks.append({
                "Truck_ID": f"TRK-{len(trucks)+1:03d}",
                "Truck_Type": selected_type,
                "Driver_Name": f"Driver {len(trucks)+1}" if len(trucks) < st.session_state.driver_count else "UNASSIGNED",
                "Destination": row['Destination'],
                "Weight": row['Weight_kg'],
                "Volume": row['Volume_cbm'],
                "Orders": [row['Order_ID']],
                "Cargo_Types": {row['Cargo_Type']},
                "Deadline_DT": row['Deadline_DT']
            })
            
    final_schedule = []
    now_th = datetime.now(tz_th)
    safe_dispatch_hour = max(0, min(23, int(st.session_state.dispatch_hour)))
    dispatch_time = now_th.replace(hour=safe_dispatch_hour, minute=0, second=0, microsecond=0)
    
    for t in trucks:
        route = st.session_state.route_data[st.session_state.route_data['Destination'] == t['Destination']].iloc[0]
        dist = route['Distance_km']
        
        specs = truck_types[t['Truck_Type']]
        payload_pct = min(t['Weight'] / specs['cap_kg'], 1.0)
        l_per_km_empty = 1.0 / specs['base_km_l']
        l_per_km_full = 1.0 / specs['loaded_km_l']
        l_per_km_actual = l_per_km_empty + (l_per_km_full - l_per_km_empty) * payload_pct
        
        fuel_cost = (dist * l_per_km_actual) * st.session_state.fuel_price
        total_cost = fuel_cost + 1500 
        
        drive_hrs = dist / SPEED_LIMIT_KMH
        total_time_hrs = drive_hrs + route['Congestion_hrs']
        eta = dispatch_time + timedelta(hours=total_time_hrs)
        
        final_schedule.append({
            "Truck_ID": t['Truck_ID'],
            "Type": t['Truck_Type'],
            "Driver": t['Driver_Name'],
            "Destination": t['Destination'],
            "Dept_Time": dispatch_time.strftime("%Y-%m-%d %H:%M"),
            "Weight_kg": t['Weight'],
            "Cost_THB": total_cost,
            "Emissions_kg": dist * 0.8,
            "ETA": eta.strftime("%Y-%m-%d %H:%M"),
            "Late_Risk": "Yes" if eta > t['Deadline_DT'] else "No",
            "Orders": ", ".join(t['Orders'])
        })
    
    # แจ้งเตือนปัญหา
    if len(trucks) > st.session_state.driver_count: 
        issues.append(f"👨‍✈️ Driver Shortages: ต้องการรถ {len(trucks)} คัน แต่มีคนขับเพียง {st.session_state.driver_count} คน")
    for t in final_schedule:
        if t['Late_Risk'] == "Yes": 
            issues.append(f"⏰ Late Delivery: รถ {t['Truck_ID']} จะส่งล่าช้ากว่า Deadline เนื่องจากใช้เวลานานเกินไป (ETA: {t['ETA']})")

    st.session_state.trucks_schedule = final_schedule
    st.session_state.ai_issues = issues

# ==========================================
# 1. เมนูนำทาง & ภาษา (Sidebar)
# ==========================================
with st.sidebar:
    st.title("🚛 BorderLoad AI")
    selected_lang = st.selectbox("🌐 Language", ["ไทย", "English"])
    t = langs[selected_lang]
    
    st.markdown(f"**{t['menu_title']}**")
    page = st.radio("Navigation:", [t["page_dashboard"], t["page_orders"], t["page_status"]], label_visibility="collapsed")
    
    st.divider()
    ai_priority = st.radio("🎯 AI Goal (เป้าหมาย):", ["Minimum Cost", "Max On-time Delivery"])
    
    st.divider()
    st.caption("📍 TIMEZONE: THAILAND (UTC+7)")
    st.caption(f"🕒 Current: {datetime.now(tz_th).strftime('%Y-%m-%d %H:%M')}")

# ==========================================
# หน้าที่ 1: Dashboard & Scenarios
# ==========================================
if page == t["page_dashboard"]:
    st.header("🎛️ AI Decision Center")
    with st.container(border=True):
        col_scen, col_opt = st.columns([2, 1])
        with col_scen:
            scenario = st.radio("เลือกสถานการณ์จำลอง (Decision Alternatives):", 
                ["Normal Operation (ปกติ)", "Disruption (พายุเข้า/ด่านติดขัดหนัก)", "Erroneous Data (น้ำหนักผิดพลาด)"], horizontal=True)
            scenario_key = scenario.split(" ")[0]
            
        with col_opt:
            st.write("") 
            if st.button("🧠 Auto-Optimize (ให้ AI แก้ปัญหาอัตโนมัติ)", type="primary", use_container_width=True):
                st.toast("AI is optimizing constraints...")
                iteration = 0
                while len(st.session_state.ai_issues) > 0 and iteration < 10:
                    issues_str = str(st.session_state.ai_issues)
                    if "Driver Shortages" in issues_str: st.session_state.driver_count += 1
                    if "Late Delivery" in issues_str: st.session_state.dispatch_hour -= 2 
                    generate_schedule(scenario_key, ai_priority)
                    iteration += 1
                st.success(f"✅ AI ปรับค่าสำเร็จ! (เพิ่มคนขับเป็น {st.session_state.driver_count} คน, ขยับเวลาออกเป็น {st.session_state.dispatch_hour}:00 น.)")

    if len(data) > 0:
        generate_schedule(scenario_key, ai_priority)
        
    trucks = st.session_state.trucks_schedule
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚛 รถที่กำลังวิ่ง (Active Trucks)", f"{len(trucks)} คัน")
    c2.metric("💰 ต้นทุนประเมินรวม (Est. Cost)", f"฿ {sum(tr['Cost_THB'] for tr in trucks):,.2f}")
    c3.metric("🌱 คาดการณ์ปล่อย CO2 (Emissions)", f"{sum(tr['Emissions_kg'] for tr in trucks):,.1f} kg")
    c4.metric("🚨 แจ้งเตือนปัญหา (Active Alerts)", f"{len(st.session_state.ai_issues)}", delta_color="inverse")

    st.write("---")

    map_col, alert_col = st.columns([2, 1])
    with map_col:
        st.subheader("🗺️ Live Fleet Tracking (Real Road Networks)")
        
        paths_traveled = []
        paths_remaining = []
        truck_positions = []
        
        now_th = datetime.now(tz_th)
        dispatch_time = now_th.replace(hour=max(0, min(23, int(st.session_state.dispatch_hour))), minute=0, second=0, microsecond=0)
        elapsed_hrs = (now_th - dispatch_time).total_seconds() / 3600.0

        for tr in trucks:
            dest_info = st.session_state.route_data[st.session_state.route_data['Destination'] == tr['Destination']].iloc[0]
            dest_lon, dest_lat = dest_info['Lon'], dest_info['Lat']
            
            coords = get_real_route(origin_coords[0], origin_coords[1], dest_lon, dest_lat)
            total_points = len(coords)
            dist_total = dest_info['Distance_km']
            
            if elapsed_hrs <= 0: progress = 0.0
            else:
                dist_traveled = elapsed_hrs * SPEED_LIMIT_KMH
                progress = min(1.0, dist_traveled / dist_total) if dist_total > 0 else 1.0
                
            cut_idx = int(total_points * progress)
            
            if progress <= 0:
                cur_lon, cur_lat = coords[0]
                remaining_path, traveled_path = coords, []
            elif progress >= 1:
                cur_lon, cur_lat = coords[-1]
                remaining_path, traveled_path = [], coords
            else:
                cur_lon, cur_lat = coords[cut_idx]
                traveled_path = coords[:cut_idx+1]
                remaining_path = coords[cut_idx:]

            if len(traveled_path) > 1:
                paths_traveled.append({"path": traveled_path, "color": [29, 78, 216]})
            if len(remaining_path) > 1:
                paths_remaining.append({"path": remaining_path, "color": [147, 197, 253]})
                
            truck_positions.append({
                "coordinates": [cur_lon, cur_lat], "text": "🚛", 
                "info": f"TRK: {tr['Truck_ID']}\nTo: {tr['Destination']}\nProgress: {progress*100:.1f}%"
            })

        layer_traveled = pdk.Layer("PathLayer", paths_traveled, get_path="path", get_color="color", width_scale=20, width_min_pixels=4, get_width=5)
        layer_remaining = pdk.Layer("PathLayer", paths_remaining, get_path="path", get_color="color", width_scale=20, width_min_pixels=4, get_width=5)
        layer_trucks = pdk.Layer("TextLayer", truck_positions, get_position="coordinates", get_text="text", get_size=40, get_alignment_baseline="'center'", pickable=True)
        
        if len(trucks) > 0:
            view_state = pdk.ViewState(latitude=15.0, longitude=102.0, zoom=4.5, pitch=40)
            st.pydeck_chart(pdk.Deck(layers=[layer_remaining, layer_traveled, layer_trucks], initial_view_state=view_state, tooltip={"text": "{info}"}))
        else:
            st.info("ไม่พบข้อมูลเส้นทาง กรุณาเพิ่มคำสั่งซื้อ")
            
    with alert_col:
        st.subheader("🚨 การตรวจจับปัญหา (Exception Alerts)")
        with st.container(border=True):
            if st.session_state.ai_issues:
                for issue in st.session_state.ai_issues:
                    st.error(issue)
            else:
                st.success("✅ ระบบทำงานปกติ ไม่มีข้อผิดพลาด")
            
        st.write("")
        st.write("**📝 ประเมินการจัดตารางของ AI (Human Rating)**")
        st.session_state.ai_rating = st.slider("ให้คะแนนความพึงพอใจ (1-5 ดาว)", 1, 5, 5)
        if st.button("ส่งคะแนน (Submit)"):
            st.toast(f"บันทึกคะแนน {st.session_state.ai_rating} ดาว! ระบบจะนำไป Train โมเดลต่อไป")

    st.write("---")

    st.subheader("🗓️ ตารางขนส่งอัตโนมัติ (AI Generated Schedule)")
    if len(trucks) > 0:
        df_display = pd.DataFrame(trucks)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    with st.expander("ℹ️ ข้อมูลจำเพาะรถบรรทุกและวิศวกรรมการคำนวณ (Engineering Specs)"):
        st.write("อัตราสิ้นเปลืองน้ำมัน (L/km) ถูกคำนวณตามเปอร์เซ็นต์น้ำหนักบรรทุกจริง (Payload %):")
        st.latex(r"Fuel_{actual} = Fuel_{empty} + (Fuel_{full} - Fuel_{empty}) \times \left( \frac{Weight_{actual}}{Weight_{max}} \right)")
        df_specs = pd.DataFrame(truck_types).T
        df_specs.columns = ["Max Weight (kg)", "Max Vol (CBM)", "Empty Fuel (km/L)", "Full Load Fuel (km/L)"]
        st.dataframe(df_specs, use_container_width=True)

# ==========================================
# หน้าที่ 2: Order Management (เพิ่มระบบ Upload File กลับมา)
# ==========================================
elif page == t["page_orders"]:
    st.header(t["page_orders"])
    
    tab1, tab2 = st.tabs(["📄 อัปโหลดไฟล์ (Upload CSV/Excel)", "✍️ กรอกข้อมูลเอง (Manual Entry)"])
    
    with tab1:
        st.info("รองรับไฟล์ข้อมูลนามสกุล .csv และ .xlsx")
        uploaded_file = st.file_uploader("เลือกไฟล์คำสั่งซื้อ", type=["csv", "xlsx"])
        if uploaded_file and st.button("บันทึกข้อมูลจากไฟล์", type="primary"):
            try:
                df_upload = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                if save_data(df_upload):
                    st.success(f"อัปโหลดสำเร็จ {len(df_upload)} รายการ!")
                    st.rerun()
            except (ValueError, TypeError, OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as e:
                st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")

    with tab2, st.container(border=True), st.form("add_order_form", clear_on_submit=True):
            c = st.columns(3)
            new_order_id = c[0].text_input("Order ID")
            new_origin = c[1].text_input("Origin (ต้นทาง)", value="Hana Lamphun")
            new_destination = c[2].selectbox("Destination (ปลายทาง)", default_routes['Destination'].tolist())
            c2 = st.columns(4)
            new_weight = c2[0].number_input("Weight (kg)", min_value=1.0, value=500.0)
            new_volume = c2[1].number_input("Volume (CBM)", min_value=0.1, value=1.0)
            new_date = c2[2].date_input("Deadline Date")
            new_time = c2[3].time_input("Deadline Time")
            new_cargo = st.selectbox("Cargo Type", ["Electronics", "Auto Parts", "Food (Dry)", "Chemical", "Medical Supplies"])

            submit_btn = st.form_submit_button("บันทึกคำสั่งซื้อ (Save Order)", type="primary")
            if submit_btn and new_order_id.strip() != "" and save_data(pd.DataFrame([{"Order_ID": new_order_id, "Origin": new_origin, "Destination": new_destination, "Weight_kg": new_weight, "Volume_cbm": new_volume, "Deadline": f"{new_date} {new_time.strftime('%H:%M')}", "Cargo_Type": new_cargo}])):
                st.rerun()
                
    st.subheader("📋 รายการคำสั่งซื้อปัจจุบัน (Current Orders)")
    st.dataframe(data, use_container_width=True, hide_index=True)

# ==========================================
# หน้าที่ 3: Current Status (พารามิเตอร์)
# ==========================================
elif page == t["page_status"]:
    st.header(t["page_status"])
    st.write("ผู้ใช้งานสามารถปรับเปลี่ยนค่าตัวแปร (Constraints) เพื่อให้ AI นำไปคำนวณแผนการเดินรถใหม่ได้ทันที")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.number_input("🚚 จำนวนคนขับที่มี (Available Drivers)", key='driver_count')
        c2.number_input("⛽ ราคาน้ำมัน (Fuel Price THB/L)", key='fuel_price')
        c3.number_input("🕒 เวลาเริ่มปล่อยรถ (Departure Hour 0-23)", min_value=0, max_value=23, key='dispatch_hour')
        
    st.subheader("🌍 ข้อมูลด่านและระยะทาง (Border & Route Data)")
    st.data_editor(st.session_state.route_data, use_container_width=True, hide_index=True, key='route_edit')
