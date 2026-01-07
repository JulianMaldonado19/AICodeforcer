"""Approach similarity checker using LLM."""

import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
_max_output_tokens: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
_api_max_retries: int = int(os.getenv("API_REQUEST_MAX_RETRIES", "30"))
_approach_rewrite_limit: int = int(os.getenv("APPROACH_REWRITE_LIMIT", "2"))

CHECKER_PROMPT = """<role>
你是算法思路去重审查员。你的任务是判断一个候选思路是否与已有思路列表中的任何一个"本质相同"。
</role>

<判断依据>
以下情况视为"本质相同"（SAME）：
1. 算法范式相同（如都是DP、都是贪心、都是图论最短路等）
2. 核心不变量/关键转化一致
3. 只是常数优化（卡常）而非复杂度级别的改变
4. 数据结构不同但核心思想相同
5. 实现细节不同但算法框架相同

以下情况视为"本质不同"（DIFFERENT）：
1. 算法范式完全不同（如一个是DP，一个是贪心）
2. 复杂度级别不同（如一个是O(n^2)，一个是O(n log n)，且不是简单的常数优化）
3. 核心不变量/关键转化明显不同
4. 解决问题的角度完全不同
</判断依据>

<输出格式>
严格按以下格式输出，不要有其他内容：

RESULT: SAME 或 DIFFERENT
REASON: 简短理由（一句话）
MATCH: 如果SAME，写出最相似的已有思路编号（从1开始）；如果DIFFERENT，写NONE
</输出格式>"""


@dataclass
class CheckResult:
    """Result of approach similarity check."""
    is_same: bool
    reason: str
    match_index: int | None  # 1-based index, None if different


class ApproachChecker:
    """LLM-based approach similarity checker."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("API key required.")

        self.base_url = base_url or os.environ.get("GEMINI_BASE_URL")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

        if self.base_url:
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(base_url=self.base_url),
            )
        else:
            self.client = genai.Client(api_key=self.api_key)

    def check(
        self,
        candidate_summary: str,
        existing_summaries: list[str],
    ) -> CheckResult:
        """Check if candidate approach is similar to any existing approach.

        Args:
            candidate_summary: The new approach summary to check
            existing_summaries: List of already accepted approach summaries

        Returns:
            CheckResult with is_same, reason, and match_index
        """
        if not existing_summaries:
            return CheckResult(is_same=False, reason="无已有思路", match_index=None)

        existing_block = "\n\n".join(
            f"已有思路 {i + 1}:\n{summary}"
            for i, summary in enumerate(existing_summaries)
        )

        user_prompt = f"""<已有思路列表>
{existing_block}
</已有思路列表>

<候选思路>
{candidate_summary}
</候选思路>

请判断候选思路是否与已有思路列表中的任何一个本质相同。"""

        config = types.GenerateContentConfig(
            system_instruction=CHECKER_PROMPT,
            temperature=0.3,
            max_output_tokens=512,
        )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_prompt)],
            )
        ]

        response = None
        for retry in range(_api_max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as e:
                print(f"[ApproachChecker] 请求失败 (重试 {retry + 1}): {e}")
                if retry == _api_max_retries - 1:
                    return CheckResult(
                        is_same=False,
                        reason=f"检测失败: {e}",
                        match_index=None,
                    )
                time.sleep(3)

        if not response:
            return CheckResult(is_same=False, reason="无响应", match_index=None)

        return self._parse_response(response)

    def _parse_response(self, response) -> CheckResult:
        """Parse LLM response into CheckResult."""
        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content:
            return CheckResult(is_same=False, reason="无响应内容", match_index=None)

        text = ""
        for part in candidate.content.parts:
            if part.text:
                text += part.text

        text = text.strip()
        lines = text.split("\n")

        is_same = False
        reason = ""
        match_index = None

        for line in lines:
            line = line.strip()
            if line.startswith("RESULT:"):
                result_str = line.replace("RESULT:", "").strip().upper()
                is_same = result_str == "SAME"
            elif line.startswith("REASON:"):
                reason = line.replace("REASON:", "").strip()
            elif line.startswith("MATCH:"):
                match_str = line.replace("MATCH:", "").strip()
                if match_str.upper() != "NONE":
                    try:
                        match_index = int(match_str)
                    except ValueError:
                        pass

        return CheckResult(is_same=is_same, reason=reason, match_index=match_index)


def get_rewrite_limit() -> int:
    """Get the approach rewrite limit from environment."""
    return _approach_rewrite_limit
