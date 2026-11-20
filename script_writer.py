"""주제 → 쇼츠 대본(제목/문장/설명/태그) 자동 작성 (Gemini). 세금·정책은 research()로 검색 확인 먼저."""
import json
import os
import time

import httpx
from google import genai
from google.genai import errors, types

from settings import BASE, load_env
# 순서대로 시도 (과부하/한도 초과 시 다음 모델로). 특정 모델 고정 시 .env에 GEMINI_MODEL=
HTTP = types.HttpOptions(timeout=90_000)  # ms — 응답 없이 몇 분씩 멈추는 것 방지
# gemini-flash-latest 별칭은 11/09 기준 404(종료) — 목록이 다 죽어도 discover_models()가 대체 모델을 찾음
FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]

PROMPT = """너는 유튜브 쇼츠 대본 작가야. 주제: "{topic}"

조건:
- 한국어, 소리 내어 읽었을 때 약 {seconds}초 분량 (대략 {chars}자 내외)
- 문장 {n_min}~{n_max}개. 각 문장은 화면 자막 한 장면이 되므로 짧고 임팩트 있게 (한 문장 35자 이내)
- 첫 문장은 스크롤을 멈추게 하는 강한 후킹, 마지막 문장은 여운이나 행동 유도
- 주제 뒤에 붙은 카테고리 지침의 형식과 말투를 우선으로 따를 것
- 이모지, 해시태그, 따옴표, 괄호, 화자 표시 없이 읽을 문장만

- scenes: 각 문장 뒤에 깔릴 배경 영상의 영어 검색어 (sentences와 같은 개수).
  2~4단어, 실제 촬영한 부동산·도시 장면 (예: "apartment complex aerial", "city skyline sunset", "house keys hand",
  "construction site crane", "land field aerial", "shop street storefront", "office building glass", "calculator money desk",
  "contract signing pen", "courtroom gavel", "family moving boxes").
  첫 단어는 반드시 장면의 주인공 명사 하나 (apartment, building, city, house, land, money, contract 등 — 형용사로 시작 금지).
  너무 어둡거나 추상적인 검색어(dark, particles, abstract, space)는 피할 것.
  사람 얼굴 클로즈업, 글자, 로고는 피할 것. 문장 내용에 어울리되 장면이 서로 다양하게.
- scenes_alt: scenes와 같은 개수. 각 장면을 다른 말로 찾을 검색어 2개 [같은 장면의 다른 영어 표현, 한국어 검색어]
  (예: "apartment complex aerial" → ["residential towers drone", "아파트 단지 항공"],
  "contract signing pen" → ["document signature hand", "계약서 서명"]). 한국어는 2~3단어 명사 위주.

JSON으로만 답해:
{{"title": "영상 제목(25자 이내, 해시태그 없이)",
  "title_point": "제목 안에서 노란색으로 강조할 핵심 말 (제목에 그대로 있는 2~6글자, 예: '집을 못 받는')",
  "sentences": ["문장1", "문장2", ...],
  "scenes": ["english query 1", "english query 2", ...],
  "scenes_alt": [["other english 1", "한국어 1"], ["other english 2", "한국어 2"], ...],
  "description": "영상 설명 2~3줄",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]}}"""


def discover_models(client, kind: str = "text") -> list[str]:
    """지금 키로 쓸 수 있는 모델 목록에서 대체 후보 찾기 (구글이 모델을 종료해도 멈추지 않게).
    text = 일반 flash 계열(최신 버전 먼저, lite는 뒤로), tts = 이름에 tts가 들어간 모델."""
    import re
    try:
        names = [m.name.removeprefix("models/") for m in client.models.list()]
    except Exception as e:
        print(f"  (모델 목록 조회 실패: {str(e)[:100]})")
        return []
    if kind == "tts":
        return [n for n in names if "tts" in n]
    skip = ("image", "tts", "audio", "live", "embedding", "omni", "research", "preview", "exp", "banana")
    cands = [n for n in names if n.startswith("gemini-") and "flash" in n and not any(k in n for k in skip)]
    ver = lambda n: [int(x) for x in re.findall(r"\d+", n.split("-")[1])] if len(n.split("-")) > 1 else [0]
    return sorted(cands, key=lambda n: ("lite" in n, [-x for x in ver(n)]))


def _generate(client, models, prompt, config):
    """모델별 최대 2회 시도. 과부하(429/5xx)·연결 끊김이면 재시도, 없는 모델(404)이면 바로 다음 모델.
    목록이 전부 실패하면 지금 쓸 수 있는 모델을 찾아 최대 3개 더 시도."""
    try:
        return _try_models(client, models, prompt, config)
    except SystemExit:
        extra = [m for m in discover_models(client) if m not in models][:3]
        if not extra:
            raise
        print(f"  대체 모델 시도: {', '.join(extra)}")
        return _try_models(client, extra, prompt, config)


def _try_models(client, models, prompt, config):
    last_err = None
    for m in models:
        for attempt in range(2):
            try:
                return client.models.generate_content(model=m, contents=prompt, config=config)
            except errors.APIError as e:
                if e.code not in (404, 429, 500, 502, 503, 504):
                    raise
                last_err = e
                print(f"  {m} 응답 없음({e.code})")
                if e.code == 404:
                    break
            except (httpx.HTTPError, ConnectionError) as e:  # 서버가 응답 없이 끊음·시간 초과
                last_err = e
                print(f"  {m} 연결 끊김({type(e).__name__})")
            if attempt == 0:
                time.sleep(5)
    raise SystemExit(f"모든 Gemini 모델이 응답하지 않습니다. 잠시 후 다시 시도하세요. ({last_err})")


TOPIC_PROMPT = """너는 유튜브 쇼츠 채널의 기획자야.
채널 콘셉트: {profile}
이번 업로드 시간대: {slot_desc}

최근에 이미 다룬 주제 (겹치거나 비슷하면 안 됨):
{recent}

이 시간대 시청자가 스크롤을 멈출 만한, 이번 카테고리에 맞는 새 주제 하나를 정해.
구체적이고 궁금증이 생기게 (예: "고양이가 꾹꾹이를 하는 진짜 이유", "냉장고에 넣으면 안 되는 의외의 음식",
"아재개그 넌센스 퀴즈 3탄", "작심삼일을 끝내는 2분 규칙", "괜찮아, 오늘은 쉬어가도 돼").
너무 무겁거나 우울한 주제는 피하고, 최근 주제와 소재가 겹치지 않게.
JSON으로만 답해: {{"topic": "주제"}}"""


def pick_topic(profile: str, slot_desc: str, recent: list[str]) -> str:
    load_env()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=HTTP)
    prompt = TOPIC_PROMPT.format(profile=profile, slot_desc=slot_desc,
                                 recent="\n".join(f"- {t}" for t in recent[-60:]) or "(없음)")
    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=1.0)
    fixed = os.environ.get("GEMINI_MODEL")
    resp = _generate(client, [fixed] if fixed else FALLBACK_MODELS, prompt, config)
    return json.loads(resp.text)["topic"].strip()


IDEA_PROMPT = """너는 유튜브 쇼츠 채널의 기획자야.
채널 콘셉트: {profile}
대표님이 길에서 떠올린 아이디어를 메신저로 보냈어 (말투가 짧거나 구어체일 수 있음):
"{idea}"

이 아이디어의 핵심을 살려 쇼츠 주제 한 줄로 다듬고, 가장 잘 맞는 카테고리 키를 골라.
카테고리:
{categories}
주제는 구체적이고 궁금증이 생기게 (예: "고양이가 상자를 좋아하는 진짜 이유"). 대표님 의도를 바꾸지 말 것.
JSON으로만 답해: {{"topic": "주제", "category": "카테고리 키"}}"""


def shape_idea(profile: str, idea: str, categories: dict[str, str]) -> dict:
    """대표님 아이디어(디스코드) → 쇼츠 주제 + 카테고리."""
    load_env()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=HTTP)
    prompt = IDEA_PROMPT.format(profile=profile, idea=idea, categories="\n".join(f"- {k}: {v}" for k, v in categories.items()))
    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.6)
    fixed = os.environ.get("GEMINI_MODEL")
    out = json.loads(_generate(client, [fixed] if fixed else FALLBACK_MODELS, prompt, config).text)
    return {"topic": out["topic"].strip(), "category": out.get("category") if out.get("category") in categories else None}


def write_script(topic: str, seconds: int = 30, model: str | None = None) -> dict:
    load_env()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit(f"GEMINI_API_KEY가 없습니다. {BASE / '.env'} 파일에 GEMINI_API_KEY=키값 을 넣어주세요.")
    client = genai.Client(api_key=key, http_options=HTTP)
    n = max(2, round(seconds / 4.5))
    prompt = PROMPT.format(topic=topic, seconds=seconds, chars=seconds * 7, n_min=n - 1, n_max=n + 1)
    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9)
    fixed = model or os.environ.get("GEMINI_MODEL")
    resp = _generate(client, [fixed] if fixed else FALLBACK_MODELS, prompt, config)
    data = json.loads(resp.text)
    data["sentences"] = [s.strip() for s in data["sentences"] if s.strip()]
    return data


RESEARCH_PROMPT = """한국 부동산 유튜브 쇼츠 대본을 쓰기 전 사실 확인이 필요해. 오늘은 {today}.
주제: "{topic}"

구글 검색으로 지금 시행 중인 기준(국토교통부·국세청·기획재정부·법제처·청약홈·대법원 경매정보 등 공식 출처 우선)을 확인해서
대본에 쓸 핵심 사실 5개 이내를 한 줄씩 적어. 각 줄 끝에 (기준 시점·출처 이름).
숫자(세율·한도·기간·금액)는 공식 출처에서 확인된 것만, 개정 예정이거나 출처마다 다르면 그 줄 앞에 [불확실] 이라고 표시.
설명 없이 목록만."""


def research(topic: str) -> str:
    """구글 검색으로 최신 기준 확인 → 대본 작가에게 줄 사실 목록. 실패하면 '' (대본은 원리 위주로)."""
    from datetime import date
    load_env()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=HTTP)
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.2)
    fixed = os.environ.get("GEMINI_MODEL")
    try:
        resp = _generate(client, [fixed] if fixed else FALLBACK_MODELS,
                         RESEARCH_PROMPT.format(today=date.today().isoformat(), topic=topic), config)
        return (resp.text or "").strip()
    except (Exception, SystemExit) as e:
        print(f"  (검색 확인 실패 — 숫자 없이 원리 위주로: {str(e)[:120]})")
        return ""
