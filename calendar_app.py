import streamlit as st
import pandas as pd
import calendar
from datetime import datetime
import os

st.set_page_config(page_title="월간 학사일정 캘린더", layout="wide")

# --- 1. 데이터 로드 (업로드 대신 파일명으로 직접 읽기) ---
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
    
    id_vars = ['학교', '학년']
    value_vars = [col for col in df.columns if col not in id_vars]
    
    df_melt = pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name='일정명', value_name='날짜문자열')
    df_melt = df_melt.dropna(subset=['날짜문자열'])
    df_melt['날짜문자열'] = df_melt['날짜문자열'].astype(str).str.strip()
    df_melt = df_melt[~df_melt['날짜문자열'].str.lower().isin(['x', '', 'nan'])]
    return df_melt

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
                    evt_name = f"-{raw_name}"
                    
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
    .day-num { font-size: 20px; padding: 5px 8px; margin-bottom: 10px;}
    .sun .day-num, th.sun { color: red; }
    .sat .day-num, th.sat { color: blue; }
    .event-bar { font-size: 13px; padding: 4px 6px; margin: 2px 0; font-weight: 500; color: #000; word-break: break-all; line-height: 1.2;}
    </style>
    """
    return css + html

st.title("📅 월간 학사일정 캘린더 시스템")

# 💡 파일 업로드 버튼 제거, 깃허브에 있는 파일 이름 직접 지정
file_name = '2026 학사일정.csv'

try:
    # 지정한 파일명으로 바로 데이터 로드
    df_raw = load_data(file_name)
    df_raw[['Start', 'End']] = df_raw.apply(lambda row: pd.Series(parse_dates(row['날짜문자열'])), axis=1)
    df_valid = df_raw.dropna(subset=['Start', 'End'])
    
    st.markdown("### 🔍 필터 설정")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        school_list = df_valid['학교'].unique()
        selected_school = st.selectbox("학교 선택", school_list)
    with col2:
        grade_list = df_valid[df_valid['학교'] == selected_school]['학년'].unique()
        selected_grade = st.selectbox("학년 선택", grade_list)
    with col3:
        selected_year = st.selectbox("연도 선택", [2026, 2027])
    with col4:
        selected_month = st.selectbox("월 선택", list(range(1, 13)), index=3) 
        
    filtered_df = df_valid[(df_valid['학교'] == selected_school) & (df_valid['학년'] == selected_grade)]
    
    st.markdown("---")
    
    st.markdown(f"<h2><span style='font-size: 40px; margin-right: 15px;'>{selected_month}</span> <span style='font-size:20px; font-weight:normal;'>{selected_year}<br>{calendar.month_name[selected_month]}</span></h2>", unsafe_allow_html=True)
    
    if not filtered_df.empty:
        calendar_html = generate_calendar_html(filtered_df, selected_year, selected_month)
        st.components.v1.html(calendar_html, height=1100, scrolling=True)
        
        with st.expander("📝 표 형태로 전체 일정 보기"):
            st.dataframe(filtered_df[['일정명', '날짜문자열', 'Start', 'End']].sort_values('Start'), hide_index=True, use_container_width=True)
    else:
        st.warning("선택하신 조건에 해당하는 일정이 없습니다.")
        
except FileNotFoundError:
    st.error(f"⚠️ 깃허브 저장소에 '{file_name}' 파일이 없습니다. 파일 이름이 정확한지 확인해 주세요!")
except Exception as e:
    st.error(f"⚠️ 데이터 처리 중 오류가 발생했습니다: {e}")
