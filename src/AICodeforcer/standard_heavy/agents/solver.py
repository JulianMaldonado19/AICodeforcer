"""Heavy algorithm solver agent with banned approaches support."""

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, TextIO

from dotenv import load_dotenv
from google import genai
from google.genai import types

from AICodeforcer.api_logger import APILogger
from AICodeforcer.standard.agents.brute_force import BruteForceGenerator
from AICodeforcer.standard.agents.cpp_translator import CppTranslator
from AICodeforcer.standard.tools import run_python_code, stress_test
from AICodeforcer.standard.tools.stress_test import _default_num_tests as STRESS_TEST_NUM
from AICodeforcer.standard_heavy.agents.approach_checker import (
    ApproachChecker,
    CheckResult,
    get_rewrite_limit,
)

load_dotenv()
_max_output_tokens: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
_api_max_retries: int = int(os.getenv("API_REQUEST_MAX_RETRIES", "30"))


@dataclass(frozen=True)
class SharedBrute:
    """Shared brute force resources for heavy mode."""
    brute_force_code: str
    generator_code: str


# Import standard prompt and tools
from AICodeforcer.standard.agents.solver import (
    SYSTEM_PROMPT as STANDARD_SYSTEM_PROMPT,
    TOOL_DECLARATIONS,
    TOOL_FUNCTIONS,
)

HEAVY_PROMPT_APPENDIX = """
<heavy-mode-requirements>
  <requirement name="APPROACH_SUMMARY" priority="critical">
    <instruction>Before your FIRST call to stress_test, you MUST output an APPROACH_SUMMARY block.</instruction>
    <format>
APPROACH_SUMMARY:
[完整描述你的做法]
END_APPROACH_SUMMARY
    </format>
  </requirement>

  <requirement name="Banned Approaches" priority="critical">
    <instruction>如果下方提供了禁止的做法，你绝对不准使用这些做法，也不准使用这些做法的变体或等价形式。</instruction>
    <instruction>你必须想出一个完全不同的算法思路。</instruction>
  </requirement>
</heavy-mode-requirements>
"""

HEAVY_SYSTEM_PROMPT = f"{STANDARD_SYSTEM_PROMPT}\n{HEAVY_PROMPT_APPENDIX}"


class HeavyAlgorithmSolver:
    """Gemini-powered algorithm solver with heavy-mode constraints.

    Supports banned approaches and APPROACH_SUMMARY extraction for
    multi-agent exploration of different solution strategies.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        log_dir: str | None = None,
        agent_id: int = 0,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("API key required. Set GEMINI_API_KEY environment variable.")

        self.base_url = base_url or os.environ.get("GEMINI_BASE_URL")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.agent_id = agent_id

        if self.base_url:
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(base_url=self.base_url),
            )
        else:
            self.client = genai.Client(api_key=self.api_key)

        self._contents: list[types.Content] = []
        self._config: types.GenerateContentConfig | None = None
        self._last_verified_code: str | None = None
        self._last_code: str | None = None

        # 日志功能
        self._log_dir = Path(log_dir) if log_dir else Path("logs")
        self._log_file: TextIO | None = None
        self._log_path: Path | None = None
        self._api_logger = APILogger(self._log_dir)

        # 暴力算法生成器（独立会话）
        self._brute_force_generator = BruteForceGenerator(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
        )
        self._brute_force_code: str | None = None
        self._generator_code: str | None = None

        # C++ 翻译器
        self._cpp_translator = CppTranslator(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
        )
        self._cpp_code: str | None = None

        # 思路去重检测器
        self._approach_checker = ApproachChecker(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
        )

    def _init_log(self, problem_text: str, session_dir: Path | None = None) -> None:
        """初始化日志文件。"""
        if session_dir is None:
            session_dir = APILogger.create_session(self._log_dir)

        self._log_path = session_dir / f"heavy_agent_{self.agent_id}.log"
        self._log_file = open(self._log_path, "w", encoding="utf-8")
        self._api_logger.init(prefix=f"heavy_agent_{self.agent_id}", model=self.model)

        self._log(f"{'='*80}")
        self._log(f"AICodeforcer Heavy Agent {self.agent_id} 求解日志")
        self._log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._log(f"模型: {self.model}")
        self._log(f"{'='*80}")
        self._log(f"\n{'='*80}")
        self._log("题目内容")
        self._log(f"{'='*80}")
        self._log(problem_text)
        self._log(f"{'='*80}\n")

    def _log(self, message: str) -> None:
        """写入日志。"""
        if self._log_file:
            self._log_file.write(message + "\n")
            self._log_file.flush()

    def _log_tool_call(self, func_name: str, func_args: dict, result: str) -> None:
        """记录工具调用详情。"""
        self._log(f"\n{'='*80}")
        self._log(f"工具调用: {func_name}")
        self._log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._log(f"{'='*80}")

        if func_name == "run_python_code":
            self._log("\n--- 代码 ---")
            self._log(func_args.get("code", ""))
            self._log("\n--- 输入 ---")
            self._log(func_args.get("test_input", ""))
        elif func_name == "stress_test":
            self._log("\n--- 优化算法代码 ---")
            self._log(func_args.get("solution_code", ""))

        self._log("\n--- 执行结果 ---")
        self._log(result)
        self._log(f"{'='*80}\n")

    def _log_response(self, turn: int, response_text: str) -> None:
        """记录模型响应。"""
        self._log(f"\n{'='*80}")
        self._log(f"Turn {turn} - 模型响应")
        self._log(f"{'='*80}")
        self._log(response_text)
        self._log(f"{'='*80}\n")

    def _close_log(self) -> None:
        """关闭日志文件。"""
        if self._log_file:
            self._log(f"\n{'='*80}")
            self._log(f"日志结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self._log(f"{'='*80}")
            self._log_file.close()
            self._log_file = None
            print(f"\n[Agent {self.agent_id}] 日志已保存到: {self._log_path}")
        self._api_logger.close()

    def _translate_to_cpp(self, python_code: str | None) -> str | None:
        """将 Python 代码翻译成 C++。"""
        if not python_code:
            return None
        cpp_code = self._cpp_translator.translate(python_code)
        if cpp_code:
            self._cpp_code = cpp_code
            self._log("\n--- C++ 翻译结果 ---")
            self._log(cpp_code)
        else:
            self._log("[翻译] C++ 翻译失败")
        return cpp_code

    def _extract_approach_summary(self, text: str) -> str | None:
        """从响应文本中提取 APPROACH_SUMMARY。"""
        if not text:
            return None
        match = re.search(
            r"APPROACH_SUMMARY:\s*(.*?)\s*END_APPROACH_SUMMARY",
            text,
            re.DOTALL,
        )
        if match:
            body = match.group(1).strip()
            return f"APPROACH_SUMMARY:\n{body}\nEND_APPROACH_SUMMARY"
        return None

    def _fallback_summary(self, text: str) -> str:
        """当无法提取结构化摘要时，使用退化策略。"""
        cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
        snippet = cleaned[:2000] if cleaned else "(empty response)"
        return f"APPROACH_SUMMARY:\n{snippet}\nEND_APPROACH_SUMMARY"

    def _extract_code(self, text: str) -> str | None:
        """从响应文本中提取 Python 代码。"""
        patterns = [
            r"```python\n(.*?)```",
            r"```py\n(.*?)```",
            r"```\n(.*?)```",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                return matches[-1].strip()
        return None

    def _build_initial_prompt(self, problem_text: str, banned_approaches: list[str]) -> str:
        """构建初始提示，包含禁止的思路。"""
        banned_block = ""
        if banned_approaches:
            banned_lines = "\n\n".join(
                f"禁止做法 {i + 1}:\n{summary}"
                for i, summary in enumerate(banned_approaches)
            )
            banned_block = f"""
<banned-approaches>
你不准使用以下做法：

{banned_lines}
</banned-approaches>
"""

        return f"""请解决以下算法题目：

{problem_text}
{banned_block}
要求：
1. 在你第一次调用 stress_test 之前，必须输出 APPROACH_SUMMARY 标签块
2. 必须调用 run_python_code 测试样例
3. 必须调用 stress_test 进行对拍验证
4. 必须看到 "STRESS TEST PASSED" 才算通过"""

    def solve(
        self,
        problem_text: str,
        max_attempts: int = 100,
        on_attempt: Callable[[int, str], None] | None = None,
        banned_approaches: list[str] | None = None,
        shared_brute: SharedBrute | None = None,
        on_first_stress_test: Callable[[str], None] | None = None,
        session_dir: Path | None = None,
        accepted_summaries: list[str] | None = None,
    ) -> tuple[str | None, str | None, bool]:
        """Solve with heavy-mode constraints.

        Args:
            problem_text: 题目描述
            max_attempts: 最大尝试轮次
            on_attempt: 每次生成代码时的回调
            banned_approaches: 禁止使用的思路列表
            shared_brute: 共享的暴力算法资源
            on_first_stress_test: 首次调用stress_test时的回调
            session_dir: 日志会话目录
            accepted_summaries: 已接受的思路列表（用于去重检测）

        Returns:
            (python_code, cpp_code, success) 元组
        """
        self._init_log(problem_text, session_dir)
        try:
            return self._solve_impl(
                problem_text=problem_text,
                max_attempts=max_attempts,
                on_attempt=on_attempt,
                banned_approaches=banned_approaches or [],
                shared_brute=shared_brute,
                on_first_stress_test=on_first_stress_test,
                accepted_summaries=accepted_summaries or [],
            )
        finally:
            self._close_log()

    def _solve_impl(
        self,
        problem_text: str,
        max_attempts: int,
        on_attempt: Callable[[int, str], None] | None,
        banned_approaches: list[str],
        shared_brute: SharedBrute | None,
        on_first_stress_test: Callable[[str], None] | None,
        accepted_summaries: list[str],
    ) -> tuple[str | None, str | None, bool]:
        """实际的求解逻辑。"""
        # 处理暴力算法资源
        if shared_brute:
            self._brute_force_code = shared_brute.brute_force_code
            self._generator_code = shared_brute.generator_code
            print(f"[Agent {self.agent_id}] 使用共享的暴力算法")
            self._log("[预处理] 使用共享的暴力算法和数据生成器")
        else:
            print(f"\n[Agent {self.agent_id}] 启动三重验证生成暴力算法...")
            self._log("[预处理] 开始三重验证生成暴力算法")
            brute_result = self._brute_force_generator.generate_with_consensus(
                problem_text, num_agents=3, validation_rounds=10,
            )
            if brute_result:
                self._brute_force_code, self._generator_code = brute_result
                self._log("[预处理] 暴力算法生成成功")
            else:
                print(f"[Agent {self.agent_id}] 警告：暴力算法生成失败")
                self._log("[预处理] 警告：暴力算法生成失败")
                self._brute_force_code = None
                self._generator_code = None

        # 记录禁止的思路
        if banned_approaches:
            self._log(f"\n[Heavy] 禁止使用 {len(banned_approaches)} 个思路:")
            for i, approach in enumerate(banned_approaches):
                self._log(f"\n--- 禁止思路 {i + 1} ---")
                self._log(approach)

        # 配置生成参数
        config = types.GenerateContentConfig(
            system_instruction=HEAVY_SYSTEM_PROMPT,
            tools=TOOL_DECLARATIONS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=1.0,
            max_output_tokens=_max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level="high"),
        )

        contents: list[types.Content] = []
        initial_prompt = self._build_initial_prompt(problem_text, banned_approaches)
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=initial_prompt)],
        ))

        # 状态变量
        last_code: str | None = None
        attempt_count = 0
        stress_test_passed = False
        verified_code: str | None = None
        first_stress_test_seen = False
        latest_summary: str | None = None  # 每轮尝试提取，避免漏掉
        rewrite_count = 0  # 思路重写次数
        rewrite_limit = get_rewrite_limit()  # 从环境变量获取重写上限

        # 主求解循环
        for turn in range(max_attempts):
            # API调用（带重试）
            response = None
            for retry in range(_api_max_retries):
                try:
                    self._api_logger.log_request(contents, config)
                    response = self.client.models.generate_content(
                        model=self.model, contents=contents, config=config,
                    )
                    self._api_logger.log_response(response)
                    break
                except Exception as e:
                    self._api_logger.log_response(None, error=str(e))
                    print(f"[Agent {self.agent_id}] Turn {turn + 1} 请求失败 (重试 {retry + 1}): {e}")
                    self._log(f"[Turn {turn + 1}] 请求失败: {e}")
                    if retry == _api_max_retries - 1:
                        raise
                    time.sleep(5)

            if not response:
                break

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                print(f"[Agent {self.agent_id}] Turn {turn + 1} 无响应内容")
                self._log(f"[Turn {turn + 1}] 无响应内容")
                break

            response_content = candidate.content
            contents.append(response_content)

            # 解析响应
            response_text = ""
            function_calls = []
            for part in response_content.parts:
                if part.text:
                    response_text += part.text
                if part.function_call:
                    function_calls.append(part.function_call)

            # 打印和记录
            print(f"\n{'='*60}")
            print(f"[Agent {self.agent_id}] Turn {turn + 1}")
            print("=" * 60)
            if response_text:
                preview = response_text[:1000] if len(response_text) > 1000 else response_text
                print(preview)
                if len(response_text) > 1000:
                    print(f"... (truncated, total {len(response_text)} chars)")
            self._log_response(turn + 1, response_text)

            # 提取代码
            code = self._extract_code(response_text)
            if code:
                last_code = code
                self._last_code = code
                attempt_count += 1
                if on_attempt:
                    on_attempt(attempt_count, code)

            # 每轮尝试提取摘要（避免漏掉前一轮的摘要）
            extracted = self._extract_approach_summary(response_text)
            if extracted:
                latest_summary = extracted

            # 检查完成标志
            if "ALL_TESTS_PASSED" in response_text and not function_calls:
                if stress_test_passed and verified_code:
                    print(f"\n[Agent {self.agent_id}] 对拍已通过，返回验证过的代码")
                    self._log("[程序化校验] 对拍已通过")
                    self._contents = contents
                    self._config = config
                    self._last_verified_code = verified_code
                    cpp_code = self._translate_to_cpp(verified_code)
                    return verified_code, cpp_code, True
                else:
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(
                            text="你声称 ALL_TESTS_PASSED，但系统未检测到对拍通过。请调用 stress_test 工具。"
                        )],
                    ))
                    continue

            # 处理工具调用
            if function_calls:
                print(f"\n[Agent {self.agent_id}] 工具调用: {len(function_calls)} 个")
                function_responses = []
                skip_tool_response_append = False  # 标志：是否跳过循环外的统一追加

                for fc in function_calls:
                    func_name = fc.name
                    func_args = dict(fc.args) if fc.args else {}

                    # 首次 stress_test 时进行去重检查
                    if func_name == "stress_test" and not first_stress_test_seen:
                        # 提取当前思路摘要
                        summary = latest_summary
                        if not summary:
                            summary = self._extract_approach_summary(response_text)
                        if not summary:
                            summary = self._fallback_summary(response_text)

                        # 如果有已接受的思路，进行去重检查
                        if accepted_summaries:
                            check_result = self._approach_checker.check(summary, accepted_summaries)
                            self._log(f"[Heavy] 去重检查结果: {'SAME' if check_result.is_same else 'DIFFERENT'}")
                            self._log(f"[Heavy] 原因: {check_result.reason}")

                            if check_result.is_same and rewrite_count < rewrite_limit:
                                # 思路相似，要求重写
                                rewrite_count += 1
                                print(f"[Agent {self.agent_id}] 思路与已有思路相似，要求重写 ({rewrite_count}/{rewrite_limit})")
                                self._log(f"[Heavy] 思路相似，要求重写 ({rewrite_count}/{rewrite_limit})")

                                rewrite_msg = f"""你的思路与已有思路本质相同，请换一个完全不同的算法思路。

相似原因: {check_result.reason}

要求：
1. 必须使用不同的算法范式（如果之前是DP，换成贪心/图论/数学等）
2. 不能只是常数优化或实现细节的改变
3. 重新输出 APPROACH_SUMMARY 描述你的新思路
4. 然后再调用 stress_test 验证"""

                                function_responses.append(types.Part.from_function_response(
                                    name=func_name,
                                    response={"result": f"REJECTED: 思路与已有思路相似，请换一个不同的算法思路。原因: {check_result.reason}"},
                                ))
                                # 为剩余的工具调用添加"被跳过"的响应
                                current_idx = function_calls.index(fc)
                                for remaining_fc in function_calls[current_idx + 1:]:
                                    function_responses.append(types.Part.from_function_response(
                                        name=remaining_fc.name,
                                        response={"result": "SKIPPED: 由于思路去重检查未通过，此工具调用被跳过"},
                                    ))
                                # 添加工具响应和重写要求到对话
                                contents.append(types.Content(role="user", parts=function_responses))
                                contents.append(types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text=rewrite_msg)],
                                ))
                                latest_summary = None  # 清空，等待新的摘要
                                skip_tool_response_append = True  # 已经添加过了，跳过循环外的统一追加
                                break  # 跳出工具调用循环，继续主循环

                            elif check_result.is_same:
                                # 达到重写上限，允许进入但标记
                                print(f"[Agent {self.agent_id}] 达到重写上限，允许进入（标记为重复思路）")
                                self._log("[Heavy] 达到重写上限，允许进入（标记为重复思路）")

                        # 思路通过检查，标记为已见并调用回调
                        first_stress_test_seen = True
                        self._log("[Heavy] 捕获 APPROACH_SUMMARY:")
                        self._log(summary)
                        print(f"[Agent {self.agent_id}] 捕获思路摘要")
                        if on_first_stress_test:
                            on_first_stress_test(summary)

                    # 处理 stress_test 参数注入
                    if func_name == "stress_test":
                        solution_code = func_args.get("solution_code", "")
                        if self._brute_force_code and self._generator_code:
                            func_args = {
                                "solution_code": solution_code,
                                "brute_force_code": self._brute_force_code,
                                "generator_code": self._generator_code,
                            }
                        else:
                            result = "Error: 暴力算法未生成，无法进行对拍验证"
                            self._log_tool_call(func_name, {"solution_code": solution_code}, result)
                            function_responses.append(types.Part.from_function_response(
                                name=func_name, response={"result": result},
                            ))
                            continue
                    elif func_name == "run_python_code":
                        allowed_keys = {"code", "test_input"}
                        func_args = {k: v for k, v in func_args.items() if k in allowed_keys}

                    # 执行工具
                    print(f"  - {func_name}")
                    if func_name in TOOL_FUNCTIONS:
                        try:
                            result = TOOL_FUNCTIONS[func_name](**func_args)
                        except Exception as e:
                            result = f"Error: {e}"
                    else:
                        result = f"Unknown function: {func_name}"

                    self._log_tool_call(func_name, func_args, result)

                    # 更新状态
                    if func_name == "stress_test" and "STRESS TEST PASSED" in result:
                        stress_test_passed = True
                        verified_code = func_args.get("solution_code")
                        print(f"    [Agent {self.agent_id}] 对拍通过!")
                    elif func_name == "stress_test" and "COUNTEREXAMPLE FOUND" in result:
                        stress_test_passed = False
                        verified_code = None
                        print(f"    [Agent {self.agent_id}] 发现反例")

                    # 打印结果预览
                    result_preview = result[:300] if len(result) > 300 else result
                    print(f"    结果: {result_preview}")

                    function_responses.append(types.Part.from_function_response(
                        name=func_name, response={"result": result},
                    ))

                # 添加工具响应到对话（如果没有被去重拒绝）
                if not skip_tool_response_append:
                    contents.append(types.Content(role="user", parts=function_responses))

                # 对拍通过则直接返回
                if stress_test_passed and verified_code:
                    print(f"\n[Agent {self.agent_id}] 对拍已通过 {STRESS_TEST_NUM} 次测试")
                    self._log(f"[程序化校验] 对拍已通过 {STRESS_TEST_NUM} 次测试")
                    self._contents = contents
                    self._config = config
                    self._last_verified_code = verified_code
                    cpp_code = self._translate_to_cpp(verified_code)
                    return verified_code, cpp_code, True
            else:
                # 无工具调用时提示继续
                if turn < max_attempts - 1:
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text="请继续。记住必须调用工具验证代码。")],
                    ))

        # 循环结束，返回最后的代码
        self._contents = contents
        self._config = config
        self._last_code = last_code
        cpp_code = self._translate_to_cpp(last_code)
        return last_code, cpp_code, False

    def continue_solving(
        self,
        feedback: str,
        max_attempts: int = 50,
        on_attempt: Callable[[int, str], None] | None = None,
    ) -> tuple[str | None, str | None, bool]:
        """根据用户反馈继续优化代码。"""
        if not self._contents or not self._config:
            raise RuntimeError("没有可继续的对话，请先调用 solve()")

        if self._log_path and not self._log_file:
            self._log_file = open(self._log_path, "a", encoding="utf-8")

        self._log(f"\n{'='*80}")
        self._log(f"[Agent {self.agent_id}] 继续优化 - 用户反馈")
        self._log(f"反馈内容: {feedback}")
        self._log("=" * 80 + "\n")

        try:
            return self._continue_impl(feedback, max_attempts, on_attempt)
        finally:
            self._close_log()

    def _continue_impl(
        self,
        feedback: str,
        max_attempts: int,
        on_attempt: Callable[[int, str], None] | None,
    ) -> tuple[str | None, str | None, bool]:
        """继续优化的实际逻辑。"""
        contents = self._contents
        config = self._config

        feedback_prompt = f"""用户提交代码后收到以下反馈：

{feedback}

请根据这个反馈分析问题原因，优化你的算法，然后：
1. 使用 run_python_code 测试样例
2. 使用 stress_test 进行对拍验证
3. 确保对拍通过后输出 "ALL_TESTS_PASSED" 和最终代码"""

        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=feedback_prompt)],
        ))

        last_code = self._last_code
        stress_test_passed = False
        verified_code: str | None = None

        for turn in range(max_attempts):
            response = None
            for retry in range(_api_max_retries):
                try:
                    self._api_logger.log_request(contents, config)
                    response = self.client.models.generate_content(
                        model=self.model, contents=contents, config=config,
                    )
                    self._api_logger.log_response(response)
                    break
                except Exception as e:
                    self._api_logger.log_response(None, error=str(e))
                    print(f"[Agent {self.agent_id}] 请求失败 (重试 {retry + 1}): {e}")
                    if retry == _api_max_retries - 1:
                        raise
                    time.sleep(5)

            if not response:
                break

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                break

            response_content = candidate.content
            contents.append(response_content)

            response_text = ""
            function_calls = []
            for part in response_content.parts:
                if part.text:
                    response_text += part.text
                if part.function_call:
                    function_calls.append(part.function_call)

            self._log_response(turn + 1, response_text)

            code = self._extract_code(response_text)
            if code:
                last_code = code
                self._last_code = code
                if on_attempt:
                    on_attempt(turn + 1, code)

            # 检查完成标志
            if "ALL_TESTS_PASSED" in response_text and not function_calls:
                if stress_test_passed and verified_code:
                    self._contents = contents
                    self._last_verified_code = verified_code
                    cpp_code = self._translate_to_cpp(verified_code)
                    return verified_code, cpp_code, True
                else:
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text="请调用 stress_test 验证。")],
                    ))
                    continue

            # 处理工具调用
            if function_calls:
                function_responses = []
                for fc in function_calls:
                    func_name = fc.name
                    func_args = dict(fc.args) if fc.args else {}

                    if func_name == "stress_test":
                        solution_code = func_args.get("solution_code", "")
                        if self._brute_force_code and self._generator_code:
                            func_args = {
                                "solution_code": solution_code,
                                "brute_force_code": self._brute_force_code,
                                "generator_code": self._generator_code,
                            }
                        else:
                            function_responses.append(types.Part.from_function_response(
                                name=func_name, response={"result": "Error: 暴力算法未生成"},
                            ))
                            continue
                    elif func_name == "run_python_code":
                        func_args = {k: v for k, v in func_args.items() if k in {"code", "test_input"}}

                    if func_name in TOOL_FUNCTIONS:
                        try:
                            result = TOOL_FUNCTIONS[func_name](**func_args)
                        except Exception as e:
                            result = f"Error: {e}"
                    else:
                        result = f"Unknown function: {func_name}"

                    self._log_tool_call(func_name, func_args, result)

                    if func_name == "stress_test" and "STRESS TEST PASSED" in result:
                        stress_test_passed = True
                        verified_code = func_args.get("solution_code")
                    elif func_name == "stress_test" and "COUNTEREXAMPLE" in result:
                        stress_test_passed = False
                        verified_code = None

                    function_responses.append(types.Part.from_function_response(
                        name=func_name, response={"result": result},
                    ))

                contents.append(types.Content(role="user", parts=function_responses))

                if stress_test_passed and verified_code:
                    self._contents = contents
                    self._last_verified_code = verified_code
                    cpp_code = self._translate_to_cpp(verified_code)
                    return verified_code, cpp_code, True
            else:
                if turn < max_attempts - 1:
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text="请继续。")],
                    ))

        self._contents = contents
        self._last_code = last_code
        cpp_code = self._translate_to_cpp(last_code)
        return last_code, cpp_code, False
