import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import pydeck as pdk
import streamlit as st

# ==========================================
# 0. Setup & State (ตั้งค่าพื้นฐาน)
# ==========================================
st.set_page_config(page_title="BorderLoad AI", layout="wide", initial_sidebar_state="expanded")
FILE_NAME = "orders.csv"

# --- Translations Dictionary ---
langs = {
    "ไทย": {
        "menu_title": "เมนูหลัก",
        "page_dashboard": "📊 ภาพรวมแดชบอร์ด (Overview)",
        "page_orders": "📦 จัดการคำสั่งซื้อ (Orders)",
        "page_status": "⚙️ สถานการณ์ปัจจุบัน (Status)",
        "page_schedule": "🗓️ ตารางขนส่ง & แจ้งเตือน AI",
        "kpi_trucks": "รถที่กำลังวิ่ง (คัน)",
        "kpi_cost": "ต้นทุนประเมินรวม (บาท)",
        "kpi_emissions": "ปล่อย CO2 (kg)",
        "kpi_alerts": "แจ้งเตือนปัญหา",
    },
    "English": {
        "menu_title": "Main Menu",
        "page_dashboard": "📊 Dashboard Overview",
        "page_orders": "📦 Order Management",
        "page_status": "⚙️ Current Status",
        "page_schedule": "🗓️ Schedule & AI Alerts",
        "kpi_trucks": "Active Trucks",
        "kpi_cost": "Est. Total Cost (THB)",
        "kpi_emissions": "CO2 Emissions (kg)",
        "kpi_alerts": "Active Alerts",
    },
    "中文": {
        "menu_title": "主菜单",
        "page_dashboard": "📊 仪表板概览 (Overview)",
        "page_orders": "📦 订单管理 (Orders)",
        "page_status": "⚙️ 当前状态 (Status)",
        "page_schedule": "🗓️ 运输计划与AI警报 (Schedule)",
        "kpi_trucks": "运行中的卡车",
        "kpi_cost": "预估总成本 (泰铢)",
        "kpi_emissions": "二氧化碳排放量 (kg)",
        "kpi_alerts": "活跃警报",
    }
}

# --- State Initialization ---
if 'fuel_price' not in st.session_state: st.session_state.fuel_price = 32.5
if 'baseline_fuel' not in st.session_state: st.session_state.baseline_fuel = 30.0
if 'driver_count' not in st.session_state: st.session_state.driver_count = 5
if 'dispatch_hour' not in st.session_state: st.session_state.dispatch_hour = 8 # เวลาออกเดินทางเริ่มต้น 08:00
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

origin_coords = [18.5733, 99.0084] # Hana Lamphun
SPEED_LIMIT_KMH = 80.0 

# กฎข้อห้ามสินค้า
if 'cargo_rules' not in st.session_state:
    st.session_state.cargo_rules = pd.DataFrame({
        "Cargo_1": ["Food (Dry)", "Medical Supplies", "Chemical"],
        "Cargo_2": ["Chemical", "Chemical", "Electronics"],
        "Can_Ship_Together": [False, False, True]
    })

# ประเภทรถบรรทุกและสเป็ค
truck_types = {
    "Small (4-Wheel)": {"cap_kg": 3000, "cap_cbm": 10.0, "base_km_l": 10.0, "loaded_km_l": 8.0},
    "Medium (6-Wheel)": {"cap_kg": 7000, "cap_cbm": 20.0, "base_km_l": 6.0, "loaded_km_l": 4.5},
    "Large (10-Wheel)": {"cap_kg": 15000, "cap_cbm": 35.0, "base_km_l": 4.0, "loaded_km_l": 2.5}
}

@st.cache_data
def load_data():
    if os.path.exists(FILE_NAME): return pd.read_csv(FILE_NAME)
    return pd.DataFrame(columns=["Order_ID", "Origin", "Destination", "Weight_kg", "Volume_cbm", "Deadline", "Cargo_Type"])

def save_data(new_data_df):
    global data
    data = pd.concat([data, new_data_df], ignore_index=True).drop_duplicates(subset=['Order_ID'], keep='last')
    data.to_csv(FILE_NAME, index=False)
    st.cache_data.clear()

data = load_data()

# ==========================================
# Core AI Logic: Generate Schedule Function
# ==========================================
def generate_schedule(scenario="Normal", ai_priority="Minimum Cost"):
    df_process = data.copy()
    issues = []
    
    # 1. จัดการ Scenario เงื่อนไข (Decision Alternatives)
    if scenario == "Disruption":
        # จำลองด่านติดขัดหนัก ทำให้เสี่ยงส่งไม่ทัน
        st.session_state.route_data.loc[st.session_state.route_data['Border_Name'].isin(['Mukdahan', 'Chiang Khong']), 'Congestion_hrs'] = 15.0
    else:
        st.session_state.route_data['Congestion_hrs'] = default_routes['Congestion_hrs']
        
    if scenario == "Erroneous Data" and len(df_process) > 0:
        # จำลองเซนเซอร์พัง น้ำหนักหาย/เป็น 0
        df_process.loc[df_process.index[0:2], 'Weight_kg'] = 0.0

    # 2. แก้ไขข้อมูล Erroneous Data (Data Imputation)
    erroneous = df_process[df_process['Weight_kg'] <= 0]
    if not erroneous.empty:
        issues.append(f"⚠️ Erroneous Data: พบสินค้าน้ำหนัก 0 kg จำนวน {len(erroneous)} ชิ้น -> AI ทำการแก้ไขโดยเติมค่าน้ำหนักเฉลี่ย (500 kg)")
        df_process.loc[df_process['Weight_kg'] <= 0, 'Weight_kg'] = 500

    # ใช้ datetime ที่มี Timezone ชัดเจน เพื่อหลีกเลี่ยง Warning DTZ005 และความคลาดเคลื่อนในการเปรียบเทียบเวลา
    df_process['Deadline_DT'] = pd.to_datetime(df_process['Deadline'], errors='coerce', utc=True)
    df_process['Deadline_DT'] = df_process['Deadline_DT'].fillna(datetime.now(timezone.utc) + timedelta(days=7))
    
    # 3. จัดเรียงตามเป้าหมาย (Cost vs Speed)
    if ai_priority == "Minimum Cost":
        df_process = df_process.sort_values(by=['Destination', 'Weight_kg'], ascending=[True, False])
    else:
        df_process = df_process.sort_values(by=['Destination', 'Deadline_DT'], ascending=[True, True])
    
    # 4. Bin Packing & Vehicle Assignment
    trucks = []
    def check_conflict(existing_cargos, new_cargo):
        for ex_cargo in existing_cargos:
            for _, rule in st.session_state.cargo_rules.iterrows():
                if (not rule['Can_Ship_Together']) and (
                    (new_cargo == rule['Cargo_1'] and ex_cargo == rule['Cargo_2']) or
                    (new_cargo == rule['Cargo_2'] and ex_cargo == rule['Cargo_1'])
                ):
                    return True
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
                "Deadline_DT": row['Deadline_DT'] # จำเวลาส่งที่ด่วนที่สุดของรถคันนี้
            })
            
    # 5. คำนวณ ETA, Cost, Emissions
    final_schedule = []
    now = datetime.now(timezone.utc)
    
    # ป้องกัน Error เวลาออกเดินทางติดลบหรือเกิน 24 ชม. ที่เกิดจากการปรับค่าอัตโนมัติของ AI
    safe_dispatch_hour = max(0, min(23, int(st.session_state.dispatch_hour)))
    dispatch_time = now.replace(hour=safe_dispatch_hour, minute=0, second=0, microsecond=0)
    
    for t in trucks:
        route = st.session_state.route_data[st.session_state.route_data['Destination'] == t['Destination']].iloc[0]
        dist = route['Distance_km']
        
        # สมการคำนวณน้ำมัน: Base + (Loaded - Base) * (Payload / Max_Cap)
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
    
    # 6. ตรวจจับปัญหา (Issue Detection)
    if len(trucks) > st.session_state.driver_count: issues.append(f"👨‍✈️ Driver Shortages: ต้องการรถ {len(trucks)} คัน แต่มีคนขับ {st.session_state.driver_count} คน")
    for t in final_schedule:
        if t['Late_Risk'] == "Yes": issues.append(f"⏰ Late Delivery: รถ {t['Truck_ID']} จะส่งของล่าช้ากว่ากำหนด (ETA: {t['ETA']})")

    st.session_state.trucks_schedule = final_schedule
    st.session_state.ai_issues = issues

# ==========================================
# 1. เมนูนำทาง & ภาษา (Sidebar)
# ==========================================
with st.sidebar:
    st.title("🚛 BorderLoad AI")
    selected_lang = st.selectbox("🌐 Language", ["ไทย", "English", "中文"])
    t = langs[selected_lang]
    
    st.write(t["menu_title"])
    page = st.radio("Navigation:", [t["page_dashboard"], t["page_orders"], t["page_status"]], label_visibility="collapsed")
    
    st.divider()
    ai_priority = st.radio("🎯 AI Goal:", ["Minimum Cost", "Max On-time Delivery"])

# ==========================================
# หน้าที่ 1: Dashboard & Scenarios
# ==========================================
if page == t["page_dashboard"]:
    
    # --- 3 Decision Alternatives (Scenarios) ---
    st.header("🎛️ เลือกสถานการณ์จำลอง (Decision Alternatives)")
    col_scen, col_opt = st.columns([2, 1])
    with col_scen:
        scenario = st.radio("เลือกลักษณะข้อมูลเพื่อทดสอบ AI:", 
            ["Normal Operation (ปกติ)", "Disruption (พายุเข้าด่าน/ด่านติดขัดหนัก)", "Erroneous Data (ข้อมูลน้ำหนักผิดพลาด)"], horizontal=True)
        scenario_key = scenario.split(" ")[0]
        
    with col_opt:
        # ระบบ Machine Learning จำลอง (Auto-Optimize)
        if st.button("🧠 ให้ AI เรียนรู้และปรับค่าจนกว่าจะไม่มี Error", type="primary"):
            st.toast("AI is optimizing constraints...")
            iteration = 0
            while len(st.session_state.ai_issues) > 0 and iteration < 10:
                issues_str = str(st.session_state.ai_issues)
                # ML Logic: ปรับค่าสถานการณ์ปัจจุบันให้ตอบโจทย์
                if "Driver Shortages" in issues_str:
                    st.session_state.driver_count += 1
                if "Late Delivery" in issues_str:
                    st.session_state.dispatch_hour -= 2 # เลื่อนเวลาออกเดินทางให้เร็วขึ้น 2 ชั่วโมง
                generate_schedule(scenario_key, ai_priority)
                iteration += 1
            st.success(f"AI ปรับค่าสำเร็จใน {iteration} รอบ! (เพิ่มคนขับเป็น {st.session_state.driver_count} คน, เลื่อนออกเดินทางเป็น {st.session_state.dispatch_hour}:00 น.)")

    # บังคับสร้างตารางแรกอัตโนมัติหากมีข้อมูล (Auto Generate First Schedule)
    if len(data) > 0:
        generate_schedule(scenario_key, ai_priority)
        
    trucks = st.session_state.trucks_schedule
    
    st.divider()
    # 1. KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t["kpi_trucks"], f"{len(trucks)}")
    c2.metric(t["kpi_cost"], f"{sum(tr['Cost_THB'] for tr in trucks):,.2f}")
    c3.metric(t["kpi_emissions"], f"{sum(tr['Emissions_kg'] for tr in trucks):,.1f}")
    c4.metric(t["kpi_alerts"], f"{len(st.session_state.ai_issues)}", delta_color="inverse")

    # 2. Live Map & Alerts
    map_col, alert_col = st.columns([2, 1])
    with map_col:
        st.subheader("🗺️ Live Fleet Tracking")
        map_data = []
        for tr in trucks:
            dest_info = st.session_state.route_data[st.session_state.route_data['Destination'] == tr['Destination']].iloc[0]
            map_data.append({"Truck": tr['Truck_ID'], "Dest": tr['Destination'], "Lat": dest_info['Lat'], "Lon": dest_info['Lon'], "Color": [0, 100, 255]})
        if map_data:
            df_map = pd.DataFrame(map_data)
            layer = pdk.Layer('ScatterplotLayer', data=df_map, get_position='[Lon, Lat]', get_color='Color', get_radius=50000, pickable=True)
            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=15.0, longitude=102.0, zoom=4, pitch=45), tooltip={"text": "{Truck} -> {Dest}"}))
            
    with alert_col:
        st.subheader(f"🚨 {t['kpi_alerts']}")
        if st.session_state.ai_issues:
            for issue in st.session_state.ai_issues:
                st.error(issue)
        else:
            st.success("✅ ระบบทำงานปกติ ไม่มีปัญหา")
            
        st.write("---")
        st.write("**📝 ประเมินการจัดตารางของ AI**")
        st.session_state.ai_rating = st.slider("ให้คะแนน (1-5 ดาว)", 1, 5, 5)
        if st.button("ส่งคะแนน (Submit Rating)"):
            st.toast(f"ขอบคุณสำหรับคะแนน {st.session_state.ai_rating} ดาว! AI จะนำไปปรับปรุงตัวแบบต่อไป")

    # 3. Schedule Table & Truck Specs
    st.divider()
    st.subheader("🗓️ ตารางขนส่งอัตโนมัติ (AI Generated Schedule)")
    if len(trucks) > 0:
        st.dataframe(pd.DataFrame(trucks), width="stretch")
    
    st.subheader("🚛 ข้อมูลจำเพาะรถบรรทุก (Truck Specifications & Fuel Equation)")
    st.write("ระบบคำนวณอัตราสิ้นเปลืองน้ำมันแปรผันตาม **เปอร์เซ็นต์น้ำหนักบรรทุก (Payload %)** ตามสมการวิศวกรรม:")
    st.latex(r"Fuel (L/km) = Empty + (Full - Empty) \times \left( \frac{Actual\ Weight}{Max\ Capacity} \right)")
    df_specs = pd.DataFrame(truck_types).T
    df_specs.columns = ["Max Weight (kg)", "Max Vol (CBM)", "Empty Fuel (km/L)", "Full Load Fuel (km/L)"]
    st.dataframe(df_specs, width="stretch")

# ==========================================
# หน้าที่ 2: Order Management
# ==========================================
elif page == t["page_orders"]:
    st.header(t["page_orders"])
    with st.form("add_order_form", clear_on_submit=True):
        c = st.columns(3)
        new_order_id = c[0].text_input("Order ID")
        new_origin = c[1].text_input("Origin")
        new_destination = c[2].selectbox("Destination", default_routes['Destination'].tolist())
        c2 = st.columns(4)
        new_weight = c2[0].number_input("Weight (kg)", min_value=1.0, value=500.0)
        new_volume = c2[1].number_input("Volume (CBM)", min_value=0.1, value=1.0)
        new_date = c2[2].date_input("Deadline Date")
        new_time = c2[3].time_input("Deadline Time")
        new_cargo = st.selectbox("Cargo Type", ["Electronics", "Auto Parts", "Food (Dry)", "Chemical", "Medical Supplies"])
        if st.form_submit_button("Save Order") and new_order_id.strip() != "":
            save_data(pd.DataFrame([{"Order_ID": new_order_id, "Origin": new_origin, "Destination": new_destination, "Weight_kg": new_weight, "Volume_cbm": new_volume, "Deadline": f"{new_date} {new_time.strftime('%H:%M')}", "Cargo_Type": new_cargo}]))
            st.rerun()
    st.dataframe(data, width="stretch")

# ==========================================
# หน้าที่ 3: Current Status (พารามิเตอร์)
# ==========================================
elif page == t["page_status"]:
    st.header(t["page_status"])
    c1, c2, c3 = st.columns(3)
    c1.number_input("Available Drivers", key='driver_count')
    c2.number_input("Fuel Price (THB/L)", key='fuel_price')
    c3.number_input("Departure Hour (0-23)", key='dispatch_hour')
    st.data_editor(st.session_state.route_data, width="stretch", key='route_edit')
