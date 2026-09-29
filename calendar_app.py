import streamlit as st
import pandas as pd
import calendar
from datetime import datetime
import os
import json
import gspread

st.set_page_config(page_title="월간 학사일정 캘린더", layout="wide")

# --- 1. 구글 시트 연결 기본 설정 ---
@st.cache_resource
def get_gsheets_client():
    creds_dict = json.loads(st.secrets["GOOGLE_KEY"])
    gc = gspread.service_account_from_dict(creds_dict)
    return gc

@st.cache_data(ttl=10)
def load_sheet_data(sheet_name):
    gc = get_gsheets_client()
    sh = gc.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sh.worksheet(sheet_name)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df

def save_sheet_data(sheet_name, df):
    gc = get_gsheets_client()
    sh = gc.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear()
    df_to_save = df.fillna('')
    worksheet.update([df_to_save.columns.values.tolist()] + df_to_save.values.tolist())
    st.cache_data.clear()

# --- 2. 데이터 처리 함수 ---
def process_data(df):
    df_proc = df.copy()
    df_proc['학교'] = df_proc['학교'].replace('', pd.NA)
    df_proc = df_proc.dropna(subset=['학교'])
    df_proc = df_proc[df_proc['학교'].astype(str).str.contains('중|고', na=False)]
    
    df_proc['학교_학년'] = df_proc['학교'].astype(str) + ' ' + df_proc['학년'].astype(str)
    
    id_vars = ['학교', '학년', '학교_학년']
    value_vars = [col for col in df_proc.columns if col not in id_vars]
    
    df_melt = pd.melt(df_proc, id_vars=id_vars, value_vars=value_vars, var_name='일정명', value_name='날짜문자열')
    df_melt['날짜문자열'] = df_melt['날짜문자열'].replace('', pd.NA)
    df_melt = df_melt.dropna(subset=['날짜문자열'])
    df_melt['날짜문자열'] = df_melt['날짜문자열'].astype(str).str.strip()
    df_melt = df_melt[~df_melt['날짜문자열'].str.lower().isin(['x', '', 'nan'])]
    return df_melt

# --- 3. 날짜 파싱 ---
def parse_dates(date_str, base_year=None):
    if base_year is None:
        base_year = datetime.now().year
        
    date_str = str(date_str).replace(' ', '').replace('.', '/').replace('-', '/')
    try:
        if '~' in date_str:
            start_str, end_str = date_str.split('~', 1)
        else:
            start_str, end_str = date_str, date_str
            
        def get_ymd(d_str, default_year):
            if not d_str: return None
            parts = [p for p in d_str.split('/') if p]
            if len(parts) >= 3:
                y = int(parts[0])
                if y < 100: y += 2000
                return y, int(parts[1]), int(parts[2])
            elif len(parts) == 2:
                m = int(parts[0])
                y = default_year + 1 if m in [1, 2] else default_year
                return y, m, int(parts[1])
            elif len(parts) == 1:
                return -1, -1, int(parts[0])
            return None

        start_ymd = get_ymd(start_str, base_year)
        if not start_ymd: return pd.NaT, pd.NaT
        
        s_y, s_m, s_d = start_ymd
        if s_m == -1: return pd.NaT, pd.NaT
        start_date = datetime(s_y, s_m, s_d)
        
        if not end_str:
            end_date = start_date
        else:
            end_ymd = get_ymd(end_str, base_year)
            if not end_ymd: end_date = start_date
            else:
                e_y, e_m, e_d = end_ymd
                if e_m == -1: e_m, e_y = s_m, s_y
                if e_y == s_y and e_m < s_m: e_y += 1
                end_date = datetime(e_y, e_m, e_d)
                
        if end_date < start_date: end_date = start_date
        return start_date, end_date
    except Exception:
        return pd.NaT, pd.NaT

# --- 4. HTML 달력 생성 ---
def generate_calendar_html(df, year, month):
    calendar.setfirstweekday(calendar.SUNDAY)
    cal = calendar.monthcalendar(year, month)
    
    html = f'<table class="calendar-table">'
    html += '<tr><th class="sun">SUN</th><th>MON</th><th>TUE</th><th>WED</th><th>THU</th><th>FRI</th><th class="sat">SAT</th></tr>'
    
    for week in cal:
        html += '<tr>'
        for i, day in enumerate(week):
            if day == 0: html += '<td class="empty-cell"></td>'
            else:
                current_date = pd.Timestamp(year, month, day)
                td_class = "day-cell sun" if i == 0 else "day-cell sat" if i == 6 else "day-cell"
                html += f'<td class="{td_class}"><div class="day-num">{day}</div>'
                
                day_events = df[(df['Start'] <= current_date) & (df['End'] >= current_date)]
                for _, row in day_events.iterrows():
                    raw_name = str(row['일정명'])
                    short_sg = str(row['학교_학년']).replace('학년', '')
                    evt_name = f"[{short_sg}] {raw_name}"
                    
                    if "모" in raw_name: color = "#cce5ff"  
                    elif "중간" in raw_name or "기말" in raw_name: color = "#ffcccc"  
                    elif "방학" in raw_name: color = "#ccffcc"  
                    else: color = "#ffffcc"  
                    html += f'<div class="event-bar" style="background-color: {color};">{evt_name}</div>'
                html += '</td>'
        html += '</tr>'
    html += '</table>'
    
    css = """
    <style>
    .calendar-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; }
    .calendar-table th { border-bottom: 2px solid #000; padding: 10px 0; text-align: left; font-size: 16px; padding-left: 10px;}
    .calendar-table td { border-bottom: 1px solid #ccc; border-right: 1px dotted #ccc; height: 160px; vertical-align: top; padding: 2px; }
    .calendar-table td:last-child { border-right: none; }
    .empty-cell { background-color: #fcfcfc; }
    .day-num { font-size: 20px; padding: 5px 8px; margin-bottom: 5px;}
    .sun .day-num, th.sun { color: red; }
    .sat .day-num, th.sat { color: blue; }
    .event-bar { font-size: 12px; padding: 4px 6px; margin: 2px 0; font-weight: 500; color: #000; word-break: break-all; line-height: 1.2; border-radius: 4px;}
    </style>
    """
    return css + html


# ==========================================
# 5. 메인 시스템 (로그인 및 탭 구성)
# ==========================================

# 5-1. 로그인 시스템 (사이드바)
st.sidebar.title("🔐 로그인")
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None

if st.session_state["user_role"] is None:
    login_id = st.sidebar.text_input("아이디")
    login_pw = st.sidebar.text_input("비밀번호", type="password")
    if st.sidebar.button("로그인"):
        try:
            users_df = load_sheet_data("사용자관리")
            user_match = users_df[(users_df['아이디'].astype(str) == str(login_id)) & (users_df['비밀번호'].astype(str) == str(login_pw))]
            
            if not user_match.empty:
                role = user_match.iloc[0]['권한']
                st.session_state["user_role"] = role
                st.sidebar.success(f"로그인 성공! ({role})")
                st.rerun()
            else:
                st.sidebar.error("⚠️ 아이디나 비밀번호가 틀렸습니다.")
        except Exception as e:
            st.sidebar.error("⚠️ 사용자 정보를 불러오는 중 오류가 발생했습니다. 구글 시트를 확인해주세요.")
else:
    st.sidebar.info(f"현재 접속 권한: **{st.session_state['user_role']}**")
    if st.sidebar.button("로그아웃"):
        st.session_state["user_role"] = None
        st.rerun()

# 5-2. 메인 화면 탭 구성
st.title("📅 월간 학사일정 비교 캘린더 시스템")

try:
    # 권한별 탭 이름 설정
    tab_names = ["📅 캘린더 보기"]
    if st.session_state["user_role"] in ["일반편집자", "총괄관리자"]:
        tab_names.append("📝 학사일정 수정")
    if st.session_state["user_role"] == "총괄관리자":
        tab_names.append("⚙️ 사용자 권한 관리")
        
    tabs = st.tabs(tab_names)
    
    # ----------------------------------------
    # [탭 1] 캘린더 보기
    # ----------------------------------------
    with tabs[0]:
        df_raw_wide = load_sheet_data("학사일정")
        df_raw = process_data(df_raw_wide)
        
        st.markdown("### 🔍 학교 및 기간 설정")
        school_grade_list = df_raw['학교_학년'].unique()
        
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_sgs = st.multiselect(
                "🏫 비교할 학교/학년을 선택하세요 (최대 5개)", 
                options=school_grade_list,
                default=[school_grade_list[0]] if len(school_grade_list) > 0 else None,
                max_selections=5
            )
        with col2:
            col2_1, col2_2 = st.columns(2)
            
            # 원본 코드 디테일 반영: 현재 연도 및 월 자동 계산
            today = datetime.now()
            current_year = today.year
            current_month = today.month
            
            with col2_1:
                # [작년, 올해, 내년, 내후년] 목록 생성 후 '올해(인덱스 1)'를 기본값으로 지정
                year_options = [current_year - 1, current_year, current_year + 1, current_year + 2]
                selected_year = st.selectbox("연도", year_options, index=1)
            with col2_2:
                # 현재 월을 기본 선택
                selected_month = st.selectbox("시작 월", list(range(1, 13)), index=current_month - 1)
                
        st.markdown("---")
        
        # 원본 코드 디테일 반영: 선택된 학교/학년 데이터만 필터링한 후 날짜 파싱 수행 (속도 최적화)
        if selected_sgs:
            filtered_raw = df_raw[df_raw['학교_학년'].isin(selected_sgs)].copy()
            filtered_raw[['Start', 'End']] = filtered_raw.apply(
                lambda row: pd.Series(parse_dates(row['날짜문자열'], base_year=selected_year)), axis=1
            )
            filtered_df = filtered_raw.dropna(subset=['Start', 'End'])
        else:
            filtered_df = pd.DataFrame()
        
        if not filtered_df.empty:
            m1_year, m1_month = selected_year, selected_month
            m2_year = m1_year + 1 if m1_month == 12 else m1_year
            m2_month = 1 if m1_month == 12 else m1_month + 1
                
            st.markdown(f"<h2><span style='font-size: 35px; margin-right: 15px;'>{m1_month}</span> <span style='font-size:20px; font-weight:normal;'>{m1_year}<br>{calendar.month_name[m1_month]}</span></h2>", unsafe_allow_html=True)
            cal1_html = generate_calendar_html(filtered_df, m1_year, m1_month)
            st.components.v1.html(cal1_html, height=750, scrolling=True)
            
            st.markdown(f"<h2><span style='font-size: 35px; margin-right: 15px;'>{m2_month}</span> <span style='font-size:20px; font-weight:normal;'>{m2_year}<br>{calendar.month_name[m2_month]}</span></h2>", unsafe_allow_html=True)
            cal2_html = generate_calendar_html(filtered_df, m2_year, m2_month)
            st.components.v1.html(cal2_html, height=750, scrolling=True)
            
            with st.expander("📝 표 형태로 선택된 전체 일정 비교하기"):
                st.dataframe(filtered_df[['학교_학년', '일정명', '날짜문자열', 'Start', 'End']].sort_values('Start'), hide_index=True, use_container_width=True)
        else:
            st.warning("선택하신 조건에 해당하는 일정이 없습니다.")

    # ----------------------------------------
    # [탭 2] 학사일정 수정 
    # ----------------------------------------
    if len(tabs) > 1:
        with tabs[1]:
            st.markdown("### 📝 학사일정 데이터 즉각 수정")
            st.info("💡 표 안의 빈칸을 더블클릭하여 데이터를 수정하거나, 맨 아래로 스크롤을 내려 새 행을 추가할 수 있습니다.")
            
            df_schedule = load_sheet_data("학사일정")
            edited_schedule = st.data_editor(df_schedule, num_rows="dynamic", use_container_width=True, height=500)
            
            if st.button("💾 일정 저장 및 캘린더에 적용하기", type="primary"):
                with st.spinner('구글 시트에 저장 중...'):
                    save_sheet_data("학사일정", edited_schedule)
                    st.success("✅ 학사일정이 구글 시트에 안전하게 영구 저장되었습니다!")
                    st.rerun()

    # ----------------------------------------
    # [탭 3] 사용자 관리 
    # ----------------------------------------
    if len(tabs) > 2:
        with tabs[2]:
            st.markdown("### ⚙️ 사용자 계정 및 권한 관리")
            st.info("💡 행을 추가하여 새로운 사람에게 권한을 주거나, 기존 사용자의 비밀번호/권한을 변경할 수 있습니다. (권한 입력 시 '일반편집자' 또는 '총괄관리자' 라고 정확히 띄어쓰기 없이 적어주세요.)")
            
            df_users = load_sheet_data("사용자관리")
            edited_users = st.data_editor(df_users, num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 사용자 정보 영구 저장하기", type="primary"):
                with st.spinner('구글 시트에 저장 중...'):
                    save_sheet_data("사용자관리", edited_users)
                    st.success("✅ 사용자 정보가 업데이트되었습니다!")
                    st.rerun()

except Exception as e:
    st.error("⚠️ 서버와 구글 시트를 연결하는 중 오류가 발생했습니다. Streamlit Settings의 Secrets 정보가 정확한지 다시 한번 확인해 주세요.")
    st.code(e)
