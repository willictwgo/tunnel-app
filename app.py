import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

# --- 設定頁面 ---
st.set_page_config(page_title="雪隧戰情室 (Web版)", page_icon="🏎️", layout="centered")

# --- CSS 美化 ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #2b2b2b;
        border: 1px solid #444;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 700;
        color: #fff;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 1rem;
        color: #aaa;
    }
    .big-font { font-size: 1.2rem; font-weight: bold; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心：爬取 tw.live 網站 ---
def scrape_tw_live():
    url = "https://tw.live/national-highway/5/guide/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8' # 確保中文不亂碼
        
        if response.status_code != 200:
            return None, "無法連線至來源網站"

        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text()
        
        # 移除多餘空白，方便正則表達式搜尋
        clean_text = re.sub(r'\s+', ' ', text_content)

        # ---------------------------------------------------------
        # 使用正則表達式 (Regex) 尋找特定關鍵字附近的數字
        # 網站格式範例: "雪隧入口(頭城) ... 左: 79 | 右: 74"
        # ---------------------------------------------------------

        # 1. 北上 (找 "頭城" 附近的 "左: xx | 右: xx")
        # 這裡假設網頁結構中，頭城入口的數據格式如下
        north_match = re.search(r"雪隧入口\(頭城\).*?左:\s*(\d+)\s*\|\s*右:\s*(\d+)", clean_text)
        
        # 2. 南下 (找 "坪林" 附近的 "左: xx | 右: xx")
        south_match = re.search(r"雪隧入口\(坪林\).*?左:\s*(\d+)\s*\|\s*右:\s*(\d+)", clean_text)

        result = {}

        if north_match:
            result["N"] = {"in": int(north_match.group(1)), "out": int(north_match.group(2))}
        else:
            result["N"] = {"in": 0, "out": 0} # 抓不到時回傳 0

        if south_match:
            result["S"] = {"in": int(south_match.group(1)), "out": int(south_match.group(2))}
        else:
            result["S"] = {"in": 0, "out": 0}

        return result, "OK"

    except Exception as e:
        return None, str(e)

# --- 介面 ---
st.title("🏎️ 雪隧戰情室")
st.caption("資料來源：tw.live 即時影像監視器")

if st.button('🔄 刷新數據', type="primary", use_container_width=True):
    st.rerun()

data, status = scrape_tw_live()

if data:
    # --- 北上 ---
    st.markdown('<div class="big-font">🛫 北上 (往台北) - 頭城入口</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    
    n_in = data["N"]["in"]
    n_out = data["N"]["out"]
    n_diff = n_in - n_out

    if n_in == 0 and n_out == 0:
        st.warning("⚠️ 暫時無法讀取北上數據 (網頁改版或讀取中)")
    else:
        c1.metric("內側 (左)", f"{n_in}", f"{n_diff} vs 右")
        c2.metric("外側 (右)", f"{n_out}", f"{-n_diff} vs 左", delta_color="inverse")
        
        # 建議
        if n_in > 70 and n_out > 70: st.success("✅ 全線順暢")
        elif n_diff >= 5: st.info("💡 建議走【內側】")
        elif n_diff <= -5: st.warning("💡 建議走【外側】")
        else: st.info("⚖️ 速度相當")

    st.markdown("---")

    # --- 南下 ---
    st.markdown('<div class="big-font">🏠 南下 (往宜蘭) - 坪林入口</div>', unsafe_allow_html=True)
    c3, c4 = st.columns(2)
    
    s_in = data["S"]["in"]
    s_out = data["S"]["out"]
    s_diff = s_in - s_out

    if s_in == 0 and s_out == 0:
        st.warning("⚠️ 暫時無法讀取南下數據 (網頁改版或讀取中)")
    else:
        c3.metric("內側 (左)", f"{s_in}", f"{s_diff} vs 右")
        c4.metric("外側 (右)", f"{s_out}", f"{-s_diff} vs 左", delta_color="inverse")

        # 建議
        if s_in > 70 and s_out > 70: st.success("✅ 全線順暢")
        elif s_diff >= 5: st.info("💡 建議走【內側】")
        elif s_diff <= -5: st.warning("💡 建議走【外側】")
        else: st.info("⚖️ 速度相當")

else:
    st.error(f"讀取錯誤: {status}")
    st.markdown("[點此直接前往來源網站查看](https://tw.live/national-highway/5/guide/)")
