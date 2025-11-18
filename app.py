import os
import streamlit as st
import pandas as pd
from data_loader import load_courses, get_all_time_slots
from filter import filter_courses
from scheduler import generate_schedules, recommend_schedule, calculate_schedule_score
import plotly.graph_objects as go
from datetime import datetime
from gemini_helper import analyze_preferences

selected_grade = None


def extract_manual_preferences(description: str):
    """간단한 키워드로 사용자 설명을 해석하는 보조 함수."""
    if not description:
        return {}
    text = description.lower()
    preferences = {
        'preferred_categories': [],
        'preferred_keywords': [],
        'excluded_keywords': []
    }

    def add_unique(target_list, value):
        if value not in target_list:
            target_list.append(value)

    if 'ai' in text or '인공지능' in text:
        add_unique(preferences['preferred_keywords'], 'AI')
        add_unique(preferences['preferred_categories'], '전선')

    if '데이터' in text or 'data' in text:
        add_unique(preferences['preferred_keywords'], '데이터')

    if '머신러닝' in text or 'machine learning' in text:
        add_unique(preferences['preferred_keywords'], '머신러닝')

    if '딥러닝' in text or 'deep learning' in text:
        add_unique(preferences['preferred_keywords'], '딥러닝')

    if '싫' in text or '빼' in text or '제외' in text:
        # 간단한 예시: '독일어'가 들어 있으면 제외
        if '독일어' in text:
            add_unique(preferences['excluded_keywords'], '독일어')

    # 빈 값 제거
    for key, value in list(preferences.items()):
        if not value:
            preferences.pop(key)

    return preferences

selected_grade = None

# 페이지 설정
st.set_page_config(
    page_title="AI 시간표 생성기",
    page_icon="📅",
    layout="wide"
)

# 제목
st.title("📅 AI 시간표 생성기")
st.markdown("원하는 조건을 입력하면 최적의 시간표를 추천해드립니다!")

# 데이터 로딩
@st.cache_data
def load_data():
    return load_courses('강좌검색.csv')

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

try:
    df = load_data()
    st.sidebar.success(f"✅ {len(df)}개의 과목 데이터를 불러왔습니다.")
except Exception as e:
    st.error(f"데이터 로딩 오류: {e}")
    st.stop()

# 사이드바 - 입력 폼
st.sidebar.header("📝 수강 조건 입력")

# 졸업요건 선택
graduation_options = ['전선', '전필', '교양', '교직', '논문', '공통']
selected_graduation = st.sidebar.multiselect(
    "과목 종류",
    graduation_options,
    default=['전선', '교양']
)

# 학년 선택
grade_options = ['1학년', '2학년', '3학년', '4학년']
selected_grade_option = st.sidebar.selectbox(
    "학년",
    ['전체'] + grade_options
)
selected_grade = None if selected_grade_option == '전체' else selected_grade_option

# 수강 최대 학점
max_credits = st.sidebar.selectbox(
    "수강 최대 학점",
    [6,9],
    index=1
)

# 희망 공강 요일
free_day_options = ['월', '화', '수', '목', '금']
preferred_free_day = st.sidebar.selectbox(
    "희망 공강 요일",
    ['없음'] + free_day_options
)
preferred_free_day = None if preferred_free_day == '없음' else preferred_free_day

# 연강/공강 시간 선호
prefer_consecutive = st.sidebar.checkbox("연강 선호")

# 원하는 교수님
professor_input = st.sidebar.text_area(
    "원하는 교수님 (쉼표로 구분, 선택사항)",
    placeholder="예: 김남준, 이정원"
)
preferred_professor = [p.strip() for p in professor_input.split(',') if p.strip()] if professor_input else None

# AI 선호 조건 입력
st.sidebar.subheader("🤖 AI에게 설명하기")
ai_preference_text = st.sidebar.text_area(
    "어떤 수업을 듣고 싶은지 자유롭게 적어보세요",
    placeholder="예: AI 관련 전선 위주로 듣고 싶고, 목요일은 공강이면 좋겠어요.",
    help="구글 Gemini가 내용을 분석해 필터 조건에 반영합니다."
)
if ai_preference_text and not GEMINI_API_KEY:
    st.sidebar.warning("Gemini API 키가 설정되어 있지 않아 AI 분석을 건너뜁니다.")

# 아침/오후 수업 선호
time_preference = st.sidebar.radio(
    "수업 시간 선호",
    ['무관', '아침 수업', '오후 수업']
)
prefer_morning = None
if time_preference == '아침 수업':
    prefer_morning = True
elif time_preference == '오후 수업':
    prefer_morning = False

# 시간표 생성 버튼
if st.sidebar.button("🚀 시간표 생성", type="primary"):
    ai_preferences = {}
    subject_keywords = None
    excluded_keywords = None

    manual_preferences = extract_manual_preferences(ai_preference_text) if ai_preference_text else {}

    def merge_lists(base, additional):
        base = base or []
        additional = additional or []
        result = list(base)
        for item in additional:
            if item not in result:
                result.append(item)
        return result

    if ai_preference_text and GEMINI_API_KEY:
        with st.spinner("AI가 선호 조건을 분석하는 중입니다..."):
            try:
                ai_preferences = analyze_preferences(ai_preference_text, GEMINI_API_KEY)
                st.session_state['ai_preferences'] = ai_preferences
                st.sidebar.success("AI 조건 분석 완료!")
            except Exception as e:
                st.sidebar.warning(f"AI 조건 분석 실패: {e}")
                ai_preferences = {}
    elif ai_preference_text:
        st.sidebar.warning("Gemini API 키가 없어 AI 분석을 건너뜁니다.")

    # AI 결과와 수동 추론을 병합
    if manual_preferences:
        if not ai_preferences:
            ai_preferences = manual_preferences
        else:
            for key, value in manual_preferences.items():
                if isinstance(value, list):
                    ai_preferences[key] = merge_lists(ai_preferences.get(key), value)
                elif key not in ai_preferences or ai_preferences[key] in (None, '', []):
                    ai_preferences[key] = value

    if ai_preferences:
        categories = ai_preferences.get('preferred_categories') or []
        if categories:
            base_categories = selected_graduation or []
            selected_graduation = merge_lists(base_categories, categories)

        keyword_list = ai_preferences.get('preferred_keywords') or []
        subject_keywords = keyword_list if keyword_list else None

        excluded_list = ai_preferences.get('excluded_keywords') or []
        excluded_keywords = excluded_list if excluded_list else None

        ai_professors = ai_preferences.get('preferred_professors') or []
        if ai_professors:
            preferred_professor = merge_lists(preferred_professor, ai_professors) if preferred_professor else ai_professors

        ai_free_day = ai_preferences.get('preferred_free_day')
        if preferred_free_day is None and ai_free_day not in (None, '없음'):
            preferred_free_day = ai_free_day

        ai_prefer_morning = ai_preferences.get('prefer_morning')
        if prefer_morning is None and ai_prefer_morning is not None:
            prefer_morning = ai_prefer_morning

        if ai_preferences.get('prefer_consecutive') and not prefer_consecutive:
            prefer_consecutive = True

    if ai_preferences:
        st.session_state['ai_preferences'] = ai_preferences

    with st.spinner("시간표를 생성하는 중..."):
        # 필터링
        filtered_df = filter_courses(
            df,
            graduation_requirements=selected_graduation if selected_graduation else None,
            grade=selected_grade,
            max_credits=max_credits,
            preferred_professor=preferred_professor,
            prefer_morning=prefer_morning,
            subject_keywords=subject_keywords,
            excluded_keywords=excluded_keywords
        )
        
        if len(filtered_df) == 0:
            st.error("조건에 맞는 과목이 없습니다. 조건을 변경해주세요.")
        else:
            st.session_state['filtered_df'] = filtered_df
            st.session_state['preferred_free_day'] = preferred_free_day
            st.session_state['prefer_consecutive'] = prefer_consecutive
            st.session_state['max_credits'] = max_credits
            st.session_state['subject_keywords'] = subject_keywords
            st.session_state['excluded_keywords'] = excluded_keywords
            
            # 시간표 생성
            schedules = generate_schedules(
                filtered_df,
                max_credits=max_credits,
                preferred_free_day=preferred_free_day,
                prefer_consecutive=prefer_consecutive,
                max_schedules=50
            )
            
            if schedules:
                st.session_state['schedules'] = schedules
                st.success(f"✅ {len(schedules)}개의 시간표를 생성했습니다!")
            else:
                st.warning("조건에 맞는 시간표를 생성할 수 없습니다.")

ai_state = st.session_state.get('ai_preferences')
if ai_state:
    with st.sidebar.expander("AI 해석 결과", expanded=False):
        if ai_state.get('preferred_categories'):
            st.write(f"추천 과목 구분: {', '.join(ai_state['preferred_categories'])}")
        if ai_state.get('preferred_keywords'):
            st.write(f"추천 키워드: {', '.join(ai_state['preferred_keywords'])}")
        if ai_state.get('excluded_keywords'):
            st.write(f"제외 키워드: {', '.join(ai_state['excluded_keywords'])}")
        if ai_state.get('preferred_professors'):
            st.write(f"추천 교수님: {', '.join(ai_state['preferred_professors'])}")
        if ai_state.get('preferred_free_day'):
            st.write(f"추천 공강 요일: {ai_state['preferred_free_day']}")
        if ai_state.get('prefer_morning') is not None:
            st.write("시간 선호: " + ("아침" if ai_state['prefer_morning'] else "오후"))
        if ai_state.get('prefer_consecutive'):
            st.write("연강 선호: 예")

# 결과 표시
if 'schedules' in st.session_state and st.session_state['schedules']:
    schedules = st.session_state['schedules']
    preferred_free_day = st.session_state.get('preferred_free_day')
    prefer_consecutive = st.session_state.get('prefer_consecutive', False)
    
    # AI 추천 시간표
    recommended_schedule, score = recommend_schedule(
        schedules,
        preferred_free_day=preferred_free_day,
        prefer_consecutive=prefer_consecutive
    )
    
    if recommended_schedule:
        st.header("🎯 AI 추천 시간표")
        st.info(f"추천 점수: {score:.1f}점")
        
        # 시간표 시각화
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 시간표 그리드 생성
            days = ['월', '화', '수', '목', '금']
            time_slots = {}
            
            for day in days:
                time_slots[day] = []
            
            for course in recommended_schedule:
                slots = get_all_time_slots(course)
                for day, start, end in slots:
                    time_slots[day].append({
                        'course': course['교과목명'],
                        'start': start,
                        'end': end,
                        'professor': course['주담당교수'],
                        'credits': course['학점']
                    })
            
            # 시간표 표시
            st.subheader("📊 시간표")
            
            # 시간대 설정 (9시 ~ 18시)
            time_labels = []
            for hour in range(9, 19):
                time_labels.append(f"{hour:02d}:00")
            
            # 시간표를 더 보기 좋게 표시
            schedule_display = []
            for day in days:
                day_schedule = []
                for slot in sorted(time_slots[day], key=lambda x: x['start']):
                    start_hour = slot['start'] // 60
                    start_min = slot['start'] % 60
                    end_hour = slot['end'] // 60
                    end_min = slot['end'] % 60
                    time_str = f"{start_hour:02d}:{start_min:02d}~{end_hour:02d}:{end_min:02d}"
                    day_schedule.append(f"{slot['course']} ({time_str})")
                
                schedule_display.append("\n".join(day_schedule) if day_schedule else "공강")
            
            schedule_df = pd.DataFrame({
                '요일': days,
                '시간표': schedule_display
            })
            
            st.dataframe(schedule_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("📚 수강 과목 목록")
            total_credits = 0
            for idx, course in enumerate(recommended_schedule, 1):
                credits = int(course['학점']) if pd.notna(course['학점']) else 0
                total_credits += credits
                st.write(f"**{idx}. {course['교과목명']}**")
                st.write(f"   - 교수: {course['주담당교수']}")
                st.write(f"   - 학점: {credits}")
                st.write(f"   - 시간: {course['수업교시']}")
                st.write("---")
            
            st.metric("총 학점", f"{total_credits}학점")
        
        # 상세 시간표 (더 보기 좋은 버전)
        st.subheader("📅 상세 시간표")
        
        # Plotly를 사용한 시각화
        fig = go.Figure()
        
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE']
        
        y_positions = []
        course_names = []
        
        for idx, course in enumerate(recommended_schedule):
            slots = get_all_time_slots(course)
            for day, start, end in slots:
                day_num = days.index(day)
                start_hour = start / 60
                end_hour = end / 60
                
                fig.add_trace(go.Scatter(
                    x=[day_num, day_num, day_num + 0.9, day_num + 0.9, day_num],
                    y=[start_hour, end_hour, end_hour, start_hour, start_hour],
                    fill='toself',
                    fillcolor=colors[idx % len(colors)],
                    line=dict(color='white', width=2),
                    mode='lines',
                    name=course['교과목명'],
                    text=f"{course['교과목명']}<br>{course['주담당교수']}<br>{course['수업교시']}",
                    hoverinfo='text'
                ))
        
        fig.update_layout(
            title="시간표 시각화",
            xaxis=dict(
                tickmode='array',
                tickvals=list(range(len(days))),
                ticktext=days,
                title="요일"
            ),
            yaxis=dict(
                title="시간",
                range=[8, 19],
                tickmode='linear',
                tick0=9,
                dtick=1
            ),
            height=600,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 다른 시간표 옵션
        st.subheader("🔄 다른 시간표 옵션")
        if len(schedules) > 1:
            num_alternatives = min(5, len(schedules) - 1)
            st.write(f"추천 시간표 외 {num_alternatives}개의 대안 시간표:")
            
            for alt_idx, alt_schedule in enumerate(schedules[1:num_alternatives+1], 1):
                alt_score = calculate_schedule_score(
                    alt_schedule,
                    preferred_free_day=preferred_free_day,
                    prefer_consecutive=prefer_consecutive
                )
                alt_credits = sum(int(c['학점']) if pd.notna(c['학점']) else 0 for c in alt_schedule)
                
                with st.expander(f"대안 {alt_idx} (점수: {alt_score:.1f}, 학점: {alt_credits})"):
                    for course in alt_schedule:
                        st.write(f"- **{course['교과목명']}** ({course['주담당교수']}, {course['학점']}학점)")

else:
    st.info("👈 왼쪽 사이드바에서 조건을 입력하고 '시간표 생성' 버튼을 클릭하세요!")

