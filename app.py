import streamlit as st
import requests
import gzip
import io
import xml.etree.ElementTree as ET
import time
import random
from datetime import datetime

# --- 設定頁面 (開啟 wide mode 以利用最大寬度) ---
st.set_page_config(page_title="國五戰情室", page_icon="🏎️", layout="wide")

# --- CSS 極致優化 (手機版強制左右並排) ---
st.markdown("""
    <style>
    /* 全局設定 */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* 標題樣式 */
    .tunnel-header {
        font-size: 1.4rem;
        font-weight: 900;
        color: #ffcc00;
        text-align: center;
        margin-top: 20px;
        margin-bottom: 10px;
        background: #333;
        padding: 5px;
        border-radius: 8px;
    }

    /* 🚗 車道容器 (Flexbox 強制並排) */
    .lane-container {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 10px;
    }

    /* 單一車道卡片 */
    .lane-card {
        width: 48%; /* 強制佔一半寬度 */
        background-color: #1E1E1E;
        border: 1px solid #444;
        border-radius: 10px;
        padding: 10px 5px;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }

    /* 🏆 較快車道的特效 (綠框+綠底) */
    .lane-fast {
        border: 2px solid #00e676;
        background-color: rgba(0, 230, 118, 0.05);
        box-shadow: 0 0 10px rgba(0, 230, 118, 0.1);
    }

    /* 文字標籤 */
    .lane-label {
        font-size: 0.9rem;
        color: #aaa;
        margin-bottom: 2px;
    }

    /* 速度數字 (手機版特化大字體) */
    .speed-num {
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1.1;
        font-family: 'Segoe UI', sans-serif;
    }
    
    .text-green { color: #00e676; }
    .text-white { color: #ffffff; }

    /* 差異小字 */
    .diff-tag {
        font-size: 0.75rem;
        font-weight: bold;
        margin-top: 2px;
        padding: 2px 6px;
        border-radius: 4px;
    }
    .diff-win { background: #064e3b; color: #6ee7b7; }
    .diff-lose { background: #450a0a; color: #fca5a5; }

    /* 🔵 建議框 */
    .rec-box {
        background: linear-gradient(90deg, #004aad 0%, #0066cc 100%);
        color: white;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        font-size: 1rem;
        font-weight: bold;
        margin-bottom: 20px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.3);
    }
    
    /* 方向標題 */
    .dir-title {
        font-size: 1rem;
        color: #ddd;
        margin-top: 10px;
        margin-bottom: 5px;
        border-left: 4px solid #00e676;
        padding-left: 8px;
    }
    
    /* 狀態標籤 */
    .status-badge {
        font-size: 0.8rem;
        padding: 4px 8px;
        border-radius: 4px;
        margin-bottom: 5px;
        text-align: center;
        display: block;
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
    def gen(): return min(90, max(20, base + random.randint(-10, 10)))
    return {
        "Pengshan": { "N": {"in": gen(), "out": gen()}, "S": {"in": gen(), "out": gen()} },
        "Hsuehshan": { "N": {"in": gen(), "out": gen()}, "S": {"in": gen(), "out": gen()} }
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
                raw = {
                    "Pengshan": {"S": {"in": [], "out": []}, "N": {"in": [], "out": []}},
                    "Hsuehshan": {"S": {"in": [], "out": []}, "N": {"in": [], "out": []}}
                }
                # 定義里程
                R_PENG = (11000, 15000)
                R_HSUE = (15000, 28000)

                for info in root.findall(".//Info"):
                    if info.attrib.get("freewayId") == "5":
                        loc = float(info.attrib.get("startLocation", 0)) * 1000
                        direc = info.attrib.get("directionId")
                        target = None
                        if R_PENG[0] <= loc <= R_PENG[1]: target = "Pengshan"
                        elif R_HSUE[0] <= loc <= R_HSUE[1]: target = "Hsuehshan"
                        
                        if target:
                            for lane in info.findall("Lane"):
                                spd = float(lane.attrib.get("speed", 0))
                                if spd > 0:
                                    lid = lane.attrib.get("laneId")
                                    if lid == "1": raw[target][direc]["in"].append(spd)
                                    elif lid == "2": raw[target][direc]["out"].append(spd)
                
                def avg(l): return int(sum(l)/len(l)) if l else 0
                res = {}
                for t in ["Pengshan", "Hsuehshan"]:
                    res[t] = {
                        "N": {"in": avg(raw[t]["N"]["in"]), "out": avg(raw[t]["N"]["out"])},
                        "S": {"in": avg(raw[t]["S"]["in"]), "out": avg(raw[t]["S"]["out"])}
                    }
                if res["Hsuehshan"]["N"]["in"] == 0: continue
                return res, f"🟢 即時連線 ({proxy['name']})"
        except: continue
    return get_simulated_data()

# --- HTML 生成函式 (核心視覺邏輯) ---
def render_lane_html(inner_spd, outer_spd):
    diff = inner_spd - outer_spd
    
    # 判斷樣式
    in_cls = "lane-card"
    out_cls = "lane-card"
    in_txt = "text-white"
    out_txt = "text-white"
    in_tag = ""
    out_tag = ""

    if diff >= 3: # 內側快
        in_cls += " lane-fast"
        in_txt = "text-green"
        in_tag = f'<div class="diff-tag diff-win">快 {diff}</div>'
        out_tag = f'<div class="diff-tag diff-lose">慢 {diff}</div>'
    elif diff <= -3: # 外側快
        out_cls += " lane-fast"
        out_txt = "text-green"
        out_tag = f'<div class="diff-tag diff-win">快 {abs(diff)}</div>'
        in_tag = f'<div class="diff-tag diff-lose">慢 {abs(diff)}</div>'
    
    html = f"""
    <div class="lane-container">
        <div class="{in_cls}">
            <div class="lane-label">內側 (左)</div>
            <div class="speed-num {in_txt}">{inner_spd}</div>
            {in_tag}
        </div>
        <div class="{out_cls}">
            <div class="lane-label">外側 (右)</div>
            <div class="speed-num {out_txt}">{outer_spd}</div>
            {out_tag}
        </div>
    </div>
    """
    return html

def render_recommendation(diff):
    if diff >= 5:
        st.markdown(f'<div class="rec-box">💡 建議走【內側】 (快 {diff} km)</div>', unsafe_allow_html=True)
    elif diff <= -5:
        st.markdown(f'<div class="rec-box">💡 建議走【外側】 (快 {abs(diff)} km)</div>', unsafe_allow_html=True)
    # 差異不大就不顯示建議，節省空間

# --- 主程式 ---
st.markdown('<div style="text-align:center; font-size:1.5rem;">🏎️ 國五戰情室</div>', unsafe_allow_html=True)
auto_refresh = st.toggle("每60秒自動刷新", value=True)

if st.button('🔄 立即刷新', type="primary", use_container_width=True):
    st.rerun()

data, status_msg = get_tunnel_data()

# 狀態列
status_cls = "status-ok" if "即時" in status_msg else "status-sim"
st.markdown(f'<div class="status-badge {status_cls}">{status_msg}</div>', unsafe_allow_html=True)

if data:
    # 彭山隧道
    st.markdown('<div class="tunnel-header">⛰️ 彭山隧道</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="dir-title">🛫 北上 (往台北)</div>', unsafe_allow_html=True)
    st.markdown(render_lane_html(data["Pengshan"]["N"]["in"], data["Pengshan"]["N"]["out"]), unsafe_allow_html=True)
    render_recommendation(data["Pengshan"]["N"]["in"] - data["Pengshan"]["N"]["out"])

    st.markdown('<div class="dir-title">🏠 南下 (往宜蘭)</div>', unsafe_allow_html=True)
    st.markdown(render_lane_html(data["Pengshan"]["S"]["in"], data["Pengshan"]["S"]["out"]), unsafe_allow_html=True)
    render_recommendation(data["Pengshan"]["S"]["in"] - data["Pengshan"]["S"]["out"])

    # 雪山隧道
    st.markdown('<div class="tunnel-header">🗻 雪山隧道</div>', unsafe_allow_html=True)

    st.markdown('<div class="dir-title">🛫 北上 (往台北)</div>', unsafe_allow_html=True)
    st.markdown(render_lane_html(data["Hsuehshan"]["N"]["in"], data["Hsuehshan"]["N"]["out"]), unsafe_allow_html=True)
    render_recommendation(data["Hsuehshan"]["N"]["in"] - data["Hsuehshan"]["N"]["out"])

    st.markdown('<div class="dir-title">🏠 南下 (往宜蘭)</div>', unsafe_allow_html=True)
    st.markdown(render_lane_html(data["Hsuehshan"]["S"]["in"], data["Hsuehshan"]["S"]["out"]), unsafe_allow_html=True)
    render_recommendation(data["Hsuehshan"]["S"]["in"] - data["Hsuehshan"]["S"]["out"])

if auto_refresh:
    time.sleep(60)
    st.rerun()
