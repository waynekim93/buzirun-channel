# 부지런 쇼츠 자동화 (buzirun-channel) — 작업 노트

유튜브 채널 **부지런**(@buzirun, "부동산 지식을 Learn" · 슬로건 "부지런한 사람이 집을 산다")에 부동산 쇼츠를
**하루 4편(07:00 · 12:00 · 18:00 · 21:00 KST)** 자동으로 만들어 예약 공개하는 프로그램.
어느 컴퓨터에서든 이 파일로 맥락을 이어간다. 큰 결정 · 완료한 일이 생기면 여기도 고친다.

> ⚠️ 이 파일 · 코드 · 커밋 메시지에 비밀번호 · 토큰 · API 키 · 채널 내부 번호를 절대 쓰지 말 것.
> 비밀값은 노트북 `~/.buzirun/channel/`(저장소 밖)과 GitHub Secrets 에만 있음.

## 한눈에
- 실행: GitHub Actions(`waynekim93/buzirun-channel`, **공개 저장소** — 실행 시간 무제한 위해 11/20 공개 전환. 비밀값은 Secrets 에만)가 전부 자동. 사람 손은 문제 생길 때만(디스코드 알림).
- 투게독(togedog-channel) 코드를 복사해 고친 것. **캄모니 · 투게독과 완전 분리** — 그쪽 저장소 · 계정 · 비밀값은 건드리지 않음.
- 계정(이름만): 구글 · 유튜브 · GitHub · Vercel 모두 **waynekim93**. 구글 클라우드 프로젝트 buzirun(OAuth 앱 '부지런 업로더', 프로덕션 게시됨).
- 디스코드: 서버 '부지런' + 봇 '부지런'. `부지런-알림` 채널 = 업로드 완료 · 오류 알림, `부지런-아이디어` 채널 = 사용자가 쓴 아이디어를 다음 영상 주제로 먼저 씀(쓴 글엔 ✅ + 답글).
- 브랜딩 페이지: https://buzirun.vercel.app (/privacy, /terms) — 원본 `site/`, 배포는 `vercel deploy --prod --global-config ~/.buzirun/vercel` (이 옵션 빼면 다른 계정으로 올라감).

## 파일
| 파일 | 하는 일 |
|---|---|
| `autopilot.py` | 주제(디스코드 아이디어 우선) → 대본 → 영상 → 예약 업로드 → `history.json`. 카테고리 · 시간대 · 공개 시각 · 내용 규칙 |
| `script_writer.py` | Gemini 대본 · 주제 · 아이디어 다듬기. `research()`(구글 검색 확인)는 유료 키에서만 → 기본 꺼짐(`RESEARCH=1`) |
| `shorts_maker.py` | 영상 편집 + **부지런 디자인**(아래) |
| `stock_video.py` | Pixabay 배경 — 장면마다 "영어 \| 다른 영어 표현 \| 한국어" 세 검색어 후보를 섞어 Gemini 가 고름 |
| `voice_gemini.py` | Gemini TTS 4종 + Whisper 정렬 |
| `ideas.py` · `alert.py` | 디스코드 아이디어 읽기 · 알림 |
| `healthcheck.py` · `health.yml` | 빈 회차 감시(KST 06:03 · 14:53 · 19:13): 14시간 안 회차가 비면 autopilot 다시 실행 + 알림, 유튜브 로그인 풀림 알림 |
| `youtube_uploader.py` · `auth_login.py` | 업로드 · 최초 로그인 |
| `settings.py` | 비밀값: 환경변수 → `.env` → `~/.buzirun/channel/*` 순 |

## 카테고리 (같은 카테고리 연달아 금지, 초보/투자자 섞기)
초보: subscription 청약·전월세 · contract 계약·매매 상식 · tax 세금·정책 / 투자자: commercial 건물·상가 · land 토지 · auction 경매·공매 / 재미(11/20 추가): landlord 건물주의 세계 · trivia 부동산 잡학·역사

## 사용자 결정
- 디자인: 박스 없이 깔끔하게. 제목 = 왼쪽 정렬 흰 글씨 60px, 핵심 말(`title_point`)만 노랑, 위에 작은 노랑 라벨 + 짧은 선. 자막 = 흰 글씨 + 그림자, 읽는 단어 노랑. 하단 노랑 진행 막대 + @buzirun, 끝 2.6초 슬로건('집을 산다'만 노랑). 기울임 · 큰 노랑 박스는 싫어함.
- 내용: **뻔한 얘기 금지**(인터넷 신청 가능 · 계약서 꼼꼼히 등), 핵심 3가지는 "이건 몰랐네" 수준, 과장 · 단정 금지. 투자 권유 · 지역 전망 금지.
- Gemini 무료 유지 → 구체적 숫자(세율 · 한도 · 금리) 없이 원리 위주. 설명란 면책 문구 필수.
- 배경 음악 없음(미정).

## 실행
- 로컬 시험(업로드 안 함): `python -X utf8 autopilot.py --no-upload` (패키지 있는 파이썬 필요 — 지금은 togedog-channel\.venv 를 빌려 씀)
- Secrets: YT_CLIENT_SECRET · YT_TOKEN_BUZIRUN · GEMINI_API_KEY · PIXABAY_API_KEY · DISCORD_BOT_TOKEN · DISCORD_ALERT_CHANNEL · DISCORD_IDEA_CHANNEL
- gh 는 `GH_CONFIG_DIR=~/.buzirun/gh` 로 waynekim93 계정 사용(기본 gh 는 nickkim).
- **작업 전 `git pull`** — Actions 가 history.json 을 커밋함.

## 함정
- 새 Gemini 키는 2.5 계열 404 → 3.x 모델 + `discover_models()`. 구글 검색(grounding)은 무료 키 429.
- `shorts_maker.build_ass` 고칠 때 bash heredoc · re.sub 로 백슬래시를 다루면 `\\` 가 깨짐(자막 통째로 사라진 적 있음) → Edit 도구로 고치고 미리보기 렌더로 확인.
