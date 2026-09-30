import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
# datetime은 특정 시각을 표현
# timedelta는 시간 간격을 표현
# timezone은 시간대 정보를 표현
# .env 파일에 저장한 값들을 읽어옴

# application에서 텍스트 저장 요청이 들어왔을 때
# 테이블에  넣는 코드
from pydantic import BaseModel 
# 요청으로 들어온 데이터가 어떤 모양이어야하는지 정해주는 틀

from fastapi import FastAPI, File, UploadFile, Header, HTTPException, Depends
# File: 파일을 받는 방식을 지정하는 도구
# uploadFile: 이 요청에는 파일이 첨부되어 온다를 알림
# Header: 요청의 헤더에서 값을 꺼내는 도구
# HEEPException: 인증실패 같은 특정 에러를 정확한 형식으로 응답하게 해주는 도구
# Depends: endPoint 함수가 실행되기 전 먼저 다른 함수 실행 후 그 결과 값을 파라미터에 저장

from openai import OpenAI
# openai 패키지에서 Whisper 호출에 쓸 OpenAI 클래스 가져옴

from anthropic import Anthropic
# anthropic 패키지에서 Claude 호출에 쓸 Anthropic 클래스 가져옴

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# Fastapi가 보안 인증 관련 기능만 모아놓은 상자
# HTTPBearer: 이 서버는 Bearer 토큰 방식으로 인증한다 선언
# HTTPAuthorizationCredentials: Bearer 토큰이 담긴 인증 정보 상자의 형태를 나타내는 타입

import json # 파이썬 내장 도구 상자(문자열 형태의 JSON을 파이썬 데이터로 변환)
import re # 정규 표현식이라는, 텍스트에서 특정 패턴을 찾아 바꿔주는 도구 상자

import requests # 웹에 요청을 보내고 응답을 받는 기능을 제공하는 패키지

from apscheduler.schedulers.background import BackgroundScheduler

from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Supabase 접속 정보 가져오기
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# 한국 시간대 정의 (UTC보다 9시간 빠름)
KST = timezone(timedelta(hours=9))

# Supabase 클라이언트 생성 (이제부터 이 변수로 DB에 접근)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


## 회원가입 & 로그인 ##

class SignupRequest(BaseModel): # 회원가입 요청
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/signup")
def signup(request: SignupRequest):
    """이메일/비밀번호로 회원가입"""
    result = supabase.auth.sign_up({
        "email": request.email,
        "password": request.password
    })
    return {"message": "회원가입 완료", "user_id": result.user.id}
    # 회원가입 완료 시 Supabase가 만든 고유 user id 꺼내주며 응답

@app.post("/login")
def login(request: LoginRequest):
    """이메일/비밀번호로 로그인, 토큰 발급"""
    result = supabase.auth.sign_in_with_password({
        "email": request.email,
        "password": request.password
    })
    return {
        "message": "로그인 성공",
        "user_id": result.user.id,
        "access_token": result.session.access_token #로그인 성공 시 토큰 제공(요청 시마다 토큰 연결)
    }

security = HTTPBearer()
# 토큰을 받는 객체


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # depends 먼저 security 방식을 통해 토큰 확인 하고, 그 결과를 credentials에 담음
    """Authorize 버튼으로 입력한 토큰을 확인해서, user_id를 반환"""
    token = credentials.credentials
    # credentials는 인증 정보 상자 전체 -> .credentials는 그 상자 안 진짜 토큰 값
    try:
        user_response = supabase.auth.get_user(token)
        return user_response.user.id
    # 토큰이 누구 거인지 supabase를 통해 확인 후 그 유저의 id만 반환
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")
     # 토큰이 잘못됐거나 만료일 경우 401(인증 실패)에러 응답


class ScheduleSettingRequest(BaseModel):
    analysis_hour: int


@app.post("/settings/schedule")
def set_analysis_schedule(request: ScheduleSettingRequest, user_id: str = Depends(get_current_user)):
    """사용자의 자동 분석 시각을 설정 (없으면 생성, 있으면 수정)"""
    supabase.table("user_settings").upsert({
        "user_id": user_id,
        "analysis_hour": request.analysis_hour
    }).execute()
    return {"message": "분석 시각 설정 완료", "hour": request.analysis_hour}


@app.get("/settings/schedule")
def get_analysis_schedule(user_id: str = Depends(get_current_user)):
    """사용자의 자동 분석 시각 조회 (없으면 기본값 23시 반환)"""
    result = supabase.table("user_settings").select("*").eq("user_id", user_id).execute()
    if len(result.data) == 0:
        return {"analysis_hour": 23}
    return {"analysis_hour": result.data[0]["analysis_hour"]}





# 요청으로 들어올 데이터의 형태를 미리 정의


@app.get("/")
def read_root():
    return {"message": "서버가 잘 돌아가고 있어요"}




def get_entries_by_date(user_id: str, date: str):
    #{}처럼 중괄호로 싸면 고정된 주소가 아닌 그 자리에 값이 들어옴을 표현
       
    start = f"{date}T00:00:00+09:00"
    end_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
 # strprime은 문자열을 실제 날짜 데이터로 변환하는 함수
    end = f"{end_date}T00:00:00+09:00"

    result = supabase.table("diary_entries") \
        .select("*") \
        .eq("user_id", user_id) \
        .gte("recorded_at", start) \
        .lt("recorded_at", end) \
        .execute()

    return {"date": date, "count": len(result.data), "entries": result.data}




# OpenAI 클라이언트 생성 (Whisper 호출용)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)



@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    # 업로드된 파일을 임시로 저장
    # async는 이 함수가 시간이 좀 걸리는 작업을 하니
    # 기다리는 동안 다른 요청도 처리할 수 있게 해줘
    # file이라는 이름으로 업로드 파일을 받겠다 선언

    # 업로드 된 파일을 내 컴퓨터에 임시 저장
    # Whisper API가 파일 형태로만 받을 수 있어서 임시 저장
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Whisper API 호출 (음성 -> 텍스트)
    with open(temp_path, "rb") as audio_file:
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    #transcript.text 안에 변환된 텍스트가 담겨 돌아옴


    # 임시 파일 삭제
    os.remove(temp_path)

    now_kst = datetime.now(KST).isoformat()
    result = supabase.table("diary_entries").insert({
        "user_id": user_id,
        "text_content": transcript.text,
        "recorded_at": now_kst
    }).execute()

    return {"message": "저장 완료", "text": transcript.text, "data": result.data}


# Anthropic 클라이언트 생성 (Claude 호출용)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)





# YouTube API 키 가져오기
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def verify_song_exists(artist, title):
    """iTunes Search API로 이 곡이 실제로 존재하는지 확인"""
    query = f"{artist} {title}"
    # 아래 주소로 params에 있는 값들을 붙여서 request 패키지가 검색해줌
    response = requests.get(
        "https://itunes.apple.com/search",
        params={
            "term": query,
            "country": "US",
            "media": "music",
            "entity": "song",
            "limit": 5
        }
    )
    data = response.json() # 방금 받은 답을 파이썬 딕셔너리 형태로 변환
    # response가 따로 json 기능 내장하고 있음
    return data["resultCount"] > 0
    # 노래가 있을 경우 0보다 크니까 True, 없으면 0이니 False 반환


def get_youtube_video(artist, title):
    """검증된 곡을 유튜브에서 검색해서 1등 영상 링크 반환"""
    query = f"{artist} {title}"
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "snippet", #snippet는 제목, 채널명 등 가장 기본으로 쓰는 정보 묶음
            "q": query,
            "type": "video",
            "maxResults": 1,
            "key": YOUTUBE_API_KEY
        }
    )
    data = response.json()

    # 아이튠즈엔 음원이 있으나 유튜브엔 관련 영상이 없을 경우
    # 테스트 해보고 이런 상황이 드물게라도 발생한다면
    # None 반환했을 때 새로운 노래 추천하도록 코드 수정
    if len(data.get("items", [])) == 0:
        return None

    video_id = data["items"][0]["id"]["videoId"]
    return f"https://www.youtube.com/watch?v={video_id}"


@app.post("/analyze/{date}")
def analyze_day(date: str, user_id: str = Depends(get_current_user)):


    # 1. 그 날짜의 모든 기록 가져오기 (기존 함수 재사용)
    entries_result = get_entries_by_date(user_id, date)
    entries = entries_result["entries"]

    # 기록이 없는 날은 Claude에게 빈 내용을 보내지 않고 미리 걸러냄
    if len(entries) == 0:
        return {"message": "그 날짜에 기록이 없어요"}


     # 이미 오늘 분석한 기록이 있는지 확인
    existing = supabase.table("daily_summary") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("summary_date", date) \
        .execute()

    if len(existing.data) > 0:
        existing_data = existing.data[0]
        keywords = existing_data.get("recommended_keywords") or []
        song = keywords[0] if len(keywords) > 0 else "정보 없음"
        return {
            "date": date,
            "analysis": {
                "dominant_emotion": existing_data["dominant_emotion"],
                "summary": existing_data["summary_text"],
                "advice": existing_data["advice_text"],
                "song_recommendation": song
            },
            "youtube_link": existing_data.get("youtube_link"),
            "message": "기존 분석 결과입니다"
        }

    

    # 2. 텍스트들을 하나로 합치기(여러 개 기록에서 텍스트 부분만 추출해 리스트 작성)
    # 리스트를 줄바꿈으로 이어붙여 하나의 긴 텍스트로 합침
    combined_text = "\n".join([e["text_content"] for e in entries])
    

     # 이번 달 시작일 계산
    month_start = date[:7] + "-01"  # "2026-09-01" 형태로 만듦

    # 이번 달에 이미 추천된 곡 목록 조회
    recent_songs_result = supabase.table("recommended_songs") \
        .select("song_title") \
        .eq("user_id", user_id) \
        .gte("recommended_at", month_start) \
        .execute()
    recent_songs = [r["song_title"] for r in recent_songs_result.data]
    recent_songs_text = ", ".join(recent_songs) if recent_songs else "없음"
    # 추천 이력이 있으면 콤마로 이어붙이고, 하나도 없으면 그냥 없음 표시


    # 3. Claude에게 분석 요청
    # content는 세 부분으로 나뉨 -> 이 세 부분이 합쳐 프롬프트
    # 1.상황 설명, 2.실제 일기 내용, 3.요청 사항+원하는 답변 형식

    # 감정분석 + 곡 추천 + 검증을 반복 시도 (최대 5번)
    max_attempts = 5
    parsed = None
    youtube_link = None

    for attempt in range(max_attempts):
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": f"""다음은 하루 동안 기록된 일기입니다:

{combined_text}

이번 달에 이미 추천한 곡: {recent_songs_text}

이 일기를 분석해서 아래 JSON 형식으로만 답해줘. 다른 설명 없이 JSON만 출력해줘.

song_recommendation을 고를 때는
1. 먼저 이 일기의 구체적인 감정과 상황을 파악하고
2. 그 감정/상황과 가사 내용, 곡 분위기가 실제로 잘 맞는 곡을 떠올린 다음
3. 확실히 실제로 존재하고, 가수와 제목이 정확히 일치하는 곡만 가수 - 제목 형태로 골라줘
4. 신나는 댄스곡을 우울한 감정에 추천하는 것처럼 어울리지 않는 조합은 피해줘
5. 위에 나온 "이미 추천한 곡" 목록과 겹치지 않게 골라줘, 


{{
  "dominant_emotion": "가장 두드러진 감정 한 단어",
  "summary": "하루 요약 2~3문장",
  "advice": "내일을 위한 조언 1~2문장",
  "song_recommendation": "가수 - 노래제목"
}}"""
                 }
            ]
        )

        # 4. Claude 응답에서 텍스트만 꺼내기
        result_text = message.content[0].text

        # 코드블럭 표시(```json ... ```) 제거
        cleaned_text = re.sub(r"```json\s*|\s*```", "", result_text).strip()

        # 문자열을 실제 파이썬 데이터(딕셔너리)로 변환
        parsed = json.loads(cleaned_text)

        # 추천된 곡 파싱 (가수, 제목 분리)
        song_full = parsed["song_recommendation"]
        # 노래 문자열 안에 - 표시로 나눔(가수랑 노래)
        if " - " in song_full:
            artist, title = song_full.split(" - ", 1)
        else:
            continue  # 형식이 이상하면 재시도

        # iTunes로 존재 여부 검증
        if not verify_song_exists(artist, title):
            continue  # 존재하지 않으면 재시도

        # 유튜브에서 검색
        youtube_link = get_youtube_video(artist, title)

        if youtube_link is not None:
            break  # 성공! 반복 종료

    if youtube_link is None:
        return {"message": "적절한 노래를 찾지 못했어요", "analysis": parsed}
   
    # daily_summary 테이블에 저장
    result = supabase.table("daily_summary").insert({
        "user_id": entries[0]["user_id"],
        "summary_date": date,
        "dominant_emotion": parsed["dominant_emotion"],
        "summary_text": parsed["summary"],
        "advice_text": parsed["advice"],
        "recommended_keywords": [parsed["song_recommendation"]],
        "youtube_link": youtube_link
    }).execute()

    # recommended_songs에 새 곡 기록
    supabase.table("recommended_songs").insert({
        "user_id": user_id,
        "song_title": parsed["song_recommendation"]
    }).execute()

    return {
        "date": date,
        "analysis": parsed,
        "youtube_link": youtube_link,
        "saved": result.data
    }






def auto_analyze_all_users():
    """매시간 실행되어, 지금이 분석 시각인 사용자들을 찾아 자동 분석"""
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")

    # 지금 이 시각이 분석 시각인 사용자 설정 조회
    settings_result = supabase.table("user_settings") \
        .select("*") \
        .eq("analysis_hour", now.hour) \
        .execute()
    # 지금 시각과 분석 시간이 일치하는 사람 찾음

    # 분석 시간에 맞는 사용자들 각각 자동 분석 실행
    for setting in settings_result.data:
        uid = setting["user_id"]
        try:
            analyze_day(today, uid)
        except Exception as e:
            print(f"자동 분석 실패 (user_id: {uid}): {e}")

    # 설정 안 한 사용자는 기본값(23시)에 처리
    if now.hour == 23:
        result = supabase.table("diary_entries") \
            .select("user_id") \
            .gte("recorded_at", f"{today}T00:00:00") \
            .execute()
        all_user_ids = set([r["user_id"] for r in result.data])
        configured_user_ids = set([s["user_id"] for s in settings_result.data])
        default_user_ids = all_user_ids - configured_user_ids

    # 설정 안 한 사람 기본 시각 분석 실행
        for uid in default_user_ids:
            try:
                analyze_day(today, uid)
            except Exception as e:
                print(f"자동 분석 실패 (user_id: {uid}): {e}")


scheduler = BackgroundScheduler(timezone="Asia/Seoul")
scheduler.add_job(auto_analyze_all_users, "cron", minute=0)  # 매시 정각마다 체크
scheduler.start()