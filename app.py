import streamlit as st
import requests
import gzip
import io
import xml.etree.ElementTree as ET

st.set_page_config(page_title="雪隧即時戰情室", page_icon="🚗", layout="centered")

# CSS 優化
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

def get_tunnel_data():
    url = "https://tisvcloud.freeway.gov.tw/live/VD/VD_Live.xml.gz"
    try:
        response = requests.get(url, timeout=10)
        compressed_file = io.BytesIO(response.content)
        decompressed_file = gzip.GzipFile(fileobj=compressed_file)
        tree = ET.parse(decompressed_file)
        root = tree.getroot()

        data_store = {"S": {"inner": [], "outer": []}, "N": {"inner": [], "outer": []}}
        TUNNEL_START, TUNNEL_END = 15000, 28000 # 雪隧里程

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
        return None

st.title("🚗 雪隧戰情室")
st.caption("即時比較左右車道速度")

if st.button('🔄 點擊刷新數據', type="primary", use_container_width=True):
    st.rerun()

data = get_tunnel_data()

if data:
    # 北上
    st.subheader("🛫 北上 (往台北)")
    c1, c2 = st.columns(2)
    n_in, n_out = data["N"]["in"], data["N"]["out"]
    diff_n = n_in - n_out
    c1.metric("內側(左)", f"{n_in}", f"{diff_n} vs 右")
    c2.metric("外側(右)", f"{n_out}", f"{-diff_n} vs 左", delta_color="inverse")
    
    if n_in > 70 and n_out > 70: st.success("✅ 全線順暢")
    elif diff_n >= 5: st.info("💡 建議走【內側】")
    elif diff_n <= -5: st.warning("💡 建議走【外側】")
    else: st.write("⚖️ 兩線差不多")

    st.markdown("---")

    # 南下
    st.subheader("🏠 南下 (往宜蘭)")
    c3, c4 = st.columns(2)
    s_in, s_out = data["S"]["in"], data["S"]["out"]
    diff_s = s_in - s_out
    c3.metric("內側(左)", f"{s_in}", f"{diff_s} vs 右")
    c4.metric("外側(右)", f"{s_out}", f"{-diff_s} vs 左", delta_color="inverse")

    if s_in > 70 and s_out > 70: st.success("✅ 全線順暢")
    elif diff_s >= 5: st.info("💡 建議走【內側】")
    elif diff_s <= -5: st.warning("💡 建議走【外側】")
    else: st.write("⚖️ 兩線差不多")
else:
    st.error("暫時無法取得數據，請稍後再試")