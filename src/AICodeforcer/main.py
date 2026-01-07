"""CLI entry point for the algorithm solver."""

import sys

from dotenv import load_dotenv

load_dotenv()


def print_solution(python_code: str | None, cpp_code: str | None, passed: bool) -> None:
    """打印解决方案（Python 和 C++ 两份代码）。"""
    print("\n" + "=" * 60)

    if passed and python_code:
        print("  对拍通过!")
        print("=" * 60)

        # 输出 Python 代码
        print("\n" + "=" * 60)
        print("  最终代码 (Python)")
        print("=" * 60)
        print(python_code)

        # 输出 C++ 代码
        if cpp_code:
            print("\n" + "=" * 60)
            print("  最终代码 (C++)")
            print("=" * 60)
            print(cpp_code)
        else:
            print("\n[注意] C++ 翻译失败，仅提供 Python 代码")
    else:
        print("  本轮求解未通过对拍")
        print("=" * 60)
        if python_code:
            print("\n当前代码 (Python):")
            print("-" * 40)
            print(python_code)
            print("-" * 40)

            if cpp_code:
                print("\n当前代码 (C++):")
                print("-" * 40)
                print(cpp_code)
                print("-" * 40)


def main() -> int:
    """Main entry point."""
    import os
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("错误: 请设置 GEMINI_API_KEY 环境变量")
        return 1

    print("=" * 60)
    print("  AICodeforcer - Gemini 算法题解 Agent")
    print("=" * 60)
    print()
    print("请选择模式:")
    print("  1. 标准算法题 (对拍验证)")
    print("  2. 交互题")
    print("  3. 通讯题")
    print("  4. Heavy模式 (多Agent探索)")
    print()

    try:
        choice = input("选择 (1/2/3/4): ").strip()
    except EOFError:
        return 0

    if choice == "1":
        return run_standard_solver(api_key)
    elif choice == "2":
        return run_interactive_solver(api_key)
    elif choice == "3":
        return run_communication_solver(api_key)
    elif choice == "4":
        return run_heavy_solver(api_key)
    else:
        print("无效选择")
        return 1


def run_standard_solver(api_key: str) -> int:
    """运行标准算法题求解器。"""
    from AICodeforcer.standard.agents import AlgorithmSolver

    print()
    print("=" * 60)
    print("  标准算法题模式")
    print("=" * 60)
    print()
    print("请粘贴完整的题目 (输入 END 结束):")
    print("-" * 60)

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    text = "\n".join(lines)

    if not text.strip():
        print("错误: 题目不能为空")
        return 1

    print("-" * 60)
    print("开始求解...")
    print("=" * 60)

    try:
        solver = AlgorithmSolver(api_key=api_key)

        def on_attempt(attempt: int, code: str) -> None:
            print(f"\n--- 尝试 #{attempt} ---")
            print("-" * 40)
            code_lines = code.split("\n")
            for line in code_lines[:30]:
                print(line)
            if len(code_lines) > 30:
                print(f"... ({len(code_lines) - 30} more lines)")
            print("-" * 40)

        solution, cpp_code, passed = solver.solve(text, max_attempts=100, on_attempt=on_attempt)

        while True:
            print_solution(solution, cpp_code, passed)

            print("\n" + "-" * 60)
            print("请输入提交结果反馈 (输入 AC/done/quit 结束):")
            print("  例如: TLE on test 5, WA on test 3, MLE, RE")
            print("-" * 60)

            try:
                feedback = input("> ").strip()
            except EOFError:
                print("\n已结束")
                break

            if not feedback:
                continue

            feedback_lower = feedback.lower()
            if feedback_lower in ("ac", "done", "quit", "exit", "q"):
                print("\n" + "=" * 60)
                print("  恭喜 AC!" if feedback_lower == "ac" else "  已结束")
                print("=" * 60)
                break

            print("\n" + "=" * 60)
            print(f"  收到反馈: {feedback}")
            print("  继续优化中...")
            print("=" * 60)

            solution, cpp_code, passed = solver.continue_solving(
                feedback=feedback,
                max_attempts=50,
                on_attempt=on_attempt,
            )

        return 0

    except KeyboardInterrupt:
        print("\n\n已取消")
        return 130

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_interactive_solver(api_key: str) -> int:
    """运行交互题求解器。"""
    from AICodeforcer.interactive.agents import InteractivePreprocessor, InteractiveSolver

    print()
    print("=" * 60)
    print("  交互题模式")
    print("=" * 60)
    print()
    print("请粘贴完整的交互题题目 (输入 END 结束):")
    print("-" * 60)

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    text = "\n".join(lines)

    if not text.strip():
        print("错误: 题目不能为空")
        return 1

    print("-" * 60)
    print("开始分析交互题...")
    print("=" * 60)

    try:
        # 阶段 1: 预处理 - 生成数据生成器和评测机
        print("\n[阶段 1] 生成数据生成器和评测机...")
        preprocessor = InteractivePreprocessor(api_key=api_key)
        result = preprocessor.generate(text, max_attempts=10)

        if not result:
            print("\n错误: 无法生成评测机和数据生成器")
            return 1

        generator_code, judge_code = result
        print("\n" + "=" * 60)
        print("  评测机和数据生成器生成成功!")
        print("=" * 60)

        # 阶段 2: 求解 - 生成交互代码并对拍验证
        print("\n[阶段 2] 开始求解交互题...")
        solver = InteractiveSolver(api_key=api_key)

        def on_attempt(attempt: int, code: str) -> None:
            print(f"\n--- 尝试 #{attempt} ---")
            print("-" * 40)
            code_lines = code.split("\n")
            for line in code_lines[:30]:
                print(line)
            if len(code_lines) > 30:
                print(f"... ({len(code_lines) - 30} more lines)")
            print("-" * 40)

        solution, cpp_code, passed = solver.solve(
            problem_text=text,
            generator_code=generator_code,
            judge_code=judge_code,
            max_attempts=50,
            on_attempt=on_attempt,
        )

        # 阶段 3: 输出和反馈循环
        while True:
            print_solution(solution, cpp_code, passed)

            print("\n" + "-" * 60)
            print("请输入提交结果反馈 (输入 AC/done/quit 结束):")
            print("  例如: TLE on test 5, WA on test 3, MLE, RE")
            print("-" * 60)

            try:
                feedback = input("> ").strip()
            except EOFError:
                print("\n已结束")
                break

            if not feedback:
                continue

            feedback_lower = feedback.lower()
            if feedback_lower in ("ac", "done", "quit", "exit", "q"):
                print("\n" + "=" * 60)
                print("  恭喜 AC!" if feedback_lower == "ac" else "  已结束")
                print("=" * 60)
                break

            print("\n" + "=" * 60)
            print(f"  收到反馈: {feedback}")
            print("  继续优化中...")
            print("=" * 60)

            solution, cpp_code, passed = solver.continue_solving(
                feedback=feedback,
                max_attempts=30,
                on_attempt=on_attempt,
            )

        return 0

    except KeyboardInterrupt:
        print("\n\n已取消")
        return 130

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_communication_solver(api_key: str) -> int:
    """运行通讯题求解器。"""
    from AICodeforcer.communication.agents.solver import CommunicationSolver

    print()
    print("=" * 60)
    print("  通讯题模式")
    print("=" * 60)
    print()
    print("请粘贴完整的通讯题题目 (输入 END 结束):")
    print("-" * 60)

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    text = "\n".join(lines)

    if not text.strip():
        print("错误: 题目不能为空")
        return 1

    print("-" * 60)
    print("开始分析通讯题...")
    print("=" * 60)

    try:
        solver = CommunicationSolver(api_key=api_key)

        def on_attempt(attempt: int, code: str) -> None:
            print(f"\n--- 尝试 #{attempt} ---")
            code_lines = code.split("\n")
            for line in code_lines[:20]:
                print(line)
            if len(code_lines) > 20:
                print(f"... ({len(code_lines) - 20} more lines)")

        solution, cpp_code, passed = solver.solve(text, max_attempts=50, on_attempt=on_attempt)

        print("\n" + "=" * 60)
        if passed and solution:
            print("  对拍通过!")
            print("=" * 60)
            print("\n最终代码 (Python):")
            print(solution)
            if cpp_code:
                print("\n" + "=" * 60)
                print("最终代码 (C++):")
                print(cpp_code)
        else:
            print("  本轮求解未通过对拍")
            print("=" * 60)
            if solution:
                print("\n当前代码:")
                print(solution)

        return 0

    except KeyboardInterrupt:
        print("\n\n已取消")
        return 130

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_heavy_solver(api_key: str) -> int:
    """运行Heavy模式求解器（多Agent探索）。"""
    from AICodeforcer.standard_heavy import HeavySolver

    print()
    print("=" * 60)
    print("  Heavy模式 - 多Agent探索")
    print("=" * 60)
    print()

    # 获取Agent数量
    try:
        num_agents_str = input("Agent数量 (默认3): ").strip()
        num_agents = int(num_agents_str) if num_agents_str else 3
    except (EOFError, ValueError):
        num_agents = 3

    print(f"\n将启动 {num_agents} 个Agent串行探索不同解法")
    print()
    print("请粘贴完整的题目 (输入 END 结束):")
    print("-" * 60)

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    text = "\n".join(lines)

    if not text.strip():
        print("错误: 题目不能为空")
        return 1

    print("-" * 60)
    print("开始Heavy模式求解...")
    print("=" * 60)

    try:
        solver = HeavySolver(api_key=api_key, num_agents=num_agents)

        def on_attempt(attempt: int, code: str) -> None:
            print(f"\n--- 尝试 #{attempt} ---")
            code_lines = code.split("\n")
            for line in code_lines[:20]:
                print(line)
            if len(code_lines) > 20:
                print(f"... ({len(code_lines) - 20} more lines)")

        def on_success(result) -> None:
            print("\n" + "=" * 60)
            print(f"  Agent {result.agent_id} 成功!")
            print("=" * 60)
            if result.python_code:
                print("\nPython代码:")
                print(result.python_code)
            if result.cpp_code:
                print("\nC++代码:")
                print(result.cpp_code)

        results, solvers = solver.solve(
            problem_text=text,
            max_attempts=100,
            on_attempt=on_attempt,
            on_success=on_success,
        )

        # 反馈循环
        while True:
            # 汇总结果
            print("\n" + "=" * 60)
            print("  Heavy模式结果汇总")
            print("=" * 60)
            successful = [r for r in results if r.success]
            print(f"成功: {len(successful)}/{len(results)} 个Agent")

            for r in results:
                status = "✓ 成功" if r.success else "✗ 失败"
                print(f"  Agent {r.agent_id}: {status}")

            print("\n" + "-" * 60)
            print("请输入提交结果反馈 (输入 AC/done/quit 结束):")
            print("-" * 60)

            try:
                feedback = input("> ").strip()
            except EOFError:
                break

            if not feedback:
                continue

            if feedback.lower() in ("ac", "done", "quit", "exit", "q"):
                print("\n" + "=" * 60)
                print("  恭喜 AC!" if feedback.lower() == "ac" else "  已结束")
                print("=" * 60)
                break

            print(f"\n[Heavy] 收到反馈: {feedback}")
            print("[Heavy] 所有Agent并行处理反馈中...")

            results = solver.continue_solving(
                feedback=feedback,
                solvers=solvers,
                max_attempts=50,
                on_attempt=on_attempt,
                on_success=on_success,
            )

        return 0

    except KeyboardInterrupt:
        print("\n\n已取消")
        return 130

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
