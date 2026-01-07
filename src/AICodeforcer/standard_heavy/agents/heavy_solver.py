"""Heavy mode coordinator with pipeline parallelism."""

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from AICodeforcer.api_logger import APILogger
from AICodeforcer.standard.agents.brute_force import BruteForceGenerator
from AICodeforcer.standard_heavy.agents.solver import HeavyAlgorithmSolver, SharedBrute


@dataclass
class AgentResult:
    """Result from a single agent."""
    agent_id: int
    python_code: str | None
    cpp_code: str | None
    success: bool
    approach_summary: str


class HeavySolver:
    """Coordinator with pipeline parallelism.

    When Agent N's first stress_test is triggered, Agent N+1 starts immediately.
    All agents run in parallel after being triggered.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        log_dir: str | None = None,
        num_agents: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.log_dir = Path(log_dir) if log_dir else Path("logs")
        self.num_agents = num_agents

        self._brute_force_generator = BruteForceGenerator(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
        )

    def _build_shared_brute(self, problem_text: str) -> SharedBrute | None:
        """生成共享的暴力算法资源。"""
        print("\n" + "=" * 60)
        print("  Heavy Mode: 生成共享暴力算法")
        print("=" * 60)

        brute_result = self._brute_force_generator.generate_with_consensus(
            problem_text, num_agents=3, validation_rounds=10,
        )
        if not brute_result:
            print("[Heavy] 警告：暴力算法生成失败")
            return None

        brute_force_code, generator_code = brute_result
        print("[Heavy] 暴力算法生成成功")
        return SharedBrute(
            brute_force_code=brute_force_code,
            generator_code=generator_code,
        )

    def solve(
        self,
        problem_text: str,
        max_attempts: int = 100,
        on_attempt: Callable[[int, str], None] | None = None,
        on_success: Callable[[AgentResult], None] | None = None,
    ) -> tuple[list[AgentResult], list[HeavyAlgorithmSolver]]:
        """Run agents with pipeline parallelism.

        Agent N+1 starts when Agent N's first stress_test is triggered.

        Returns:
            (results, solvers) 元组，solvers 用于后续 continue_solving
        """
        session_dir = APILogger.create_session(self.log_dir)
        print(f"[Heavy] 日志目录: {session_dir}")

        shared_brute = self._build_shared_brute(problem_text)

        # 线程安全的共享状态
        lock = threading.Lock()
        banned_approaches: list[str] = []
        results: list[AgentResult] = [None] * self.num_agents  # type: ignore
        solvers: list[HeavyAlgorithmSolver | None] = [None] * self.num_agents
        threads: list[threading.Thread] = []
        next_agent_started = [False] * self.num_agents  # 防止重复启动

        def start_next_agent(current_id: int):
            """启动下一个Agent（如果还有的话）。"""
            next_id = current_id + 1
            if next_id >= self.num_agents:
                return
            with lock:
                if next_agent_started[next_id]:
                    return
                next_agent_started[next_id] = True
            # 在新线程中启动下一个Agent
            t = threading.Thread(target=run_agent, args=(next_id,), daemon=True)
            threads.append(t)
            t.start()

        def run_agent(agent_id: int):
            """运行单个Agent。"""
            # 获取当前禁止的思路快照和已接受的思路快照
            with lock:
                current_banned = banned_approaches.copy()
                current_accepted = banned_approaches.copy()  # 已接受的思路用于去重检测

            print("\n" + "=" * 60)
            print(f"  Heavy Mode: 启动 Agent {agent_id}")
            print(f"  禁止思路数量: {len(current_banned)}")
            print("=" * 60)

            summary_holder = {"summary": None}

            def on_first_stress_test(summary: str):
                summary_holder["summary"] = summary
                # 添加到禁止列表
                with lock:
                    banned_approaches.append(summary)
                # 启动下一个Agent
                start_next_agent(agent_id)

            solver = HeavyAlgorithmSolver(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                log_dir=str(self.log_dir),
                agent_id=agent_id,
            )
            solvers[agent_id] = solver  # 保存solver以便后续continue

            python_code, cpp_code, success = solver.solve(
                problem_text=problem_text,
                max_attempts=max_attempts,
                on_attempt=on_attempt,
                banned_approaches=current_banned,
                shared_brute=shared_brute,
                on_first_stress_test=on_first_stress_test,
                session_dir=session_dir,
                accepted_summaries=current_accepted,
            )

            # 构建结果
            summary = summary_holder["summary"] or "APPROACH_SUMMARY:\n(未捕获)\nEND_APPROACH_SUMMARY"
            result = AgentResult(
                agent_id=agent_id,
                python_code=python_code,
                cpp_code=cpp_code,
                success=success,
                approach_summary=summary,
            )
            results[agent_id] = result

            if success:
                print(f"\n[Heavy] Agent {agent_id} 成功!")
                if on_success:
                    on_success(result)
            else:
                print(f"\n[Heavy] Agent {agent_id} 未通过对拍")

        # 启动 Agent 0
        next_agent_started[0] = True
        thread0 = threading.Thread(target=run_agent, args=(0,), daemon=True)
        threads.append(thread0)
        thread0.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 过滤掉None结果
        valid_results = [r for r in results if r is not None]
        valid_solvers = [s for s in solvers if s is not None]
        return valid_results, valid_solvers

    def continue_solving(
        self,
        feedback: str,
        solvers: list[HeavyAlgorithmSolver],
        max_attempts: int = 50,
        on_attempt: Callable[[int, str], None] | None = None,
        on_success: Callable[[AgentResult], None] | None = None,
    ) -> list[AgentResult]:
        """并行让所有Agent根据反馈继续优化。"""
        lock = threading.Lock()
        results: list[AgentResult] = [None] * len(solvers)  # type: ignore
        threads: list[threading.Thread] = []

        def run_continue(idx: int, solver: HeavyAlgorithmSolver):
            print(f"\n[Heavy] Agent {idx} 开始处理反馈...")
            python_code, cpp_code, success = solver.continue_solving(
                feedback=feedback,
                max_attempts=max_attempts,
                on_attempt=on_attempt,
            )
            result = AgentResult(
                agent_id=idx,
                python_code=python_code,
                cpp_code=cpp_code,
                success=success,
                approach_summary="",
            )
            with lock:
                results[idx] = result
            if success and on_success:
                on_success(result)

        for idx, solver in enumerate(solvers):
            t = threading.Thread(target=run_continue, args=(idx, solver), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        return [r for r in results if r is not None]
