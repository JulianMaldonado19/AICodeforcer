"""Generator agent for communication problems."""

import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from AICodeforcer.api_logger import APILogger

load_dotenv()
_max_output_tokens: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536"))

GENERATOR_PROMPT = """<role>
You are a test data generator specialist for competitive programming.
Your task is to generate random test data for communication problems.
</role>

<requirements>
  <item>Generate small-scale random data (n ≤ 6) for stress testing</item>
  <item>Use Python's random module</item>
  <item>Output to stdout</item>
  <item>Generate different data each run</item>
  <item>Cover edge cases</item>
</requirements>

<output-format>
  <rule>Wrap code with ```python and ```</rule>
  <rule>Code must be complete and self-contained</rule>
</output-format>
"""


class GeneratorAgent:
    """Generates test data generator for communication problems."""

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
        """Generate test data generator code."""
        config = types.GenerateContentConfig(
            system_instruction=GENERATOR_PROMPT,
            temperature=1.0,
            max_output_tokens=_max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level="high"),
        )

        prompt = f"""请为以下通讯题生成数据生成器：

{problem_text}

要求：生成小规模随机数据 (n ≤ 6)，用于对拍测试。"""

        contents = [types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )]

        self._api_logger.init(prefix="comm_generator", model=self.model)

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
