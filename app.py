import streamlit as st
import requests
import gzip
import io
import xml.etree.ElementTree as ET
import time
import random
from datetime import datetime

# --- 設定頁面 ---
st.set_page_config(page_title="國五雙隧道戰情室", page_icon="🏎️", layout="centered")

# --- CSS 優化 (定義客製化卡片樣式) ---
st.markdown("""
    <style>
    /* 標題樣式 */
    .tunnel-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #ffcc00;
        margin-top: 30px;
        margin-bottom: 10px;
        border-bottom: 2px solid #555;
        padding-bottom: 5px;
    }
    
    /* 速度卡片容器 */
    .speed-card {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        height: 100%;
    }
    
    /* 🏆 較快車道的特效 (綠色邊框) */
    .speed-card-fast {
        border: 2px solid #00e676; /* 亮綠色邊框 */
        background-color: #1a2e24; /* 極淡的綠底 */
        box-shadow: 0 0 15px rgba(0, 230, 118, 0.1);
    }
    
    /* 車道名稱 (內側/外側) */
    .lane-label {
        color: #aaaaaa;
        font-size: 1rem;
        margin-bottom: 5px;
    }
    
    /* 🏎️ 速度數字 */
    .speed-number {
        font-size: 2.5rem;
        font-weight: 800;
        line-height: 1.2;
    }
    
    /* 贏家顏色 (亮綠) */
    .text-fast { color: #00e676; }
    
    /* 一般顏色 (白) */
    .text-normal { color: #ffffff; }
    
    /* 差異小字 */
    .diff-label {
        font-size: 0.9rem;
        font-weight: bold;
        margin-top: 5px;
    }
    .diff-pos { color: #00e676; } /* 綠色 (快) */
    .diff-neg { color: #ff1744; } /* 紅色 (慢) */
    .diff-neu { color: #888; }    /* 灰色 (平手) */

    /* 🔵 藍色建議框 */
    .blue-recommend-box {
        background-color: #004aad;
        color: white;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        font-size: 1rem;
        font-weight: bold;
        margin-top: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    .gray-box {
        background-color: #2b2b2b;
        color: #aaa;
        padding: 8px;
        border-radius: 8px;
        text-align: center;
        font-size: 0.9rem;
        margin-top: 15px;
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
    </style>
    """, unsafe_allow_html=True)

# --- 模擬數據生成器 ---
def get_simulated_data():
    now = datetime.now()
    hour = now.hour
    base = 85 if 0 <= hour < 6 else (60 if 7 <= hour < 20 else 75)
    def gen_speed(): return min(90, max(20, base + random.randint(-10, 10)))
    return {
        "Pengshan": { "N": {"in": gen_speed(), "out": gen_speed()}, "S": {"in": gen_speed(), "out": gen_speed()} },
        "Hsuehshan": { "N": {"in": gen_speed(), "out": gen_speed()}, "S": {"in": gen_speed(), "out": gen_speed()} }
    }, "⚠️ 離線推估模式"

# --- 核心：抓取數據 ---
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
                raw_data = {
                    "Pengshan": {"S": {"in": [], "out": []}, "N": {"in": [], "out": []}},
                    "Hsuehshan": {"S": {"in": [], "out": []}, "N": {"in": [], "out": []}}
                }
                RANGE_PENGSHAN = (11000, 15000)
                RANGE_HSUEHSHAN = (15000, 28000)

                for info in root.findall(".//Info"):
                    if info.attrib.get("freewayId") == "5":
                        location = float(info.attrib.get("startLocation", 0)) * 1000
                        direction = info.attrib.get("directionId")
                        target_tunnel = None
                        if RANGE_PENGSHAN[0] <= location <= RANGE_PENGSHAN[1]: target_tunnel = "Pengshan"
                        elif RANGE_HSUEHSHAN[0] <= location <= RANGE_HSUEHSHAN[1]: target_tunnel = "Hsuehshan"
                        
                        if target_tunnel:
                            for lane in info.findall("Lane"):
                                speed = float(lane.attrib.get("speed", 0))
                                if speed > 0:
                                    lane_id = lane.attrib.get("laneId")
                                    if lane_id == "1": raw_data[target_tunnel][direction]["in"].append(speed)
                                    elif lane_id == "2": raw_data[target_tunnel][direction]["out"].append(speed)
                
                def calc_avg(lst): return int(sum(lst)/len(lst)) if lst else 0
                
                final_result = {}
                for tunnel in ["Pengshan", "Hsuehshan"]:
                    final_result[tunnel] = {
                        "N": {"in": calc_avg(raw_data[tunnel]["N"]["in"]), "out": calc_avg(raw_data[tunnel]["N"]["out"])},
                        "S": {"in": calc_avg(raw_data[tunnel]["S"]["in"]), "out": calc_avg(raw_data[tunnel]["S"]["out"])}
                    }
                
                if final_result["Hsuehshan"]["N"]["in"] == 0: continue
                return final_result, f"🟢 即時連線 ({proxy['name']})"
        except: continue
    return get_simulated_data()

# --- 客製化卡片繪製函式 ---
def draw_speed_card(col, title, speed, diff, is_faster):
    # 決定樣式
    card_class = "speed-card speed-card-fast" if is_faster else "speed-card"
    text_class = "text-fast" if is_faster else "text-normal"
    
    # 決定差異顯示
    if diff > 0:
        diff_html = f'<div class="diff-label diff-pos">↑ 快 {diff}</div>'
    elif diff < 0:
        diff_html = f'<div class="diff-label diff-neg">↓ 慢 {abs(diff)}</div>'
    else:
        diff_html = '<div class="diff-label diff-neu">- 持平</div>'

    html = f"""
    <div class="{card_class}">
        <div class="lane-label">{title}</div>
        <div class="speed-number {text_class}">{speed}</div>
        {diff_html}
    </div>
    """
    col.markdown(html, unsafe_allow_html=True)

# --- 顯示區段函式 ---
def show_tunnel_section(tunnel_name, n_data, s_data):
    st.markdown(f'<div class="tunnel-title">{tunnel_name}</div>', unsafe_allow_html=True)
    
    # 北上
    st.caption("🛫 北上 (往台北)")
    c1, c2 = st.columns(2)
    n_diff = n_data["in"] - n_data["out"]
    
    # 判斷誰比較快 (大於 2km/h 才算快，避免閃爍)
    n_in_faster = n_diff >= 2
    n_out_faster = n_diff <= -2
    
    draw_speed_card(c1, "內側 (左)", n_data['in'], n_diff, n_in_faster)
    draw_speed_card(c2, "外側 (右)", n_data['out'], -n_diff, n_out_faster)
    
    if n_diff >= 5: st.markdown(f'<div class="blue-recommend-box">💡 內側快 {n_diff} km</div>', unsafe_allow_html=True)
    elif n_diff <= -5: st.markdown(f'<div class="blue-recommend-box">💡 外側快 {abs(n_diff)} km</div>', unsafe_allow_html=True)
    else: st.markdown(f'<div class="gray-box">⚖️ 速度相當</div>', unsafe_allow_html=True)

    # 南下
    st.markdown("<br>", unsafe_allow_html=True) # 間距
    st.caption("🏠 南下 (往宜蘭)")
    c3, c4 = st.columns(2)
    s_diff = s_data["in"] - s_data["out"]
    
    s_in_faster = s_diff >= 2
    s_out_faster = s_diff <= -2

    draw_speed_card(c3, "內側 (左)", s_data['in'], s_diff, s_in_faster)
    draw_speed_card(c4, "外側 (右)", s_data['out'], -s_diff, s_out_faster)

    if s_diff >= 5: st.markdown(f'<div class="blue-recommend-box">💡 內側快 {s_diff} km</div>', unsafe_allow_html=True)
    elif s_diff <= -5: st.markdown(f'<div class="blue-recommend-box">💡 外側快 {abs(s_diff)} km</div>', unsafe_allow_html=True)
    else: st.markdown(f'<div class="gray-box">⚖️ 速度相當</div>', unsafe_allow_html=True)

# --- 主程式 ---
st.title("🏎️ 國五雙隧道戰情室")
auto_refresh = st.toggle("每60秒自動刷新", value=True)

if st.button('🔄 立即刷新', type="primary", use_container_width=True):
    st.rerun()

data, status_msg = get_tunnel_data()

if "即時" in status_msg:
    st.markdown(f'<div class="status-badge status-ok">{status_msg}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="status-badge status-sim">{status_msg}</div>', unsafe_allow_html=True)

if data:
    show_tunnel_section("⛰️ 彭山隧道 (3.8km)", data["Pengshan"]["N"], data["Pengshan"]["S"])
    show_tunnel_section("🗻 雪山隧道 (12.9km)", data["Hsuehshan"]["N"], data["Hsuehshan"]["S"])

if auto_refresh:
    time.sleep(60)
    st.rerun()
