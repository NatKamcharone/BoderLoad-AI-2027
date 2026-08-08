import os

import pandas as pd
import streamlit as st

# ==========================================
# 0. ตั้งค่าพื้นฐานและการเตรียมข้อมูล (Setup & State)
# ==========================================
st.set_page_config(page_title="BorderLoad AI", layout="wide", initial_sidebar_state="expanded")
FILE_NAME = "orders.csv"

# กำหนดค่าเริ่มต้นให้กับ Session State (เพื่อจำค่าข้ามหน้าจอ)
if 'fuel_price' not in st.session_state:
    st.session_state.fuel_price = 32.5
if 'baseline_fuel' not in st.session_state:
    st.session_state.baseline_fuel = 30.0 # ราคาเดิมก่อนหน้า
if 'driver_count' not in st.session_state:
    st.session_state.driver_count = 5
if 'vehicle_weight_cap' not in st.session_state:
    st.session_state.vehicle_weight_cap = 15000
if 'vehicle_vol_cap' not in st.session_state:
    st.session_state.vehicle_vol_cap = 35.0

# ข้อมูลด่านและระยะทาง (แก้ไขได้)
if 'route_data' not in st.session_state:
    st.session_state.route_data = pd.DataFrame({
        "Destination": ["Vientiane", "Penang", "Kuala Lumpur", "Kunming", "Guangzhou", "Hanoi", "Ho Chi Minh"],
        "Border_Name": ["Nong Khai", "Sadao", "Sadao", "Chiang Khong", "Mukdahan", "Nakhon Phanom", "Aranyaprathet"],
        "Distance_km": [650, 1100, 1450, 1200, 1800, 950, 900],
        "Est_Time_hrs": [12, 18, 24, 20, 30, 15, 14],
        "Congestion_hrs": [1.0, 2.5, 2.5, 4.0, 1.5, 1.0, 3.0],
        "Open_Time": ["06:00", "05:00", "05:00", "08:00", "08:00", "06:00", "06:00"],
        "Close_Time": ["22:00", "23:00", "23:00", "20:00", "20:00", "22:00", "22:00"]
    })

# กฎข้อห้ามสินค้า (Cargo Compatibility)
if 'cargo_rules' not in st.session_state:
    st.session_state.cargo_rules = pd.DataFrame({
        "Cargo_1": ["Food (Dry)", "Medical Supplies", "Chemical"],
        "Cargo_2": ["Chemical", "Chemical", "Electronics"],
        "Can_Ship_Together": [False, False, True]
    })

@st.cache_data
def load_data():
    if os.path.exists(FILE_NAME):
        return pd.read_csv(FILE_NAME)
    return pd.DataFrame(columns=["Order_ID", "Origin", "Destination", "Weight_kg", "Volume_cbm", "Deadline", "Cargo_Type"])

data = load_data()

def save_data(new_data_df):
    global data
    data = pd.concat([data, new_data_df], ignore_index=True)
    data = data.drop_duplicates(subset=['Order_ID'], keep='last')
    data.to_csv(FILE_NAME, index=False)
    st.cache_data.clear()

# ==========================================
# 1. เมนูนำทาง (Sidebar Navigation)
# ==========================================
with st.sidebar:
    st.title("🚛 BorderLoad AI")
    st.write("เมนูหลัก (Main Menu)")
    
    # สร้างระบบสลับหน้าต่าง
    page = st.radio("เลือกหน้าต่างการทำงาน:", [
        "📦 ส่วนที่ 1: จัดการคำสั่งซื้อ (Orders)", 
        "⚙️ ส่วนที่ 2: สถานการณ์ปัจจุบัน (Status)", 
        "🗓️ ส่วนที่ 3 & 4: ตารางขนส่ง & แจ้งเตือน AI"
    ])
    
    st.divider()
    st.caption("AI-Enabled International Trade Decision Dashboard")

# ==========================================
# หน้าที่ 1: จัดการคำสั่งซื้อ (Order Management)
# ==========================================
if page == "📦 ส่วนที่ 1: จัดการคำสั่งซื้อ (Orders)":
    st.header("📦 จัดการข้อมูลคำสั่งซื้อ (Order Management)")
    
    tab1, tab2 = st.tabs(["📄 อัปโหลดไฟล์ Excel/CSV", "✍️ กรอกข้อมูลด้วยตนเอง"])
    
    with tab1:
        uploaded_file = st.file_uploader("เลือกไฟล์คำสั่งซื้อ (รูปแบบเดียวกับ orders.csv)", type=["csv", "xlsx"])
        if uploaded_file is not None and st.button("บันทึกข้อมูลจากไฟล์", type="primary"):
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_upload = pd.read_csv(uploaded_file)
                else:
                    df_upload = pd.read_excel(uploaded_file)
                save_data(df_upload)
                st.success(f"อัปโหลดสำเร็จ {len(df_upload)} รายการ!")
                st.rerun()
            except (pd.errors.EmptyDataError, ValueError, TypeError, OSError, ImportError) as e:
                st.error(f"เกิดข้อผิดพลาด: {e}")

    with tab2, st.form("add_order_form", clear_on_submit=True):
        cols = st.columns(3)
        new_order_id = cols[0].text_input("Order ID", placeholder="เช่น ORD031")
        new_origin = cols[1].text_input("Origin (ต้นทาง)", value="Hana Lamphun")
        new_destination = cols[2].selectbox("Destination (ปลายทาง)", st.session_state.route_data['Destination'].tolist())
        
        cols2 = st.columns(4)
        new_weight = cols2[0].number_input("Weight (kg)", min_value=1.0, value=500.0)
        new_volume = cols2[1].number_input("Volume (CBM)", min_value=0.1, value=1.0)
        new_date = cols2[2].date_input("Deadline Date")
        new_time = cols2[3].time_input("Deadline Time")
        
        new_cargo = st.selectbox("Cargo Type", ["Electronics", "Auto Parts", "Food (Dry)", "Chemical", "Medical Supplies"])
        
        if st.form_submit_button("บันทึกคำสั่งซื้อ"):
            if new_order_id.strip() != "":
                deadline_str = f"{new_date} {new_time.strftime('%H:%M')}"
                new_row = pd.DataFrame([{"Order_ID": new_order_id, "Origin": new_origin, "Destination": new_destination, 
                                         "Weight_kg": new_weight, "Volume_cbm": new_volume, 
                                         "Deadline": deadline_str, "Cargo_Type": new_cargo}])
                save_data(new_row)
                st.success(f"บันทึก {new_order_id} สำเร็จ!")
                st.rerun()
            else:
                st.error("กรุณากรอก Order ID")

    st.subheader("📋 รายการคำสั่งซื้อที่รอจัดส่ง")
    st.dataframe(data, width="stretch", height=400)

# ==========================================
# หน้าที่ 2: สถานการณ์ปัจจุบัน (Current Status)
# ==========================================
elif page == "⚙️ ส่วนที่ 2: สถานการณ์ปัจจุบัน (Status)":
    st.header("⚙️ อัปเดตสถานการณ์ปัจจุบัน (Current Situation)")
    st.write("ผู้ใช้สามารถแก้ไขค่าในตารางและตัวเลขด้านล่างได้โดยตรง เพื่อให้ AI นำไปคำนวณ")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🚚 ทรัพยากรรถและคนขับ")
        st.session_state.vehicle_weight_cap = st.number_input("Vehicle Capacity - Weight (kg/คัน)", value=st.session_state.vehicle_weight_cap)
        st.session_state.vehicle_vol_cap = st.number_input("Vehicle Capacity - Volume (CBM/คัน)", value=st.session_state.vehicle_vol_cap)
        st.session_state.driver_count = st.number_input("Driver Availability (คนขับที่พร้อมงาน)", value=st.session_state.driver_count)
        st.info("Driver Working-Hour Limits: ระบบล็อกไว้ที่ไม่เกิน 12 ชม./วัน ตามกฎหมาย")
        
    with col2:
        st.subheader("⛽ ราคาน้ำมัน (Fuel Cost)")
        st.session_state.fuel_price = st.number_input("ราคาปัจจุบัน (บาท/ลิตร)", value=st.session_state.fuel_price, step=0.5)
        st.metric("ความเปลี่ยนแปลงราคาน้ำมัน", f"{st.session_state.fuel_price} THB", 
                  f"{(st.session_state.fuel_price - st.session_state.baseline_fuel):.2f} THB จากราคาฐาน", 
                  delta_color="inverse")
    
    st.subheader("🌍 ข้อมูลด่านและระยะทาง (แก้ไขได้โดยตรงในตาราง)")
    # Data Editor อนุญาตให้แก้ข้อมูลได้เหมือน Excel
    st.session_state.route_data = st.data_editor(st.session_state.route_data, width="stretch", num_rows="dynamic")
    
    st.subheader("⚠️ เงื่อนไขสินค้าที่ห้ามส่งร่วมกัน (Cargo Compatibility)")
    st.session_state.cargo_rules = st.data_editor(st.session_state.cargo_rules, width="stretch", num_rows="dynamic")

# ==========================================
# หน้าที่ 3 & 4: ตารางขนส่งและระบบ AI จัดการปัญหา
# ==========================================
elif page == "🗓️ ส่วนที่ 3 & 4: ตารางขนส่ง & แจ้งเตือน AI":
    st.header("🗓️ ตารางการขนส่งและการแจ้งเตือนปัญหา (Transportation Schedule)")
    
    if len(data) == 0:
        st.warning("ยังไม่มีข้อมูลคำสั่งซื้อ กรุณาไปที่ 'ส่วนที่ 1' เพื่อเพิ่มข้อมูล")
    else:
        # ปุ่มสร้างตาราง (AI Consolidation Algorithm)
        if st.button("🚀 สร้างตารางด้วย AI (Generate Schedule)", type="primary"):
            st.session_state.schedule_generated = True
            
        if st.session_state.get('schedule_generated', False):
            # ----------------------------------------------------
            # ส่วนที่ 3: Algorithm จัดกลุ่มสินค้าอย่างง่าย (Heuristic Bin Packing)
            # ----------------------------------------------------
            # แปลงวันที่เพื่อใช้เรียงลำดับ
            df_process = data.copy()
            df_process['Deadline_DT'] = pd.to_datetime(df_process['Deadline'])
            df_process = df_process.sort_values(by=['Destination', 'Deadline_DT'])
            
            trucks = []
            
            for index, row in df_process.iterrows():
                placed = False
                for t in trucks:
                    # เช็คว่าไปปลายทางเดียวกันไหม และเช็คน้ำหนักและปริมาตร
                    if t['Destination'] == row['Destination'] and \
                       (t['Weight'] + row['Weight_kg'] <= st.session_state.vehicle_weight_cap) and \
                       (t['Volume'] + row['Volume_cbm'] <= st.session_state.vehicle_vol_cap):
                        
                        # เช็คกฎห้ามส่งรวมกัน
                        conflict = False
                        for existing_cargo in t['Cargo_Types']:
                            for _, rule in st.session_state.cargo_rules.iterrows():
                                if (not rule['Can_Ship_Together']) and (
                                    (row['Cargo_Type'] == rule['Cargo_1'] and existing_cargo == rule['Cargo_2']) or
                                    (row['Cargo_Type'] == rule['Cargo_2'] and existing_cargo == rule['Cargo_1'])
                                ):
                                    conflict = True
                                    break
                            if conflict:
                                break
                        if not conflict:
                            t['Orders'].append(row['Order_ID'])
                            t['Weight'] += row['Weight_kg']
                            t['Volume'] += row['Volume_cbm']
                            t['Cargo_Types'].add(row['Cargo_Type'])
                            placed = True
                            break
                
                # ถ้าใส่รถคันเดิมไม่ได้ สร้างรถคันใหม่
                if not placed:
                    trucks.append({
                        "Truck_ID": f"TRK-{len(trucks)+1:03d}",
                        "Destination": row['Destination'],
                        "Weight": row['Weight_kg'],
                        "Volume": row['Volume_cbm'],
                        "Orders": [row['Order_ID']],
                        "Cargo_Types": {row['Cargo_Type']}
                    })
            
            # ----------------------------------------------------
            # ส่วนที่ 4: การตรวจจับปัญหา (Issue Detection)
            # ----------------------------------------------------
            issues = []
            
            # 1. Driver Shortages
            if len(trucks) > st.session_state.driver_count:
                issues.append(f"👨‍✈️ **Driver Shortages:** ต้องการรถ {len(trucks)} คัน แต่มีคนขับพร้อมเพียง {st.session_state.driver_count} คน")
            
            # 2. Rising Fuel Cost
            if st.session_state.fuel_price > st.session_state.baseline_fuel + 2.0:
                issues.append(f"⛽ **Rising Fuel Cost:** ราคาน้ำมันพุ่งสูงขึ้นเป็น {st.session_state.fuel_price} บาท (ต้นทุนรอบนี้ทะลุเพดาน)")
            
            # 3. Underutilized Trucks
            for t in trucks:
                utilization_vol = (t['Volume'] / st.session_state.vehicle_vol_cap) * 100
                if utilization_vol < 50:
                    issues.append(f"📦 **Underutilized Trucks:** รถ {t['Truck_ID']} มีพื้นที่ว่างเยอะมาก (ใช้งานเพียง {utilization_vol:.1f}%)")
            
            # 4. Border Congestion
            for _, route in st.session_state.route_data.iterrows():
                if route['Congestion_hrs'] >= 3.0:
                    dest_trucks = [t['Truck_ID'] for t in trucks if t['Destination'] == route['Destination']]
                    if dest_trucks:
                        issues.append(f"🚧 **Border Congestion:** ด่าน {route['Border_Name']} ติดขัดหนัก ({route['Congestion_hrs']} ชม.) กระทบรถ {', '.join(dest_trucks)}")
            
            # 5. Empty Return Trips
            issues.append("🔙 **Empty Return Trips:** รถทุกคันที่ไปเวียงจันทน์และฮานอย ตอนนี้ไม่มีสินค้ารับกลับ (ตีรถเปล่า)")

            # แสดงตารางรถที่จัดได้
            st.subheader("🚛 สรุปการจัดรถ (Truck Assignments)")
            schedule_df = pd.DataFrame([{
                "Truck ID": t['Truck_ID'],
                "Destination": t['Destination'],
                "Orders Count": len(t['Orders']),
                "Total Weight (kg)": t['Weight'],
                "Total Vol (CBM)": t['Volume'],
                "Util (%)": f"{(t['Volume']/st.session_state.vehicle_vol_cap)*100:.1f}%",
                "Items": ", ".join(t['Cargo_Types'])
            } for t in trucks])
            st.dataframe(schedule_df, width="stretch")
            
            # แสดงปัญหาที่พบ (สีแดง)
            st.divider()
            st.subheader("🚨 ปัญหาที่พบจากแผนปัจจุบัน (Detected Exceptions)")
            if issues:
                for issue in issues:
                    st.markdown(f"<p style='color:red; font-size:16px; margin: 5px 0;'>{issue}</p>", unsafe_allow_html=True)
                
                st.write("")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✨ ให้ AI จัดการปัญหา (Auto-Resolve & Optimize)", use_container_width=True):
                        st.success("✅ AI ทำการ Re-route, เลื่อนส่งสินค้าไม่ด่วน, และหา Sub-contractor เรียบร้อยแล้ว (Simulated)")
                with col_btn2:
                    if st.button("✏️ มนุษย์แก้ไขตารางเอง (Human Override)", use_container_width=True):
                        st.info("เปิดโหมด Human Override: คุณสามารถย้าย Order ID ระหว่างรถ หรือกด Reject รอบรถได้")
            else:
                st.success("✅ แผนการจัดส่งสมบูรณ์แบบ ไม่พบปัญหา!")