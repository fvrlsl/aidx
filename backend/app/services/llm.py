"""LLM 抽取：把一条素材（标题 + 摘要）抽取成结构化依据草稿。

配置了 LLM_API_KEY 时走 OpenAI 兼容协议；否则用关键词规则 mock，保证离线也能跑通整条管道。
"""

import json
import re
from datetime import date

import httpx

from app.config import settings

SYSTEM_PROMPT = """你是一个劳动权益信息分析助手。给你一条关于某企业的公开信息（标题、来源、摘要），请抽取：
1. merchants: 文中涉及的企业/品牌名列表（只列主体，不列人名）
2. dimension: 所属维度，取值 pay(薪酬与保障)/hours(工时与休假)/dignity(尊严与文化)/disputes(争议与处罚)/none(与员工待遇无关)
3. polarity: 1 表示对员工有利的正面信息，-1 表示负面
4. impact: 影响程度，1 为一般，2 为重大（如全员分红、大规模欠薪、行政处罚）
5. event_date: 事件日期 YYYY-MM-DD，未知则 null
6. summary: 不超过 80 字的中性事实摘要，不含个人姓名
7. confidence: 0-1 的置信度
只输出 JSON，不要任何其他文字。"""

RULES: list[tuple[str, str, int, int]] = [
    # pattern, dimension, polarity, impact
    (r"欠薪|拖欠工资|拒不支付劳动报酬|克扣", "pay", -1, 2),
    (r"未缴社保|不交社保|社保断缴|社保违规", "pay", -1, 2),
    (r"分红|全员持股|资产分配|涨薪|加薪|奖金", "pay", 1, 2),
    (r"不裁员|稳岗|员工福利|带薪", "pay", 1, 1),
    (r"强制加班|996|超时加班|猝死|过劳", "hours", -1, 2),
    (r"7小时工作|缩短工时|强制下班|不加班|带薪休假|带薪年假|双休", "hours", 1, 2),
    (r"辱骂|体罚|羞辱|跪|扇|侮辱性", "dignity", -1, 2),
    (r"尊重员工|员工赋权|委屈奖|申诉|反形式主义|尊重", "dignity", 1, 1),
    (r"行政处罚|劳动仲裁|违法|立案|通报|黑名单|失信", "disputes", -1, 2),
    (r"杰出雇主|最佳雇主|雇主品牌|诚信之星|文明单位", "dignity", 1, 1),
]

DATE_RE = re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})")


def _mock_extract(title: str, summary: str, known_names: list[str]) -> dict:
    text = f"{title}\n{summary or ''}"
    dim, pol, imp, matched = "none", 0, 1, False
    for pattern, d, p, i in RULES:
        if re.search(pattern, text):
            dim, pol, imp, matched = d, p, i, True
            break
    merchants = [n for n in known_names if n and n in text]
    m = DATE_RE.search(text)
    event_date = None
    if m:
        try:
            event_date = date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            event_date = None
    return {
        "merchants": merchants,
        "dimension": dim,
        "polarity": pol,
        "impact": imp,
        "event_date": event_date,
        "summary": (summary or title)[:80],
        "confidence": 0.75 if matched and merchants else (0.4 if matched else 0.2),
        "provider": "mock",
    }


def extract(title: str, summary: str | None, publisher: str | None, known_names: list[str]) -> dict:
    if not settings.llm_api_key:
        return _mock_extract(title, summary or "", known_names)

    user_prompt = f"标题：{title}\n来源：{publisher or '未知'}\n摘要：{summary or '（无）'}"
    body = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=60) as client:
        r = client.post(
            f"{settings.llm_api_base.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=body,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
    content = content.strip().removeprefix("```json").removesuffix("```").strip()
    data = json.loads(content)
    data.setdefault("merchants", [])
    data.setdefault("dimension", "none")
    data.setdefault("polarity", 0)
    data.setdefault("impact", 1)
    data.setdefault("confidence", 0.5)
    data["provider"] = settings.llm_model
    return data
