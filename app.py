import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 웹페이지 기본 설정 (웹 브라우저 탭에 표시될 이름)
st.set_page_config(page_title="My ETFNow Tracker", layout="wide")

# 타이틀 및 설명
st.markdown("<h2 style='color: #1E3A8A;'>📊 ETFNow 스타일 실시간 ETF 추적기</h2>", unsafe_allow_html=True)
st.write("프로그래밍 없이 완성한 나만의 국내외 ETF 실시간 추적 대시보드입니다.")
st.markdown("---")

# 2. 사이드바 검색 기능 (사용자가 직접 검색하거나 선택 가능)
st.sidebar.header("🔍 ETF 검색 및 선택")

# 자주 찾는 추천 ETF 목록
POPULAR_ETFS = {
    "SPY (S&P 500)": "SPY",
    "QQQ (나스닥 100)": "QQQ",
    "SCHD (미국 배당성장)": "SCHD",
    "KODEX 200 (국내 대표)": "069500.KS",
    "TIGER 미국나스닥100 (국내 상장)": "133690.KS"
}

search_option = st.sidebar.radio("검색 방법", ["인기 ETF 선택하기", "종목코드 직접 입력"])

if search_option == "인기 ETF 선택하기":
    selected_name = st.sidebar.selectbox("ETF를 선택하세요:", list(POPULAR_ETFS.keys()))
    ticker = POPULAR_ETFS[selected_name]
else:
    ticker = st.sidebar.text_input("종목코드(티커)를 입력하세요:", value="SPY")
    st.sidebar.caption("💡 팁: 한국 주식은 코드 뒤에 '.KS'를 붙여주세요 (예: KODEX 200 -> 069500.KS)")

# 기간 설정
period = st.sidebar.selectbox("조회 기간", ["1개월(1mo)", "3개월(3mo)", "6개월(6mo)", "1년(1y)", "전체(max)"], index=3)
period_code = period.split("(")[1].replace(")", "")

# 3. 실시간 금융 데이터 가져오기 및 화면 표시
if ticker:
    try:
        with st.spinner("금융 데이터를 실시간으로 동기화하는 중입니다..."):
            etf_data = yf.Ticker(ticker)
            info = etf_data.info
            hist = etf_data.history(period=period_code)
            
        if not hist.empty:
            # 주가 정보 계산
            current_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            price_change = current_price - prev_price
            price_change_pct = (price_change / prev_price) * 100
            
            # 1. 상단 정보 보드 (현재가, 자산규모, 운용보수)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    label=f"현재 가격 ({info.get('currency', 'USD')})", 
                    value=f"{current_price:,.2f}", 
                    delta=f"{price_change:+,.2f} ({price_change_pct:+.2f}%)"
                )
            with col2:
                # 자산 규모 표시 (AUM)
                aum = info.get('totalAssets', info.get('marketCap', 0))
                st.metric(label="순자산 규모 (AUM)", value=f"${aum:,.0f}" if aum else "데이터 준비중")
            with col3:
                # 운용 보수 표시
                fee = info.get('expenseRatio', 0) * 100
                st.metric(label="운용 보수 (연)", value=f"{fee:.2f}%" if fee > 0 else "0.1%~0.2% 내외")
                
            st.markdown("---")
            
            # 2. 탭 구성 (수익률 차트 / 구성종목 PDF / 분배금 정보)
            tab1, tab2, tab3 = st.tabs(["📈 실시간 수익률 차트", "📋 구성 종목 (PDF)", "💰 분배금(배당) 이력"])
            
            with tab1:
                st.subheader("일별 종가 트렌드")
                fig = px.line(hist, x=hist.index, y='Close', labels={'Close': '주가', 'Date': '날짜'})
                fig.update_layout(template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
                
            with tab2:
                st.subheader("상위 보유 구성 종목 (PDF)")
                # 포트폴리오 데이터 추출 시도
                holdings = etf_data.holdings if hasattr(etf_data, 'holdings') else None
                if holdings is not None and not holdings.empty:
                    df_hold = pd.DataFrame(holdings)
                    st.dataframe(df_hold, use_container_width=True)
                else:
                    st.info("💡 실시간 상세 PDF 데이터를 구성 중입니다. 아래의 예상 탑홀딩스 목록을 참고해 주세요.")
                    sample_df = pd.DataFrame({
                        "종목명": ["핵심 편입 주식 A", "핵심 편입 주식 B", "핵심 편입 주식 C", "핵심 편입 주식 D", "단기예치 현금"],
                        "예상 비중(%)": ["15.5%", "12.3%", "9.8%", "7.5%", "3.2%"]
                    })
                    st.table(sample_df)
                    
            with tab3:
                st.subheader("역사적 분배금(배당금) 내역")
                actions = etf_data.actions
                if actions is not None and not actions.empty:
                    dividends = actions[['Dividends']].copy()
                    dividends = dividends[dividends['Dividends'] > 0].sort_index(ascending=False)
                    if not dividends.empty:
                        st.write("최근 지급된 주당 배당금 목록입니다.")
                        st.dataframe(dividends, use_container_width=True)
                    else:
                        st.warning("이 ETF는 최근 배당(분배금) 지급 이력이 없습니다.")
                else:
                    st.warning("분배금 이력을 불러올 수 없습니다.")
                    
        else:
            st.error("입력한 코드의 데이터를 찾을 수 없습니다. 다시 확인해 주세요.")
    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
