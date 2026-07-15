import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="My ETFNow Tracker", layout="wide")

st.markdown("<h2 style='color: #1E3A8A;'>📊 ETF 실시간 추적 대시보드 (업그레이드 버전)</h2>", unsafe_allow_html=True)
st.write("실시간 환율, ETF 정확한 명칭, 그리고 구성 종목의 실시간 가격까지 모두 연동됩니다.")
st.markdown("---")

# 2. 💵 실시간 원/달러 환율 불러오기
try:
    krw_usd = yf.Ticker("KRW=X").history(period="5d")
    if len(krw_usd) >= 2:
        cur_ex = krw_usd['Close'].iloc[-1]
        prev_ex = krw_usd['Close'].iloc[-2]
        ex_diff = cur_ex - prev_ex
        ex_pct = (ex_diff / prev_ex) * 100
        st.sidebar.metric(label="💵 실시간 환율 (원/달러)", value=f"{cur_ex:,.2f} 원", delta=f"{ex_diff:+.2f} ({ex_pct:+.2f}%)")
        st.sidebar.markdown("---")
except Exception:
    st.sidebar.info("환율 정보를 불러오는 중입니다.")

# 3. 사이드바 검색 기능
st.sidebar.header("🔍 ETF 검색")
search_option = st.sidebar.radio("검색 방법", ["종목코드 직접 입력", "인기 ETF 선택하기"])

if search_option == "인기 ETF 선택하기":
    POPULAR_ETFS = {"KODEX 200 (한국)": "069500.KS", "SPY (미국 S&P500)": "SPY", "QQQ (미국 나스닥)": "QQQ"}
    selected_name = st.sidebar.selectbox("ETF를 선택하세요:", list(POPULAR_ETFS.keys()))
    ticker = POPULAR_ETFS[selected_name]
else:
    ticker = st.sidebar.text_input("종목코드(티커)를 입력하세요:", value="0183J0.KS")
    st.sidebar.caption("💡 팁: 한국 주식은 코드 뒤에 '.KS'를 붙여주세요.")

period = st.sidebar.selectbox("조회 기간", ["1개월(1mo)", "3개월(3mo)", "6개월(6mo)", "1년(1y)"], index=3)
period_code = period.split("(")[1].replace(")", "")

# 4. 실시간 데이터 동기화 로직
if ticker:
    with st.spinner("해당 ETF의 실시간 주가 및 구성 종목 데이터를 동기화 중입니다..."):
        try:
            etf_data = yf.Ticker(ticker)
            hist = etf_data.history(period=period_code)
            info = etf_data.info
            
            # --- [핵심 추가] 한국 ETF(네이버 증권) vs 미국 ETF 분기 처리 ---
            is_korean = ticker.endswith('.KS') or ticker.endswith('.KQ')
            etf_name = info.get('longName', info.get('shortName', ticker))
            pdf_df = pd.DataFrame()
            
            if is_korean:
                # 🇰🇷 한국 ETF: 네이버 증권 실시간 크롤링
                code = ticker.replace('.KS', '').replace('.KQ', '')
                url = f"https://finance.naver.com/item/main.naver?code={code}"
                headers = {'User-Agent': 'Mozilla/5.0'}
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.content.decode('euc-kr', 'replace'), 'html.parser')
                
                # 정확한 이름 추출
                name_tag = soup.find('div', {'class': 'wrap_company'})
                if name_tag and name_tag.find('h2'):
                    etf_name = name_tag.find('h2').text
                
                # 실시간 구성 종목 및 현재가 추출 (네이버 ETF 테이블)
                table = soup.find('table', {'class': 'type_5'})
                if table:
                    h_data = []
                    rows = table.find('tbody').find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            h_name = cols[0].text.strip()
                            if h_name and h_name != "종목명":
                                weight = cols[2].text.strip()
                                h_price = cols[3].text.strip()
                                h_data.append({"구성 종목명": h_name, "비중(%)": weight, "실시간 현재가(원)": h_price})
                    pdf_df = pd.DataFrame(h_data)
                    
            else:
                # 🇺🇸 미국 ETF: 야후 파이낸스 실시간 가격 추적
                holdings = etf_data.holdings if hasattr(etf_data, 'holdings') else None
                if holdings is not None and not holdings.empty:
                    top_10 = pd.DataFrame(holdings).head(10)
                    h_data = []
                    for symbol, row in top_10.iterrows():
                        weight = row.get('holdingPercent', 0) * 100
                        try:
                            # 개별 구성 종목 실시간 가격 조회
                            c_price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
                            h_data.append({"구성 종목(티커)": symbol, "비중(%)": f"{weight:.2f}%", "실시간 현재가(USD)": f"${c_price:,.2f}"})
                        except:
                            h_data.append({"구성 종목(티커)": symbol, "비중(%)": f"{weight:.2f}%", "실시간 현재가(USD)": "데이터 로드 실패"})
                    pdf_df = pd.DataFrame(h_data)

            # 5. 화면 출력 (UI)
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                price_change = current_price - prev_price
                
                st.subheader(f"🏷️ {etf_name} ({ticker})")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    currency = "KRW" if is_korean else "USD"
                    st.metric(label=f"현재 가격 ({currency})", value=f"{current_price:,.2f}", delta=f"{price_change:+,.2f}")
                with col2:
                    aum = info.get('totalAssets', info.get('marketCap', 0))
                    st.metric(label="순자산 규모 (AUM)", value=f"{aum:,.0f}" if aum else "증권사 참조")
                with col3:
                    fee = info.get('expenseRatio', 0) * 100
                    st.metric(label="운용 보수 (연)", value=f"{fee:.2f}%" if fee > 0 else "증권사 공시 참조")
                    
                st.markdown("---")
                
                tab1, tab2 = st.tabs(["📋 실시간 구성 종목(PDF) 및 주가", "📈 수익률 차트"])
                
                with tab1:
                    st.markdown("### 🔍 ETF 핵심 구성 종목 (Top 10 실시간 주가 추적)")
                    if not pdf_df.empty:
                        st.dataframe(pdf_df, use_container_width=True)
                    else:
                        st.warning("이 ETF는 구성 종목을 실시간으로 공개하지 않거나 파생/레버리지 상품입니다.")
                        
                with tab2:
                    st.markdown("### 📈 일별 종가 트렌드 차트")
                    fig = px.line(hist, x=hist.index, y='Close', labels={'Close': '주가', 'Date': '날짜'})
                    fig.update_layout(template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)

            else:
                st.error("입력한 티커의 데이터를 찾을 수 없습니다. 다시 한 번 확인해 주세요.")

        except Exception as e:
            st.error(f"데이터를 처리하는 도중 문제가 발생했습니다: {e}")
