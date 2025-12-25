"""C++ translator agent for converting Python to competitive programming style C++."""

import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
_max_output_tokens: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
_api_max_retries: int = int(os.getenv("API_REQUEST_MAX_RETRIES", "30"))

CPP_TRANSLATOR_PROMPT = """<role>
You are a senior C++ Competitive Programming contestant. Your task is to translate the input Python algorithm code into a specific "competitive programming personal template style" C++ code.
</role>

<style-guidelines>
  <guideline name="Header Template" priority="must-be-exact">
    <description>The code must start with the following template exactly (do not modify):</description>
    <template language="cpp">
#include &lt;bits/stdc++.h&gt;
#define ranges std::ranges
#define views std::views
using u32 = unsigned;
using i64 = long long;
using u64 = unsigned long long;
using u128 = unsigned __int128;
using i128 = __int128;
using a2 = std::array&lt;int, 2&gt;;
using a3 = std::array&lt;int, 3&gt;;
using a4 = std::array&lt;int, 4&gt;;
constexpr int N = 2e5 + 5;
constexpr int MAXN = 2e5 + 5;
constexpr int inf = 1e9;
constexpr i64 mod = 998244353;
    </template>
  </guideline>

  <guideline name="Namespace Rule" priority="critical">
    <forbidden>using namespace std;</forbidden>
    <rule>All standard library types and functions must use std:: prefix</rule>
    <exception>ranges:: and views:: are allowed (defined as macros in template)</exception>
    <examples>
      <correct>std::vector, std::string, std::cin, std::cout, std::sort, std::map</correct>
      <correct>ranges::sort(v), views::iota(0, n)</correct>
      <wrong>vector, string, cin, cout, sort, map</wrong>
    </examples>
  </guideline>

  <guideline name="Type Replacements">
    <replacement from="long long" to="i64"/>
    <replacement from="unsigned long long" to="u64"/>
    <replacement from="unsigned int" to="u32"/>
    <replacement from="__int128 (signed)" to="i128"/>
    <replacement from="__int128 (unsigned)" to="u128"/>
    <note>a2/a3/a4 are std::array types, use index access [0], [1], [2] instead of .first/.second</note>
    <note>When translating pair/tuple, convert .first to [0], .second to [1], etc.</note>
  </guideline>

  <guideline name="Container and Algorithm Operations">
    <rule>Use std:: prefix for all operations</rule>
    <rule>Use ranges:: or views:: (defined macros) when appropriate</rule>
    <examples>
      <correct>std::sort(v.begin(), v.end())</correct>
      <correct>ranges::sort(v)</correct>
      <correct>v.emplace_back(x)</correct>
      <correct>v.push_back(x)</correct>
    </examples>
  </guideline>

  <guideline name="Input Logic" priority="critical">
    <forbidden-patterns>
      <pattern>if (!(std::cin &gt;&gt; ...))</pattern>
      <pattern>if (std::cin.fail())</pattern>
      <pattern>Any form of input checking or defensive code</pattern>
    </forbidden-patterns>
    <correct-patterns>
      <pattern name="Reading variables">directly `std::cin &gt;&gt; n;`, no checks</pattern>
      <pattern name="Multiple test cases">
int t;std::cin &gt;&gt; t;
while(t--) solve();
      </pattern>
      <pattern name="Single test case">directly `std::cin &gt;&gt; n;` then process</pattern>
    </correct-patterns>
  </guideline>

  <guideline name="Main Function Template">
    <description>The `main` function must start with IO acceleration:</description>
    <template language="cpp">
std::ios::sync_with_stdio(false);
std::cin.tie(nullptr);
    </template>
    <rule>Encapsulate the main logic in a `void solve()` function</rule>
    <rule>`main` function only handles IO acceleration and calling `solve`</rule>
  </guideline>

  <guideline name="Code Format Style" priority="critical">
    <rule name="Brace Style">K&amp;R style - opening brace `{` on the same line as function/loop declaration</rule>
    <rule name="Compactness">Compact style - multiple short statements can be on one line separated by semicolons</rule>
    <rule name="Minimal Whitespace">Minimize blank lines, no extra spacing</rule>
    <rule name="Naming">Use short variable names (n, m, t, ans, res, dp, vis, adj)</rule>
    <examples>
      <correct>int main() {</correct>
      <correct>for (int i = 0; i &lt; n; i++) {</correct>
      <correct>int n, m;std::cin &gt;&gt; n &gt;&gt; m;</correct>
      <wrong>int main()\n{</wrong>
    </examples>
  </guideline>

  <guideline name="No Comments" priority="critical">
    <forbidden>// single line comments</forbidden>
    <forbidden>/* block comments */</forbidden>
    <forbidden>Any form of comments or explanations in the code</forbidden>
    <rule>Output pure code only, no documentation</rule>
  </guideline>
</style-guidelines>

<output-format>
  <rule>Only output C++ code, no explanations or descriptions</rule>
  <rule>Code wrapped in ```cpp</rule>
  <rule>Must output complete code, no truncation allowed</rule>
  <rule>No comments allowed - code must contain zero // or /* */ markers</rule>
</output-format>

<reference-example>
Below is a complete example of the expected output style:

```cpp
#include &lt;bits/stdc++.h&gt;
#define ranges std::ranges
#define views std::views
using u32 = unsigned;
using i64 = long long;
using u64 = unsigned long long;
using u128 = unsigned __int128;
using i128 = __int128;
using a2 = std::array&lt;int, 2&gt;;
using a3 = std::array&lt;int, 3&gt;;
using a4 = std::array&lt;int, 4&gt;;
constexpr int N = 2e5 + 5;
constexpr int MAXN = 2e5 + 5;
constexpr int inf = 1e9;
constexpr i64 mod = 998244353;

void solve() {
    int n, m;std::cin &gt;&gt; n &gt;&gt; m;
    std::vector&lt;int&gt; a(n);
    for (int i = 0; i &lt; n; i++) std::cin &gt;&gt; a[i];
    i64 ans = 0;
    for (int i = 0; i &lt; n; i++) {
        for (int j = i + 1; j &lt; n; j++) {
            ans += a[i] * a[j];
        }
    }
    std::cout &lt;&lt; ans &lt;&lt; "\n";
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    int t;std::cin &gt;&gt; t;
    while (t--) solve();
    return 0;
}
```
</reference-example>
"""


class CppTranslator:
    """将 Python 算法代码翻译成 C++ 竞赛风格代码。"""

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

    def translate(self, python_code: str) -> str | None:
        """将 Python 代码翻译成 C++ 竞赛风格代码。

        Args:
            python_code: Python 源代码

        Returns:
            C++ 代码，失败返回 None
        """
        print("\n" + "=" * 60)
        print("  翻译 Python -> C++")
        print("=" * 60)

        config = types.GenerateContentConfig(
            system_instruction=CPP_TRANSLATOR_PROMPT,
            temperature=1.0,
            max_output_tokens=_max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level="high"),
        )

        user_prompt = f"""```python
{python_code}
```"""

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
                print(f"[翻译] 请求失败 (重试 {retry + 1}/{_api_max_retries}): {e}")
                if retry == _api_max_retries - 1:
                    print("[翻译] 翻译失败")
                    return None
                time.sleep(5)

        if not response:
            return None

        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content:
            print("[翻译] 无响应内容")
            return None

        response_text = ""
        for part in candidate.content.parts:
            if part.text:
                response_text += part.text

        if not response_text.strip():
            print("[翻译] 无有效输出")
            return None

        # 提取 C++ 代码
        cpp_code = self._extract_cpp_code(response_text)

        if not cpp_code:
            print("[翻译] 未能提取 C++ 代码")
            return None

        print(f"[翻译] 成功 ({len(cpp_code)} 字符)")
        return cpp_code

    def _extract_cpp_code(self, text: str) -> str | None:
        """从响应文本中提取 C++ 代码并移除注释。

        Args:
            text: 响应文本

        Returns:
            提取的 C++ 代码，失败返回 None
        """
        patterns = [
            r"```cpp\s*\n(.*?)```",
            r"```c\+\+\s*\n(.*?)```",
            r"```\s*\n(.*?)```",
        ]

        code = None
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                code = matches[0].strip()
                break

        if not code and "#include" in text:
            code = text.strip()

        if code:
            code = self._remove_comments(code)

        return code

    def _remove_comments(self, code: str) -> str:
        """移除 C++ 代码中的所有注释。

        Args:
            code: C++ 源代码

        Returns:
            移除注释后的代码
        """
        result = []
        i = 0
        in_string = False
        string_char = None

        while i < len(code):
            if not in_string:
                if code[i] == '"' or code[i] == "'":
                    in_string = True
                    string_char = code[i]
                    result.append(code[i])
                elif code[i:i+2] == '//':
                    while i < len(code) and code[i] != '\n':
                        i += 1
                    continue
                elif code[i:i+2] == '/*':
                    i += 2
                    while i < len(code) - 1 and code[i:i+2] != '*/':
                        i += 1
                    i += 2
                    continue
                else:
                    result.append(code[i])
            else:
                result.append(code[i])
                if code[i] == '\\' and i + 1 < len(code):
                    i += 1
                    result.append(code[i])
                elif code[i] == string_char:
                    in_string = False
            i += 1

        return ''.join(result)
