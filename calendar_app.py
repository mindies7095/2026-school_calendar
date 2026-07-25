import streamlit as st
import pandas as pd
import calendar
from datetime import datetime
import os
import glob

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
    
    df['학교_학년'] = df['학교'].astype(str) + ' ' + df['학년'].astype(str)
    
    id_vars = ['학교', '학년', '학교_학년']
    value_vars = [col for col in df.columns if col not in id_vars]
    
    df_melt = pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name='일정명', value_name='날짜문자열')
    df_melt = df_melt.dropna(subset=['날짜문자열'])
    df_melt['날짜문자열'] = df_melt['날짜문자열'].astype(str).str.strip()
    df_melt = df_melt[~df_melt['날짜문자열'].str.lower().isin(['x', '', 'nan'])]
    return df_melt

# --- 2. 날짜 파싱 (💡 연도가 포함된 날짜도 완벽하게 읽어내는 만능 번역기) ---
def parse_dates(date_str, base_year=2026):
    date_str = str(date_str).replace(' ', '').replace('.', '/').replace('-', '/')
    try:
        if '~' in date_str:
            start_str, end_str = date_str.split('~', 1)
        else:
            start_str, end_str = date_str, date_str
            
        def get_ymd(d_str, default_year):
            if not d_str:
                return None
            parts = [p for p in d_str.split('/') if p]
            if len(parts) >= 3: # '2027.1.9' 처럼 연도가 포함된 경우
                y = int(parts[0])
                if y < 100: y += 2000
                m = int(parts[1])
                d = int(parts[2])
            elif len(parts) == 2: # '1.9' 처럼 월/일만 있는 경우
                m = int(parts[0])
                d = int(parts[1])
                # 1, 2월은 다음 해로 간주
                y = default_year + 1 if m in [1, 2] else default_year
            elif len(parts) == 1: # '~25' 처럼 일자만 있는 경우
                m = -1
                d = int(parts[0])
                y = -1
            else:
                return None
            return y, m, d

        # 시작일 계산
        start_ymd = get_ymd(start_str, base_year)
        if not start_ymd:
            return pd.NaT, pd.NaT
        
        s_y, s_m, s_d = start_ymd
        if s_m == -1: return pd.NaT, pd.NaT
        start_date = datetime(s_y, s_m, s_d)
        
        # 종료일 계산
        if not end_str:
            end_date = start_date
        else:
            end_ymd = get_ymd(end_str, base_year)
            if not end_ymd:
                end_date = start_date
            else:
                e_y, e_m, e_d = end_ymd
                if e_m == -1: 
                    e_m = s_m
                    e_y = s_y
                if e_y == s_y and e_m < s_m:
                    e_y += 1
                end_date = datetime(e_y, e_m, e_d)
                
        # 오류 방어 (종료일이 시작일보다 앞서면 같게 맞춤)
        if end_date < start_date:
            end_date = start_date
            
        return start_date, end_date
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
                    short_sg = str(row['학교_학년']).replace('학년', '')
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
csv_files = glob.glob(os.path.join(current_dir, "*.csv"))

if not csv_files:
    st.error("⚠️ 깃허브 저장소에 CSV 파일이 하나도 없습니다! 파일을 업로드해 주세요.")
else:
    file_name = csv_files[0]
    
    try:
        df_raw = load_data(file_name)
        df_raw[['Start', 'End']] = df_raw.apply(lambda row: pd.Series(parse_dates(row['날짜문자열'])), axis=1)
        df_valid = df_raw.dropna(subset=['Start', 'End'])
        
        st.markdown("### 🔍 학교 및 기간 설정")
        
        school_grade_list = df_valid['학교_학년'].unique()
        
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
            m1_year = selected_year
            m1_month = selected_month
            
            if m1_month == 12:
                m2_year = m1_year + 1
                m2_month = 1
            else:
                m2_year = m1_year
                m2_month = m1_month + 1
                
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
            
    except Exception as e:
        st.error(f"⚠️ 데이터 처리 중 오류가 발생했습니다: {e}")
