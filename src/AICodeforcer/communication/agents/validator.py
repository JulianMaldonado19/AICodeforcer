"""Validator for communication problem components."""

import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from AICodeforcer.api_logger import APILogger

load_dotenv()
_max_output_tokens: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536"))

VALIDATOR_PROMPT = """<role>
You are a code reviewer for communication problem components.
</role>

<data-format>
Generator output: alice_data + "===ALICE_QUERY_SEPARATOR===" + query_data
Middleware input: alice_data + "===SEPARATOR===" + alice_output + "===SEPARATOR===" + query_data
Verifier input: alice_data + "===SEPARATOR===" + query_data + "===SEPARATOR===" + alice_output + "===SEPARATOR===" + bob_output
</data-format>

<task>
1. Check generator uses ===ALICE_QUERY_SEPARATOR=== correctly
2. Check middleware parses 3 parts with ===SEPARATOR===
3. Check verifier parses 4 parts with ===SEPARATOR===
4. Identify any bugs
</task>

<output-format>
If correct: VALID
If issues: INVALID: description
</output-format>
"""


class ComponentValidator:
    """Validates communication problem components."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.base_url = base_url or os.environ.get("GEMINI_BASE_URL")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

        if self.base_url:
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(base_url=self.base_url),
            )
        else:
            self.client = genai.Client(api_key=self.api_key)

        self._api_logger = APILogger()

    def validate(
        self,
        problem_text: str,
        generator_code: str,
        middleware_code: str,
        verifier_code: str,
    ) -> tuple[bool, str]:
        """Validate all components.

        Returns:
            (is_valid, issues) tuple
        """
        config = types.GenerateContentConfig(
            system_instruction=VALIDATOR_PROMPT,
            temperature=0.5,
            max_output_tokens=_max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level="high"),
        )

        prompt = f"""请验证以下通讯题的三个组件是否正确：

## 题目
{problem_text}

## 数据生成器
```python
{generator_code}
```

## 中间件
```python
{middleware_code}
```

## 验证器
```python
{verifier_code}
```

请检查：
1. 生成器是否生成符合题目约束的数据
2. 中间件是否正确转换 Alice 输出
3. 验证器是否正确判断答案

输出 VALID 或 INVALID: 问题描述"""

        contents = [types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )]

        self._api_logger.init(prefix="comm_validator", model=self.model)

        response = self._call_api(contents, config)
        if not response:
            self._api_logger.close()
            return False, "API 调用失败"

        result = self._extract_result(response)
        self._api_logger.close()

        if result.startswith("VALID"):
            return True, ""
        else:
            return False, result.replace("INVALID:", "").strip()

    def _call_api(self, contents, config):
        """Call API with retry."""
        for retry in range(10):
            try:
                self._api_logger.log_request(contents, config)
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                self._api_logger.log_response(response)
                return response
            except Exception as e:
                self._api_logger.log_response(None, error=str(e))
                if retry == 9:
                    return None
                time.sleep(3)
        return None

    def _extract_result(self, response) -> str:
        """Extract result from response."""
        if not response.candidates:
            return "INVALID: 无响应"
        candidate = response.candidates[0]
        if not candidate.content:
            return "INVALID: 无内容"

        text = ""
        for part in candidate.content.parts:
            if part.text:
                text += part.text

        # 查找 VALID 或 INVALID
        if "VALID" in text:
            if "INVALID" in text:
                idx = text.find("INVALID")
                return text[idx:idx+500]
            return "VALID"
        return "INVALID: 未知结果"
