import streamlit as st
import requests
import gzip
import io
import xml.etree.ElementTree as ET
import time
import random
from datetime import datetime

# --- 設定頁面 ---
st.set_page_config(page_title="雪隧戰情室", page_icon="🏎️", layout="centered")

# --- CSS 優化 (加入深藍色建議框樣式) ---
st.markdown("""
    <style>
    /* 數字儀表板樣式 */
    .stMetric {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
    }
    
    /* 狀態標籤 */
    .status-badge {
        font-size: 0.8rem;
        padding: 4px 8px;
        border-radius: 4px;
        margin-bottom: 10px;
        display: inline-block;
    }
    .status-ok { background-color: #064e3b; color: #6ee7b7; border: 1px solid #059669; }
    .status-sim { background-color: #451a03; color: #fcd34d; border: 1px solid #d97706; }

    /* 🔵 藍色建議框 (新功能) */
    .blue-recommend-box {
        background-color: #004aad; /* 顯眼的深藍色 */
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-size: 1.1rem;
        font-weight: bold;
        margin-top: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        border: 1px solid #007bff;
    }
    
    /* 灰色無建議框 */
    .gray-box {
        background-color: #2b2b2b;
        color: #aaa;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-size: 0.9rem;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 模擬數據生成器 ---
def get_simulated_data():
    now = datetime.now()
    hour = now.hour
    is_weekend = now.weekday() >= 5
    if 0 <= hour < 6: base = 85
    elif 7 <= hour < 20: base = 60 if is_weekend else 70
    else: base = 75
    
    # 加入隨機波動
    n_in = min(90, max(20, base + random.randint(-5, 10)))
    n_out = min(90, max(20, base + random.randint(-10, 5)))
    s_in = min(90, max(20, base + random.randint(-5, 10)))
    s_out = min(90, max(20, base + random.randint(-8, 8)))
    
    return {
        "N": {"in": n_in, "out": n_out},
        "S": {"in": s_in, "out": s_out}
    }, "⚠️ 離線推估模式 (連線逾時)"

# --- 核心：多重路徑抓取 ---
def get_tunnel_data():
    target_url = "https://tisvcloud.freeway.gov.tw/live/VD/VD_Live.xml.gz"
    proxies = [
        {"url": f"https://thingproxy.freeboard.io/fetch/{target_url}", "name": "線路 A"},
        {"url": f"https://api.allorigins.win/raw?url={target_url}", "name": "線路 B"},
        {"url": target_url, "name": "直連"}
    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    for proxy in proxies:
        try:
            response = requests.get(proxy["url"], headers=headers, timeout=5)
            if response.status_code == 200:
                try:
                    compressed_file = io.BytesIO(response.content)
                    decompressed_file = gzip.GzipFile(fileobj=compressed_file)
                    tree = ET.parse(decompressed_file)
                except:
                    try: tree = ET.fromstring(response.content)
                    except: continue

                root = tree.getroot()
                data_store = {"S": {"inner": [], "outer": []}, "N": {"inner": [], "outer": []}}
                TUNNEL_START, TUNNEL_END = 15000, 28000

                for info in root.findall(".//Info"):
                    if info.attrib.get("freewayId") == "5":
                        location = float(info.attrib.get("startLocation", 0)) * 1000
                        if TUNNEL_START <= location <= TUNNEL_END:
                            direction = info.attrib.get("directionId")
                            for lane in info.findall("Lane"):
                                speed = float(lane.attrib.get("speed", 0))
                                if speed > 0:
                                    lane_id = lane.attrib.get("laneId")
                                    if lane_id == "1": data_store[direction]["inner"].append(speed)
                                    elif lane_id == "2": data_store[direction]["outer"].append(speed)
                
                def calc_avg(lst):
                    return int(sum(lst)/len(lst)) if lst else 0
                
                result = {
                    "N": {"in": calc_avg(data_store["N"]["inner"]), "out": calc_avg(data_store["N"]["outer"])},
                    "S": {"in": calc_avg(data_store["S"]["inner"]), "out": calc_avg(data_store["S"]["outer"])}
                }
                
                if result["N"]["in"] == 0 and result["S"]["in"] == 0: continue
                return result, f"🟢 即時連線 ({proxy['name']})"
        except: continue

    return get_simulated_data()

# --- 介面顯示 ---
st.title("🏎️ 雪隧戰情室")

# 自動刷新開關
auto_refresh = st.toggle("開啟每60秒自動刷新", value=True)

if st.button('🔄 立即刷新數據', type="primary", use_container_width=True):
    st.rerun()

data, status_msg = get_tunnel_data()

# 顯示狀態
if "即時" in status_msg:
    st.markdown(f'<div class="status-badge status-ok">{status_msg}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="status-badge status-sim">{status_msg}</div>', unsafe_allow_html=True)

# 輔助函式：顯示藍色建議框
def show_recommendation(diff, faster_lane_name):
    if diff >= 5: # 內側快
        st.markdown(f'<div class="blue-recommend-box">💡 建議走【內側】 (快 {diff} km/h)</div>', unsafe_allow_html=True)
    elif diff <= -5: # 外側快
        st.markdown(f'<div class="blue-recommend-box">💡 建議走【外側】 (快 {abs(diff)} km/h)</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="gray-box">⚖️ 兩側速度相當，請保持車道</div>', unsafe_allow_html=True)

if data:
    # --- 北上 ---
    st.subheader("🛫 北上 (往台北)")
    c1, c2 = st.columns(2)
    n_in, n_out = data["N"]["in"], data["N"]["out"]
    n_diff = n_in - n_out

    c1.metric("內側 (左)", f"{n_in}", f"{n_diff} vs 右")
    c2.metric("外側 (右)", f"{n_out}", f"{-n_diff} vs 左", delta_color="inverse")
    
    # 呼叫建議函式
    show_recommendation(n_diff, "內側")

    st.markdown("---")

    # --- 南下 ---
    st.subheader("🏠 南下 (往宜蘭)")
    c3, c4 = st.columns(2)
    s_in, s_out = data["S"]["in"], data["S"]["out"]
    s_diff = s_in - s_out

    c3.metric("內側 (左)", f"{s_in}", f"{s_diff} vs 右")
    c4.metric("外側 (右)", f"{s_out}", f"{-s_diff} vs 左", delta_color="inverse")

    # 呼叫建議函式
    show_recommendation(s_diff, "內側")

# 自動刷新邏輯 (放在最後)
if auto_refresh:
    time.sleep(60) # 等待60秒
    st.rerun()     # 重新執行
