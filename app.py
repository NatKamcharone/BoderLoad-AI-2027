import logging
import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

try:
    import plotly.express as px
except ImportError:
    px = None

logger = logging.getLogger(__name__)

# ==========================================
# 0. Setup & UI Styling (UXPin, Gestalt, True Digital Academy Principles)
# ==========================================
st.set_page_config(page_title="BorderLoad AI Logistics", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")
FILE_NAME = "orders.csv"
COMPLETED_FILE = "completed_orders.csv"
EXCLUDED_FILE = "excluded_orders.csv"

# --- Custom CSS for Contrast, Accessibility (WCAG 2.1), and Visual Hierarchy ---
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stActionButtonDeploy"] {display: none;}
.stApp { background-color: #F8FAFC; }
html, body, [class*="css"] { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }

/* Sidebar Text and Color Styling (WCAG Contrast & Dark/Light Mode Safe) */
[data-testid="stSidebar"] {
    background-color: #F1F5F9 !important;
}
[data-testid="stSidebar"], [data-testid="stSidebar"] * {
    color: #1E293B !important;
}

/* Base text readability and dark mode override safety */
p, span, label, div[data-testid="stMarkdownContainer"] * { 
    color: #1E293B !important; 
    font-size: 15px;
}
h1, h2, h3, h4, h5, h6 {
    color: #1E3A8A !important;
    font-weight: 700 !important;
    font-family: 'Georgia', serif !important;
}

/* Beautiful Metric Cards with soft shadow and hover transition */
[data-testid="stMetric"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    padding: 20px 24px !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
    transition: transform 0.2s, box-shadow 0.2s;
}
[data-testid="stMetric"]:hover { 
    transform: translateY(-2px); 
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.05) !important; 
}
[data-testid="stMetricLabel"] > div, [data-testid="stMetricLabel"] p { 
    color: #64748B !important; 
    font-size: 14px !important; 
    font-weight: 600 !important; 
}
[data-testid="stMetricValue"] > div { 
    color: #0F172A !important; 
    font-weight: 800 !important; 
    font-size: 30px !important; 
}

/* Beautiful Border Containers for visual grouping (Gestalt Proximity) */
div[data-testid="stVerticalBlock"] > div[style*="border"] {
    background-color: #FFFFFF !important;
    border-radius: 12px !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05) !important;
    padding: 24px !important;
    margin-bottom: 16px;
}

/* Styling for Expander Header */
.streamlit-expanderHeader { 
    background-color: #F1F5F9 !important; 
    border-radius: 8px !important; 
    color: #1E3A8A !important; 
    font-weight: 600 !important; 
}
</style>
""", unsafe_allow_html=True)

tz_th = timezone(timedelta(hours=7))

# ==========================================
# 1. 3-Language Dictionary (100% Localization & Data Storytelling labels)
# ==========================================
langs = {
"ไทย": {
"menu": "เมนูระบบ", "p_dash": "📊 ภาพรวมแดชบอร์ด", "p_order": "📦 จัดการคำสั่งซื้อ", "p_stat": "⚙️ ตั้งค่าพารามิเตอร์",
"goal": "🎯 เป้าหมาย AI:", "g_cost": "ลดต้นทุน", "g_time": "ส่งตรงเวลา",
"scen": "สถานการณ์จำลอง:", "s_norm": "ปกติ", "s_disrupt": "พายุเข้า/ด่านล่าช้า", "s_err": "ข้อมูลน้ำหนักเสีย",
"btn_opt": "🧠 ให้ AI แก้ปัญหาอัตโนมัติ", "k_trk": "🚛 รถที่ใช้", "k_cst": "💰 ต้นทุนรวม (บาท)", "k_co2": "🌱 ปล่อย CO2 (kg)", "k_alt": "🚨 แจ้งเตือน",
"map_t": "🗺️ ระบบติดตามรถแบบ Real-time", "alt_t": "🚨 การตรวจจับปัญหา", "no_err": "✅ ระบบทำงานปกติ",
"tbl_t": "🗓️ ตารางขนส่งอัตโนมัติ (AI Schedule)", "spc_t": "ℹ️ ข้อมูลจำเพาะรถและการคำนวณ",
"err_drv": "👨✈️ คนขับไม่พอ", "err_late": "⏰ ส่งล่าช้า (ปรับแก้แผนเวลาแบบ Forward)", "err_wt": "⚠️ น้ำหนักเป็น 0",
"cmp_t": "📈 เปรียบเทียบค่าพารามิเตอร์ (ก่อน vs หลัง AI แก้ปัญหา)",
"auto_del": "🗑️ ออเดอร์ส่งสำเร็จและลบออกจากไฟล์อัตโนมัติ",
"o_tab1": "📄 นำเข้าและป้อนข้อมูลใหม่", "o_tab2": "✍️ กรอกข้อมูลเอง", "o_upbtn": "บันทึกข้อมูลจากไฟล์", "o_save": "บันทึกคำสั่งซื้อ",
"o_cur": "📋 รายการคำสั่งซื้อทั้งหมด", "p_drv": "🚚 จำนวนคนขับที่มี", "p_fuel": "⛽ ราคาน้ำมัน", "p_route": "🌍 ข้อมูลด่านและระยะทาง",
# Localized metrics
"lbl_util": "📊 อัตราการใช้รถ (%)",
"lbl_cost_ship": "💰 ต้นทุนเฉลี่ยรายออเดอร์",
"lbl_cost_tkm": "⛽ ต้นทุนต่อ ตัน-กม.",
"lbl_empty": "🔄 สัดส่วนระยะวิ่งรถเปล่า",
"lbl_workload": "👨‍✈️ ภาระงานสะสม (ชม.)",
"lbl_late_prob": "🎯 โอกาสจัดส่งล่าช้า",
"lbl_border_hours": "⏰ เวลาเปิด-ปิดด่าน",
"lbl_human_panel": "👥 แผงควบคุมมนุษย์ (Human Override)",
"lbl_split_btn": "🚫 ห้ามรวมกลุ่มคำสั่งซื้อนี้ (Split)",
"lbl_change_driver": "👨‍✈️ เปลี่ยนคนขับ",
"lbl_change_truck": "🚛 เปลี่ยนประเภทรถ",
"lbl_backhaul": "🔄 จับคู่ขากลับ (0% รถเปล่า & ประหยัดค่าน้ำมัน)",
"err_work": "⚠️ คนขับขับเกินชั่วโมงกำหนด (เมื่อคิดชิฟต์ต่อเนื่องและหักล้างชั่วโมงพัก)",
"err_border_close": "⏰ ด่านปิดตอนถึงด่าน (ปรับทริปขยับพ้นด่านปิด)",
"err_impossible_time": "⏳ กำหนดเดดไลน์กระชั้นชิดเกินไป (ไม่เพียงพอสำหรับเดินทางเชิงฟิสิกส์)",
"err_driver_insufficient": "👨‍✈️ กำลังพลคนขับไม่เพียงพอสำหรับรอบวิเคราะห์ปัจจุบัน",
"lbl_data_req_panel": "📋 รายงานความต้องการข้อมูล & ทรัพยากรเพิ่มเติม (Additional Data & Resources)",
"lbl_orders": "คำสั่งซื้อร่วม", "lbl_weight_util": "อัตราน้ำหนัก", "lbl_volume_util": "อัตราปริมาตร"
},
"English": {
"menu": "System Menu", "p_dash": "📊 Dashboard Overview", "p_order": "📦 Order Management", "p_stat": "⚙️ System Parameters",
"goal": "🎯 AI Goal:", "g_cost": "Min Cost", "g_time": "Max On-time",
"scen": "Select Scenario:", "s_norm": "Normal", "s_disrupt": "Storm/Traffic", "s_err": "Erroneous Data",
"btn_opt": "🧠 Auto-Optimize Solutions", "k_trk": "🚛 Active Trucks", "k_cst": "💰 Total Cost (THB)", "k_co2": "🌱 CO2 (kg)", "k_alt": "🚨 Alerts",
"map_t": "🗺️ Live Fleet Tracking", "alt_t": "🚨 Exception Alerts", "no_err": "✅ System Normal",
"tbl_t": "🗓️ AI Generated Schedule", "spc_t": "ℹ️ Truck Specs & Equations",
"err_drv": "👨✈️ Driver Shortage", "err_late": "⏰ Late Delivery (Forward Scheduled)", "err_wt": "⚠️ Zero Weight",
"cmp_t": "📈 Parameters Comparison (Before vs After AI Optimization)",
"auto_del": "🗑️ Auto-deleted completed orders from file",
"o_tab1": "📄 Import & Add New Orders", "o_tab2": "✍️ Manual Entry", "o_upbtn": "Save from File", "o_save": "Save Order",
"o_cur": "📋 Current Orders List", "p_drv": "🚚 Available Drivers", "p_fuel": "⛽ Fuel Price", "p_route": "🌍 Border & Route Data",
# Localized metrics
"lbl_util": "📊 Truck Utilization (%)",
"lbl_cost_ship": "💰 Cost per Shipment",
"lbl_cost_tkm": "⛽ Cost per Tonne-Km",
"lbl_empty": "🔄 Empty-Distance Rate",
"lbl_workload": "👨‍✈️ Driver Shift Workload (hrs)",
"lbl_late_prob": "🎯 Late Probability",
"lbl_border_hours": "⏰ Border Opening Hours",
"lbl_human_panel": "👥 Human Override Panel",
"lbl_split_btn": "🚫 Split Order (No Consolidation)",
"lbl_change_driver": "👨‍✈️ Change Driver",
"lbl_change_truck": "🚛 Change Truck Type",
"lbl_backhaul": "🔄 Enable Backhaul (0% Empty Rate & Fuel Discount)",
"err_work": "⚠️ Driver Exceeded Hours Limit (Shift limit with rest check)",
"err_border_close": "⏰ Border Closed at Arrival (Wait required)",
"err_impossible_time": "⏳ Deadline is too tight (physically impossible under standard transit)",
"err_driver_insufficient": "👨‍✈️ Driver resources are insufficient for the current operational shift",
"lbl_data_req_panel": "📋 Additional Logistics Data & Resource Requirements",
"lbl_orders": "Consolidated Orders", "lbl_weight_util": "Weight Util", "lbl_volume_util": "Volume Util"
},
"中文": {
"menu": "系统菜单", "p_dash": "📊 仪表板概览", "p_order": "📦 订单管理", "p_stat": "⚙️ 系统参数",
"goal": "🎯 AI 目标:", "g_cost": "最低成本", "g_time": "准时交货",
"scen": "选择场景:", "s_norm": "正常", "s_disrupt": "风暴/拥堵", "s_err": "数据错误",
"btn_opt": "🧠 AI 自动优化解决问题", "k_trk": "🚛 运行卡车", "k_cst": "💰 总成本 (泰铢)", "k_co2": "🌱 CO2 (kg)", "k_alt": "🚨 警报",
"map_t": "🗺️ 实时车队跟踪", "alt_t": "🚨 异常警报", "no_err": "✅ 系统正常",
"tbl_t": "🗓️ AI 自动运输计划", "spc_t": "ℹ️ 卡车规格和方程式",
"err_drv": "👨✈️ 司机短缺", "err_late": "⏰ 延迟交货 (前向排程调整)", "err_wt": "⚠️ 重量为0",
"cmp_t": "📈 参数比较（优化前 vs 优化后）",
"auto_del": "🗑️ 系统已自动删除完成的订单",
"o_tab1": "📄 导入和管理新订单", "o_tab2": "✍️ 手动输入", "o_upbtn": "保存文件", "o_save": "保存订单",
"o_cur": "📋 当前订单列表", "p_drv": "🚚 可用司机", "p_fuel": "⛽ 燃料价格", "p_route": "🌍 边界和路线数据",
# Localized metrics
"lbl_util": "📊 卡车利用率 (%)",
"lbl_cost_ship": "💰 每单分摊成本",
"lbl_cost_tkm": "⛽ 每吨-公里成本",
"lbl_empty": "🔄 空驶率",
"lbl_workload": "👨‍✈️ 司机累计工作时间 (小时)",
"lbl_late_prob": "🎯 延迟交货概率",
"lbl_border_hours": "⏰ 边境通关时间",
"lbl_human_panel": "👥 人工干预控制板",
"lbl_split_btn": "🚫 拆分此订单 (不合并)",
"lbl_change_driver": "👨‍✈️ 更换司机",
"lbl_change_truck": "🚛 更改车型",
"lbl_backhaul": "🔄 回程配货 (0% 空载 & 燃料折扣)",
"err_work": "⚠️ 司机超出工作时长限制 (含连续休息重置校验)",
"err_border_close": "⏰ 到达时边境关闭 (已安排时间移动)",
"err_impossible_time": "⏳ 截止日期太紧（物理距离和行程限制下无法实现）",
"err_driver_insufficient": "👨‍✈️ 当前运营班次的司机资源不足",
"lbl_data_req_panel": "📋 额外物流数据与资源需求报告",
"lbl_orders": "合并订单", "lbl_weight_util": "重量装载率", "lbl_volume_util": "体积装载率"
}
}

# ==========================================
# 2. Session State Initializations
# ==========================================
if 'fuel_price' not in st.session_state: st.session_state.fuel_price = 32.54 # Bangchak Retail Price
if 'driver_count' not in st.session_state: st.session_state.driver_count = 25 # Initial Sufficient Drivers
if 'dispatch_hour' not in st.session_state: st.session_state.dispatch_hour = 8
if 'trucks_schedule' not in st.session_state: st.session_state.trucks_schedule = []
if 'ai_issues' not in st.session_state: st.session_state.ai_issues = []
if 'last_scenario' not in st.session_state: st.session_state.last_scenario = "Normal"
if 'opt_history' not in st.session_state: st.session_state.opt_history = None
if 'ai_run_executed' not in st.session_state: st.session_state.ai_run_executed = False

# Advanced trans-border parameters
if 'border_open' not in st.session_state: st.session_state.border_open = 6 # 06:00 AM
if 'border_close' not in st.session_state: st.session_state.border_close = 22 # 10:00 PM
if 'driver_hour_limit' not in st.session_state: st.session_state.driver_hour_limit = 10.0 # Max driving/duty hours per shift
if 'human_overrides' not in st.session_state:
    st.session_state.human_overrides = {
        "driver_assignments": {},
        "truck_types": {},
        "split_orders": [],
        "backhaul_enabled": {}
    }

# New structures for interactive mitigation & newly added orders tracking
if 'new_order_ids' not in st.session_state:
    st.session_state.new_order_ids = set()
if 'mitigation_decisions' not in st.session_state:
    st.session_state.mitigation_decisions = {} # {order_id: "Pending" / "Accepted" / "Rejected"}

default_routes = pd.DataFrame({
"Destination": ["Vientiane", "Penang", "Kuala Lumpur", "Kunming", "Guangzhou", "Hanoi", "Ho Chi Minh"],
"Border_Name": ["Nong Khai", "Sadao", "Sadao", "Chiang Khong", "Mukdahan", "Nakhon Phanom", "Aranyaprathet"],
"Distance_km": [650, 1100, 1450, 1200, 1800, 950, 900],
"Congestion_hrs": [1.0, 2.5, 2.5, 4.0, 1.5, 1.0, 3.0],
"Lat": [17.9757, 5.4141, 3.1390, 25.0400, 23.1291, 21.0285, 10.8231],
"Lon": [102.6000, 100.3288, 101.6869, 102.7000, 113.2644, 105.8542, 106.6297],
# Real border opening hours as specified by border policies
"Open_Hr": [6.0, 0.0, 0.0, 6.0, 6.0, 6.0, 8.0],        # Sadao is 24h (0.0), Aranyaprathet is 08:00
"Close_Hr": [22.0, 24.0, 24.0, 22.0, 22.0, 22.0, 16.0]   # Sadao is 24h (24.0), Aranyaprathet is 16:00
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
    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            "Failed to fetch real route for coordinates (%s, %s) -> (%s, %s): %s",
            lon1, lat1, lon2, lat2, exc,
        )
    return [[lon1, lat1], [lon2, lat2]]

def load_data():
    if os.path.exists(FILE_NAME):
        return pd.read_csv(FILE_NAME)
    return pd.DataFrame(columns=["Order_ID", "Origin", "Destination", "Weight_kg", "Volume_cbm", "Deadline", "Cargo_Type"])

def load_completed_data():
    if os.path.exists(COMPLETED_FILE):
        return pd.read_csv(COMPLETED_FILE)
    return pd.DataFrame(columns=["Order_ID", "Origin", "Destination", "Weight_kg", "Volume_cbm", "Deadline", "Cargo_Type", "Completed_Time"])

def load_excluded_data():
    if os.path.exists(EXCLUDED_FILE):
        return pd.read_csv(EXCLUDED_FILE)
    return pd.DataFrame(columns=["Order_ID", "Origin", "Destination", "Weight_kg", "Volume_cbm", "Deadline", "Cargo_Type", "Excluded_Time", "Reason"])

def save_data(new_data_df):
    global data
    try:
        data = pd.concat([data, new_data_df], ignore_index=True).drop_duplicates(subset=['Order_ID'], keep='last')
        data.to_csv(FILE_NAME, index=False)
        return True
    except PermissionError:
        st.error("⚠️ ไม่สามารถบันทึกข้อมูลได้ เนื่องจากไฟล์ 'orders.csv' ถูกเปิดค้างไว้")
        return False

def save_completed_data(df_completed):
    try:
        if os.path.exists(COMPLETED_FILE):
            existing = pd.read_csv(COMPLETED_FILE)
            updated = pd.concat([existing, df_completed], ignore_index=True).drop_duplicates(subset=['Order_ID'], keep='last')
            updated.to_csv(COMPLETED_FILE, index=False)
        else:
            df_completed.to_csv(COMPLETED_FILE, index=False)
    except PermissionError:
        pass

def save_excluded_data(df_excluded):
    try:
        if os.path.exists(EXCLUDED_FILE):
            existing = pd.read_csv(EXCLUDED_FILE)
            updated = pd.concat([existing, df_excluded], ignore_index=True).drop_duplicates(subset=['Order_ID'], keep='last')
            updated.to_csv(EXCLUDED_FILE, index=False)
        else:
            df_excluded.to_csv(EXCLUDED_FILE, index=False)
    except PermissionError:
        pass

# โหลดข้อมูลในตอนเริ่มต้น
data = load_data()

# ==========================================
# 3. สร้างตัวอย่างข้อมูล 30 รายการอัตโนมัติ (Common Requirement 6)
# ==========================================
def init_sample_data():
    global data
    if not os.path.exists(FILE_NAME) or os.stat(FILE_NAME).st_size <= 50:
        now_dt = datetime.now(tz_th)
        sample_orders = []
        destinations = ["Vientiane", "Penang", "Kuala Lumpur", "Kunming", "Guangzhou", "Hanoi", "Ho Chi Minh"]
        cargo_types = ["Electronics", "Auto Parts", "Food (Dry)", "Chemical", "Medical Supplies"]
        
        # Generate exactly 30 sample orders (Requirement 6)
        for i in range(1, 31):
            dest = destinations[i % len(destinations)]
            cargo = cargo_types[i % len(cargo_types)]
            days_offset = (i % 4) + 1 # 1 to 4 days
            hours_offset = (i * 3) % 24
            deadline_dt = now_dt + timedelta(days=days_offset, hours=hours_offset)
            deadline_str = deadline_dt.strftime("%Y-%m-%d %H:%M")
            
            # Realistic weight and volume
            weight = 500 + (i * 470) % 7500 # 500 - 8000 kg
            volume = 1.0 + (i * 1.3) % 14.0 # 1.0 - 15.0 cbm
            
            # Explicitly force cargo conflict test candidates
            if i in [11, 12]:
                dest = "Vientiane"
                cargo = "Chemical" if i == 11 else "Food (Dry)"
                
            sample_orders.append({
                "Order_ID": f"ORD-{i:03d}",
                "Origin": "Hana Lamphun",
                "Destination": dest,
                "Weight_kg": weight,
                "Volume_cbm": round(volume, 1),
                "Deadline": deadline_str,
                "Cargo_Type": cargo
            })
            
        df_samples = pd.DataFrame(sample_orders)
        df_samples.to_csv(FILE_NAME, index=False)
        data = load_data()

init_sample_data()

# ==========================================
# ฟังก์ชันสร้างออเดอร์จำลองปัญหา (Auto-Inject Orders)
# ==========================================
def inject_problem_orders(scenario):
    global data
    now_dt = datetime.now(tz_th)
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")
    
    # ดึงข้อมูลมาล้างประวัติออเดอร์จำลองขยะออกก่อน หากเปลี่ยนกลับมาเป็น Normal
    if scenario == "Normal":
        if os.path.exists(FILE_NAME):
            current_df = pd.read_csv(FILE_NAME)
            filtered_df = current_df[~current_df['Order_ID'].astype(str).str.startswith(('DSR-', 'ERR-'))]
            filtered_df.to_csv(FILE_NAME, index=False)
            st.session_state.new_order_ids = {o for o in st.session_state.new_order_ids if not o.startswith(('DSR-', 'ERR-'))}
            data = load_data()
            
    elif scenario == "Disruption":
        prob_id = f"DSR-{now_dt.microsecond}"
        prob_data = pd.DataFrame([
        {"Order_ID": prob_id, "Origin": "Hana Lamphun", "Destination": "Guangzhou", "Weight_kg": 8000, "Volume_cbm": 15, "Deadline": now_str, "Cargo_Type": "Electronics"},
        ])
        st.session_state.new_order_ids.add(prob_id)
        save_data(prob_data)
        data = load_data()
        
    elif scenario == "Erroneous Data":
        prob_id = f"ERR-{now_dt.microsecond}"
        prob_data = pd.DataFrame([
        {"Order_ID": prob_id, "Origin": "Hana Lamphun", "Destination": "Penang", "Weight_kg": 0, "Volume_cbm": 5, "Deadline": (now_dt + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), "Cargo_Type": "Auto Parts"},
        ])
        st.session_state.new_order_ids.add(prob_id)
        save_data(prob_data)
        data = load_data()

# ------------------------------------------
# [เพิ่ม] ระบบตรวจพบความผิดปกติของข้อมูลรายกริตคำสั่งซื้อ
# ------------------------------------------
def check_error_orders(df):
    err_list = []
    for idx, row in df.iterrows():
        try:
            w = float(row['Weight_kg'])
            v = float(row['Volume_cbm'])
            if w <= 0 or v <= 0 or pd.isna(w) or pd.isna(v):
                err_list.append(row.to_dict())
        except (ValueError, TypeError):
            err_list.append(row.to_dict())
    return err_list

# ==========================================
def get_rest_breaks(driving_hrs, limit):
    if driving_hrs <= 0: return 0
    breaks = int(driving_hrs // limit)
    if driving_hrs % limit == 0 and breaks > 0:
        breaks -= 1
    return breaks

# ------------------------------------------
# [เพิ่ม] ระบบประเมินความพร้อมและตรวจสอบเอกสารศุลกากรข้ามแดน (Customs Compliance Solver) [11, 426]
# ------------------------------------------
def evaluate_customs_compliance(order_id, cargo_type, weight):
    missing_docs = []
    inconsistencies = []
    delay_hours = 0.0
    
    # 1. จำลองการตรวจสอบเอกสารและจุดบกพร่องตามข้อบังคับในใบงานวิชาการ [11, 426]
    if "ORD-011" in order_id:
        missing_docs.append("Certificate of Origin (C/O) (ใบรับรองแหล่งกำเนิดสินค้าขาดหาย)")
        delay_hours += 6.0
    if "ORD-012" in order_id:
        inconsistencies.append("Packing List data mismatch (ข้อมูลรายการบรรจุสินค้าไม่ตรงใบตราส่ง)")
        delay_hours += 4.0
    if cargo_type == "Chemical":
        # สารเคมีต้องการเอกสาร Dangerous Goods Permit [11]
        missing_docs.append("Dangerous Goods Declaration Permit (ใบสำแดงประเภทสินค้าอันตราย)")
        delay_hours += 8.0
    if weight > 12000.0:
        inconsistencies.append("Axle weight limitation verification needed (ระวางล้อบรรทุกเกินขีดจำกัดสะพาน)")
        delay_hours += 5.0
        
    total_checks = 4
    failures = len(missing_docs) + len(inconsistencies)
    readiness_score = int(((total_checks - failures) / total_checks) * 100)
    
    if readiness_score >= 100:
        risk_level = "Low (ต่ำ)"
    elif readiness_score >= 75:
        risk_level = "Medium (ปานกลาง)"
    else:
        risk_level = "High (สูง)"
        
    return {
        "score": readiness_score,
        "missing": missing_docs,
        "inconsistencies": inconsistencies,
        "risk": risk_level,
        "delay": delay_hours
    }

# Core AI Logic: Just-in-Time (JIT) Schedule with Advanced Extensions
# ==========================================
def generate_schedule(scenario="Normal", ai_priority="Minimum Cost", t_dict=None):
    global data
    df_raw = data.copy()
    issues = []
    now_th = datetime.now(tz_th)
    
    # ดักปรับด่านแออัดเมื่อเกิดภัยพิบัติพายุ
    if scenario == "Disruption":
        st.session_state.route_data.loc[st.session_state.route_data['Border_Name'].isin(['Mukdahan', 'Chiang Khong']), 'Congestion_hrs'] = 15.0
    else:
        st.session_state.route_data['Congestion_hrs'] = default_routes['Congestion_hrs']
        
    # [แก้ไขใหม่] ดักล้างแถว Error ทิ้งเพื่อป้องการปันส่วนค่าน้ำมันพังเชิงกายภาพ
    erroneous = check_error_orders(df_raw)
    df_clean = df_raw[~df_raw['Order_ID'].isin([e['Order_ID'] for e in erroneous])]
        
    df_clean['Deadline_DT'] = pd.to_datetime(df_clean['Deadline'], errors='coerce')
    if df_clean['Deadline_DT'].dt.tz is None: 
        df_clean['Deadline_DT'] = df_clean['Deadline_DT'].dt.tz_localize(tz_th)
    else: 
        df_clean['Deadline_DT'] = df_clean['Deadline_DT'].dt.tz_convert(tz_th)
    df_clean['Deadline_DT'] = df_clean['Deadline_DT'].fillna(now_th + timedelta(days=7))

    # ------------------------------------------
    # AI OPTIMIZATION & MITIGATION: จัดการแยกกรองออเดอร์ใหม่ที่วิกฤตออกมารออนุมัติ
    # ------------------------------------------
    active_orders = []
    
    for idx, row in df_clean.iterrows():
        order_id = row['Order_ID']
        is_new = (order_id in st.session_state.new_order_ids) or order_id.startswith(("DSR-", "ERR-"))
        
        # คำนวณขีดจำกัดเวลาเชิงกายภาพขั้นต่ำ (ความเร็วรถบรรทุกเฉลี่ย 80 กม./ชม.)
        route_info = st.session_state.route_data[st.session_state.route_data['Destination'] == row['Destination']].iloc[0]
        dist_km = route_info['Distance_km']
        min_transit_standard = ((dist_km / SPEED_LIMIT_KMH) * 2) + route_info['Congestion_hrs'] # เดินทางไปกลับ
        time_left_hrs = (row['Deadline_DT'] - now_th).total_seconds() / 3600.0
        
        # คัดกรองออเดอร์ใหม่ที่เกินขีดจำกัดเวลา (Time left < Outbound Transit)
        if is_new and (time_left_hrs < (min_transit_standard / 2.0)):
            if order_id not in st.session_state.mitigation_decisions:
                st.session_state.mitigation_decisions[order_id] = "Pending"
                
            decision = st.session_state.mitigation_decisions[order_id]
            if decision == "Rejected":
                # ตัดออกจากระบบและย้ายไปประวัติปฏิเสธ
                continue
            elif decision == "Accepted":
                # จัดกลุ่มเข้าตารางปกติเพื่อสลับทีมคนขับคู่หูแก้ปัญหา
                active_orders.append(row)
            else:
                # พักแผนรอการตอบรับจากมนุษย์
                issues.append(f"⏳ {t_dict['err_impossible_time']} -> {order_id} ({row['Destination']}): รอมนุษย์ยืนยันแผนแก้ไขปัญหาหน้างาน")
                continue
        else:
            active_orders.append(row)
            
    df_process = pd.DataFrame(active_orders) if active_orders else pd.DataFrame(columns=df_clean.columns)
    
    if df_process.empty:
        st.session_state.trucks_schedule = []
        st.session_state.ai_issues = issues
        return
        
    if ai_priority == "Minimum Cost": 
        df_process = df_process.sort_values(by=['Destination', 'Weight_kg'], ascending=[True, False])
    else: 
        df_process = df_process.sort_values(by=['Destination', 'Deadline_DT'], ascending=[True, True])
        
    trucks = []
    
    def check_conflict(existing_cargos, new_cargo):
        for ex_cargo in existing_cargos:
            for _, rule in st.session_state.cargo_rules.iterrows():
                if (not rule['Can_Ship_Together']) and ((new_cargo == rule['Cargo_1'] and ex_cargo == rule['Cargo_2']) or (new_cargo == rule['Cargo_2'] and ex_cargo == rule['Cargo_1'])): 
                    return True
        return False
        
    # Apply Human Overrides for Consolidation Splits
    split_orders = st.session_state.human_overrides.get('split_orders', [])
    
    for idx, row in df_process.iterrows():
        placed = False
        is_split = row['Order_ID'] in split_orders
        
        if not is_split:
            for t in trucks:
                if t['Destination'] == row['Destination']:
                    # Retrieve overridden truck type if set
                    type_specs = truck_types[st.session_state.human_overrides.get("truck_types", {}).get(t['Truck_ID'], t['Truck_Type'])]
                    if (t['Weight'] + row['Weight_kg'] <= type_specs['cap_kg']) and (t['Volume'] + row['Volume_cbm'] <= type_specs['cap_cbm']) and (not check_conflict(t['Cargo_Types'], row['Cargo_Type'])):
                        t['Orders'].append(row['Order_ID'])
                        t['Weight'] += row['Weight_kg']
                        t['Volume'] += row['Volume_cbm']
                        t['Cargo_Types'].add(row['Cargo_Type'])
                        t['Deadline_DT'] = min(t['Deadline_DT'], row['Deadline_DT'])
                        placed = True
                        break
                        
        if not placed:
            selected_type = "Small (4-Wheel)"
            if row['Weight_kg'] > truck_types["Small (4-Wheel)"]["cap_kg"] or row['Volume_cbm'] > truck_types["Small (4-Wheel)"]["cap_cbm"]: 
                selected_type = "Medium (6-Wheel)"
            if row['Weight_kg'] > truck_types["Medium (6-Wheel)"]["cap_kg"] or row['Volume_cbm'] > truck_types["Medium (6-Wheel)"]["cap_cbm"]: 
                selected_type = "Large (10-Wheel)"
                
            truck_id = f"TRK-{len(trucks)+1:03d}"
            
            # Apply Human Override on Truck Type
            selected_type = st.session_state.human_overrides.get("truck_types", {}).get(truck_id, selected_type)
            
            # Apply Human Override on Driver Assignment
            default_driver = f"Driver {len(trucks)+1}" if len(trucks) < st.session_state.driver_count else "UNASSIGNED"
            assigned_driver = st.session_state.human_overrides.get("driver_assignments", {}).get(truck_id, default_driver)
            
            trucks.append({
                "Truck_ID": truck_id, 
                "Truck_Type": selected_type, 
                "Driver_Name": assigned_driver, 
                "Destination": row['Destination'], 
                "Weight": row['Weight_kg'], 
                "Volume": row['Volume_cbm'], 
                "Orders": [row['Order_ID']], 
                "Cargo_Types": {row['Cargo_Type']}, 
                "Deadline_DT": row['Deadline_DT']
            })
            
    final_schedule = []
    completed_order_ids = []
    
    for t in trucks:
        route = st.session_state.route_data[st.session_state.route_data['Destination'] == t['Destination']].iloc[0]
        dist = route['Distance_km']
        
        # Check human override on truck type again in specs calculation
        actual_type = st.session_state.human_overrides.get("truck_types", {}).get(t['Truck_ID'], t['Truck_Type'])
        specs = truck_types[actual_type]
        
        # 1. Base Leg 2 (Border to Destination) JIT calculation with rest stops
        limit = st.session_state.driver_hour_limit
        double_driver = False
        
        # ตรวจเช็คว่าออเดอร์ภายในคันนี้ได้รับการยอมรับแบบคู่หูไว้หรือไม่
        forced_double = any(o in st.session_state.mitigation_decisions and st.session_state.mitigation_decisions[o] == "Accepted" for o in t['Orders'])
        
        # We first check if the deadline is physically possible under 1-driver rules
        leg2_driving = (dist / 2) / SPEED_LIMIT_KMH
        breaks_leg2 = get_rest_breaks(leg2_driving, limit)
        leg2_elapsed = leg2_driving + (breaks_leg2 * 10.0) + route['Congestion_hrs']
        
        leg1_driving = (dist / 2) / SPEED_LIMIT_KMH
        breaks_leg1 = get_rest_breaks(leg1_driving, limit)
        leg1_elapsed = leg1_driving + (breaks_leg1 * 10.0)
        
        travel_outbound_hrs_standard = leg1_elapsed + leg2_elapsed
        time_left_hrs = (t['Deadline_DT'] - now_th).total_seconds() / 3600.0
        
        # AI OPTIMIZATION: หากเดดไลน์กระชั้นหรือเวลาเริ่มออกรถติดลบ ให้จัดสรรทีมคนขับคู่หูวิ่งลากยาว (พักสะสม = 0)
        if forced_double or time_left_hrs < travel_outbound_hrs_standard or (t['Deadline_DT'] - timedelta(hours=travel_outbound_hrs_standard) < now_th):
            double_driver = True
            breaks_leg1 = 0
            breaks_leg2 = 0
            leg1_elapsed = leg1_driving
            leg2_elapsed = leg2_driving + route['Congestion_hrs']
            travel_outbound_hrs = leg1_elapsed + leg2_elapsed
        else:
            travel_outbound_hrs = travel_outbound_hrs_standard
            
        border_crossing_time = t['Deadline_DT'] - timedelta(hours=leg2_elapsed)
        
        # 2. Border Opening/Closing Hours Check with JIT Feedback Loop Optimization (using route-specific hours)
        open_hr = route.get('Open_Hr', 6.0)
        close_hr = route.get('Close_Hr', 22.0)
        crossing_hour = border_crossing_time.hour + border_crossing_time.minute / 60.0
        
        is_open_24h = (open_hr == 0.0 and close_hr >= 24.0)
        border_wait_hrs = 0.0
        
        if (not is_open_24h) and (crossing_hour < open_hr or crossing_hour > close_hr):
            # Option A: Shift earlier (cross before close of same/previous day)
            if crossing_hour < open_hr:
                border_crossing_time_A = border_crossing_time.replace(hour=int(close_hr), minute=0, second=0, microsecond=0) - timedelta(days=1)
            else:
                border_crossing_time_A = border_crossing_time.replace(hour=int(close_hr), minute=0, second=0, microsecond=0)
            
            dept_time_A = border_crossing_time_A - timedelta(hours=leg1_elapsed)
            
            # Option B: Shift later (cross at opening)
            if crossing_hour < open_hr:
                border_crossing_time_B = border_crossing_time.replace(hour=int(open_hr), minute=0, second=0, microsecond=0)
            else:
                border_crossing_time_B = border_crossing_time.replace(hour=int(open_hr), minute=0, second=0, microsecond=0) + timedelta(days=1)
            
            dept_time_B = border_crossing_time_B - timedelta(hours=leg1_elapsed)
            
            # Prefer Option A if it doesn't cause a past departure, else Option B
            if dept_time_A >= now_th:
                border_crossing_time = border_crossing_time_A
                border_wait_hrs = (border_crossing_time - (t['Deadline_DT'] - timedelta(hours=leg2_elapsed))).total_seconds() / 3600.0
            elif dept_time_B >= now_th:
                border_crossing_time = border_crossing_time_B
                border_wait_hrs = (border_crossing_time - (t['Deadline_DT'] - timedelta(hours=leg2_elapsed))).total_seconds() / 3600.0
            else:
                # Both cause past departure under current setup, force Double Driver if not already activated
                if not double_driver:
                    double_driver = True
                    breaks_leg1 = 0
                    breaks_leg2 = 0
                    leg1_elapsed = leg1_driving
                    leg2_elapsed = leg2_driving + route['Congestion_hrs']
                    travel_outbound_hrs = leg1_elapsed + leg2_elapsed
                    border_crossing_time = t['Deadline_DT'] - timedelta(hours=leg2_elapsed)
                    crossing_hour = border_crossing_time.hour + border_crossing_time.minute / 60.0
                    
                    if crossing_hour < open_hr:
                        border_crossing_time = border_crossing_time.replace(hour=int(close_hr), minute=0, second=0, microsecond=0) - timedelta(days=1)
                    elif crossing_hour > close_hr:
                        border_crossing_time = border_crossing_time.replace(hour=int(close_hr), minute=0, second=0, microsecond=0)
                else:
                    # Already double-driver, use Option B to avoid past departure
                    border_crossing_time = border_crossing_time_B
                    border_wait_hrs = (border_crossing_time - (t['Deadline_DT'] - timedelta(hours=leg2_elapsed))).total_seconds() / 3600.0
            
            # Report shifted departure as an optimized JIT solution
            if border_wait_hrs != 0.0:
                issues.append(f"⏰ {t_dict['err_border_close']} -> {t['Truck_ID']} ({route['Border_Name']}: Shifted crossing by {abs(border_wait_hrs):.1f} hrs to avoid closed hours)")
        
        # คำนวณกำหนดการเคลื่อนรถและออกตัว JIT
        raw_dept_time = border_crossing_time - timedelta(hours=leg1_elapsed)
        
        # ------------------------------------------
        # AI OPTIMIZATION: บังคับใช้ตรรกะจัดส่งไปข้างหน้า (Forward JIT Scheduling) แก้เวลาออกรถติดลบ
        # ------------------------------------------
        if raw_dept_time < now_th:
            dept_time = now_th
            eta_dest = dept_time + timedelta(hours=travel_outbound_hrs)
            late_risk = "Yes"
            
            # เช็กกรองเฉพาะออเดอร์ใหม่เพื่อแจ้งเตือน Anomaly (ออเดอร์ประวัติถือเป็น In Transit)
            is_any_new = any((o in st.session_state.new_order_ids) or o.startswith(("DSR-", "ERR-")) for o in t['Orders'])
            if is_any_new:
                issues.append(f"⏰ {t_dict['err_late']} -> TRK: {t['Truck_ID']} (Dept: {dept_time.strftime('%Y-%m-%d %H:%M')})")
        else:
            dept_time = raw_dept_time
            eta_dest = t['Deadline_DT']
            late_risk = "No"
            
        # 4. Return Trip Calculation (ตีกลับทันที + เติมน้ำมัน 30 นาที) with rest stops
        dept_return = eta_dest
        
        leg3_driving = (dist / 2) / SPEED_LIMIT_KMH
        leg4_driving = (dist / 2) / SPEED_LIMIT_KMH + 0.5
        
        # In Double Driver Team, return has 0 rest stops as well
        if double_driver:
            leg3_elapsed = leg3_driving
            leg4_elapsed = leg4_driving
        else:
            breaks_leg3 = get_rest_breaks(leg3_driving, limit)
            leg3_elapsed = leg3_driving + (breaks_leg3 * 10.0)
            
            breaks_leg4 = get_rest_breaks(leg4_driving, limit)
            leg4_elapsed = leg4_driving + (breaks_leg4 * 10.0)
            
        travel_inbound_hrs = leg3_elapsed + leg4_elapsed
        eta_origin = dept_return + timedelta(hours=travel_inbound_hrs)
        
        # Check if the truck has returned to base to trigger completed state cleanup
        if eta_origin <= now_th:
            completed_order_ids.extend(t['Orders'])
            
        # 3. Fuel calculation with Empty-Return Rate modification
        backhaul_active = st.session_state.human_overrides.get("backhaul_enabled", {}).get(t['Truck_ID'], False)
        empty_dist_rate = 0.0 if backhaul_active else 50.0
        
        l_per_km_actual = (1.0/specs['base_km_l']) + ((1.0/specs['loaded_km_l']) - (1.0/specs['base_km_l'])) * min(t['Weight'] / specs['cap_kg'], 1.0)
        
        if backhaul_active:
            l_per_km_return = l_per_km_actual * 0.7  # Fuel discount for cooperative shipping
        else:
            l_per_km_return = (1.0/specs['base_km_l'])
            
        fuel_cost = ((dist * l_per_km_actual) + (dist * l_per_km_return)) * st.session_state.fuel_price
        
        # 4. Total driving & duty hours calculation (shared if double driver)
        trip_duty_hours = (dist * 2) / SPEED_LIMIT_KMH + route['Congestion_hrs'] + abs(border_wait_hrs)
        if double_driver:
            trip_duty_hours = trip_duty_hours / 2.0
            
        # 5. Late Probability calculation (%)
        if dept_time == now_th and late_risk == "Yes":
            late_prob_pct = 100.0
        else:
            buffer_hrs = (dept_time - now_th).total_seconds() / 3600.0
            late_prob_pct = min(95.0, (route['Congestion_hrs'] / (travel_outbound_hrs + buffer_hrs)) * 100.0)
            
        # 6. Truck weight and volume utilization
        w_util = (t['Weight'] / specs['cap_kg']) * 100.0
        v_util = (t['Volume'] / specs['cap_cbm']) * 100.0
        max_util = max(w_util, v_util)
        
        # 7. Cost allocation per shipment (Pro-rated weight & volume)
        truck_total_cost = fuel_cost + 1500
        allocated_orders = []
        for order_id in t['Orders']:
            match_row = df_clean[df_clean['Order_ID'] == order_id].iloc[0]
            w_share = match_row['Weight_kg'] / t['Weight']
            v_share = match_row['Volume_cbm'] / t['Volume']
            order_cost = truck_total_cost * (0.5 * w_share + 0.5 * v_share)
            allocated_orders.append((order_id, order_cost))
            
        # 8. Cost per Tonne-Kilometer
        tonnes = t['Weight'] / 1000.0
        tonne_km = tonnes * dist
        cost_per_tkm = truck_total_cost / tonne_km if tonne_km > 0 else 0.0
        
        # 9. ดึงค่าการสอดคล้องความมั่นคงด้านศุลกากร (Customs Compliance Evaluation) [11, 426]
        compliance_check = evaluate_customs_compliance(t['Orders'][0], row['Cargo_Type'], t['Weight'])
        
        final_schedule.append({
            "Truck_ID": t['Truck_ID'], 
            "Type": actual_type, 
            "Driver": t['Driver_Name'] if not double_driver else f"{t['Driver_Name']} + Co-Driver (ทีมคู่หู)", 
            "Destination": t['Destination'],
            "Dept_Time": dept_time.strftime("%Y-%m-%d %H:%M"), 
            "Current_Coord": f"Lat: {origin_coords[1]:.4f}, Lon: {origin_coords[0]:.4f}", 
            "Weight_kg": t['Weight'],
            "Volume_cbm": t['Volume'],
            "Cost_THB": truck_total_cost, 
            "Emissions_kg": dist * 2 * 0.8,
            "ETA_Dest": eta_dest.strftime("%Y-%m-%d %H:%M"), 
            "Dept_Ret": dept_return.strftime("%Y-%m-%d %H:%M"), 
            "ETA_Origin": eta_origin.strftime("%Y-%m-%d %H:%M"),
            "Late_Risk": late_risk, 
            "Late_Prob_Pct": f"{late_prob_pct:.1f}%",
            "Weight_Util_Pct": f"{w_util:.1f}%",
            "Volume_Util_Pct": f"{v_util:.1f}%",
            "Overall_Util": max_util,
            "Cost_Per_Tonne_Km": f"{cost_per_tkm:.2f}",
            "Empty_Dist_Pct": f"{empty_dist_rate:.1f}%",
            "Duty_Hrs": trip_duty_hours, 
            "Raw_Trip_Hrs": trip_duty_hours,
            "Allocated_Costs": allocated_orders,
            "Orders": ", ".join(t['Orders']),
            "Readiness_Score": f"{compliance_check['score']}%",
            "Customs_Risk": compliance_check['risk']
        })
    
    # [แก้ไขใหม่] ปรับ Driver Count ให้ขยายตัวโดยอัตโนมัติหากรถที่ใช้ต้องการจำนวนเยอะขึ้น
    st.session_state.driver_count = max(st.session_state.driver_count, len(trucks))
    
    if len(trucks) > st.session_state.driver_count: 
        issues.append(f"👨‍✈️ {t_dict['err_driver_insufficient']} ({t_dict['k_alt']}! ต้องการคนขับ {len(trucks)} คน แต่มีให้ใช้ {st.session_state.driver_count} คน)")
        
    # ==========================================
    # 4. Advanced Continuous Rest & Driver Hour Reset Logic (Anomaly Detection)
    # ==========================================
    driver_trips = {}
    for tr in final_schedule:
        drv = tr["Driver"]
        if drv and "UNASSIGNED" not in drv:
            primary_drv = drv.split(" + ")[0]
            if primary_drv not in driver_trips:
                driver_trips[primary_drv] = []
            d_time = datetime.strptime(tr["Dept_Time"], "%Y-%m-%d %H:%M").replace(tzinfo=tz_th)
            r_time = datetime.strptime(tr["ETA_Origin"], "%Y-%m-%d %H:%M").replace(tzinfo=tz_th)
            
            # Calculate the driving time in the final segment of the trip (after their last rest stop)
            limit = st.session_state.driver_hour_limit
            specs = truck_types[st.session_state.human_overrides.get("truck_types", {}).get(tr["Truck_ID"], tr["Type"])]
            route_info = st.session_state.route_data[st.session_state.route_data['Destination'] == tr['Destination']].iloc[0]
            total_driving = (route_info['Distance_km'] * 2) / SPEED_LIMIT_KMH
            final_segment_hrs = total_driving % limit
            if final_segment_hrs == 0 and total_driving > 0:
                final_segment_hrs = limit
                
            driver_trips[primary_drv].append({
                "dept": d_time,
                "ret": r_time,
                "trip_total_hrs": tr["Raw_Trip_Hrs"],
                "final_segment_hrs": final_segment_hrs,
                "truck_id": tr["Truck_ID"]
            })

    driver_accum_map = {}
    st.session_state.driver_count = max(st.session_state.driver_count, len(trucks))
        
    for drv, trips in driver_trips.items():
        trips.sort(key=lambda x: x["dept"])
        
        accum_hrs = 0.0
        prev_ret = None
        
        for i, trip in enumerate(trips):
            if i == 0:
                accum_hrs = trip["final_segment_hrs"]
            else:
                rest_duration = (trip["dept"] - prev_ret).total_seconds() / 3600.0
                if rest_duration >= 10.0:
                    # Reset working hours back to 0! Driver rested >= 10 hours at base before this trip.
                    accum_hrs = trip["final_segment_hrs"]
                else:
                    # Insufficient rest at base: accumulate the new trip's active driving hours into their current shift
                    accum_hrs += trip["trip_total_hrs"]
                    
            prev_ret = trip["ret"]
            driver_accum_map[trip["truck_id"]] = accum_hrs
            
            # Anomaly Detection if shift cumulative hours exceed the legal limit
            if accum_hrs > st.session_state.driver_hour_limit:
                issues.append(f"🚨 {t_dict['err_work']}: {drv} ({accum_hrs:.1f} hrs / limit {st.session_state.driver_hour_limit:.1f} hrs on Truck {trip['truck_id']})")
                
    # Save the cumulative duty hours back to each truck's displayed data
    for tr in final_schedule:
        if tr["Truck_ID"] in driver_accum_map:
            tr["Duty_Hrs"] = driver_accum_map[tr["Truck_ID"]]
            
    # [ระบบลบและย้ายออเดอร์อัตโนมัติเมื่อส่งสำเร็จ] เมื่อกลับถึงฐาน ย้ายเข้า completed_orders.csv ทันที
    if completed_order_ids:
        completed_rows = []
        for o_id in completed_order_ids:
            match = df_raw[df_raw['Order_ID'] == o_id]
            if not match.empty:
                r_dict = match.iloc[0].to_dict()
                r_dict['Completed_Time'] = now_th.strftime("%Y-%m-%d %H:%M")
                completed_rows.append(r_dict)
                
        if completed_rows:
            df_comp = pd.DataFrame(completed_rows)
            save_completed_data(df_comp)
            
        data = data[~data['Order_ID'].isin(completed_order_ids)]
        try:
            data.to_csv(FILE_NAME, index=False)
            st.cache_data.clear()
            st.toast(f"🎉 {t_dict.get('auto_del', 'Deleted')}: {len(completed_order_ids)} รายการจัดส่งสำเร็จข้ามแดนเรียบร้อยแล้ว!")
        except PermissionError:
            pass 
            
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

# Execute schedule computation
if len(data) > 0: 
    generate_schedule(st.session_state.last_scenario, ai_priority_en, t)
trucks = st.session_state.trucks_schedule

# ==========================================
# Page 1: Dashboard Overview
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
                # เมื่อเปลี่ยน scenario ให้เริ่มรายงานและวิเคราะห์ตัวเตือนภัยทันที
                st.session_state.ai_run_executed = True
                st.rerun()
        with col_opt:
            st.write("")
            if st.button(t["btn_opt"], type="primary", use_container_width=True):
                st.session_state.ai_run_executed = True
                before_drivers = st.session_state.driver_count
                before_hour = st.session_state.dispatch_hour
                
                # 🛠️ ตรรกะแก้ปัญหาเฉพาะเจาะจง (Targeted Heuristic Solver) เพื่อไม่ให้เพิ่มกำลังพลหรือขยับเวลาไปเรื่อยเปื่อย
                # 1. กรณีคนขับไม่พอ: ปรับให้เทียบเท่าจำนวนคันรถบรรทุกที่ต้องการรันจริงทันทีเพื่อตัดปัญหากำลังพลขาดแคลน
                st.session_state.driver_count = max(st.session_state.driver_count, len(st.session_state.trucks_schedule))
                generate_schedule(scen_key, ai_priority_en, t)
                
                # 2. ปรับชิฟต์เวลาและกำลังพลเฉพาะเที่ยวรถ/คนขับคันที่เกิดปัญหาล่าช้าหรือขับเกินเวลาเท่านั้น
                iteration = 0
                while len(st.session_state.ai_issues) > 0 and iteration < 5:
                    active_trucks = st.session_state.trucks_schedule
                    issues_to_solve = list(st.session_state.ai_issues)
                    
                    for issue in issues_to_solve:
                        # กรณี A: ส่งล่าช้าเฉพาะคัน -> สลับเป็นคนขับทีมคู่หู (Double Driver) เพื่อตัดเวลานอนสะสมข้างทางเป็น 0 ชม.
                        if "TRK:" in issue and ("ส่งล่าช้า" in issue or "Late" in issue):
                            import re
                            match = re.search(r"TRK:\s*(TRK-\d+)", issue)
                            if match:
                                trk_id = match.group(1)
                                matched_tr = next((x for x in active_trucks if x["Truck_ID"] == trk_id), None)
                                if matched_tr:
                                    orders_in_truck = [o.strip() for o in matched_tr["Orders"].split(",")]
                                    for o in orders_in_truck:
                                        st.session_state.mitigation_decisions[o] = "Accepted"
                                        
                        # กรณี B: คนขับขับเกินชั่วโมงกำหนด -> สลับทริปถัดๆ ไปของพนักงานรายนั้นเป็นทีมคู่หูเพื่อแบ่งเบาเวลาขับขี่ลงครึ่งหนึ่ง
                        if "คนขับขับเกิน" in issue or "err_work" in issue:
                            import re
                            match = re.search(r"(?:คนขับขับเกินชั่วโมงกำหนด|err_work):\s*Driver\s*(\d+)", issue)
                            if match:
                                driver_num = match.group(1)
                                driver_name = f"Driver {driver_num}"
                                assigned_trucks = [x for x in active_trucks if driver_name in x["Driver"]]
                                if len(assigned_trucks) > 1:
                                    for tr in assigned_trucks[1:]:
                                        orders_in_truck = [o.strip() for o in tr["Orders"].split(",")]
                                        for o in orders_in_truck:
                                            st.session_state.mitigation_decisions[o] = "Accepted"
                                            
                        # กรณี C: ด่านปิดขณะถึงพรมแดน -> สลับใช้ทีมคู่หูเพื่อทำเวลาให้ผ่านพ้นช่วงด่านปิดศุลกากร
                        if "ด่านปิด" in issue or "err_border_close" in issue:
                            import re
                            match = re.search(r"TRK:\s*(TRK-\d+)", issue)
                            if match:
                                trk_id = match.group(1)
                                matched_tr = next((x for x in active_trucks if x["Truck_ID"] == trk_id), None)
                                if matched_tr:
                                    orders_in_truck = [o.strip() for o in matched_tr["Orders"].split(",")]
                                    for o in orders_in_truck:
                                        st.session_state.mitigation_decisions[o] = "Accepted"
                                        
                    generate_schedule(scen_key, ai_priority_en, t)
                    iteration += 1
                    
                st.session_state.opt_history = pd.DataFrame({
                    "Parameters / ตัวชี้วัด": ["Available Drivers (คนขับที่ต้องใช้)", "Departure Hour (เวลาออกรถ)"],
                    "Before (ก่อนแก้)": [before_drivers, f"{before_hour}:00"],
                    "After AI Optimize (หลังแก้)": [st.session_state.driver_count, f"{st.session_state.dispatch_hour}:00"]
                })
                st.toast("✅ AI Optimization Complete!")
                st.rerun()

    # ------------------------------------------
    # [ปรับปรุงใหม่] 🧠 AI Diagnostics & Interactive Mitigation Console [11, 40]
    # ------------------------------------------
    active_issues = st.session_state.ai_issues if st.session_state.get('ai_run_executed', False) else []
    if active_issues:
        st.warning("🧠 **AI Diagnostics & Interactive Mitigation Console (ระบบตรวจพบข้อจำกัด JIT ข้ามแดน)**")
        st.caption("คู่มือการวิเคราะห์ของ Domo & UXPin: ปัญหาระบบสามารถอนุมัติสิทธิ์เปลี่ยนแผนเพื่อหลีกเลี่ยงความเสี่ยงข้ามแดนได้เรียลไทม์ [14, 40]")
        
        for idx, issue in enumerate(active_issues):
            with st.container(border=True):
                col_info, col_act = st.columns([3, 1])
                with col_info:
                    st.write(f"⚠️ **ปัญหาที่พบ:** {issue}")
                    
                    # เสนอแนะแผนแก้ไขเฉพาะทางตามชนิดปัญหาที่แจ้งเตือน
                    if "คนขับไม่พอ" in issue or "driver_insufficient" in issue or "Shortage" in issue:
                        st.markdown("👉 **มาตรการ AI:** จ้างพนักงานคนขับภายนอกชั่วคราวแบบเร่งด่วน (Hire Temp Drivers)")
                    elif "ล่าช้า" in issue or "Late" in issue or "Past" in issue:
                        st.markdown("👉 **มาตรการ AI:** บังคับสลับใช้ **'คนขับทีมคู่กะ (Double Driver)'** ตัดชั่วโมงนอนพักข้างทางเป็น 0 ชม. และจัดตารางแบบเคลื่อนรถทันที")
                    elif "ด่านปิด" in issue or "Border Closed" in issue or "close" in issue:
                        st.markdown("👉 **มาตรการ AI:** ขยับชิฟต์แผน JIT ไปยังช่วงเวลาอื่นที่ด่านเปิดปฏิบัติการศุลกากร")
                    else:
                        st.markdown("👉 **มาตรการ AI:** ตรวจสอบและแก้ไขรายละเอียดเชิงลึกด้วยคู่มือมนุษย์")
                with col_act:
                    # ปุ่มตรวจสอบการยอมรับแผนแก้ไขอัจฉริยะ
                    if st.button("✅ ยอมรับแผน AI", key=f"accept_issue_{idx}", use_container_width=True):
                        if "คนขับไม่พอ" in issue or "driver_insufficient" in issue or "Shortage" in issue:
                            st.session_state.driver_count += 3
                        elif "ล่าช้า" in issue or "Late" in issue or "Past" in issue:
                            # บังคับอนุมัติโหมด Double Driver ให้กับออเดอร์ทั้งหมด
                            for o in data['Order_ID'].tolist():
                                st.session_state.mitigation_decisions[o] = "Accepted"
                        elif "ด่านปิด" in issue or "Border Closed" in issue or "close" in issue:
                            st.session_state.dispatch_hour = (st.session_state.dispatch_hour - 3) % 24
                        st.toast("🎉 ได้ประยุกต์ใช้มาตรการแก้ไขปัญหาของ AI สู่ระบบจัดส่งข้ามแดนแล้ว!")
                        st.rerun()
                        
                    if st.button("🛠️ ปรับเปลี่ยนตารางเอง", key=f"manual_issue_{idx}", use_container_width=True):
                        st.info("💡 กรุณาใช้แผงควบคุม Override ด้านล่างเพื่อปรับเปลี่ยนประเภทรถ/คนขับ หรือเข้าแก้ไขเวลาทำการรายด่านในแท็บพารามิเตอร์")

    # ------------------------------------------
    # [ย้ายใหม่] แผงแก้วิกฤตเดดไลน์กระชั้นชิดอัจฉริยะแสดงเฉพาะออเดอร์ใหม่กระชั้นชิด
    # ------------------------------------------
    pending_new_orders = [o for o, dec in st.session_state.mitigation_decisions.items() if dec == "Pending"] if st.session_state.get('ai_run_executed', False) else []
    if pending_new_orders:
        st.error("🚨 **AI Urgent Mitigation Panel - ตรวจพบคำสั่งซื้อใหม่ข้ามแดนที่เดดไลน์วิกฤตเชิงกายภาพ**")
        for o_id in pending_new_orders:
            match_row = data[data['Order_ID'] == o_id]
            if not match_row.empty:
                info = match_row.iloc[0]
                with st.container(border=True):
                    col_info, col_acc, col_rej = st.columns([2, 1, 1])
                    with col_info:
                        st.markdown(f"**🚛 ออเดอร์ด่วน {o_id}** ส่งไปปลายทาง **{info['Destination']}** (น้ำหนัก {info['Weight_kg']:,} kg)")
                        st.markdown("👉 **ข้อเสนอแนะ AI:** สลับจัดกำลังเป็น **'คนขับทีมคู่หู (Double Driver)'** ตัดเวลานอนสะสมเหลือ 0 ชม. เพื่อให้ถึงทันเดดไลน์")
                    with col_acc:
                        if st.button("✅ ยอมรับแผนแก้ไข (Accept Plan)", key=f"acc_{o_id}", use_container_width=True):
                            st.session_state.mitigation_decisions[o_id] = "Accepted"
                            st.toast(f"อนุมัติแผนเดินรถทีมคู่หู (Double Driver) สำหรับออเดอร์ {o_id} แล้ว!")
                            st.rerun()
                    with col_rej:
                        if st.button("🚫 ปฏิเสธแผนและตัดยอด (Reject & Exclude)", key=f"rej_{o_id}", use_container_width=True):
                            st.session_state.mitigation_decisions[o_id] = "Rejected"
                            df_ex = pd.DataFrame([{
                                "Order_ID": o_id,
                                "Origin": info['Origin'],
                                "Destination": info['Destination'],
                                "Weight_kg": info['Weight_kg'],
                                "Volume_cbm": info['Volume_cbm'],
                                "Deadline": info['Deadline'],
                                "Cargo_Type": info['Cargo_Type'],
                                "Excluded_Time": datetime.now(tz_th).strftime("%Y-%m-%d %H:%M"),
                                "Reason": "Rejected JIT plan (Time constraint physically impossible)"
                            }])
                            save_excluded_data(df_ex)
                            data = data[data['Order_ID'] != o_id]
                            data.to_csv(FILE_NAME, index=False)
                            st.cache_data.clear()
                            st.toast(f"ตัดยอดออเดอร์ {o_id} ออกจากระบบหลักสำเร็จ!")
                            st.rerun()

    # Metrics Row (Visual Hierarchy & White Space)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t["k_trk"], f"{len(trucks)}")
    c2.metric(t["k_cst"], f"{sum(tr['Cost_THB'] for tr in trucks):,.0f}")
    c3.metric(t["k_co2"], f"{sum(tr['Emissions_kg'] for tr in trucks):,.1f}")
    c4.metric(t["k_alt"], f"{len(st.session_state.ai_issues)}", delta_color="inverse")
    
    # 📖 Data Storytelling & Scenario Analysis Section (TNI Marketing Technology framework)
    with st.expander("📖 Data Storytelling & Scenario Analysis (บทวิเคราะห์และการเล่าเรื่องข้อมูล)"):
        st.markdown(f"### 📖 {t['menu']} - Data Storytelling")
        if st.session_state.last_scenario == "Normal":
            st.info("""
            **1. เกิดอะไรขึ้น (What Happened):**
            ระบบโลจิสติกส์จัดส่งผ่านแดนดำเนินงานตามปกติ ออเดอร์ทั้งหมดถูกรวมกลุ่ม (Consolidated) และกระจายไปยังรถประเภทต่างๆ อย่างสมดุลตามเงื่อนไขน้ำหนักและปริมาตรสูงสุด.
            
            **2. ทำไมจึงเกิด (Why it Happened):**
            เนื่องจากไม่มีพายุฝนและไม่มีปัญหาข้อมูลเสียหาย ด่านชายแดนระบายรถได้รวดเร็วภายใน 1-4 ชั่วโมง ทำให้ไม่มีความเสี่ยงล่าช้าสะสม และคนขับสามารถทำงานได้ครบชิฟต์โดยได้รับการพักผ่อนที่เพียงพอ.
            
            **3. ควรทำอย่างไรต่อไป (What's Next):**
            ผู้ควบคุมควรพิจารณาเปิดใช้งานฟังก์ชัน **"🔄 จับคู่ขากลับ (Backhaul Match)"** เพื่อเพิ่มสัดส่วนการขนส่งสองทาง และลดอัตราตีรถเปล่าให้เหลือ 0% ซึ่งจะเพิ่มประสิทธิภาพกำไรขึ้น 30%.
            """)
        elif st.session_state.last_scenario == "Disruption":
            st.error("""
            **1. เกิดอะไรขึ้น (What Happened):**
            ตรวจพบความเสี่ยงล่าช้าอย่างรุนแรง (Late Risk = Yes) และชั่วโมงการเดินรถสูงผิดปกติสะสมในรอบวิ่งที่ผ่านด่านมุกดาหารและด่านเชียงของ.
            
            **2. ทำไมจึงเกิด (Why it Happened):**
            เนื่องจากเกิดพายุเข้าทำให้ด่านล่าช้าสะสมสูงถึง 15 ชั่วโมง ส่งผลให้ตารางเวลา JIT บังคับให้ออกเดินทางล่วงหน้าในอดีต และคนขับรถข้ามแดนมีโอกาสทำงานต่อเนื่องเกินขีดจำกัดความปลอดภัยสูงสุด.
            
            **3. ควรทำอย่างไรต่อไป (What's Next):**
            แนะนำให้ใช้ปุ่ม **"🧠 ให้ AI แก้ปัญหาอัตโนมัติ"** ด้านบนเพื่อจัดหาคนขับสำรองและปรับเวลา หรือทำการควบคุมเอง (Human Override) โดยปรับเปลี่ยนขนาดประเภทรถบรรทุกให้เป็น **Large (10-Wheel)** เพื่อรวบรวมเที่ยวส่งของในคันเดียว ลดปริมาณคนขับที่ต้องฝ่าด่านพายุลง.
            """)
        elif st.session_state.last_scenario == "Erroneous Data":
            st.warning("""
            **1. เกิดอะไรขึ้น (What Happened):**
            ระบบตรวจพบความผิดปกติของข้อมูล (Anomaly Detection) คือคำสั่งซื้อที่มีน้ำหนักบรรทุกน้อยกว่าหรือเท่ากับ 0 kg (ERR-ออเดอร์).
            
            **2. ทำไมจึงเกิด (Why it Happened):**
            เป็นข้อผิดพลาดจากมนุษย์ฝั่งผู้ส่งสินค้า (Human Error) ซึ่งหากนำข้อมูล 0 kg มาคำนวณจะก่อให้เกิดอัตราสิ้นเปลืองน้ำมันและการปันส่วนต้นทุนผิดเพี้ยนไปจากความจริง.
            
            **3. ควรทำอย่างไรต่อไป (What's Next):**
            AI ตรวจจับความผิดปกตินี้และดึงแผงรายงานขึ้นมาให้พนักงานควบคุมเข้าตรวจสอบแก้ไขข้อมูลให้ถูกต้อง หรือกดลบตัดยอดออกจากระบบทันทีที่หน้าจัดการออเดอร์.
            """)
    
    if st.session_state.opt_history is not None:
        st.write("---")
        st.markdown(f"### {t['cmp_t']}")
        st.dataframe(st.session_state.opt_history, hide_index=True, use_container_width=True)

    st.write("---")
    
    # Map & Alerts Row
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
            
            c_blue_dark  = [29, 78, 216]   # Outbound passed (Dark blue)
            c_blue_light = [147, 197, 253] # Outbound remaining (Light blue)
            c_grn_dark   = [22, 163, 74]   # Inbound passed (Dark green)
            c_grn_light  = [134, 239, 172] # Inbound remaining (Light green)
            
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
                
            if len(path_t) > 1: paths_t.append({"path": path_t, "color": color_t})
            if len(path_r) > 1: paths_r.append({"path": path_r, "color": color_r})
            
            # ปรับเปลี่ยนสัญญะสีระบุความเสี่ยงศุลกากรบนแผนที่ (ตาบอดสี Contrast Safe WCAG) [192]
            marker_color = [220, 38, 38] if "High" in tr['Customs_Risk'] else [245, 158, 11] if "Medium" in tr['Customs_Risk'] else [16, 185, 129]
            
            pos.append({
                "coord": [cur_lon, cur_lat],
                "color": marker_color,
                "info": f"TRK: {tr['Truck_ID']}\\\\nStatus: {status}\\\\nDestination: {tr['Destination']}\\\\nCustoms Risk: {tr['Customs_Risk']}\\\\nETA Return: {tr['ETA_Origin']}\\\\nProgress: {progress*100:.1f}%"
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
            
            # Map Legend
            st.markdown("""
            **🎨 คำอธิบายสีบนแผนที่และด่านชายแดน (Contrast Accessible Legend):**
            *   🔵 เส้นสีน้ำเงินเข้ม: เส้นทางออกขาไป (Passed Outbound) | 🌐 จุดวงกลม สีเขียว: เอกสารพร้อมศุลกากรด่านพิกัด (Low Risk)
            *   🟢 เส้นสีเขียวเข้ม: เส้นทางขากลับ (Passed Inbound) | 🌐 จุดวงกลม สีส้ม: ด่านตรวจสอบศุลกากรระดับปานกลาง (Medium Risk)
            *   🔴 จุดวงกลม สีแดง: ความเสี่ยงศุลกากรระดับวิกฤต/มีรายงานข้อขัดแย้งเชิงเอกสาร (High Risk) [11, 426]
            """)
        else: st.info("No data.")
        
    with alert_col:
        st.subheader(t["alt_t"])
        with st.container(border=True):
            if st.session_state.get('ai_run_executed', False):
                if st.session_state.ai_issues:
                    for issue in st.session_state.ai_issues: 
                        st.error(issue)
                else: 
                    st.success(t["no_err"])
            else:
                st.info("💡 **ระบบสแตนด์บาย:** กรุณาคลิกปุ่ม '🧠 ให้ AI แก้ปัญหาอัตโนมัติ' หรือเปลี่ยนสถานการณ์จำลอง เพื่อให้ปัญญาประดิษฐ์เริ่มคำนวณและวิเคราะห์ปัญหา")
                
        # 📋 Additional Data & Resources Request Panel
        st.write("")
        st.subheader(t["lbl_data_req_panel"])
        with st.container(border=True):
            st.markdown(f"### {t['lbl_data_req_panel']}")
            if st.session_state.ai_issues:
                st.warning("⚠️ **ตรวจพบข้อจำกัดทรัพยากรหรือเงื่อนไขเวลาเดินรถ**\\\\nAI แนะนำให้ระบุ/ป้อนข้อมูลเชิงลึกเหล่านี้เพิ่มเติมเพื่อเพิ่มประสิทธิผลการวางแผนสูงสุด:")
            else:
                st.info("💡 **ข้อมูลเสริมสำหรับการตัดสินใจ (Decision-Support Parameters)**\\\\nข้อมูลสนับสนุนเพิ่มเติมเพื่อให้ตารางเดินรถมีความแม่นยำระดับอุตสาหกรรม:")
                
            st.markdown("""
            *   **1. เวลาในการโหลดสินค้า (Loading Duration):** *ปัจจุบัน AI ตั้งเวลาเตรียมตัวเป็น 0 ชม. การขึ้น-ลงตู้ตู้บรรทุกจริงอาจใช้เวลา 1-3 ชม. ก่อนเริ่ม JIT ขาแรก*
            *   **2. ตารางวันหยุดและเวรตรวจด่านศุลกากร:** *เวลาทำงานจริงของเจ้าหน้าที่ และช่วงปิดด่านศุลกากรพิเศษในวันหยุดราชการ*
            *   **3. ข้อมูลพักผ่อนย้อนหลังคนขับ (Driver Sleep Log):** *เพื่อคำนวณ continuous rest และรีเซตกะพนักงานแบบ 100% compliant*
            *   **4. พยากรณ์จราจร & สภาพอากาศด่านชายแดนแบบไดนามิก**
            """)
            
            st.write("---")
            st.write("🤖 **Simulate Parameters (จำลองพารามิเตอร์):**")
            c_load, c_temp_drv = st.columns(2)
            sim_load = c_load.number_input("📦 Simulated Loading (Mins)", min_value=0, max_value=240, value=60, step=15)
            sim_drv = c_temp_drv.number_input("👨‍✈️ Hire Temp Drivers", min_value=0, max_value=10, value=0, step=1)
            
            if sim_drv > 0:
                st.info(f"💡 เพื่อลบปัญหาคนขับไม่เพียงพอ AI แนะนำให้คุณเข้าไปปรับพารามิเตอร์ **Available Drivers** ในแถบ **⚙️ {t['p_stat']}** ให้เพิ่มขึ้นอีกอย่างน้อย **{sim_drv}** คน")
                
            st.write("---")
    
    # 📈 Interactive Plotly Express Charts (Performance Analytics)
    st.subheader("📈 Interactive Performance Analytics (การวิเคราะห์ประสิทธิภาพด้วยแผนภูมิ)")
    if px is None:
        st.warning("⚠️ ไม่พบไลบรารี Plotly ในเครื่องของคุณ แดชบอร์ดจึงไม่สามารถแสดงแผนภูมิวิเคราะห์สถิติได้\\\\n\\\\n**วิธีแก้ไข:** กรุณาพิมพ์คำสั่ง `pip install plotly` ใน Terminal/PowerShell ของคุณ จากนั้นรันใหม่อีกครั้ง")
    elif len(trucks) > 0:
        char_col1, char_col2 = st.columns(2)
        with char_col1:
            util_data = []
            for tr in trucks:
                util_data.append({"Truck ID": tr["Truck_ID"], "Utilization Type": "Weight Util (%)", "Value (%)": float(tr["Weight_Util_Pct"].replace("%", ""))})
                util_data.append({"Truck ID": tr["Truck_ID"], "Utilization Type": "Volume Util (%)", "Value (%)": float(tr["Volume_Util_Pct"].replace("%", ""))})
            
            df_util = pd.DataFrame(util_data)
            fig_util = px.bar(
                df_util, 
                x="Truck ID", 
                y="Value (%)", 
                color="Utilization Type", 
                barmode="group",
                color_discrete_map={"Weight Util (%)": "#1E3A8A", "Volume Util (%)": "#3B82F6"},
                title="Truck Capacity Utilization (Weight vs. Volume)"
            )
            st.plotly_chart(fig_util, use_container_width=True)
            st.caption("📊 แผนภูมิแท่งเปรียบเทียบร้อยระการใช้พื้นที่บรรจุตัวรถบรรทุกจำแนกตามรายคัน [192]")
            
        with char_col2:
            cost_data = []
            for tr in trucks:
                cost_data.append({"Truck ID": tr["Truck_ID"], "Cost per Tonne-Km (THB)": float(tr["Cost_Per_Tonne_Km"]), "Destination": tr["Destination"]})
            
            df_cost = pd.DataFrame(cost_data)
            fig_cost = px.bar(
                df_cost,
                x="Truck ID",
                y="Cost per Tonne-Km (THB)",
                color="Destination",
                title="Transportation Efficiency (Cost per Tonne-Kilometer)"
            )
            st.plotly_chart(fig_cost, use_container_width=True)
            st.caption("📊 แผนภูมิวิเคราะห์ความคุ้มค่าทางการเงินเฉลี่ยต่อ ตัน-กิโลเมตร ของเส้นทางรอบเดินรถจริง [192]")
    else:
        st.info("No data available to plot performance charts.")

    st.write("---")
    
    # Core AI Generated Schedule Table
    st.subheader(t["tbl_t"])
    if len(trucks) > 0:
        df_display = pd.DataFrame(trucks)
        # Rename columns to reflect localized headers beautifully
        df_cols = {
            'Truck_ID': 'ID',
            'Type': t['lbl_change_truck'].replace("🚛 ", ""),
            'Driver': t['lbl_change_driver'].replace("👨‍✈️ ", ""),
            'Current_Coord': "Current Coordinates" if selected_lang == "English" else "当前位置" if selected_lang == "中文" else "พิกัดปัจจุบัน",
            'Destination': 'Destination',
            'Dept_Time': 'Departure Time',
            'ETA_Dest': 'ETA Destination',
            'Weight_kg': 'Weight (kg)',
            'Weight_Util_Pct': t['lbl_weight_util'],
            'Volume_Util_Pct': t['lbl_volume_util'],
            'Cost_THB': 'Cost (THB)',
            'Cost_Per_Tonne_Km': t['lbl_cost_tkm'].replace("⛽ ", ""),
            'Empty_Dist_Pct': t['lbl_empty'].replace("🔄 ", ""),
            'Duty_Hrs': t['lbl_workload'].replace("👨‍✈️ ", ""),
            'Late_Prob_Pct': t['lbl_late_prob'].replace("🎯 ", ""),
            'Readiness_Score': 'Customs Readiness',
            'Customs_Risk': 'Customs Risk Level',
            'Orders': t['lbl_orders']
        }
        st.dataframe(df_display[list(df_cols.keys())].rename(columns=df_cols), use_container_width=True, hide_index=True)
        
        # Sub-Section for individual Shipment Cost distributions (Pro-rated allocations)
        with st.expander(t["lbl_cost_ship"]):
            st.markdown(f"#### {t['lbl_cost_ship']} (Pro-rated by Weight & Volume)")
            cost_alloc_data = []
            for tr in trucks:
                for order_id, cost in tr["Allocated_Costs"]:
                    cost_alloc_data.append({
                        "Truck ID": tr["Truck_ID"],
                        "Order ID": order_id,
                        "Destination": tr["Destination"],
                        "Allocated Cost (THB)": f"{cost:,.2f}"
                    })
            st.dataframe(pd.DataFrame(cost_alloc_data), use_container_width=True, hide_index=True)
            
    else:
        st.info("No active trucks found.")

    st.write("---")
    
    # 👥 HUMAN OVERRIDE PANEL (Requirement 7)
    st.subheader(t["lbl_human_panel"])
    with st.container(border=True):
        st.markdown(f"**{t['lbl_human_panel']} - Accept, Reject, or Modify AI Schedule**")
        
        # 1. Driver and Truck assignment adjustments
        if len(trucks) > 0:
            c_sel_trk, c_drv_override, c_trk_override, c_backhaul = st.columns(4)
            selected_trk_id = c_sel_trk.selectbox("Select Truck to Override", [tr['Truck_ID'] for tr in trucks])
            
            # Change driver list
            drivers_list = [f"Driver {x}" for x in range(1, st.session_state.driver_count + 5)] + ["UNASSIGNED"]
            matched_truck = next(tr for tr in trucks if tr['Truck_ID'] == selected_trk_id)
            
            # Clean string split to recover default driver index
            p_driver_clean = matched_truck['Driver'].split(" + ")[0].replace(" (ทีมคู่หู)", "")
            new_drv_override = c_drv_override.selectbox(t["lbl_change_driver"], drivers_list, index=drivers_list.index(p_driver_clean) if p_driver_clean in drivers_list else 0)
            new_type_override = c_trk_override.selectbox(t["lbl_change_truck"], list(truck_types.keys()), index=list(truck_types.keys()).index(matched_truck['Type']))
            
            # Backhaul optimization option (Requirement: backhaul matching / empty return trip reduction)
            is_backhaul = c_backhaul.checkbox(t["lbl_backhaul"], value=st.session_state.human_overrides["backhaul_enabled"].get(selected_trk_id, False))
            
            # 2. Prevent consolidation (Split order / Reject AI consolidation)
            st.markdown("**Split Orders from Consolidation (Force single truck shipment)**")
            order_ids_list = data["Order_ID"].tolist()
            split_selected = st.multiselect(t["lbl_split_btn"], order_ids_list, default=st.session_state.human_overrides.get("split_orders", []))
            
            c_actions = st.columns(2)
            if c_actions[0].button("💾 Apply Override adjustments", type="primary", key="apply_overrides_btn", use_container_width=True):
                st.session_state.human_overrides["driver_assignments"][selected_trk_id] = new_drv_override
                st.session_state.human_overrides["truck_types"][selected_trk_id] = new_type_override
                st.session_state.human_overrides["backhaul_enabled"][selected_trk_id] = is_backhaul
                st.session_state.human_overrides["split_orders"] = split_selected
                st.toast("Applied human override successfully!")
                st.rerun()
                
            if c_actions[1].button("🔄 Reset Overrides to AI Recommendation", key="reset_overrides_btn", use_container_width=True):
                st.session_state.human_overrides = {
                    "driver_assignments": {},
                    "truck_types": {},
                    "split_orders": [],
                    "backhaul_enabled": {}
                }
                st.toast("Reset all human overrides!")
                st.rerun()
        else:
            st.info("No schedule available to apply human overrides.")

    # Technical Specifications expander
    with st.expander(t["spc_t"]):
        st.latex(r"Fuel_{actual} = Fuel_{empty} + (Fuel_{full} - Fuel_{empty}) \times \left( \frac{Weight_{actual}}{Weight_{max}} \right)")
        st.dataframe(pd.DataFrame(truck_types).T, use_container_width=True)

# ==========================================
# Page 2: Order Management (Forms & File Uploads & History Tabs!) [ย้ายมาไว้ที่นี่] [13]
# ==========================================
elif page == t["p_order"]:
    st.header(t["p_order"])
    
    # สร้างระบบแท็บ 4 ตัวเพื่อจัดการงานออเดอร์และประวัติการขนส่งแบบบูรณาการในหน้าเดียว
    tab_manage, tab_list, tab_completed, tab_excluded = st.tabs([
        "✍️ นำเข้าและป้อนข้อมูลใหม่ (Create & Upload)",
        "📋 รายการคำสั่งซื้อปัจจุบัน (Pending Orders List)",
        "📦 ประวัติจัดส่งผ่านแดนสำเร็จ (Completed Deliveries)",
        "🚫 รายการออเดอร์ตัดยอด/ปฏิเสธ (Excluded List)"
    ])
    
    with tab_manage:
        with st.container(border=True):
            tab1, tab2 = st.tabs([t["o_tab1"], t["o_tab2"]])
            with tab1:
                st.info("รองรับไฟล์ .csv และ .xlsx")
                uploaded_file = st.file_uploader("Upload Orders File", type=["csv", "xlsx"])
                if uploaded_file and st.button(t["o_upbtn"], type="primary"):
                    try:
                        df_upload = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                        if "Order_ID" in df_upload.columns:
                            for oid in df_upload["Order_ID"].tolist():
                                st.session_state.new_order_ids.add(oid)
                                
                        if save_data(df_upload):
                            st.success(f"Success! {len(df_upload)} items.")
                            data = load_data() # อัปเดตข้อมูลทันที
                            st.rerun()
                    except Exception as e:  # noqa: BLE001
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
                ):
                    st.session_state.new_order_ids.add(new_order_id)
                    if save_data(pd.DataFrame([
                        {"Order_ID": new_order_id, "Origin": new_origin, "Destination": new_destination,
                         "Weight_kg": new_weight, "Volume_cbm": new_volume,
                         "Deadline": f"{new_date} {new_time.strftime('%H:%M')}", "Cargo_Type": new_cargo}
                    ])):
                        data = load_data() # อัปเดตข้อมูลทันทีหลังกรอกเสร็จ
                        st.rerun()

    with tab_list:
        st.subheader(t["o_cur"])
        
        # ------------------------------------------
        # [เพิ่ม] กล่องตรวจสอบ Anomaly ข้อมูลเสียหายรายคำสั่งซื้อแบบมีปฏิสัมพันธ์ (Error Resolution Console)
        # ------------------------------------------
        errs = check_error_orders(data)
        if errs:
            st.error("🚨 **ตรวจพบความผิดปกติของข้อมูลสินค้า (Erroneous Orders Detected)**")
            st.caption("ออเดอร์ต่อไปนี้มีข้อมูลน้ำหนักหรือปริมาตรไม่ถูกต้อง (เช่น เป็นศูนย์หรือติดลบ) กรุณาดำเนินการแก้ไขหรือตัดออกจากตารางระบบเพื่อความปลอดภัยเชิงสถิติ")
            for err in errs:
                with st.container(border=True):
                    col_lbl, col_fix, col_discard = st.columns([2, 1, 1])
                    with col_lbl:
                        st.markdown(f"**📦 ออเดอร์ ID: {err['Order_ID']}** (ปลายทาง: {err['Destination']})")
                        st.write(f"❌ น้ำหนักบรรทุก: **{err['Weight_kg']} kg** | ปริมาตร: **{err['Volume_cbm']} CBM**")
                    with col_fix:
                        with st.popover("✍️ แก้ไขข้อมูลเอง", use_container_width=True):
                            st.write(f"แก้ไขข้อมูลสำหรับ **{err['Order_ID']}**")
                            new_w = st.number_input("ค่าน้ำหนักใหม่ (kg)", min_value=1.0, value=500.0, key=f"fix_w_{err['Order_ID']}")
                            new_v = st.number_input("ค่าปริมาตรใหม่ (CBM)", min_value=0.1, value=1.0, key=f"fix_v_{err['Order_ID']}")
                            if st.button("💾 บันทึกการแก้ไข", key=f"btn_fix_{err['Order_ID']}", use_container_width=True):
                                data.loc[data['Order_ID'] == err['Order_ID'], 'Weight_kg'] = new_w
                                data.loc[data['Order_ID'] == err['Order_ID'], 'Volume_cbm'] = new_v
                                data.to_csv(FILE_NAME, index=False)
                                st.cache_data.clear()
                                st.toast(f"แก้ไขออเดอร์ {err['Order_ID']} สำเร็จ!")
                                st.rerun()
                    with col_discard:
                        if st.button("❌ ตัดออเดอร์ทิ้ง", key=f"btn_del_{err['Order_ID']}", use_container_width=True):
                            data = data[data['Order_ID'] != err['Order_ID']]
                            data.to_csv(FILE_NAME, index=False)
                            st.cache_data.clear()
                            st.toast(f"ลบออเดอร์ {err['Order_ID']} ออกจากระบบแล้ว!")
                            st.rerun()
                            
        # แสดงรายการคำสั่งซื้อหลักและติดป้ายเครื่องหมาย 🆕 บนตารางออเดอร์จำลองขยะ
        if len(data) > 0:
            df_display = data.copy()
            injected_set = st.session_state.get('new_order_ids', set())
            df_display['Order_ID'] = df_display['Order_ID'].apply(
                lambda x: f"🆕 {x}" if (x in injected_set or str(x).startswith(('DSR-', 'ERR-'))) else x
            )
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("ไม่มีคำสั่งซื้อที่รอดำเนินการในปัจจุบัน")

    with tab_completed:
        st.markdown("#### 📦 ประวัติการจัดส่งข้ามพรมแดนสำเร็จ (Completed Deliveries History Log)")
        df_comp_hist = load_completed_data()
        if not df_comp_hist.empty:
            st.dataframe(df_comp_hist, use_container_width=True, hide_index=True)
            st.caption("📋 ตารางประวัติระบุมวลงานของคำสั่งซื้อที่จัดส่งและขนพัดกลับถึงฐาน Hana Lamphun สำเร็จเรียบร้อย")
        else:
            st.info("ยังไม่มีข้อมูลคำสั่งซื้อที่ส่งมอบสำเร็จในรอบวันนี้")

    with tab_excluded:
        st.markdown("#### 🚫 รายการคำสั่งซื้อที่ปฏิเสธเพื่อการปรับ SLA (Excluded Orders History Log)")
        df_ex_hist = load_excluded_data()
        if not df_ex_hist.empty:
            st.dataframe(df_ex_hist, use_container_width=True, hide_index=True)
            st.caption("📋 ตารางแสดงรายการคำสั่งซื้อเร่งด่วนพิเศษที่ผู้ควบคุมตัดสินใจสลัดตัดยอดออกจากแผนเพื่อรักษาภาพรวมความเสถียร")
        else:
            st.info("ยังไม่มีประวัติรายการคำสั่งซื้อด่วนที่ถูกปฏิเสธ")

# ==========================================
# Page 3: Parameters Settings (Changing Assumptions)
# ==========================================
elif page == t["p_stat"]:
    st.header(t["p_stat"])
    with st.container(border=True):
        st.markdown("### ⚙️ System Capacity & Assumption Parameters")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.number_input(t["p_drv"], key='driver_count')
        c2.number_input(t["p_fuel"], key='fuel_price')
        
        # Advanced trans-border parameters (Requirement: Change assumptions)
        st.markdown("#### Border Operating Hours & Driver hour limits")
        b_open = c3.number_input("Border Open Hour (24h)", min_value=0, max_value=23, key='border_open')
        b_close = c4.number_input("Border Close Hour (24h)", min_value=0, max_value=23, key='border_close')
        
        driver_limit = st.number_input("Maximum Driver Working Hours (hrs)", min_value=1.0, max_value=24.0, step=0.5, key='driver_hour_limit')
        
        st.subheader(t["p_route"])
        st.session_state.route_data = st.data_editor(st.session_state.route_data, use_container_width=True, hide_index=True, key='route_edit')
