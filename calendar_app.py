import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import datetime

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="학사일정 캘린더", page_icon="🗓️", layout="wide")

# ==========================================
# 2. 구글 시트 연결 (비밀 열쇠 사용)
# ==========================================
@st.cache_resource
def init_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(st.secrets["GOOGLE_KEY"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    doc = client.open_by_url(st.secrets["SHEET_URL"])
    return doc

try:
    doc = init_connection()
    sheet_calendar = doc.worksheet("학사일정")
    sheet_users = doc.worksheet("사용자관리")
except Exception as e:
    st.error(f"구글 시트 연결 오류: {e}")
    st.stop()

# ==========================================
# 3. 데이터 불러오기 함수
# ==========================================
def load_calendar_data():
    data = sheet_calendar.get_all_records()
    return pd.DataFrame(data)

def load_user_data():
    data = sheet_users.get_all_records()
    return pd.DataFrame(data)

# ==========================================
# 4. 로그인 및 권한 관리 (사이드바)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['role'] = None
    st.session_state['username'] = None

with st.sidebar:
    if not st.session_state['logged_in']:
        st.subheader("🔐 로그인")
        login_id = st.text_input("아이디")
        login_pw = st.text_input("비밀번호", type="password")
        if st.button("로그인"):
            users_df = load_user_data()
            # 아이디와 비밀번호가 일치하는 행 찾기
            match = users_df[(users_df['아이디'] == login_id) & (users_df['비밀번호'] == login_pw)]
            
            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['role'] = match.iloc[0]['권한']
                st.session_state['username'] = login_id
                st.success(f"로그인 성공! ({st.session_state['role']})")
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 틀렸습니다.")
    else:
        st.subheader("🔐 로그인 정보")
        st.info(f"현재 접속 권한: **{st.session_state['role']}**")
        if st.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.session_state['role'] = None
            st.session_state['username'] = None
            st.rerun()

# ==========================================
# 5. 메인 화면 및 탭 구성
# ==========================================
st.title("🗓️ 월간 학사일정 비교 캘린더 시스템")

# 권한에 따른 탭 노출
if st.session_state['role'] == '총괄관리자':
    tabs = st.tabs(["🗓️ 캘린더 보기", "📝 학사일정 수정", "⚙️ 사용자 권한 관리"])
elif st.session_state['role'] == '일반편집자':
    tabs = st.tabs(["🗓️ 캘린더 보기", "📝 학사일정 수정"])
else:
    tabs = st.tabs(["🗓️ 캘린더 보기"])

# ------------------------------------------
# [탭 1] 캘린더 보기 (일반 방문자 포함 모두 접근 가능)
# ------------------------------------------
with tabs[0]:
    st.subheader("🔍 학교 및 기간 설정")
    
    # 데이터 불러오기
    cal_df = load_calendar_data()
    
    # 학교/학년 목록 생성 (예: "충북여고 1학년")
    if not cal_df.empty:
        school_options = (cal_df['학교'].astype(str) + " " + cal_df['학년'].astype(str)).unique().tolist()
    else:
        school_options = []

    # 연도 선택 메뉴를 삭제하고 화면을 2칸으로 조정 (비율 3:1)
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_schools = st.multiselect("비교할 학교/학년을 선택하세요 (최대 5개)", school_options, max_selections=5)
    with col2:
        # 오늘 날짜를 기준으로 현재 연도 자동 인식
        current_year = datetime.date.today().year
        selected_month = st.selectbox("시작 월", list(range(1, 13)), index=datetime.date.today().month - 1)
        
    st.write("---")
    st.header(f"{selected_month}  {current_year}")
    st.caption(datetime.date(current_year, selected_month, 1).strftime("%B"))
    
    # (이곳에 기존에 작성해두셨던 실제 달력 화면을 그리는 세부 코드가 있다면 유지해 주시면 됩니다.)
    st.info("선택한 학교의 일정이 캘린더에 표시됩니다.")
    st.dataframe(cal_df, use_container_width=True) # 임시 데이터 확인용

# ------------------------------------------
# [탭 2] 학사일정 수정 (일반편집자, 총괄관리자 전용)
# ------------------------------------------
if st.session_state['role'] in ['총괄관리자', '일반편집자']:
    with tabs[1]:
        st.write("표 안의 데이터를 더블클릭하여 바로 수정하거나, 맨 아래 빈칸에 새 일정을 추가하세요.")
        cal_df = load_calendar_data()
        
        # 데이터 에디터 (웹에서 직접 엑셀처럼 수정)
        edited_cal_df = st.data_editor(cal_df, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 일정 저장 및 캘린더에 적용하기"):
            # 구글 시트 덮어쓰기 로직
            sheet_calendar.clear()
            sheet_calendar.update([edited_cal_df.columns.values.tolist()] + edited_cal_df.values.tolist())
            st.success("학사일정이 구글 시트에 성공적으로 저장되었습니다! 캘린더 탭을 확인해 보세요.")

# ------------------------------------------
# [탭 3] 사용자 권한 관리 (총괄관리자 전용)
# ------------------------------------------
if st.session_state['role'] == '총괄관리자':
    with tabs[2]:
        st.write("새로운 사용자를 추가하거나 권한(총괄관리자, 일반편집자)을 수정할 수 있습니다.")
        users_df = load_user_data()
        
        edited_users_df = st.data_editor(users_df, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 사용자 정보 영구 저장하기"):
            sheet_users.clear()
            sheet_users.update([edited_users_df.columns.values.tolist()] + edited_users_df.values.tolist())
            st.success("사용자 권한 정보가 성공적으로 업데이트되었습니다.")
