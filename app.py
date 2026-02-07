import streamlit as st
import requests
import gzip
import io
import xml.etree.ElementTree as ET

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
    .status-ok { color: #00e676; font-size: 0.8rem; }
    .status-fail { color: #ff1744; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心功能：多重路徑抓取數據 ---
def get_tunnel_data():
    target_url = "https://tisvcloud.freeway.gov.tw/live/VD/VD_Live.xml.gz"
    
    # 定義多種連線路徑 (路徑池)
    sources = [
        # 1. 嘗試直連 (本地或運氣好時可用)
        {"url": target_url, "name": "直連模式"},
        # 2. 跳板 A: CorsProxy
        {"url": f"https://corsproxy.io/?{target_url}", "name": "跳板 A"},
        # 3. 跳板 B: CodeTabs (備用)
        {"url": f"https://api.codetabs.com/v1/proxy?quest={target_url}", "name": "跳板 B"},
        # 4. 跳板 C: AllOrigins (備用2)
        {"url": f"https://api.allorigins.win/raw?url={target_url}", "name": "跳板 C"}
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    content = None
    success_source = ""

    # 迴圈測試所有路徑，直到成功為止
    for source in sources:
        try:
            # 設定短一點的 timeout 避免卡太久，跳板通常需要 10秒
            response = requests.get(source["url"], headers=headers, timeout=10)
            
            if response.status_code == 200:
                content = response.content
                success_source = source["name"]
                break # 成功了！跳出迴圈
        except Exception:
            continue # 失敗了，試下一個

    if content is None:
        st.error("❌ 所有連線路徑皆失敗，請稍後再試 (高公局伺服器可能繁忙)")
        return None

    # 解析數據
    try:
        compressed_file = io.BytesIO(content)
        decompressed_file = gzip.GzipFile(fileobj=compressed_file)
        tree = ET.parse(decompressed_file)
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
        # 回傳數據與成功的來源
        return result, success_source

    except Exception as e:
        st.error(f"數據解析失敗: {e}")
        return None, None

# --- 介面顯示 ---
st.title("🚗 雪隧即時戰情室")

if st.button('🔄 點擊刷新數據', type="primary", use_container_width=True):
    st.rerun()

data, source_name = get_tunnel_data()

if data:
    st.caption(f"連線來源: {source_name} (🟢 連線成功)")
    
    # --- 北上區塊 ---
    st.subheader("🛫 北上 (往台北/南港)")
    col1, col2 = st.columns(2)
    n_in, n_out = data["N"]["in"], data["N"]["out"]
    diff_n = n_in - n_out

    with col1:
        st.metric("內側 (左)", f"{n_in} km/h", delta=f"{diff_n} vs 右")
    with col2:
        st.metric("外側 (右)", f"{n_out} km/h", delta=f"{-diff_n} vs 左", delta_color="inverse")

    if n_in > 70 and n_out > 70: st.success("✅ 全線順暢")
    elif diff_n >= 5: st.info("💡 建議走【內側】")
    elif diff_n <= -5: st.warning("💡 建議走【外側】")
    else: st.info("⚖️ 速度相當")

    st.markdown("---")

    # --- 南下區塊 ---
    st.subheader("🏠 南下 (往宜蘭/員山)")
    col3, col4 = st.columns(2)
    s_in, s_out = data["S"]["in"], data["S"]["out"]
    diff_s = s_in - s_out

    with col3:
        st.metric("內側 (左)", f"{s_in} km/h", delta=f"{diff_s} vs 右")
    with col4:
        st.metric("外側 (右)", f"{s_out} km/h", delta=f"{-diff_s} vs 左", delta_color="inverse")

    if s_in > 70 and s_out > 70: st.success("✅ 全線順暢")
    elif diff_s >= 5: st.info("💡 建議走【內側】")
    elif diff_s <= -5: st.warning("💡 建議走【外側】")
    else: st.info("⚖️ 速度相當")

else:
    st.write("數據載入中...")
