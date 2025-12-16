import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import linregress
import os

# --- 설정 및 데이터 파일 경로 ---
# 파일 이름은 'golf_scores.xlsx'로 유지 (사용자 의도 존중)
FILE_NAME = 'golf_scores.xlsx'
# 만약 첨부된 파일 이름 그대로 사용하려면: FILE_NAME = 'golf_scores.xlsx - Sheet1.csv'
FILE_PATH = os.path.join(os.getcwd(), FILE_NAME)
STANDARD_PAR = 72  # 18홀 기준 타수 (Par 72)

st.set_page_config(layout="wide", page_title="⛳ 골프 스코어 분석 대시보드")


@st.cache_data
def load_data(filepath):
    """
    엑셀(.xlsx) 또는 CSV(.csv) 파일을 로드하고 데이터를 정제합니다.
    """
    df = None
    try:
        # 1. 엑셀 파일(.xlsx)로 시도
        df = pd.read_excel(filepath)
    except FileNotFoundError:
        # 파일이 아예 없을 때 (이 경우 아래 CSV 시도도 실패할 것임)
        st.error(f"오류: '{FILE_NAME}' 파일을 찾을 수 없습니다. 파일 경로와 이름을 확인하세요.")
        st.stop()
    except Exception as e:
        # 2. 엑셀 로드에 실패하면 CSV 파일로 시도 (첨부된 파일처럼 이름이 .xlsx인데 내용이 CSV일 수 있음)
        try:
            st.info("파일을 엑셀 형식으로 읽는 데 실패하여 CSV 형식으로 재시도합니다.")
            df = pd.read_csv(filepath)
        except Exception as e_csv:
            st.error(f"데이터 로드 중 심각한 오류 발생. 엑셀/CSV 형식을 모두 확인할 수 없습니다: {e_csv}")
            st.stop()

    if df is None:
        st.stop()

    # --- 데이터 정제 로직 ---
    try:
        # 엑셀 첫 번째 열의 실제 헤더 이름 가져오기
        round_col_name = df.columns[0]

        # Wide -> Long Format 변환 (Player 열과 Score 열 분리)
        df_long = df.melt(id_vars=[round_col_name],
                          var_name='Player',
                          value_name='Score')

        # 'Round' 열 이름 통일
        df_long = df_long.rename(columns={round_col_name: 'Round_Label'})

        # 'Round' 라벨에서 숫자만 추출하여 Round_Num 생성 (추세선 계산용)
        df_long['Round_Num'] = pd.to_numeric(
            df_long['Round_Label'].astype(str).str.replace('회', '').str.strip(),
            errors='coerce'
        )

        # Score 열 정리 (숫자가 아닌 값은 NaN으로 처리)
        df_long['Score'] = pd.to_numeric(df_long['Score'], errors='coerce')

        # 필수 데이터(Round 번호, Score)가 없는 행 제거
        df_long = df_long.dropna(subset=['Round_Num', 'Score']).copy()
        df_long['Round_Num'] = df_long['Round_Num'].astype(int)
        df_long = df_long.sort_values(by='Round_Num')  # 라운드 순으로 정렬

        return df_long

    except Exception as e:
        st.error(f"데이터 정제 중 오류 발생. 엑셀/CSV 파일 구조가 '라운딩 수 | 플레이어1 | 플레이어2' 형식인지 확인하세요: {e}")
        st.stop()


# 데이터 로드 및 플레이어 목록 가져오기
df = load_data(FILE_PATH)
players = df['Player'].unique()

# --- 사이드바: 플레이어 선택 ---
st.sidebar.header("⛳ 플레이어 선택")
selected_player = st.sidebar.selectbox("분석할 플레이어를 선택하세요", players)

# 선택된 플레이어 데이터 필터링 및 정렬
player_df = df[df['Player'] == selected_player].copy()

if len(player_df) < 2:
    st.warning(f"{selected_player}님은 라운드 데이터가 2개 미만이라 분석을 표시할 수 없습니다.")
    st.stop()

# 추세선 계산을 위한 순차 번호 (1, 2, 3... 같은 순차적인 X축 데이터 필요)
player_df['Seq_Num'] = range(1, len(player_df) + 1)

# 통계 계산
avg_score = player_df['Score'].mean()
min_score = player_df['Score'].min()
max_score = player_df['Score'].max()
total_rounds = len(player_df)

# --- [수정] 아마추어 핸디캡 계산 로직 ---
# 1. 스코어를 오름차순(낮은 스코어부터) 정렬
sorted_scores = player_df['Score'].sort_values(ascending=True)

# 2. 최저 스코어 5개를 선택 (라운드가 5개 미만인 경우 가능한 모든 라운드를 사용)
num_best_rounds = min(5, total_rounds)
best_scores = sorted_scores.head(num_best_rounds)

# 3. 핸디캡 스코어 계산 (베스트 N개 라운드의 평균)
handicap_score_calc = best_scores.mean()

# 추세선 계산
slope, intercept, r_value, _, _ = linregress(player_df['Seq_Num'], player_df['Score'])
r_squared = r_value ** 2
correlation = r_value

# 예상 변화량 계산
expected_change = slope * total_rounds

# 핸디캡 계산
handicap_over_par = avg_score - STANDARD_PAR
handicap_display = f"{int(round(avg_score))}타 ({handicap_over_par:+.0f})"

# --- 대시보드 UI 구현 ---
st.title(f"{selected_player}님의 골프 스코어 분석 대시보드")
st.markdown("---")

# 상단 통계 카드 (6개)
# 컬럼 순서 변경: 1.추세 기울기, 2.예상 변화, 3.결정계수, 4.평균 스코어, 5.최저/최고, 6.추정 핸디캡
col1, col2, col3, col4, col5, col6 = st.columns(6)

# 1. 추세 기울기 (이전 col2 위치 -> col1로 이동)
delta_color = "inverse" if slope < 0 else "normal"
col1.metric("추세 기울기 (타/회)", f"{slope:.2f}", delta_color=delta_color)

# 2. 예상 변화 (이전 col3 위치 -> col2로 이동)
col2.metric("총 변화 예측", f"{expected_change:+.1f}타", delta_color=delta_color)

# 3. 결정계수 (이전 col4 위치 -> col3로 이동)
col3.metric("결정계수 (R²)", f"{r_squared:.2f}")

# 4. 평균 스코어 (이전 col5 위치 -> col4로 이동)
col4.metric("평균 스코어", f"{avg_score:.1f}타")

# 5. 최저/최고 (이전 col6 위치 -> col5로 이동)
col5.metric("최저 / 최고", f"{min_score:.0f} / {max_score:.0f}타")

# 6. 추정 핸디캡 (이전 col1 위치 -> col6으로 이동)
col6.metric("추정 핸디캡 (평균)", handicap_display, delta=f"{handicap_over_par:+.0f} Par", delta_color="off")

st.markdown("---")

# --- 그래프 시각화 (Plotly) ---
fig = go.Figure()

# 1. 실제 스코어 (점과 선)
fig.add_trace(go.Scatter(
    x=player_df['Round_Label'],
    y=player_df['Score'],
    # mode에 'text'를 추가하여 스코어 값을 그래프 위에 표시
    mode='lines+markers+text',
    name='실제 스코어',
    line=dict(color='red', width=3, shape='spline'),
    marker=dict(size=10),
    # text 인수에 Score 값 지정 (정수형으로 표시)
    text=player_df['Score'].astype(int).astype(str),
    # textposition을 'top center'로 설정 (Y축이 반전되어 스코어 점 위쪽에 표시됨)
    textposition="top center",
    textfont=dict(size=10, color='red')
))

# 2. 추세선 (점선)
trend_y_values = slope * player_df['Seq_Num'] + intercept
fig.add_trace(go.Scatter(x=player_df['Round_Label'], y=trend_y_values,
                         mode='lines', name='추세선',
                         line=dict(color='green', dash='dot', width=2)))


# 그래프 레이아웃 설정
fig.update_layout(
    title_text=f'📈 {selected_player}님의 라운드별 스코어 분석',
    title_font_size=20,
    xaxis_title='스크린 대회',
    yaxis_title='스코어 (타) - 낮을수록 상단',
    legend_title="",
    # Y축 반전: 골프는 낮은 점수가 위로 가야 함
    yaxis=dict(
        autorange="reversed",
        range=[max_score + 5, min_score - 5]
    ),
    template="plotly_white",
    hovermode="x unified",
    height=500
)

# Streamlit에 그래프 렌더링
st.plotly_chart(fig, use_container_width=True)

# 실행명령 터머널에서 streamlit run app.py

