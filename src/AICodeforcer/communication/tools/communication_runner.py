"""Communication problem runner - two-pass execution for Alice/Bob problems."""

import time
from dataclasses import dataclass
from typing import Literal

from AICodeforcer.standard.tools.executor import execute_code

Verdict = Literal["AC", "WA", "PE", "TLE", "RE"]

# 分隔符，用于在 stdin 中分隔多个输入
SEPARATOR = "===SEPARATOR==="
# 分隔 Alice 输入和查询信息
ALICE_QUERY_SEPARATOR = "===ALICE_QUERY_SEPARATOR==="


@dataclass
class CommunicationResult:
    """Result of running a communication problem."""

    verdict: Verdict
    log: str
    time_ms: float
    alice_output: str | None = None
    bob_input: str | None = None
    bob_output: str | None = None
    error_message: str | None = None


def run_communication(
    solver_code: str,
    original_input: str,
    middleware_code: str,
    verifier_code: str,
    timeout_per_pass: float = 5.0,
) -> CommunicationResult:
    """Run a communication problem with two-pass execution.

    Args:
        solver_code: Python code for the solver (handles both Alice and Bob)
        original_input: Original test input data
        middleware_code: Python code that transforms Alice's output to Bob's input
        verifier_code: Python code that verifies the final answer
        timeout_per_pass: Timeout for each pass in seconds

    Returns:
        CommunicationResult with verdict, log, and intermediate outputs
    """
    log_lines: list[str] = []
    start_time = time.perf_counter()

    # 解析 original_input，分离 Alice 输入和查询信息
    if ALICE_QUERY_SEPARATOR in original_input:
        parts = original_input.split(ALICE_QUERY_SEPARATOR)
        alice_data = parts[0].strip()
        query_data = parts[1].strip() if len(parts) > 1 else ""
    else:
        alice_data = original_input
        query_data = ""

    # === Pass 1: Run Alice ===
    log_lines.append("=== Pass 1: Alice ===")
    alice_input = "first\n" + alice_data

    alice_result = execute_code(
        code=solver_code,
        stdin=alice_input,
        timeout_seconds=timeout_per_pass,
        memory_mb=256,
    )

    elapsed_alice = time.perf_counter() - start_time
    log_lines.append(f"[Alice] Input:\n{_truncate(alice_input, 500)}")

    if alice_result.status != "passed":
        log_lines.append(f"[Alice] Status: {alice_result.status}")
        log_lines.append(f"[Alice] Error: {alice_result.error_message}")
        return CommunicationResult(
            verdict=_status_to_verdict(alice_result.status),
            log="\n".join(log_lines),
            time_ms=elapsed_alice * 1000,
            error_message=f"Alice failed: {alice_result.error_message}",
        )

    alice_output = (alice_result.actual_output or "").strip()
    log_lines.append(f"[Alice] Output:\n{_truncate(alice_output, 500)}")

    if not alice_output:
        log_lines.append("[Alice] Error: Empty output")
        return CommunicationResult(
            verdict="WA",
            log="\n".join(log_lines),
            time_ms=elapsed_alice * 1000,
            alice_output=alice_output,
            error_message="Alice produced empty output",
        )

    # === Middleware: Transform Alice's output to Bob's input ===
    log_lines.append("\n=== Middleware ===")
    middleware_input = SEPARATOR.join([alice_data, alice_output, query_data])

    middleware_result = execute_code(
        code=middleware_code,
        stdin=middleware_input,
        timeout_seconds=timeout_per_pass,
        memory_mb=256,
    )

    elapsed_middleware = time.perf_counter() - start_time

    if middleware_result.status != "passed":
        log_lines.append(f"[Middleware] Status: {middleware_result.status}")
        log_lines.append(f"[Middleware] Error: {middleware_result.error_message}")
        return CommunicationResult(
            verdict="PE",
            log="\n".join(log_lines),
            time_ms=elapsed_middleware * 1000,
            alice_output=alice_output,
            error_message=f"Middleware failed: {middleware_result.error_message}",
        )

    bob_input = (middleware_result.actual_output or "").strip()
    log_lines.append(f"[Middleware] Bob's input:\n{_truncate(bob_input, 500)}")

    # === Pass 2: Run Bob ===
    log_lines.append("\n=== Pass 2: Bob ===")
    bob_full_input = "second\n" + bob_input

    bob_result = execute_code(
        code=solver_code,
        stdin=bob_full_input,
        timeout_seconds=timeout_per_pass,
        memory_mb=256,
    )

    elapsed_bob = time.perf_counter() - start_time
    log_lines.append(f"[Bob] Input:\n{_truncate(bob_full_input, 500)}")

    if bob_result.status != "passed":
        log_lines.append(f"[Bob] Status: {bob_result.status}")
        log_lines.append(f"[Bob] Error: {bob_result.error_message}")
        return CommunicationResult(
            verdict=_status_to_verdict(bob_result.status),
            log="\n".join(log_lines),
            time_ms=elapsed_bob * 1000,
            alice_output=alice_output,
            bob_input=bob_input,
            error_message=f"Bob failed: {bob_result.error_message}",
        )

    bob_output = (bob_result.actual_output or "").strip()
    log_lines.append(f"[Bob] Output:\n{_truncate(bob_output, 500)}")

    # === Verifier: Check the answer ===
    log_lines.append("\n=== Verifier ===")
    verifier_input = SEPARATOR.join([alice_data, query_data, alice_output, bob_output])

    verifier_result = execute_code(
        code=verifier_code,
        stdin=verifier_input,
        timeout_seconds=timeout_per_pass,
        memory_mb=256,
    )

    elapsed_total = time.perf_counter() - start_time

    if verifier_result.status != "passed":
        log_lines.append(f"[Verifier] Status: {verifier_result.status}")
        log_lines.append(f"[Verifier] Error: {verifier_result.error_message}")
        return CommunicationResult(
            verdict="PE",
            log="\n".join(log_lines),
            time_ms=elapsed_total * 1000,
            alice_output=alice_output,
            bob_input=bob_input,
            bob_output=bob_output,
            error_message=f"Verifier failed: {verifier_result.error_message}",
        )

    verdict_str = (verifier_result.actual_output or "").strip()
    log_lines.append(f"[Verifier] Result: {verdict_str}")

    # Parse verdict
    if verdict_str == "AC":
        return CommunicationResult(
            verdict="AC",
            log="\n".join(log_lines),
            time_ms=elapsed_total * 1000,
            alice_output=alice_output,
            bob_input=bob_input,
            bob_output=bob_output,
        )
    elif verdict_str.startswith("WA"):
        error_msg = verdict_str[3:].strip() if len(verdict_str) > 3 else "Wrong answer"
        return CommunicationResult(
            verdict="WA",
            log="\n".join(log_lines),
            time_ms=elapsed_total * 1000,
            alice_output=alice_output,
            bob_input=bob_input,
            bob_output=bob_output,
            error_message=error_msg,
        )
    else:
        return CommunicationResult(
            verdict="WA",
            log="\n".join(log_lines),
            time_ms=elapsed_total * 1000,
            alice_output=alice_output,
            bob_input=bob_input,
            bob_output=bob_output,
            error_message=f"Unknown verdict: {verdict_str}",
        )


def _status_to_verdict(status: str) -> Verdict:
    """Convert execution status to verdict."""
    if status == "timeout":
        return "TLE"
    elif status == "memory_exceeded":
        return "RE"
    elif status == "runtime_error":
        return "RE"
    else:
        return "RE"


def _truncate(text: str, max_len: int) -> str:
    """Truncate text if too long."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... (truncated, {len(text)} chars total)"
