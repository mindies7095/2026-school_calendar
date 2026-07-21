import streamlit as st
import pandas as pd
import calendar
from datetime import datetime
import os

st.set_page_config(page_title="월간 학사일정 캘린더", layout="wide")

# --- 1. 데이터 로드 ---
@st.cache_data
def load_data(file_path):
    if file_path.endswith('.csv'):
        try:
            df = pd.read_csv(file_path, encoding='cp949')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='utf-8')
    else:
        df = pd.read_excel(file_path)
        
    df = df.dropna(subset=['학교'])
    df = df[df['학교'].str.contains('중|고', na=False)]
    
    # 💡 [요구사항 3] 학교와 학년을 하나의 컬럼으로 합치기 (예: 충북여고 1학년)
    df['학교_학년'] = df['학교'].astype(str) + ' ' + df['학년'].astype(str)
    
    id_vars = ['학교', '학년', '학교_학년']
    value_vars = [col for col in df.columns if col not in id_vars]
    
    df_melt = pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name='일정명', value_name='날짜문자열')
    df_melt = df_melt.dropna(subset=['날짜문자열'])
    df_melt['날짜문자열'] = df_melt['날짜문자열'].astype(str).str.strip()
    df_melt = df_melt[~df_melt['날짜문자열'].str.lower().isin(['x', '', 'nan'])]
    return df_melt

# --- 2. 날짜 파싱 ---
def parse_dates(date_str, year=2026):
    date_str = str(date_str).replace(' ', '').replace('.', '/')
    try:
        if '~' in date_str:
            start_str, end_str = date_str.split('~')
            s_parts = start_str.replace('-', '/').split('/')
            s_month, s_day = int(s_parts[0]), int(s_parts[1])
            start_date = datetime(year, s_month, s_day)
            
            if not end_str:
                end_date = datetime(year, 12, 31)
            else:
                e_parts = end_str.replace('-', '/').split('/')
                if len(e_parts) == 1:
                    end_date = datetime(year, s_month, int(e_parts[0]))
                else:
                    end_date = datetime(year, int(e_parts[0]), int(e_parts[1]))
            return start_date, end_date
        else:
            parts = date_str.replace('-', '/').split('/')
            start_date = datetime(year, int(parts[0]), int(parts[1]))
            return start_date, start_date
    except Exception:
        return pd.NaT, pd.NaT

# --- 3. HTML 달력 생성 ---
def generate_calendar_html(df, year, month):
    calendar.setfirstweekday(calendar.SUNDAY)
    cal = calendar.monthcalendar(year, month)
    
    html = f'<table class="calendar-table">'
    html += '<tr><th class="sun">SUN</th><th>MON</th><th>TUE</th><th>WED</th><th>THU</th><th>FRI</th><th class="sat">SAT</th></tr>'
    
    for week in cal:
        html += '<tr>'
        for i, day in enumerate(week):
            if day == 0:
                html += '<td class="empty-cell"></td>'
            else:
                current_date = pd.Timestamp(year, month, day)
                td_class = "day-cell"
                if i == 0: td_class += " sun"
                if i == 6: td_class += " sat"
                
                html += f'<td class="{td_class}"><div class="day-num">{day}</div>'
                
                day_events = df[(df['Start'] <= current_date) & (df['End'] >= current_date)]
                for _, row in day_events.iterrows():
                    raw_name = str(row['일정명'])
                    # 💡 [요구사항 2] 캘린더에 표시할 때 어떤 학교/학년인지 알 수 있게 텍스트 가공
                    short_sg = str(row['학교_학년']).replace('학년', '') # 공간 절약을 위해 '학년' 글자 제거 (예: 충북여고 1)
                    evt_name = f"[{short_sg}] {raw_name}"
                    
                    if "모" in raw_name:
                        color = "#cce5ff"  
                    elif "중간" in raw_name or "기말" in raw_name:
                        color = "#ffcccc"  
                    elif "방학" in raw_name:
                        color = "#ccffcc"  
                    else:
                        color = "#ffffcc"  
                    
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

# --- 4. 메인 화면 ---
st.title("📅 월간 학사일정 비교 캘린더 시스템")

current_dir = os.path.dirname(os.path.abspath(__file__))
file_name = os.path.join(current_dir, '2026 학사일정.csv')

try:
    df_raw = load_data(file_name)
    df_raw[['Start', 'End']] = df_raw.apply(lambda row: pd.Series(parse_dates(row['날짜문자열'])), axis=1)
    df_valid = df_raw.dropna(subset=['Start', 'End'])
    
    st.markdown("### 🔍 학교 및 기간 설정")
    
    school_grade_list = df_valid['학교_학년'].unique()
    
    # 💡 UI 배치: 넓은 칸엔 학교 필터, 좁은 칸엔 날짜 필터 배치
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
        with col2_1:
            selected_year = st.selectbox("연도", [2026, 2027])
        with col2_2:
            selected_month = st.selectbox("시작 월", list(range(1, 13)), index=3) 
            
    filtered_df = df_valid[df_valid['학교_학년'].isin(selected_sgs)]
    
    st.markdown("---")
    
    if not filtered_df.empty:
        # 💡 [요구사항 1] 2개월치 달력의 연/월 계산
        m1_year = selected_year
        m1_month = selected_month
        
        # 선택한 월이 12월이면 다음 달력은 다음 해 1월로 넘기기
        if m1_month == 12:
            m2_year = m1_year + 1
            m2_month = 1
        else:
            m2_year = m1_year
            m2_month = m1_month + 1
            
        # --- 첫 번째 달력 출력 ---
        st.markdown(f"<h2><span style='font-size: 35px; margin-right: 15px;'>{m1_month}</span> <span style='font-size:20px; font-weight:normal;'>{m1_year}<br>{calendar.month_name[m1_month]}</span></h2>", unsafe_allow_html=True)
        cal1_html = generate_calendar_html(filtered_df, m1_year, m1_month)
        st.components.v1.html(cal1_html, height=750, scrolling=True)
        
        # --- 두 번째 달력 출력 ---
        st.markdown(f"<h2><span style='font-size: 35px; margin-right: 15px;'>{m2_month}</span> <span style='font-size:20px; font-weight:normal;'>{m2_year}<br>{calendar.month_name[m2_month]}</span></h2>", unsafe_allow_html=True)
        cal2_html = generate_calendar_html(filtered_df, m2_year, m2_month)
        st.components.v1.html(cal2_html, height=750, scrolling=True)
        
        # 상세 데이터 표
        with st.expander("📝 표 형태로 선택된 전체 일정 비교하기"):
            st.dataframe(filtered_df[['학교_학년', '일정명', '날짜문자열', 'Start', 'End']].sort_values('Start'), hide_index=True, use_container_width=True)
    else:
        st.warning("선택하신 조건에 해당하는 일정이 없습니다.")
        
except FileNotFoundError:
    st.error(f"⚠️ 깃허브 저장소에 '{file_name}' 파일이 없습니다. 위치나 이름을 확인해 주세요!")
except Exception as e:
    st.error(f"⚠️ 데이터 처리 중 오류가 발생했습니다: {e}")
