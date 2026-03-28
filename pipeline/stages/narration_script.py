"""Stage 3b — Narration script generation.

Generates a three-part narration script (part1 / pivot / part2) from coaching
text using Gemini. The pivot line is always overridden with the fixed Japanese
string regardless of what Gemini returns.
"""

from google import genai

from backend.core.settings import settings
from pipeline.stages.db_helpers import (
    get_session_with_dish,
    update_session_fields,
)
from pipeline.utils import parse_json_response

PIVOT_LINE = "動画を使ってそのポイントを見てみましょう"

_REQUIRED_KEYS = {"part1", "pivot", "part2"}


def run_narration_script(session_id: int, coaching_text: dict) -> dict:
    """Generate narration script for the coaching video.

    Returns:
        dict with keys: part1 (str), pivot (str — always PIVOT_LINE), part2 (str)
    """
    session, dish = get_session_with_dish(session_id)

    prompt = f"""あなたは料理コーチです。以下のコーチングテキストと料理情報をもとに、
コーチング動画のナレーション台本を日本語で作成してください。

【料理】
{dish.name_ja}（{dish.name_en}）

【コーチングテキスト】
- 問題点: {coaching_text.get("mondaiten", "")}
- スキル: {coaching_text.get("skill", "")}
- 次のアクション: {coaching_text.get("next_action", "")}
- 成功のサイン: {coaching_text.get("success_sign", "")}

台本は以下の3パートに分けてください（合計約90秒）:
- part1: 約60秒。挨拶と今回の調理の振り返り・診断。問題点とその理由を丁寧に説明する。
- pivot: 動画への誘導フレーズ（1文）。
- part2: 約30秒。次回の練習に向けた具体的なアドバイスと励ましのメッセージ。

以下のJSON形式で返してください（コードブロック不要）:
{{"part1": "...", "pivot": "...", "part2": "..."}}"""

    gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = gemini_client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )
    narration = parse_json_response(response.text or "")

    # Always override pivot with the fixed canonical string.
    narration["pivot"] = PIVOT_LINE

    missing = _REQUIRED_KEYS - narration.keys()
    if missing:
        raise ValueError(
            f"Narration script response missing required keys: {missing}. Got: {list(narration.keys())}"
        )

    update_session_fields(session_id, narration_script=narration)
    return narration
