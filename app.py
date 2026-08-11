import logging
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

logger = logging.getLogger(__name__)

# ==========================================
# 0. Setup & UI Styling
# ==========================================
st.set_page_config(page_title="BorderLoad AI", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")
FILE_NAME = "orders.csv"

# --- Custom CSS (ปรับให้ตัวอักษรตัดกับพื้นหลัง ไม่กลืนกัน และ Sidebar อ่านง่าย) ---
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        .stApp { background-color: #F3F4F6; }
        html, body, [class*="css"] { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        
        /* แก้สีตัวอักษร Sidebar ให้ตัดกับพื้นหลัง */
        [data-testid="stSidebar"], [data-testid="stSidebar"] * {
            color: #0F172A !important;
        }
        
        /* ปรับสีตัวอักษรทั่วไปทั้งหมดให้สู้กับ Dark Mode */
        p, span, label, div[data-testid="stMarkdownContainer"] * { color: #0F172A !important; }
        button p, button span, div[data-testid="stAlert"] * { color: inherit !important; }
        [data-testid="stDataFrame"], [data-testid="stDataFrame"] * { color: #0F172A !important; }
        button[data-baseweb="tab"] p { color: #1E3A8A !important; font-weight: 600 !important; }
        
        [data-testid="stMetric"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E5E7EB !important;
            padding: 24px 20px !important;
            border-radius: 16px !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03) !important;
            transition: transform 0.2s;
        }
        [data-testid="stMetric"]:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06) !important; }
        
        [data-testid="stMetricLabel"] > div, [data-testid="stMetricLabel"] p { color: #64748B !important; font-size: 16px !important; font-weight: 600 !important; }
        [data-testid="stMetricValue"] > div { color: #0F172A !important; font-weight: 800 !important; font-size: 32px !important; }
        h1, h2, h3 { color: #1E3A8A !important; font-weight: 700 !important; padding-bottom: 10px; }
        
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background-color: #FFFFFF !important;
            border-radius: 16px !important;
            border: 1px solid #E5E7EB !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.02) !important;
            padding: 20px !important;
        }
        .streamlit-expanderHeader { background-color: #F8FAFC !important; border-radius: 8px !important; color: #1E3A8A !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

tz_th = timezone(timedelta(hours=7))

# ==========================================
# 1. ระบบ 3 ภาษา (Translations Dictionary) 100% Localization
# ==========================================
langs = {
    "ไทย": {
        "menu": "เมนูระบบ", "p_dash": "📊 ภาพรวมแดชบอร์ด", "p_order": "📦 จัดการคำสั่งซื้อ", "p_stat": "⚙️ ตั้งค่าพารามิเตอร์",
        "goal": "🎯 เป้าหมาย AI:", "g_cost": "ลดต้นทุน", "g_time": "ส่งตรงเวลา",
        "scen": "สถานการณ์จำลอง:", "s_norm": "ปกติ", "s_disrupt": "พายุเข้า/รถติดหนัก", "s_err": "ข้อมูลน้ำหนักเสีย",
        "btn_opt": "🧠 ให้ AI แก้ปัญหาอัตโนมัติ", "k_trk": "🚛 รถที่ใช้", "k_cst": "💰 ต้นทุนรวม (บาท)", "k_co2": "🌱 ปล่อย CO2 (kg)", "k_alt": "🚨 แจ้งเตือน",
        "map_t": "🗺️ ระบบติดตามรถแบบ Real-time", "alt_t": "🚨 การตรวจจับปัญหา", "no_err": "✅ ระบบทำงานปกติ",
        "tbl_t": "🗓️ ตารางขนส่งอัตโนมัติ (AI Schedule)", "spc_t": "ℹ️ ข้อมูลจำเพาะรถและการคำนวณ",
        "err_drv": "👨‍✈️ คนขับไม่พอ", "err_late": "⏰ ส่งล่าช้า (ออกรถในอดีต)", "err_wt": "⚠️ น้ำหนักเป็น 0",
        "cmp_t": "📈 เปรียบเทียบค่าพารามิเตอร์ (ก่อน vs หลัง AI แก้ปัญหา)",
        "auto_del": "🗑️ ออเดอร์ส่งสำเร็จและลบออกจากไฟล์อัตโนมัติ",
        "o_tab1": "📄 อัปโหลดไฟล์ (CSV/Excel)", "o_tab2": "✍️ กรอกข้อมูลเอง", "o_upbtn": "บันทึกข้อมูลจากไฟล์", "o_save": "บันทึกคำสั่งซื้อ",
        "o_cur": "📋 รายการคำสั่งซื้อทั้งหมด", "p_drv": "🚚 จำนวนคนขับที่มี", "p_fuel": "⛽ ราคาน้ำมัน", "p_route": "🌍 ข้อมูลด่านและระยะทาง"
    },
    "English": {
        "menu": "System Menu", "p_dash": "📊 Dashboard Overview", "p_order": "📦 Order Management", "p_stat": "⚙️ System Parameters",
        "goal": "🎯 AI Goal:", "g_cost": "Min Cost", "g_time": "Max On-time",
        "scen": "Select Scenario:", "s_norm": "Normal", "s_disrupt": "Storm/Traffic", "s_err": "Erroneous Data",
        "btn_opt": "🧠 Auto-Optimize Solutions", "k_trk": "🚛 Active Trucks", "k_cst": "💰 Total Cost (THB)", "k_co2": "🌱 CO2 (kg)", "k_alt": "🚨 Alerts",
        "map_t": "🗺️ Live Fleet Tracking", "alt_t": "🚨 Exception Alerts", "no_err": "✅ System Normal",
        "tbl_t": "🗓️ AI Generated Schedule", "spc_t": "ℹ️ Truck Specs & Equations",
        "err_drv": "👨‍✈️ Driver Shortage", "err_late": "⏰ Late Delivery (Past Dept)", "err_wt": "⚠️ Zero Weight",
        "cmp_t": "📈 Parameters Comparison (Before vs After AI Optimization)",
        "auto_del": "🗑️ Auto-deleted completed orders from file",
        "o_tab1": "📄 Upload File", "o_tab2": "✍️ Manual Entry", "o_upbtn": "Save from File", "o_save": "Save Order",
        "o_cur": "📋 Current Orders List", "p_drv": "🚚 Available Drivers", "p_fuel": "⛽ Fuel Price", "p_route": "🌍 Border & Route Data"
    },
    "中文": {
        "menu": "系统菜单", "p_dash": "📊 仪表板概览", "p_order": "📦 订单管理", "p_stat": "⚙️ 系统参数",
        "goal": "🎯 AI 目标:", "g_cost": "最低成本", "g_time": "准时交货",
        "scen": "选择场景:", "s_norm": "正常", "s_disrupt": "风暴/拥堵", "s_err": "数据错误",
        "btn_opt": "🧠 AI 自动优化解决问题", "k_trk": "🚛 运行卡车", "k_cst": "💰 总成本 (泰铢)", "k_co2": "🌱 CO2 (kg)", "k_alt": "🚨 警报",
        "map_t": "🗺️ 实时车队跟踪", "alt_t": "🚨 异常警报", "no_err": "✅ 系统正常",
        "tbl_t": "🗓️ AI 自动运输计划", "spc_t": "ℹ️ 卡车规格和方程式",
        "err_drv": "👨‍✈️ 司机短缺", "err_late": "⏰ 延迟交货 (过去时间)", "err_wt": "⚠️ 重量为0",
        "cmp_t": "📈 参数比较（优化前 vs 优化后）",
        "auto_del": "🗑️ 系统已自动删除完成的订单",
        "o_tab1": "📄 上传文件", "o_tab2": "✍️ 手动输入", "o_upbtn": "保存文件", "o_save": "保存订单",
        "o_cur": "📋 当前订单列表", "p_drv": "🚚 可用司机", "p_fuel": "⛽ 燃料价格", "p_route": "🌍 边界和路线数据"
    }
}

if 'fuel_price' not in st.session_state: st.session_state.fuel_price = 32.5
if 'driver_count' not in st.session_state: st.session_state.driver_count = 5
if 'trucks_schedule' not in st.session_state: st.session_state.trucks_schedule = []
if 'ai_issues' not in st.session_state: st.session_state.ai_issues = []
if 'last_scenario' not in st.session_state: st.session_state.last_scenario = "Normal"
if 'opt_history' not in st.session_state: st.session_state.opt_history = None

default_routes = pd.DataFrame({
    "Destination": ["Vientiane", "Penang", "Kuala Lumpur", "Kunming", "Guangzhou", "Hanoi", "Ho Chi Minh"],
    "Border_Name": ["Nong Khai", "Sadao", "Sadao", "Chiang Khong", "Mukdahan", "Nakhon Phanom", "Aranyaprathet"],
    "Distance_km": [650, 1100, 1450, 1200, 1800, 950, 900],
    "Congestion_hrs": [1.0, 2.5, 2.5, 4.0, 1.5, 1.0, 3.0],
    "Lat": [17.9757, 5.4141, 3.1390, 25.0400, 23.1291, 21.0285, 10.8231],
    "Lon": [102.6000, 100.3288, 101.6869, 102.7000, 113.2644, 105.8542, 106.6297]
})
if 'route_data' not in st.session_state: st.session_state.route_data = default_routes.copy()

origin_coords = [99.0084, 18.5733] # Hana Lamphun
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

@st.cache_data(ttl=3600)
def get_real_route(lon1, lat1, lon2, lat2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') == 'Ok' and payload.get('routes'):
            return payload['routes'][0]['geometry']['coordinates']
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning(
            "Failed to fetch real route for coordinates (%s, %s) -> (%s, %s): %s",
            lon1,
            lat1,
            lon2,
            lat2,
            exc,
        )
    return [[lon1, lat1], [lon2, lat2]]

def load_data():
    if os.path.exists(FILE_NAME): return pd.read_csv(FILE_NAME)
    return pd.DataFrame(columns=["Order_ID", "Origin", "Destination", "Weight_kg", "Volume_cbm", "Deadline", "Cargo_Type"])

def save_data(new_data_df):
    global data
    try:
        data = pd.concat([data, new_data_df], ignore_index=True).drop_duplicates(subset=['Order_ID'], keep='last')
        data.to_csv(FILE_NAME, index=False)
        return True
    except PermissionError:
        st.error("⚠️ ไม่สามารถบันทึกข้อมูลได้ เนื่องจากไฟล์ 'orders.csv' ถูกเปิดค้างไว้")
        return False

# โหลดข้อมูลในตอนเริ่มต้น
data = load_data()

# ==========================================
# ฟังก์ชันสร้างออเดอร์จำลองปัญหา (Auto-Inject Orders)
# ==========================================
def inject_problem_orders(scenario):
    global data
    now_dt = datetime.now(tz_th)
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")
    if scenario == "Disruption":
        prob_data = pd.DataFrame([
            {"Order_ID": f"DSR-{now_dt.microsecond}", "Origin": "Hana Lamphun", "Destination": "Guangzhou", "Weight_kg": 8000, "Volume_cbm": 15, "Deadline": now_str, "Cargo_Type": "Electronics"},
        ])
        save_data(prob_data)
        data = load_data()
    elif scenario == "Erroneous Data":
        prob_data = pd.DataFrame([
            {"Order_ID": f"ERR-{now_dt.microsecond}", "Origin": "Hana Lamphun", "Destination": "Penang", "Weight_kg": 0, "Volume_cbm": 5, "Deadline": (now_dt + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), "Cargo_Type": "Auto Parts"},
        ])
        save_data(prob_data)
        data = load_data()

# ==========================================
# Core AI Logic: Just-in-Time (JIT) Schedule
# ==========================================
def generate_schedule(scenario="Normal", ai_priority="Minimum Cost", t_dict=None):
    global data
    df_process = data.copy()
    issues = []
    now_th = datetime.now(tz_th)
    
    if scenario == "Disruption":
        st.session_state.route_data.loc[st.session_state.route_data['Border_Name'].isin(['Mukdahan', 'Chiang Khong']), 'Congestion_hrs'] = 15.0
    else:
        st.session_state.route_data['Congestion_hrs'] = default_routes['Congestion_hrs']

    erroneous = df_process[df_process['Weight_kg'] <= 0]
    if not erroneous.empty:
        issues.append(f"{t_dict['err_wt']} ({len(erroneous)} items) -> AI used 500kg mean.")
        df_process.loc[df_process['Weight_kg'] <= 0, 'Weight_kg'] = 500

    df_process['Deadline_DT'] = pd.to_datetime(df_process['Deadline'], errors='coerce')
    if df_process['Deadline_DT'].dt.tz is None: df_process['Deadline_DT'] = df_process['Deadline_DT'].dt.tz_localize(tz_th)
    else: df_process['Deadline_DT'] = df_process['Deadline_DT'].dt.tz_convert(tz_th)
    df_process['Deadline_DT'] = df_process['Deadline_DT'].fillna(now_th + timedelta(days=7))
    
    if ai_priority == "Minimum Cost": df_process = df_process.sort_values(by=['Destination', 'Weight_kg'], ascending=[True, False])
    else: df_process = df_process.sort_values(by=['Destination', 'Deadline_DT'], ascending=[True, True])
    
    trucks = []
    def check_conflict(existing_cargos, new_cargo):
        for ex_cargo in existing_cargos:
            for _, rule in st.session_state.cargo_rules.iterrows():
                if (not rule['Can_Ship_Together']) and ((new_cargo == rule['Cargo_1'] and ex_cargo == rule['Cargo_2']) or (new_cargo == rule['Cargo_2'] and ex_cargo == rule['Cargo_1'])): return True
        return False

    for idx, row in df_process.iterrows():
        placed = False
        for t in trucks:
            if t['Destination'] == row['Destination']:
                type_specs = truck_types[t['Truck_Type']]
                if (t['Weight'] + row['Weight_kg'] <= type_specs['cap_kg']) and (t['Volume'] + row['Volume_cbm'] <= type_specs['cap_cbm']) and (not check_conflict(t['Cargo_Types'], row['Cargo_Type'])):
                    t['Orders'].append(row['Order_ID']); t['Weight'] += row['Weight_kg']; t['Volume'] += row['Volume_cbm']; t['Cargo_Types'].add(row['Cargo_Type']); 
                    t['Deadline_DT'] = min(t['Deadline_DT'], row['Deadline_DT'])
                    placed = True
                    break
        if not placed:
            selected_type = "Small (4-Wheel)"
            if row['Weight_kg'] > truck_types["Small (4-Wheel)"]["cap_kg"] or row['Volume_cbm'] > truck_types["Small (4-Wheel)"]["cap_cbm"]: selected_type = "Medium (6-Wheel)"
            if row['Weight_kg'] > truck_types["Medium (6-Wheel)"]["cap_kg"] or row['Volume_cbm'] > truck_types["Medium (6-Wheel)"]["cap_cbm"]: selected_type = "Large (10-Wheel)"
            trucks.append({"Truck_ID": f"TRK-{len(trucks)+1:03d}", "Truck_Type": selected_type, "Driver_Name": f"Driver {len(trucks)+1}" if len(trucks) < st.session_state.driver_count else "UNASSIGNED", "Destination": row['Destination'], "Weight": row['Weight_kg'], "Volume": row['Volume_cbm'], "Orders": [row['Order_ID']], "Cargo_Types": {row['Cargo_Type']}, "Deadline_DT": row['Deadline_DT']})
            
    final_schedule = []
    completed_order_ids = []
    
    for t in trucks:
        route = st.session_state.route_data[st.session_state.route_data['Destination'] == t['Destination']].iloc[0]
        dist = route['Distance_km']
        specs = truck_types[t['Truck_Type']]
        
        # JIT Time Calculation (ออกรถตรงเวลา ไม่ลงของ กลับทันที)
        travel_outbound_hrs = (dist / SPEED_LIMIT_KMH) + route['Congestion_hrs']
        dept_time = t['Deadline_DT'] - timedelta(hours=travel_outbound_hrs) 
        eta_dest = t['Deadline_DT']
        
        # Return Trip Calculation (ตีกลับทันที + เติมน้ำมัน 30 นาที)
        dept_return = eta_dest 
        travel_inbound_hrs = (dist / SPEED_LIMIT_KMH) + 0.5 
        eta_origin = dept_return + timedelta(hours=travel_inbound_hrs)
        
        # ถ้ารถวิ่งกลับมาถึงฐานเรียบร้อยแล้ว ให้เตรียมลบออเดอร์ออกจากไฟล์
        if eta_origin <= now_th:
            completed_order_ids.extend(t['Orders'])
        
        l_per_km_actual = (1.0/specs['base_km_l']) + ((1.0/specs['loaded_km_l']) - (1.0/specs['base_km_l'])) * min(t['Weight'] / specs['cap_kg'], 1.0)
        l_per_km_return = (1.0/specs['base_km_l']) 
        fuel_cost = ((dist * l_per_km_actual) + (dist * l_per_km_return)) * st.session_state.fuel_price
        
        final_schedule.append({
            "Truck_ID": t['Truck_ID'], "Type": t['Truck_Type'], "Driver": t['Driver_Name'], "Destination": t['Destination'],
            "Dept_Time": dept_time.strftime("%Y-%m-%d %H:%M"), "Weight_kg": t['Weight'],
            "Cost_THB": fuel_cost + 1500, "Emissions_kg": dist * 2 * 0.8, 
            "ETA_Dest": eta_dest.strftime("%Y-%m-%d %H:%M"), "Dept_Ret": dept_return.strftime("%Y-%m-%d %H:%M"), "ETA_Origin": eta_origin.strftime("%Y-%m-%d %H:%M"),
            "Late_Risk": "Yes" if dept_time < now_th else "No", "Orders": ", ".join(t['Orders'])
        })
    
    if len(trucks) > st.session_state.driver_count: issues.append(f"{t_dict['err_drv']} ({len(trucks)} vs {st.session_state.driver_count})")
    for t in final_schedule:
        if t['Late_Risk'] == "Yes": issues.append(f"{t_dict['err_late']} -> TRK: {t['Truck_ID']} (Dept: {t['Dept_Time']})")

    # [ระบบลบออเดอร์อัตโนมัติ] เมื่อรถกลับถึงฐาน ลบออกจาก orders.csv ทันที
    if completed_order_ids:
        data = data[~data['Order_ID'].isin(completed_order_ids)]
        try:
            data.to_csv(FILE_NAME, index=False)
            st.cache_data.clear()
            st.toast(f"{t_dict.get('auto_del', 'Deleted')}: {len(completed_order_ids)} items")
        except PermissionError:
            pass # หากไฟล์เปิดค้างไว้ จะทำการลบใหม่ในรอบถัดไป

    st.session_state.trucks_schedule = final_schedule
    st.session_state.ai_issues = issues

# ==========================================
# Sidebar 
# ==========================================
with st.sidebar:
    selected_lang = st.selectbox("🌐 Language / ภาษา / 语言", ["ไทย", "English", "中文"])
    t = langs[selected_lang]
    st.title("🚛 BorderLoad AI")
    
    st.markdown(f"**{t['menu']}**")
    page = st.radio("Nav", [t["p_dash"], t["p_order"], t["p_stat"]], label_visibility="collapsed")
    
    st.divider()
    st.markdown(f"**{t['goal']}**")
    ai_priority = st.radio("Goal", [t["g_cost"], t["g_time"]], label_visibility="collapsed")
    ai_priority_en = "Minimum Cost" if ai_priority == t["g_cost"] else "Max On-time Delivery"
    
    st.divider()
    st.caption("📍 TIMEZONE: THAILAND (UTC+7)")

# ==========================================
# Page 1: Dashboard
# ==========================================
if page == t["p_dash"]:
    st.header(t["p_dash"])
    
    with st.container(border=True):
        col_scen, col_opt = st.columns([2, 1])
        with col_scen:
            scen_sel = st.radio(t["scen"], [t["s_norm"], t["s_disrupt"], t["s_err"]], horizontal=True)
            scen_key = "Normal" if scen_sel == t["s_norm"] else "Disruption" if scen_sel == t["s_disrupt"] else "Erroneous Data"
            
            if scen_key != st.session_state.last_scenario:
                st.session_state.last_scenario = scen_key
                inject_problem_orders(scen_key)
                st.session_state.opt_history = None 
            
        with col_opt:
            st.write("") 
            if st.button(t["btn_opt"], type="primary", use_container_width=True):
                before_drivers = st.session_state.driver_count
                before_hour = st.session_state.dispatch_hour
                initial_issues_count = len(st.session_state.ai_issues) # จำจำนวนปัญหาเริ่มต้นไว้
                
                iteration = 0
                # ลูปจะทำงานจนกว่า ปัญหาจะหมดไป (0) หรือ อย่างน้อยปัญหามันลดลง 1 อย่าง (< initial)
                while len(st.session_state.ai_issues) > 0 and len(st.session_state.ai_issues) >= initial_issues_count and iteration < 10:
                    issues_str = str(st.session_state.ai_issues)
                    
                    if "Driver Shortage" in issues_str or "คนขับ" in issues_str or "司机" in issues_str: 
                        st.session_state.driver_count += 1
                        
                    if "Late Delivery" in issues_str or "ล่าช้า" in issues_str or "延迟" in issues_str: 
                        st.session_state.dispatch_hour -= 2 
                        if st.session_state.dispatch_hour < 0: 
                            st.session_state.dispatch_hour = 23 # หากเวลาถอยไปติดลบ ให้วนกลับไปเที่ยงคืน
                            
                    generate_schedule(scen_key, ai_priority_en, t)
                    iteration += 1
                
                st.session_state.opt_history = pd.DataFrame({
                    "Parameters / ตัวชี้วัด": ["Available Drivers (คนขับที่ต้องใช้)", "Departure Hour (เวลาออกรถ)"],
                    "Before (ก่อนแก้)": [before_drivers, f"{before_hour}:00"],
                    "After AI Optimize (หลังแก้)": [st.session_state.driver_count, f"{st.session_state.dispatch_hour}:00"]
                })
                st.toast("✅ AI Optimization Complete!")

    if len(data) > 0: generate_schedule(scen_key, ai_priority_en, t)
    trucks = st.session_state.trucks_schedule
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t["k_trk"], f"{len(trucks)}")
    c2.metric(t["k_cst"], f"{sum(tr['Cost_THB'] for tr in trucks):,.0f}")
    c3.metric(t["k_co2"], f"{sum(tr['Emissions_kg'] for tr in trucks):,.1f}")
    c4.metric(t["k_alt"], f"{len(st.session_state.ai_issues)}", delta_color="inverse")

    if st.session_state.opt_history is not None:
        st.write("---")
        st.markdown(f"### {t['cmp_t']}")
        st.dataframe(st.session_state.opt_history, hide_index=True, use_container_width=True)

    st.write("---")
    map_col, alert_col = st.columns([2, 1])
    with map_col:
        st.subheader(t["map_t"])
        paths_t, paths_r, pos = [], [], []
        now_th = datetime.now(tz_th)
        
        for tr in trucks:
            dest_info = st.session_state.route_data[st.session_state.route_data['Destination'] == tr['Destination']].iloc[0]
            coords = get_real_route(origin_coords[0], origin_coords[1], dest_info['Lon'], dest_info['Lat'])
            
            dept = datetime.strptime(tr['Dept_Time'], "%Y-%m-%d %H:%M").replace(tzinfo=tz_th)
            eta_dest = datetime.strptime(tr['ETA_Dest'], "%Y-%m-%d %H:%M").replace(tzinfo=tz_th)
            eta_org = datetime.strptime(tr['ETA_Origin'], "%Y-%m-%d %H:%M").replace(tzinfo=tz_th)
            
            # สีเส้นทาง (RGB)
            c_blue_dark  = [29, 78, 216]   # ขาไป ผ่านแล้ว (น้ำเงินเข้ม)
            c_blue_light = [147, 197, 253] # ขาไป ยังไม่ผ่าน (ฟ้า)
            c_grn_dark   = [22, 163, 74]   # ขากลับ ผ่านแล้ว (เขียวเข้ม)
            c_grn_light  = [134, 239, 172] # ขากลับ ยังไม่ผ่าน (เขียวอ่อน)
            
            if now_th < dept:
                progress, cur_lon, cur_lat = 0.0, origin_coords[0], origin_coords[1]
                path_t, path_r = [], coords
                status = "Waiting"
                color_t, color_r = c_blue_dark, c_blue_light
            elif dept <= now_th <= eta_dest:
                progress = (now_th - dept).total_seconds() / (eta_dest - dept).total_seconds()
                cut_idx = int((len(coords)-1) * progress)
                cur_lon, cur_lat = coords[cut_idx][0], coords[cut_idx][1]
                path_t, path_r = coords[:cut_idx+1], coords[cut_idx:]
                status = "Outbound"
                color_t, color_r = c_blue_dark, c_blue_light
            elif eta_dest < now_th <= eta_org:
                # ขากลับทันทีไม่ต้องรอลงของ (Inbound)
                progress = (now_th - eta_dest).total_seconds() / (eta_org - eta_dest).total_seconds()
                coords_rev = coords[::-1] 
                cut_idx = int((len(coords_rev)-1) * progress)
                cur_lon, cur_lat = coords_rev[cut_idx][0], coords_rev[cut_idx][1]
                path_t, path_r = coords_rev[:cut_idx+1], coords_rev[cut_idx:]
                status = "Inbound (Return + Refuel)"
                color_t, color_r = c_grn_dark, c_grn_light
            else:
                progress, cur_lon, cur_lat = 1.0, origin_coords[0], origin_coords[1]
                path_t, path_r = coords[::-1], []
                status = "Completed"
                color_t, color_r = c_grn_dark, c_grn_light

            # เพิ่มเส้นทางด้วยขนาดพิกเซลที่ปรับตามการซูมอัตโนมัติ (width_min_pixels, width_max_pixels)
            if len(path_t) > 1: paths_t.append({"path": path_t, "color": color_t})
            if len(path_r) > 1: paths_r.append({"path": path_r, "color": color_r})
            
            # วงกลมสีแดง พอดีกับเส้นทาง
            pos.append({
                "coord": [cur_lon, cur_lat], 
                "color": [220, 38, 38], 
                "info": f"TRK: {tr['Truck_ID']}\nStatus: {status}\nTo: {tr['Destination']}\nETA Return: {tr['ETA_Origin']}\nProgress: {progress*100:.1f}%"
            })

        if len(trucks) > 0:
            st.pydeck_chart(pdk.Deck(
                layers=[
                    pdk.Layer("PathLayer", paths_r, get_path="path", get_color="color", get_width=5000, width_min_pixels=3, width_max_pixels=8),
                    pdk.Layer("PathLayer", paths_t, get_path="path", get_color="color", get_width=5000, width_min_pixels=3, width_max_pixels=8),
                    pdk.Layer("ScatterplotLayer", pos, get_position="coord", get_fill_color="color", get_radius=6000, radius_min_pixels=5, radius_max_pixels=12, pickable=True)
                ], 
                initial_view_state=pdk.ViewState(latitude=15.0, longitude=102.0, zoom=4.5, pitch=40), tooltip={"text": "{info}"},
                map_style="dark"
            ))
        else: st.info("No data.")
            
    with alert_col:
        st.subheader(t["alt_t"])
        with st.container(border=True):
            if st.session_state.ai_issues:
                for issue in st.session_state.ai_issues: st.error(issue)
            else: st.success(t["no_err"])

    st.write("---")
    st.subheader(t["tbl_t"])
    if len(trucks) > 0: 
        # แสดงคอลัมน์ ETA_Origin ในตารางหลัก
        st.dataframe(pd.DataFrame(trucks)[['Truck_ID', 'Driver', 'Destination', 'Dept_Time', 'ETA_Dest', 'ETA_Origin', 'Cost_THB', 'Late_Risk']], use_container_width=True, hide_index=True)
    
    with st.expander(t["spc_t"]):
        st.latex(r"Fuel_{actual} = Fuel_{empty} + (Fuel_{full} - Fuel_{empty}) \times \left( \frac{Weight_{actual}}{Weight_{max}} \right)")
        st.dataframe(pd.DataFrame(truck_types).T, use_container_width=True)

# ==========================================
# Page 2: Orders 
# ==========================================
elif page == t["p_order"]:
    st.header(t["p_order"])
    with st.container(border=True):
        tab1, tab2 = st.tabs([t["o_tab1"], t["o_tab2"]])
        
        with tab1:
            st.info("รองรับไฟล์ .csv และ .xlsx")
            uploaded_file = st.file_uploader("Upload Orders File", type=["csv", "xlsx"])
            if uploaded_file and st.button(t["o_upbtn"], type="primary"):
                try:
                    df_upload = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    if save_data(df_upload):
                        st.success(f"Success! {len(df_upload)} items.")
                        data = load_data() # อัปเดตข้อมูลทันที
                        st.rerun()
                except (ValueError, TypeError, OSError, pd.errors.EmptyDataError, pd.errors.ParserError, KeyError) as e:
                    st.error(f"Error: {e}")

        with tab2, st.form("add_order_form", clear_on_submit=True):
            c = st.columns(3)
            new_order_id = c[0].text_input("Order ID")
            new_origin = c[1].text_input("Origin", value="Hana Lamphun")
            new_destination = c[2].selectbox("Destination", default_routes['Destination'].tolist())
            c2 = st.columns(4)
            new_weight = c2[0].number_input("Weight (kg)", min_value=1.0, value=500.0)
            new_volume = c2[1].number_input("Volume (CBM)", min_value=0.1, value=1.0)
            new_date = c2[2].date_input("Deadline Date")
            new_time = c2[3].time_input("Deadline Time")
            new_cargo = st.selectbox("Cargo Type", ["Electronics", "Auto Parts", "Food (Dry)", "Chemical", "Medical Supplies"])
            if (
                st.form_submit_button(t["o_save"], type="primary")
                and new_order_id.strip() != ""
                and save_data(pd.DataFrame([
                    {"Order_ID": new_order_id, "Origin": new_origin, "Destination": new_destination,
                     "Weight_kg": new_weight, "Volume_cbm": new_volume,
                     "Deadline": f"{new_date} {new_time.strftime('%H:%M')}", "Cargo_Type": new_cargo}
                ]))
            ):
                data = load_data() # อัปเดตข้อมูลทันทีหลังกรอกเสร็จ
                st.rerun()
                    
    st.subheader(t["o_cur"])
    st.dataframe(data, use_container_width=True, hide_index=True)

# ==========================================
# Page 3: Status
# ==========================================
elif page == t["p_stat"]:
    st.header(t["p_stat"])
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.number_input(t["p_drv"], key='driver_count')
        c2.number_input(t["p_fuel"], key='fuel_price')
    st.subheader(t["p_route"])
    st.data_editor(st.session_state.route_data, use_container_width=True, hide_index=True, key='route_edit')
 
