import streamlit as st
import requests
import gzip
import io
import xml.etree.ElementTree as ET
import time

# --- 設定頁面資訊 ---
st.set_page_config(page_title="雪隧即時戰情室", page_icon="🚗", layout="centered")

# --- CSS 優化 ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 核心功能：抓取數據 (含防封鎖機制) ---
def get_tunnel_data():
    # 原始網址
    target_url = "https://tisvcloud.freeway.gov.tw/live/VD/VD_Live.xml.gz"
    
    # 偽裝 Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Encoding": "gzip"
    }

    content = None

    # 方法 1: 嘗試直連 (本地端通常可以，雲端可能會被擋)
    try:
        response = requests.get(target_url, headers=headers, timeout=5)
        if response.status_code == 200:
            content = response.content
    except:
        pass # 直連失敗，準備切換方法 2

    # 方法 2: 如果直連失敗，使用 CORS Proxy 跳板 (繞過地區限制)
    if content is None:
        try:
            # 使用 corsproxy.io 作為跳板
            proxy_url = f"https://corsproxy.io/?{target_url}"
            response = requests.get(proxy_url, headers=headers, timeout=10)
            if response.status_code == 200:
                content = response.content
            else:
                st.error(f"跳板連線失敗: {response.status_code}")
                return None
        except Exception as e:
            st.error(f"無法取得數據 (所有連線方式皆逾時): {e}")
            return None

    # 解析數據
    try:
        compressed_file = io.BytesIO(content)
        decompressed_file = gzip.GzipFile(fileobj=compressed_file)
        tree = ET.parse(decompressed_file)
        root = tree.getroot()

        data_store = {"S": {"inner": [], "outer": []}, "N": {"inner": [], "outer": []}}
        
        # 篩選雪隧 (15k - 28k)
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
            
        return {
            "N": {"in": calc_avg(data_store["N"]["inner"]), "out": calc_avg(data_store["N"]["outer"])},
            "S": {"in": calc_avg(data_store["S"]["inner"]), "out": calc_avg(data_store["S"]["outer"])}
        }
    except Exception as e:
        st.error(f"數據解析錯誤: {e}")
        return None

# --- 介面顯示 ---
st.title("🚗 雪隧即時戰情室")
st.caption("即時比較左右車道速度 (使用海外跳板連線)")

if st.button('🔄 點擊刷新數據', type="primary", use_container_width=True):
    st.rerun()

data = get_tunnel_data()

if data:
    # --- 北上區塊 ---
    st.subheader("🛫 北上 (往台北/南港)")
    col1, col2 = st.columns(2)
    
    n_in = data["N"]["in"]
    n_out = data["N"]["out"]
    diff_n = n_in - n_out

    with col1:
        st.metric("內側 (左)", f"{n_in} km/h", delta=f"{diff_n} vs 右")
    with col2:
        st.metric("外側 (右)", f"{n_out} km/h", delta=f"{-diff_n} vs 左", delta_color="inverse")

    if n_in > 70 and n_out > 70:
        st.success("✅ 全線順暢，兩道皆可。")
    elif diff_n >= 5:
        st.info("💡 建議走【內側】，速度較快。")
    elif diff_n <= -5:
        st.warning("💡 建議走【外側】，內側可能有龜速車。")
    else:
        st.info("⚖️ 速度相當，建議保持當前車道。")

    st.markdown("---")

    # --- 南下區塊 ---
    st.subheader("🏠 南下 (往宜蘭/員山)")
    col3, col4 = st.columns(2)
    
    s_in = data["S"]["in"]
    s_out = data["S"]["out"]
    diff_s = s_in - s_out

    with col3:
        st.metric("內側 (左)", f"{s_in} km/h", delta=f"{diff_s} vs 右")
    with col4:
        st.metric("外側 (右)", f"{s_out} km/h", delta=f"{-diff_s} vs 左", delta_color="inverse")

    if s_in > 70 and s_out > 70:
        st.success("✅ 全線順暢，快樂回家。")
    elif diff_s >= 5:
        st.info("💡 建議走【內側】。")
    elif diff_s <= -5:
        st.warning("💡 建議走【外側】，外側較快！")
    else:
        st.info("⚖️ 速度相當。")
else:
    st.write("數據載入中...")
