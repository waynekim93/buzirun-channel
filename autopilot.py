"""부지런 채널 완전 자동: 주제 선정(디스코드 아이디어 우선) → 사실 확인 → 대본 → 영상 → 예약 업로드 → 기록.
투게독(togedog-channel) 코드를 복사해 고친 것 — 투게독과 저장소 · 계정 · 비밀값 모두 따로.

  python autopilot.py --schedule        # 예약 대기열 채우기 (07:00 / 12:00 / 18:00 / 21:00 KST) — 자동 실행은 이것
  python autopilot.py --plan            # 만들 회차 수만 출력
  python autopilot.py --no-upload       # 업로드 없이 1편 시험 제작
  python autopilot.py --category tax --topic "..."   # 카테고리 · 주제 지정
"""
import argparse
import json
import os
import random
import re
import traceback
from datetime import datetime, timedelta, timezone

from settings import BASE

KST = timezone(timedelta(hours=9))
CHANNEL = "부지런"
HISTORY = BASE / "history.json"
PROFILE = ("부지런 — '부지런한 사람이 집을 산다'. 부동산 지식을 쉽고 짧게 알려 주는 쇼츠 채널. "
           "내 집 마련 초보(청약·전월세·계약·세금)와 투자자(건물·상가·토지·경매) 모두를 위한 실전 상식. "
           "말투는 친한 선배가 핵심만 짚어 주듯 시원시원한 존댓말. 투자 권유·특정 지역 집값 전망·종목 추천 금지, "
           "정치적 평가 금지. 숫자(세율·한도·기간)는 확인된 것만 쓰고, 애매하면 숫자 없이 원리로 설명. "
           "주제는 누구나 아는 상식이 아니라, 알면 손해를 피하거나 돈이 되는 한 끗 차이 지식 "
           "(예: '전세 계약 당일 집주인이 대출받으면 생기는 일', '경매 낙찰받고도 집을 못 받는 경우', "
           "'같은 땅인데 지목 하나로 값이 달라지는 이유').")
FORMAT = ("구성: 첫 문장은 2초 안에 스크롤을 멈추게 하는 훅(손해·함정·몰랐던 사실), "
          "중간은 핵심 3가지를 '첫째·둘째·셋째'처럼 또렷하게, 마지막 문장은 한 줄 정리 + 댓글 유도. "
          "⚠️ 누구나 아는 뻔한 말 금지 (예: '인터넷으로 신청할 수 있다', '계약서를 꼼꼼히 읽어라', '전문가와 상담하라', "
          "'발품을 팔아라') — 핵심 3가지는 각각 '이건 몰랐네' 싶은 구체적인 내용이어야 함: 실제로 손해 보는 구조, "
          "헷갈리는 용어의 정확한 뜻, 사람들이 흔히 잘못 아는 것, 순서·조건에 숨은 함정. "
          "'안전하다·무조건 싸다·누구나 돈 번다' 같은 과장 · 단정 금지 (장점을 말하면 조건이나 위험도 함께). ")

# 카테고리: (설명, 대본 지시, 목소리 톤, 태그, 대상)
CATEGORIES = {
    "subscription": ("청약 · 전월세 — 청약 제도와 가점, 특별공급, 전세·월세 계약, 보증금 지키기, 전세사기 예방",
                     FORMAT + "마지막은 '청약·전세 궁금한 점 댓글로!'. 초보도 바로 이해하게 쉬운 말로.",
                     "든든한 선배처럼 차분하고 또렷하게",
                     ["청약", "전세", "내집마련"], "초보"),
    "contract": ("계약 · 매매 상식 — 아파트 사고팔 때 절차, 등기부등본, 계약금·중도금·잔금, 중개수수료, 주택담보대출",
                 FORMAT + "마지막은 '계약 앞두고 있다면 저장해 두세요!'. 실수하기 쉬운 포인트 위주로.",
                 "꼼꼼하게 짚어 주듯 또박또박",
                 ["부동산계약", "아파트매매", "부동산상식"], "초보"),
    "tax": ("세금 · 정책 — 취득세·양도세·보유세(재산세·종부세), 대출 규제(DSR·LTV), 새로 바뀐 부동산 정책",
            FORMAT + "제도가 자주 바뀌니 구체적 숫자 대신 원리와 체크 포인트 위주로. "
            "마지막은 '내 상황은 세무사와 꼭 확인하세요' 뉘앙스 + 댓글 유도.",
            "신뢰감 있게 차분하고 명확하게",
            ["부동산세금", "양도세", "부동산정책"], "초보"),
    "commercial": ("건물 · 상가 — 꼬마빌딩, 상가 투자, 임대수익률 계산, 공실·권리금, 상가임대차",
                   FORMAT + "마지막은 '건물주 되고 싶다면 팔로우!'. 수익 과장 금지, 위험도 같이.",
                   "자신감 있게 시원시원하게",
                   ["상가투자", "꼬마빌딩", "건물주"], "투자자"),
    "land": ("토지 — 땅 투자 기초, 용도지역, 맹지, 개발제한구역, 토지거래허가, 지목",
             FORMAT + "마지막은 '땅 공부 같이 해요, 댓글로 질문!'. 특정 지역 호재 단정 금지.",
             "흥미로운 비밀을 알려 주듯 생생하게",
             ["토지투자", "땅투자", "부동산공부"], "투자자"),
    "auction": ("경매 · 공매 — 경매 절차, 권리분석(말소기준권리), 명도, 유찰, 공매(온비드)와 경매 차이",
                FORMAT + "마지막은 '경매 입문, 저장해 두세요!'. 어려운 용어는 한 번 더 쉬운 말로.",
                "차근차근 풀어 주듯 또렷하게",
                ["부동산경매", "경매", "공매"], "투자자"),
}
LABELS = {"subscription": "청약·전월세", "contract": "계약·매매 상식", "tax": "세금·정책",
          "commercial": "건물·상가", "land": "토지", "auction": "경매·공매"}
SLOTS = {
    "morning": ("아침 7시. 출근길에 폰으로 보는 직장인 · 내 집 마련 준비하는 사람들",
                {"subscription": 3, "contract": 2, "tax": 3, "commercial": 1, "land": 1, "auction": 2}),
    "noon": ("점심 12시. 점심시간에 잠깐 쉬며 보는 직장인들",
             {"subscription": 2, "contract": 2, "tax": 2, "commercial": 2, "land": 2, "auction": 2}),
    "evening": ("저녁 6시. 퇴근길에 재테크 공부하는 사람들",
                {"subscription": 2, "contract": 2, "tax": 2, "commercial": 2, "land": 2, "auction": 3}),
    "night": ("밤 9시. 집에서 여유 있게 부동산 공부하는 사람들 · 투자 관심층",
              {"subscription": 2, "contract": 1, "tax": 2, "commercial": 3, "land": 3, "auction": 3}),
}
BASE_TAGS = ["Shorts", "부지런", "부동산"]
# 유튜브 예약 공개 시각 (KST) — 사용자 11/20 결정 07:00 / 12:00 / 18:00 / 21:00
PUBLISH_TIMES = {"morning": (7, 0), "noon": (12, 0), "evening": (18, 0), "night": (21, 0)}
HORIZON = timedelta(hours=26)    # 이 시간 안에 공개될 회차만 미리 만듦
LEAD = timedelta(minutes=25)     # 1편 제작·업로드 여유
SECONDS = 40                     # 30~50초 목표
DISCLAIMER = ("※ 이 영상은 일반적인 부동산 정보이며 투자 · 세무 · 법률 자문이 아닙니다. "
              "제도와 세율은 바뀔 수 있으니 실제 결정 전 국토교통부 · 국세청 등 공식 자료와 전문가에게 꼭 확인하세요.")


def pick_category(slot: str, history: list[dict]) -> str:
    """시간대 비중대로 랜덤, 단 직전 영상과 같은 카테고리는 피하고 직전 두 편이 같은 대상(초보/투자자)이면 반대쪽으로."""
    weights = dict(SLOTS[slot][1])
    last = [h.get("category") for h in history[-2:] if h.get("category") in CATEGORIES]
    if last:
        weights.pop(last[-1], None)
    if len(last) == 2 and CATEGORIES[last[0]][4] == CATEGORIES[last[1]][4]:
        weights = {k: v for k, v in weights.items() if CATEGORIES[k][4] != CATEGORIES[last[1]][4]} or weights
    return random.choices(list(weights), weights=list(weights.values()))[0]


def current_slot(now: datetime) -> str:
    if 4 <= now.hour < 10:
        return "morning"
    if 10 <= now.hour < 15:
        return "noon"
    return "evening" if 15 <= now.hour < 19 else "night"


def load_history() -> list[dict]:
    return json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []


def pending_slots(now: datetime, history: list[dict]) -> list[tuple[str, datetime]]:
    """앞으로 HORIZON 안에 공개될 회차 중 아직 예약 업로드 안 된 것 (공개 시각 순)."""
    done = {h["publish_at"] for h in history if h.get("publish_at") and h.get("video_id")}
    todo = []
    for day in range(3):
        d = (now + timedelta(days=day)).date()
        for slot, (hh, mm) in PUBLISH_TIMES.items():
            at = datetime(d.year, d.month, d.day, hh, mm, tzinfo=KST)
            if at - now <= HORIZON and at.isoformat() not in done:
                todo.append((slot, at))
    todo.sort(key=lambda x: x[1])
    return [(slot, at) for i, (slot, at) in enumerate(todo) if at - now > LEAD * (i + 1)]


def run_once(slot: str, topic: str | None, upload: bool, privacy: str, category: str | None = None,
             publish_at: datetime | None = None) -> dict:
    from ideas import next_idea
    from script_writer import pick_topic, research, shape_idea, write_script
    from shorts_maker import make_shorts

    history = load_history()
    idea = None
    if not topic:
        idea = next_idea()
        if idea:
            shaped = shape_idea(PROFILE, idea["text"], {k: v[0] for k, v in CATEGORIES.items()})
            topic, category = shaped["topic"], category or shaped["category"]
            print(f"💡 디스코드 아이디어 사용: {idea['text'][:60]}")
    category = category or pick_category(slot, history)
    cat_desc, guide, tone, cat_tags, _ = CATEGORIES[category]
    if not topic:
        topic = pick_topic(PROFILE, f"{SLOTS[slot][0]}\n이번 카테고리: {cat_desc}", [h["topic"] for h in history])
    print(f"▶ [{slot}/{category}] 주제: {topic}")
    # 구글 검색 확인은 유료 Gemini 키에서만 됨 — 사용자 11/20 결정: 무료 유지(B) → 꺼 둠, 숫자 없이 원리 위주
    facts = research(f"{topic} ({LABELS[category]})") if os.environ.get("RESEARCH") == "1" else ""
    if facts:
        print("  확인된 사실:\n" + "\n".join("    " + x for x in facts.splitlines() if x.strip()))
    s = write_script(f"{topic}\n(채널 콘셉트: {PROFILE})\n(카테고리 지침: {guide})"
                     + (f"\n(확인된 사실 — 숫자는 여기 있는 것만, [불확실]은 숫자 빼고:\n{facts})" if facts else
                        "\n(최신 기준을 확인할 수 없음 — 세율·한도·금액·기간·금리 같은 구체적 숫자와 '올해 바뀐' 같은 시점 단정은 "
                        "쓰지 말고, 제도의 원리 · 따져 볼 점 · 흔한 실수 위주로. 숫자가 필요하면 '꼭 공식 자료로 확인하세요'로)"),
                     seconds=SECONDS)
    title, sentences = s["title"], s["sentences"]
    print(f"  제목: {title}\n" + "\n".join(f"  - {x}" for x in sentences) + "\n  장면: " + " / ".join(s.get("scenes") or []))

    now = datetime.now(KST)
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_")[:40]
    out = BASE / "output" / f"{now:%Y%m%d_%H%M}_{slot}_{safe}.mp4"
    out.parent.mkdir(exist_ok=True)
    # 장면 검색어 = "영어 | 다른 영어 표현 | 한국어" (stock_video 가 세 가지로 후보를 모아 고름)
    alts = s.get("scenes_alt") or []
    scenes = [" | ".join([q, *[a for a in (alts[i] if i < len(alts) and isinstance(alts[i], list) else [])
                               if isinstance(a, str) and a.strip()]])
              for i, q in enumerate(s.get("scenes") or [])]
    make_shorts("\n".join(sentences), out, title=title, scenes=scenes or None, tone=tone,
                label=f"부지런 · {LABELS[category]}", title_point=s.get("title_point") or "")

    record = {"date": now.isoformat(timespec="minutes"), "slot": slot, "category": category, "topic": topic,
              "title": title, "file": out.name, "video_id": None}
    if idea:
        record["idea"] = idea["text"][:200]
    if publish_at:
        record["publish_at"] = publish_at.isoformat()
    rec = finish(record, s, out, upload, privacy, publish_at, history, cat_tags)
    if idea and rec["video_id"]:  # 시험 제작(업로드 안 함)에선 ✅ 안 달아서 실제 회차에서 다시 쓰게
        from ideas import mark_used
        when = f"{publish_at:%m/%d %H:%M} 공개 예약" if publish_at else "바로 공개"
        mark_used(idea, f"이 아이디어로 만들었어요 → '{title}' ({when}) https://youtube.com/shorts/{rec['video_id']}")
    return rec


def finish(record: dict, s: dict, out, upload: bool, privacy: str, publish_at, history: list[dict],
           cat_tags: list[str]) -> dict:
    """업로드(선택) + 알림 + history 기록."""
    if upload:
        from alert import send
        from youtube_uploader import upload_video
        tags = [t.replace(" ", "").lstrip("#") for t in s.get("tags", [])][:8]
        hashtags = list(dict.fromkeys(["Shorts", "부동산"] + cat_tags[:2] + tags[:2]))
        desc = (f"{s.get('description', '')}\n\n" + "\n".join(s["sentences"])
                + "\n\n🏠 부지런한 사람이 집을 산다 — 부동산 지식을 매일 짧게, 부지런\n\n"
                + DISCLAIMER + "\n\n" + " ".join("#" + t for t in hashtags))
        record["video_id"] = upload_video(out, f"{s['title']} #Shorts", CHANNEL, description=desc,
                                          tags=list(dict.fromkeys(BASE_TAGS + cat_tags + tags)), privacy=privacy,
                                          publish_at=publish_at)
        when = f"{publish_at:%m/%d %H:%M} 공개 예약" if publish_at else "바로 공개"
        send(f"✅ {when} · [{LABELS.get(record['category'], '')}] {s['title']}\nhttps://youtube.com/shorts/{record['video_id']}")
    import stock_video  # 위에서 import하면 --plan(패키지 설치 전)이 requests 없어서 죽음
    record["clips"] = stock_video.take_picked()  # 다음 영상들이 같은 배경 클립을 안 쓰게
    history.append(record)
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def run_with_retry(**kw) -> dict | None:
    """실패 시 새 주제로 1번 더 시도 (Gemini 과부하·영상 검색 실패 등 일시적 오류 대비)."""
    for attempt in (1, 2):
        try:
            rec = run_once(**kw)
            print(f"✅ 완료: {rec}")
            return rec
        except SystemExit as e:
            if "토큰" in str(e) or "채널" in str(e):  # 로그인 문제는 재시도해도 소용없음
                raise
            print(f"⚠ {e}")
        except Exception:
            traceback.print_exc()
        print("⚠ 실패 → 재시도" if attempt == 1 else "❌ 2회 모두 실패")
    return None


def schedule():
    """예약 대기열 채우기. 하나가 실패해도 다음 회차는 계속 만들고, 실패가 있으면 마지막에 실패 처리."""
    todo = pending_slots(datetime.now(KST), load_history())
    if not todo:
        print("예약할 회차 없음 (이미 다 채워짐)")
        return
    print("만들 회차: " + ", ".join(f"{at:%m/%d %H:%M}({slot})" for slot, at in todo))
    failed = []
    for slot, at in todo:
        if at - datetime.now(KST) <= LEAD / 2:
            print(f"⏭ {at:%m/%d %H:%M} 공개 시각이 너무 가까워 건너뜀")
            failed.append(at)
            continue
        print(f"\n===== {at:%m/%d %H:%M} 공개 예약분 ({slot}) =====")
        if not run_with_retry(slot=slot, topic=None, upload=True, privacy="private", publish_at=at):
            failed.append(at)
        os.environ.pop("VOICE", None)  # 목소리 고정은 첫 편에만
    if failed:
        raise SystemExit("❌ 실패한 회차: " + ", ".join(f"{at:%m/%d %H:%M}" for at in failed))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--schedule", action="store_true", help="예약 대기열 채우기")
    p.add_argument("--plan", action="store_true", help="만들 회차 수만 출력")
    p.add_argument("--slot", choices=list(SLOTS))
    p.add_argument("--topic")
    p.add_argument("--category", choices=list(CATEGORIES))
    p.add_argument("--privacy", default="public", choices=["private", "unlisted", "public"])
    p.add_argument("--no-upload", action="store_true")
    a = p.parse_args()
    if a.plan:
        todo = pending_slots(datetime.now(KST), load_history())
        print(len(todo), " ".join(f"{at:%m/%d_%H:%M}" for _, at in todo))
        return
    if a.schedule:
        return schedule()
    slot = a.slot or current_slot(datetime.now(KST))
    if not run_with_retry(slot=slot, topic=a.topic, upload=not a.no_upload, privacy=a.privacy, category=a.category):
        raise SystemExit("❌ 2회 모두 실패")


if __name__ == "__main__":
    main()
