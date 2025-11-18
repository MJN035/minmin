import pandas as pd
from typing import List, Optional
from data_loader import get_course_time_range

def filter_courses(df: pd.DataFrame, 
                  graduation_requirements: Optional[List[str]] = None,
                  grade: Optional[str] = None,
                  max_credits: int = 21,
                  excluded_courses: Optional[List[str]] = None,
                  preferred_free_day: Optional[str] = None,
                  preferred_professor: Optional[List[str]] = None,
                  prefer_morning: Optional[bool] = None,
                  subject_keywords: Optional[List[str]] = None,
                  excluded_keywords: Optional[List[str]] = None) -> pd.DataFrame:
    """
    조건에 맞게 과목을 필터링합니다.
    
    Args:
        df: 전체 과목 데이터프레임
        graduation_requirements: 졸업요건 리스트 (예: ['전선', '교양'])
        grade: 학년 (예: '1학년', '2학년')
        max_credits: 최대 수강 학점
        excluded_courses: 수강 불가능한 과목명 리스트
        preferred_free_day: 희망 공강 요일 (예: '월', '화')
        preferred_professor: 원하는 교수님 리스트
        prefer_morning: 아침 수업 선호 여부 (True: 아침, False: 오후, None: 무관)
        subject_keywords: 교과목명 키워드 필터 (예: ['AI', '데이터'])
        excluded_keywords: 교과목명 제외 키워드 (예: ['초급', '독일어'])
    """
    filtered_df = df.copy()
    
    # 1. 졸업요건 필터링
    if graduation_requirements:
        filtered_df = filtered_df[filtered_df['교과구분'].isin(graduation_requirements)]
    
    # 2. 학년 필터링
    if grade:
        filtered_df = filtered_df[filtered_df['학년'].str.contains(grade, na=False)]
    
    # 3. 수강 불가능한 과목 제거
    if excluded_courses:
        for excluded in excluded_courses:
            filtered_df = filtered_df[~filtered_df['교과목명'].str.contains(excluded, na=False)]
    
    # 4. 원하는 교수님 필터링 (선택사항)
    if preferred_professor:
        professor_filter = filtered_df['주담당교수'].isin(preferred_professor)
        # 원하는 교수님이 있으면 우선, 없으면 전체
        if professor_filter.any():
            filtered_df = filtered_df[professor_filter]
    
    # 5. 아침/오후 수업 필터링
    if prefer_morning is not None:
        def is_morning_course(course):
            start_time, _ = get_course_time_range(course)
            # 오전 12시(720분) 이전이면 아침 수업
            return start_time < 720
        
        if prefer_morning:
            filtered_df = filtered_df[filtered_df.apply(is_morning_course, axis=1)]
        else:
            filtered_df = filtered_df[~filtered_df.apply(is_morning_course, axis=1)]

    # 6. 교과목명 키워드 필터
    if subject_keywords:
        keyword_mask = pd.Series([False] * len(filtered_df))
        for keyword in subject_keywords:
            keyword = keyword.strip()
            if not keyword:
                continue
            keyword_mask = keyword_mask | filtered_df['교과목명'].str.contains(keyword, case=False, na=False)
        filtered_df = filtered_df[keyword_mask]

    # 7. 교과목명 제외 키워드
    if excluded_keywords:
        for keyword in excluded_keywords:
            keyword = keyword.strip()
            if not keyword:
                continue
            filtered_df = filtered_df[~filtered_df['교과목명'].str.contains(keyword, case=False, na=False)]
    
    return filtered_df.reset_index(drop=True)

