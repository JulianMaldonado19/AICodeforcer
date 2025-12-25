"""Communication problem stress test tool."""

import os

from dotenv import load_dotenv

from AICodeforcer.communication.tools.communication_runner import run_communication
from AICodeforcer.standard.tools.executor import execute_code

load_dotenv()

_LOG_MAX_CHARS = 3500
_default_num_tests: int = int(os.getenv("COMMUNICATION_STRESS_TEST_NUM", "100"))


def _truncate_log(log: str, max_chars: int = _LOG_MAX_CHARS) -> str:
    """Truncate log if too long, preserving key sections."""
    if len(log) <= max_chars:
        return log

    lines = log.splitlines()

    # Find section markers
    sections = {"Alice": [], "Middleware": [], "Bob": [], "Verifier": []}
    current_section = None

    for i, line in enumerate(lines):
        if "=== Pass 1: Alice ===" in line:
            current_section = "Alice"
        elif "=== Middleware ===" in line:
            current_section = "Middleware"
        elif "=== Pass 2: Bob ===" in line:
            current_section = "Bob"
        elif "=== Verifier ===" in line:
            current_section = "Verifier"

        if current_section:
            sections[current_section].append(line)

    # Build truncated output
    output = ["=== LOG TRUNCATED ===", f"Original: {len(log)} chars", ""]

    for section_name in ["Alice", "Middleware", "Bob", "Verifier"]:
        section_lines = sections[section_name]
        if section_lines:
            # Keep first 5 and last 5 lines of each section
            if len(section_lines) <= 10:
                output.extend(section_lines)
            else:
                output.extend(section_lines[:5])
                output.append(f"... ({len(section_lines) - 10} lines omitted) ...")
                output.extend(section_lines[-5:])
            output.append("")

    result = "\n".join(output)

    # Final hard truncation
    if len(result) > max_chars:
        result = result[:max_chars] + "\n...(truncated)..."

    return result


def communication_stress_test(
    solver_code: str,
    generator_code: str,
    middleware_code: str,
    verifier_code: str,
    num_tests: int = _default_num_tests,
) -> str:
    """Run stress test for communication problem.

    Args:
        solver_code: Python code for the solver (handles both Alice and Bob)
        generator_code: Python code that generates test input data
        middleware_code: Python code that transforms Alice's output to Bob's input
        verifier_code: Python code that verifies the final answer
        num_tests: Number of test cases to run

    Returns:
        "AC" if all tests pass, otherwise error message with details
    """
    print(f"\n[通讯题对拍] 开始 {num_tests} 组测试...")

    progress_parts = []
    progress_interval = max(1, num_tests // 10)
    for i in range(num_tests):
        # 每 1/10 输出进度
        if i > 0 and i % progress_interval == 0:
            progress_parts.append(f"[{i}/{num_tests}] ✓")
            print(f"[{i}/{num_tests}] ✓", end="", flush=True)
        # Generate test input
        gen_result = execute_code(
            code=generator_code,
            stdin="",
            timeout_seconds=5.0,
            memory_mb=256,
        )

        if gen_result.status != "passed":
            return (
                f"生成器执行失败 (测试 {i + 1}/{num_tests})\n"
                f"状态: {gen_result.status}\n"
                f"错误: {gen_result.error_message or 'Unknown'}"
            )

        test_input = (gen_result.actual_output or "").strip()
        if not test_input:
            return f"生成器输出为空 (测试 {i + 1}/{num_tests})"

        # Run communication problem
        result = run_communication(
            solver_code=solver_code,
            original_input=test_input,
            middleware_code=middleware_code,
            verifier_code=verifier_code,
            timeout_per_pass=5.0,
        )

        # Check result
        if result.verdict != "AC":
            # 先换行避免与进度输出粘连
            if progress_parts:
                print()
            print(f"  [{i + 1}/{num_tests}] ✗ {result.verdict}")
            error_details = [
                f"测试 {i + 1}/{num_tests} 失败",
                f"判定: {result.verdict}",
                f"错误: {result.error_message or 'Unknown'}",
                "",
                "=== 测试输入 ===",
                test_input[:500] + ("..." if len(test_input) > 500 else ""),
                "",
            ]

            if result.alice_output is not None:
                error_details.extend([
                    "=== Alice 输出 ===",
                    result.alice_output[:500] + ("..." if len(result.alice_output) > 500 else ""),
                    "",
                ])

            if result.bob_input is not None:
                error_details.extend([
                    "=== Bob 输入 (Middleware 输出) ===",
                    result.bob_input[:500] + ("..." if len(result.bob_input) > 500 else ""),
                    "",
                ])

            if result.bob_output is not None:
                error_details.extend([
                    "=== Bob 输出 ===",
                    result.bob_output[:500] + ("..." if len(result.bob_output) > 500 else ""),
                    "",
                ])

            error_details.extend([
                "=== 详细日志 ===",
                _truncate_log(result.log),
            ])

            return "\n".join(error_details)

    # 结束后换行
    if progress_parts:
        print()
    print(f"\n[通讯题对拍] 全部 {num_tests} 组测试通过!")
    return "AC"
