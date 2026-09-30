# emotion_diary
# 음성 기반 AI 감정 일기 및 음악 추천 시스템

말하는 것만으로 하루의 감정을 기록하고, 그 감정에 어울리는 음악을 추천받는 서비스입니다.

**서비스 바로가기**: https://emotion-diary-c111208-e3d0f.web.app

## 소개

바쁜 일상 속에서 감정을 글로 기록하는 건 번거롭고 부담스럽습니다. 이 프로젝트는 사용자가 하루 중 언제든 짧게 음성으로 기분이나 있었던 일을 남기면, AI가 하루치 기록을 종합해 감정을 분석하고 그에 어울리는 노래를 추천해주는 서비스입니다.

## 주요 기능

- 음성 녹음 및 자동 텍스트 변환 (Whisper)
- 하루치 기록을 종합한 감정 분석 및 조언 생성 (Claude)
- 감정에 어울리는 노래 추천 및 실제 존재 여부 검증 (iTunes Search API)
- 검증된 곡의 유튜브 링크 자동 연결 (YouTube Data API)
- 월 단위 중복 추천 방지
- 하루 1회 분석 제한 및 재조회 기능
- 사용자별 자동 분석 시각 설정 및 스케줄링
- 회원가입 및 로그인 (토큰 기반 인증)

## 기술 스택

**Backend**
- Python, FastAPI
- Supabase (PostgreSQL, Auth)
- APScheduler

**Frontend**
- Flutter (Web)

**AI / External API**
- OpenAI Whisper API (음성 인식)
- Anthropic Claude API (감정 분석, 노래 추천)
- iTunes Search API (곡 검증)
- YouTube Data API (영상 링크)

**Deployment**
- Railway (Backend)
- Firebase Hosting (Frontend)

## 트러블슈팅

### 1. AI 노래 추천 할루시네이션 문제
Claude가 존재하지 않는 가수-곡 조합을 추천하는 문제를 발견했습니다. Spotify, YouTube Music, MusicBrainz, Apple Music API 등 여러 대안을 비교 검토한 끝에, 무료이며 인증이 필요 없는 iTunes Search API로 곡의 실제 존재 여부를 검증하고, 실패 시 자동으로 재추천을 요청하는 로직을 구현했습니다.

### 2. 시간대 처리
국제표준시(UTC) 기준으로 데이터를 저장했을 때, 한국 사용자의 실제 하루 경계와 시스템이 인식하는 하루 경계가 어긋나는 문제를 발견했습니다. 한국 사용자만을 대상으로 하는 서비스라는 점을 고려해, 한국 시간(KST)을 직접 저장하는 방식으로 데이터베이스 스키마를 재설계했습니다.

### 3. Flutter Web 환경에서의 파일 업로드
`MultipartFile.fromPath`가 브라우저 환경(`dart:io` 미지원)에서 동작하지 않는 문제를 발견했습니다. 녹음된 오디오의 blob URL에서 바이트 데이터를 직접 읽어 `MultipartFile.fromBytes`로 전송하도록 수정해 해결했습니다.

### 4. 인증 방식 개선
초기에는 FastAPI의 기본 `Header` 방식으로 토큰을 받았으나, API 테스트 도구에서 파일 업로드와 커스텀 헤더를 함께 사용할 경우 인증 정보가 누락되는 문제를 발견했습니다. FastAPI가 공식 지원하는 `HTTPBearer` 방식으로 전환해 근본적으로 해결했습니다.

## 실행 방법 (로컬)

### Backend
\`\`\`bash
cd backend
python -m venv venv
venv\Scripts\Activate
pip install -r requirements.txt
uvicorn main:app --reload
\`\`\`

### Frontend
\`\`\`bash
cd frontend
flutter pub get
flutter run -d chrome
\`\`\`

## 개발자
황보민 · 홍익대학교 컴�터공학전공
