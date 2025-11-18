import pandas as pd
import re
from typing import List, Dict, Tuple

def load_courses(file_path: str = '강좌검색.csv') -> pd.DataFrame:
    """강좌 데이터를 로드하고 전처리합니다."""
    # CSV 파일 읽기 (헤더가 3번째 줄에 있음)
    df = pd.read_csv(file_path, skiprows=2, encoding='utf-8')
    
    # 빈 행 제거
    df = df.dropna(subset=['교과목명'])
    
    # 수업교시가 없는 과목 제거
    df = df[df['수업교시'].notna()]
    df = df[df['수업교시'] != '']
    
    return df

def parse_time_slot(time_str: str) -> List[Tuple[str, int, int]]:
    """
    시간 문자열을 파싱합니다.
    예: '월(10:00~12:50)' -> [('월', 10, 0), ('월', 12, 50)]
    """
    slots = []
    if pd.isna(time_str) or time_str == '':
        return slots
    
    # 여러 시간대를 '/'로 분리
    time_parts = str(time_str).split('/')
    
    for part in time_parts:
        # 요일과 시간 추출
        match = re.match(r'([월화수목금토일])\((\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})\)', part.strip())
        if match:
            day = match.group(1)
            start_hour = int(match.group(2))
            start_min = int(match.group(3))
            end_hour = int(match.group(4))
            end_min = int(match.group(5))
            
            # 시작 시간과 종료 시간을 분 단위로 변환
            start_total_min = start_hour * 60 + start_min
            end_total_min = end_hour * 60 + end_min
            
            slots.append((day, start_total_min, end_total_min))
    
    return slots

def get_all_time_slots(course: pd.Series) -> List[Tuple[str, int, int]]:
    """과목의 모든 시간 슬롯을 반환합니다."""
    time_str = course['수업교시']
    return parse_time_slot(time_str)

def check_time_conflict(course1: pd.Series, course2: pd.Series) -> bool:
    """두 과목의 시간이 겹치는지 확인합니다."""
    slots1 = get_all_time_slots(course1)
    slots2 = get_all_time_slots(course2)
    
    for day1, start1, end1 in slots1:
        for day2, start2, end2 in slots2:
            if day1 == day2:
                # 시간이 겹치는지 확인
                if not (end1 <= start2 or end2 <= start1):
                    return True
    
    return False

def get_course_time_range(course: pd.Series) -> Tuple[int, int]:
    """과목의 가장 이른 시작 시간과 가장 늦은 종료 시간을 반환합니다."""
    slots = get_all_time_slots(course)
    if not slots:
        return (0, 0)
    
    start_times = [start for _, start, _ in slots]
    end_times = [end for _, _, end in slots]
    
    return (min(start_times), max(end_times))

