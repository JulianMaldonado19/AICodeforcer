"""Verifier agent for communication problems."""

import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from AICodeforcer.api_logger import APILogger

load_dotenv()
_max_output_tokens: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536"))

SEPARATOR = "===SEPARATOR==="

VERIFIER_PROMPT = """<role>
You are a verifier specialist for communication problems.
Your task is to verify if the final answer is correct.
</role>

<input-format>
Read from stdin: original_input + "===SEPARATOR===" + alice_output + "===SEPARATOR===" + bob_output
</input-format>

<output-format>
Output "AC" if correct, "WA: reason" if wrong.
Wrap code with ```python and ```
</output-format>
"""


class VerifierAgent:
    """Generates verifier for communication problems."""

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

    def generate(self, problem_text: str) -> str | None:
        """Generate verifier code."""
        config = types.GenerateContentConfig(
            system_instruction=VERIFIER_PROMPT,
            temperature=1.0,
            max_output_tokens=_max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level="high"),
        )

        prompt = f"""请为以下通讯题生成验证器：

{problem_text}

验证器读取: original_input + "===SEPARATOR===" + alice_output + "===SEPARATOR===" + bob_output
输出 "AC" 或 "WA: 原因"。"""

        contents = [types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )]

        self._api_logger.init(prefix="comm_verifier", model=self.model)

        response = self._call_api(contents, config)
        if not response:
            self._api_logger.close()
            return None

        code = self._extract_code(response)
        self._api_logger.close()
        return code

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

    def _extract_code(self, response) -> str | None:
        """Extract code from response."""
        if not response.candidates:
            return None
        candidate = response.candidates[0]
        if not candidate.content:
            return None

        text = ""
        for part in candidate.content.parts:
            if part.text:
                text += part.text

        pattern = r"```python\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return matches[-1].strip() if matches else None
