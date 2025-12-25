"""Communication problem preprocessor - single AI generation with validation."""

import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from AICodeforcer.api_logger import APILogger
from AICodeforcer.communication.agents.validator import ComponentValidator

load_dotenv()
_max_output_tokens: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
_max_retries: int = int(os.getenv("COMMUNICATION_PREPROCESSOR_RETRIES", "3"))

SEPARATOR = "===SEPARATOR==="

SYSTEM_PROMPT = """<role>
You are a problem setter for communication problems.
Generate generator, middleware, and verifier as a coherent set.
ALL CODE MUST BE IN PYTHON.
</role>

<generator-spec>
Generate small-scale random test data (n ≤ 6).
Output format:
1. Alice's input (graph info): t, then for each test case: n m, edges
2. Then output: ===ALICE_QUERY_SEPARATOR===
3. Query info: for each test case: q, then queries (v, permutation)

Example output:
2
4 3
1 2
2 3
3 4
3 3
1 2
2 3
1 3
===ALICE_QUERY_SEPARATOR===
2
2
1 2
3
1 2
1
3
1
</generator-spec>

<middleware-spec>
Input: alice_data + "===SEPARATOR===" + alice_output + "===SEPARATOR===" + query_data
Output: Bob's input (t, then for each test case: q, then for each query: d(v), color_string)
</middleware-spec>

<verifier-spec>
Input: alice_data + "===SEPARATOR===" + query_data + "===SEPARATOR===" + alice_output + "===SEPARATOR===" + bob_output
Output: "AC" or "WA: reason"
</verifier-spec>

<output-format>
CRITICAL: Use EXACTLY these markers:
```generator
# Python code here
```

```middleware
# Python code here
```

```verifier
# Python code here
```
</output-format>
"""


class CommunicationPreprocessor:
    """Single AI generation with validation."""

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

    def generate(
        self,
        problem_text: str,
        max_attempts: int = 10,
    ) -> tuple[str, str, str] | None:
        """Generate all components with AI validation."""
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=1.0,
            max_output_tokens=_max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level="high"),
        )

        prompt = f"""请为以下通讯题生成三个组件：

{problem_text}

用 ```generator、```middleware、```verifier 分别包裹。"""

        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        ]

        self._api_logger.init(prefix="comm_preprocessor", model=self.model)

        for attempt in range(max_attempts):
            print(f"\n[预处理] 生成组件 (尝试 {attempt + 1}/{max_attempts})...")

            response = self._call_api(contents, config)
            if not response or not response.candidates:
                continue

            candidate = response.candidates[0]
            if not candidate.content:
                continue

            response_text = ""
            for part in candidate.content.parts:
                if part.text:
                    response_text += part.text

            # 提取代码
            gen = self._extract_code(response_text, "generator")
            mid = self._extract_code(response_text, "middleware")
            ver = self._extract_code(response_text, "verifier")

            if not gen or not mid or not ver:
                missing = []
                if not gen: missing.append("generator")
                if not mid: missing.append("middleware")
                if not ver: missing.append("verifier")
                print(f"  缺少: {', '.join(missing)}")
                contents.append(candidate.content)
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=f"缺少 {', '.join(missing)}，请补充。")]
                ))
                continue

            print(f"  generator: {len(gen)} 字符")
            print(f"  middleware: {len(mid)} 字符")
            print(f"  verifier: {len(ver)} 字符")

            # AI 验证
            print("\n[验证] AI 检查组件...")
            validator = ComponentValidator(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
            )

            is_valid, issues = validator.validate(problem_text, gen, mid, ver)

            if is_valid:
                print("  验证通过!")
                self._api_logger.close()
                return gen, mid, ver

            print(f"  验证失败: {issues[:200]}...")
            contents.append(candidate.content)

            # 详细反馈，包含代码和问题
            fix_prompt = f"""验证发现以下问题：
{issues}

当前代码：

```generator
{gen}
```

```middleware
{mid}
```

```verifier
{ver}
```

请根据问题修复上述代码，不要全部重写，只修复有问题的部分。
输出修复后的完整代码，仍用 ```generator、```middleware、```verifier 包裹。"""

            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=fix_prompt)]
            ))

        print("[预处理] 生成失败")
        self._api_logger.close()
        return None

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

    def _extract_code(self, text: str, code_type: str) -> str | None:
        """Extract code block."""
        pattern = rf"```{re.escape(code_type)}[ \t]*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[-1].strip()
        return None
