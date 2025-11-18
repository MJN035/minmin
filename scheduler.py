import pandas as pd
from typing import List, Dict, Tuple, Optional
from itertools import combinations
from data_loader import check_time_conflict, get_all_time_slots
import random

def generate_schedules(filtered_courses: pd.DataFrame, 
                      max_credits: int = 21,
                      preferred_free_day: Optional[str] = None,
                      prefer_consecutive: bool = False,
                      max_schedules: int = 100) -> List[List[pd.Series]]:
    """
    여러 시간표를 생성합니다.
    
    Args:
        filtered_courses: 필터링된 과목 데이터프레임
        max_credits: 최대 수강 학점
        preferred_free_day: 희망 공강 요일
        prefer_consecutive: 연강 선호 여부
        max_schedules: 생성할 최대 시간표 개수
    
    Returns:
        시간표 리스트 (각 시간표는 과목 Series 리스트)
    """
    schedules = []
    courses_list = filtered_courses.to_dict('records')
    
    # 시간표 생성 시도
    attempts = 0
    max_attempts = max_schedules * 10
    
    while len(schedules) < max_schedules and attempts < max_attempts:
        attempts += 1
        
        # 랜덤하게 과목 선택
        random.shuffle(courses_list)
        schedule = []
        total_credits = 0
        
        for course in courses_list:
            course_series = pd.Series(course)
            course_credits = int(course_series['학점']) if pd.notna(course_series['학점']) else 0
            
            # 학점 제한 확인
            if total_credits + course_credits > max_credits:
                continue
            
            # 시간 충돌 확인
            conflict = False
            for existing_course in schedule:
                if check_time_conflict(course_series, existing_course):
                    conflict = True
                    break
            
            if not conflict:
                schedule.append(course_series)
                total_credits += course_credits
        
        # 유효한 시간표인지 확인 (중복 체크)
        if schedule:
            # 시간표를 문자열로 변환하여 중복 체크
            try:
                schedule_key = tuple(sorted([
                    (str(c.get('교과목번호', '')), str(c.get('강좌번호', ''))) 
                    for c in schedule
                ]))
                existing_keys = [
                    tuple(sorted([
                        (str(c.get('교과목번호', '')), str(c.get('강좌번호', ''))) 
                        for c in s
                    ])) 
                    for s in schedules
                ]
                
                if schedule_key not in existing_keys:
                    schedules.append(schedule)
            except Exception:
                # 에러 발생 시 그냥 추가 (중복 가능)
                schedules.append(schedule)
    
    return schedules

def calculate_schedule_score(schedule: List[pd.Series],
                            preferred_free_day: Optional[str] = None,
                            prefer_consecutive: bool = False) -> float:
    """
    시간표의 점수를 계산합니다.
    점수가 높을수록 더 좋은 시간표입니다.
    """
    score = 0.0
    
    if not schedule:
        return 0.0
    
    # 1. 학점 점수 (적절한 학점일수록 높은 점수)
    total_credits = sum(int(course['학점']) if pd.notna(course['학점']) else 0 for course in schedule)
    if 15 <= total_credits <= 21:
        score += 10
    elif 12 <= total_credits < 15:
        score += 7
    elif total_credits > 21:
        score -= 5
    
    # 2. 공강 요일 점수
    if preferred_free_day:
        days_used = set()
        for course in schedule:
            slots = get_all_time_slots(course)
            for day, _, _ in slots:
                days_used.add(day)
        
        if preferred_free_day not in days_used:
            score += 15  # 희망 공강 요일에 수업이 없으면 높은 점수
    
    # 3. 연강 점수
    if prefer_consecutive:
        # 같은 요일에 연속된 수업이 있으면 점수 추가
        day_schedules = {}
        for course in schedule:
            slots = get_all_time_slots(course)
            for day, start, end in slots:
                if day not in day_schedules:
                    day_schedules[day] = []
                day_schedules[day].append((start, end))
        
        for day, times in day_schedules.items():
            times.sort()
            for i in range(len(times) - 1):
                if times[i][1] == times[i+1][0]:  # 연속된 시간
                    score += 5
    
    # 4. 시간 분산 점수 (너무 집중되지 않으면 좋음)
    all_times = []
    for course in schedule:
        slots = get_all_time_slots(course)
        for _, start, end in slots:
            all_times.append((start + end) / 2)  # 평균 시간
    
    if all_times:
        time_variance = max(all_times) - min(all_times)
        if time_variance > 300:  # 5시간 이상 분산
            score += 3
    
    return score

def recommend_schedule(schedules: List[List[pd.Series]],
                      preferred_free_day: Optional[str] = None,
                      prefer_consecutive: bool = False) -> Tuple[List[pd.Series], float]:
    """
    여러 시간표 중 가장 좋은 시간표를 추천합니다.
    """
    if not schedules:
        return [], 0.0
    
    best_schedule = None
    best_score = -float('inf')
    
    for schedule in schedules:
        score = calculate_schedule_score(schedule, preferred_free_day, prefer_consecutive)
        if score > best_score:
            best_score = score
            best_schedule = schedule
    
    return best_schedule, best_score

