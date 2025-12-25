# AICodeforcer

Gemini-powered algorithm problem solver agent.

使用 Gemini AI 自动解决 Codeforces 等 OJ 平台的算法竞赛题目，支持自动对拍验证和 Python 转 C++ 翻译。

## 系统架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AICodeforcer                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐                  │
│  │   Standard  │    │ Interactive │    │  Communication  │                  │
│  │    Mode     │    │    Mode     │    │      Mode       │                  │
│  └──────┬──────┘    └──────┬──────┘    └────────┬────────┘                  │
│         │                  │                    │                            │
│         ▼                  ▼                    ▼                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐                  │
│  │   Solver    │    │ Preprocessor│    │  Preprocessor   │                  │
│  │   Agent     │    │   Agent     │    │     Agent       │                  │
│  └──────┬──────┘    └──────┬──────┘    └────────┬────────┘                  │
│         │                  │                    │                            │
│         │                  ▼                    ▼                            │
│         │           ┌─────────────┐    ┌─────────────────┐                  │
│         │           │   Solver    │    │     Solver      │                  │
│         │           │   Agent     │    │     Agent       │                  │
│         │           └──────┬──────┘    └────────┬────────┘                  │
│         │                  │                    │                            │
│         ▼                  ▼                    ▼                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐                  │
│  │ BruteForce  │    │   Stress    │    │     Stress      │                  │
│  │  Generator  │    │    Test     │    │      Test       │                  │
│  │ (3-way)     │    │             │    │                 │                  │
│  └──────┬──────┘    └──────┬──────┘    └────────┬────────┘                  │
│         │                  │                    │                            │
│         ▼                  ▼                    ▼                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐                  │
│  │   Stress    │    │     C++     │    │       C++       │                  │
│  │    Test     │    │  Translator │    │   Translator    │                  │
│  └──────┬──────┘    └─────────────┘    └─────────────────┘                  │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────┐                                                            │
│  │     C++     │                                                            │
│  │  Translator │                                                            │
│  └─────────────┘                                                            │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                           Shared Components                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Executor   │  │  API Logger │  │   Types     │  │    Tools    │        │
│  │  (Sandbox)  │  │             │  │             │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 功能特性

- **标准算法题模式**
  - 自动分析算法题目并生成解法
  - 三路共识暴力生成（3 个独立 Agent 必须一致）
  - 自动对拍验证（默认 1000 组随机测试）
  - 失败自动重试机制

- **交互题模式**
  - 自动生成评测机（Judge）和数据生成器
  - AI 验证评测机正确性
  - 交互式对拍验证（默认 100 组测试）

- **通讯题模式**
  - 支持 Alice/Bob 两阶段通讯问题
  - 自动生成中间件（Middleware）和验证器
  - 两阶段串行执行对拍验证（默认 100 组测试）

- **通用功能**
  - 使用沙箱环境执行代码测试
  - Python 代码自动翻译为竞赛风格 C++
  - 支持交互式反馈优化（TLE/WA/MLE/RE）
  - 完整 API 请求/响应日志记录

## 安装

```bash
# 克隆项目
git clone https://github.com/yourname/AICodeforcer.git
cd AICodeforcer

# 使用 uv 安装依赖
uv sync

# 或使用 pip
pip install -e .
```

## 配置

创建 `.env` 文件并配置：

```bash
# Gemini API 配置（必需）
GEMINI_API_KEY=your_api_key_here

# 可选配置
GEMINI_MODEL=gemini-2.5-flash          # 模型名称
GEMINI_BASE_URL=https://your-proxy.com # 自定义 API 地址
GEMINI_MAX_OUTPUT_TOKENS=65536         # 最大输出 token 数

# API 请求重试次数
API_REQUEST_MAX_RETRIES=30             # API 请求失败重试次数

# 对拍测试次数
STRESS_TEST_NUM=1000                   # 标准模式对拍次数
INTERACTIVE_STRESS_TEST_NUM=100        # 交互模式对拍次数
COMMUNICATION_STRESS_TEST_NUM=100      # 通讯题模式对拍次数

# 重试配置
BRUTE_FORCE_CONSENSUS_RETRIES=3        # 三路共识失败重试次数
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `GEMINI_API_KEY` | - | **必需** Gemini API 密钥 |
| `GEMINI_MODEL` | `gemini-2.5-flash` | 使用的模型名称 |
| `GEMINI_BASE_URL` | - | 自定义 API 地址（代理） |
| `GEMINI_MAX_OUTPUT_TOKENS` | `65536` | 单次请求最大输出 token |
| `API_REQUEST_MAX_RETRIES` | `30` | API 请求失败重试次数 |
| `STRESS_TEST_NUM` | `1000` | 标准模式对拍测试次数 |
| `INTERACTIVE_STRESS_TEST_NUM` | `100` | 交互模式对拍测试次数 |
| `COMMUNICATION_STRESS_TEST_NUM` | `100` | 通讯题模式对拍测试次数 |
| `BRUTE_FORCE_CONSENSUS_RETRIES` | `3` | 三路共识失败重试次数 |

## 使用方法

```bash
# 运行
aicodeforcer

# 或
python -m AICodeforcer.main
```

运行后选择模式：
1. **标准算法题** - 对拍验证模式
2. **交互题** - 交互式评测模式
3. **通讯题** - Alice/Bob 两阶段模式

然后：
1. 粘贴完整的题目内容
2. 输入 `END` 结束输入
3. 等待 AI 分析、编写代码、对拍验证
4. 获得 Python + C++ 双份代码
5. 提交后输入反馈（如 `TLE on test 5`）继续优化
6. 输入 `AC` 或 `quit` 结束

## 项目结构

```
src/AICodeforcer/
├── main.py                # CLI 入口
├── types.py               # 类型定义
├── api_logger.py          # API 日志记录器
├── standard/              # 标准算法题模块
│   ├── agents/
│   │   ├── solver.py      # 算法求解 Agent
│   │   ├── brute_force.py # 三路共识暴力生成
│   │   └── cpp_translator.py
│   └── tools/
│       ├── executor.py    # 沙箱代码执行器
│       ├── run_python.py  # 代码执行工具
│       └── stress_test.py # 对拍验证工具
└── interactive/           # 交互题模块
    ├── agents/
    │   ├── solver.py      # 交互题求解 Agent
    │   ├── preprocessor.py # 评测机生成器
    │   └── judge_validator.py
    └── tools/
        ├── interaction_runner.py    # IPC 通信管理
        └── interactive_stress_test.py
└── communication/         # 通讯题模块
    ├── agents/
    │   ├── solver.py      # 通讯题求解 Agent
    │   └── preprocessor.py # 中间件/验证器生成
    └── tools/
        ├── communication_runner.py  # 两阶段执行器
        └── stress_test.py           # 通讯题对拍
```

## 日志

每次运行会在 `logs/` 下创建时间戳文件夹：

```
logs/20251224_165001/
├── solve.log              # 普通日志
├── solve_full.log         # 完整 API 日志
├── brute_force_full.log   # 暴力生成日志
└── brute_force_agent*_full.log
```

## 工作流程

### 1. 标准算法题模式 (Standard Mode)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Standard Algorithm Solver                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. Problem Analysis (题意分析)                                           │
│     ├─ Restate problem in own words                                      │
│     ├─ Identify input/output format                                      │
│     └─ Build mathematical model                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  2. Algorithm Design (算法设计)                                           │
│     ├─ Propose 2-3 candidate approaches                                  │
│     ├─ Analyze time/space complexity                                     │
│     └─ Select optimal approach with proof                                │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  3. Code Implementation (代码实现)                                        │
│     ├─ Write Python solution                                             │
│     ├─ Use run_python_code tool to test                                  │
│     └─ Verify with sample cases                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  4. Brute Force Generation (暴力生成) - 3-Way Consensus                   │
│     ┌─────────────────────────────────────────────────────────────────┐  │
│     │  ┌─────────┐    ┌─────────┐    ┌─────────┐                      │  │
│     │  │ Agent 1 │    │ Agent 2 │    │ Agent 3 │  (Parallel)          │  │
│     │  └────┬────┘    └────┬────┘    └────┬────┘                      │  │
│     │       │              │              │                            │  │
│     │       ▼              ▼              ▼                            │  │
│     │  ┌─────────┐    ┌─────────┐    ┌─────────┐                      │  │
│     │  │ Code 1  │    │ Code 2  │    │ Code 3  │                      │  │
│     │  └────┬────┘    └────┬────┘    └────┬────┘                      │  │
│     │       └──────────────┼──────────────┘                            │  │
│     │                      ▼                                           │  │
│     │              ┌──────────────┐                                    │  │
│     │              │  Consensus?  │                                    │  │
│     │              │ (All Same?)  │                                    │  │
│     │              └──────┬───────┘                                    │  │
│     │                     │                                            │  │
│     │         ┌───────────┴───────────┐                                │  │
│     │         ▼                       ▼                                │  │
│     │    [Yes: Pass]           [No: Retry]                             │  │
│     └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  5. Stress Test (对拍验证) - Default 1000 tests                          │
│     ┌─────────────────────────────────────────────────────────────────┐  │
│     │  for i in range(1000):                                          │  │
│     │      test_data = brute_force.generate_random_input()            │  │
│     │      expected = brute_force.solve(test_data)                    │  │
│     │      actual = optimized.solve(test_data)                        │  │
│     │      if expected != actual:                                     │  │
│     │          return FAILED with counterexample                      │  │
│     │  return PASSED                                                  │  │
│     └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                    [PASSED]             [FAILED]
                          │                   │
                          ▼                   ▼
┌─────────────────────────────┐    ┌─────────────────────────┐
│  6. C++ Translation         │    │  Analyze counterexample │
│     Python → C++            │    │  Fix and retry          │
└─────────────────────────────┘    └─────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  7. Feedback Loop (反馈优化)                                              │
│     User submits to OJ → Gets feedback (TLE/WA/MLE/RE)                   │
│     → AI analyzes and optimizes → Repeat until AC                        │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2. 交互题模式 (Interactive Mode)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Interactive Problem Solver                         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 1: Preprocessing (预处理阶段)                                      │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  InteractivePreprocessor Agent                                     │  │
│  │     ├─ Analyze interaction protocol                                │  │
│  │     ├─ Generate Judge (评测机)                                      │  │
│  │     │    └─ Reads test data from file                              │  │
│  │     │    └─ Interacts via stdin/stdout                             │  │
│  │     │    └─ Returns: 0=AC, 1=WA, 2=PE                              │  │
│  │     └─ Generate Data Generator (数据生成器)                         │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 2: Judge Validation (评测机验证)                                   │
│     JudgeValidator Agent verifies judge correctness                      │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 3: Solution Development (解法开发)                                 │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  InteractiveSolver Agent                                           │  │
│  │     ├─ Analyze query strategy (Binary Search / Divide & Conquer)   │  │
│  │     ├─ Estimate query count upper bound                            │  │
│  │     ├─ Write interactive solution with flush=True                  │  │
│  │     └─ Handle -1 error responses                                   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 4: Interactive Stress Test (交互对拍) - Default 100 tests         │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  for i in range(100):                                              │  │
│  │      test_data = generator.generate()                              │  │
│  │      ┌─────────────┐         ┌─────────────┐                       │  │
│  │      │   Judge     │ ◄─────► │   Solver    │  (IPC Communication)  │  │
│  │      │  (stdin)    │         │  (stdout)   │                       │  │
│  │      └─────────────┘         └─────────────┘                       │  │
│  │      if judge.exit_code != 0: return FAILED                        │  │
│  │  return PASSED                                                     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 5: C++ Translation + Feedback Loop                                │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3. 通讯题模式 (Communication Mode)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      Communication Problem Solver                         │
│                        (Alice & Bob Protocol)                             │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 1: Preprocessing (预处理阶段)                                      │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  CommunicationPreprocessor Agent generates:                        │  │
│  │     ├─ Data Generator (数据生成器)                                  │  │
│  │     ├─ Middleware (中间件) - transforms Alice output → Bob input   │  │
│  │     └─ Verifier (验证器) - checks final answer correctness         │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 2: Solution Development (解法开发)                                 │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  CommunicationSolver Agent writes single file handling both phases │  │
│  │                                                                    │  │
│  │  def main():                                                       │  │
│  │      phase = input()  # "first" or "second"                        │  │
│  │      if phase == "first":                                          │  │
│  │          solve_alice()  # Process original input                   │  │
│  │      else:                                                         │  │
│  │          solve_bob()    # Process transformed input                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 3: Two-Phase Execution (两阶段执行)                                │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │  │
│  │  │  Original   │───►│   Solver    │───►│   Alice     │            │  │
│  │  │   Input     │    │  (Alice)    │    │   Output    │            │  │
│  │  └─────────────┘    └─────────────┘    └──────┬──────┘            │  │
│  │                                               │                    │  │
│  │                                               ▼                    │  │
│  │                                        ┌─────────────┐            │  │
│  │                                        │ Middleware  │            │  │
│  │                                        │ (Transform) │            │  │
│  │                                        └──────┬──────┘            │  │
│  │                                               │                    │  │
│  │                                               ▼                    │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │  │
│  │  │   Final     │◄───│   Solver    │◄───│    Bob      │            │  │
│  │  │   Answer    │    │   (Bob)     │    │   Input     │            │  │
│  │  └─────────────┘    └─────────────┘    └─────────────┘            │  │
│  │                                                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 4: Communication Stress Test (通讯对拍) - Default 100 tests       │
│     Verifier checks: Final Answer == Expected Answer                     │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Phase 5: C++ Translation + Feedback Loop                                │
└──────────────────────────────────────────────────────────────────────────┘
```

## 依赖

- Python >= 3.10
- google-genai >= 1.0.0
- pydantic >= 2.0
- python-dotenv >= 1.2.1

---

## Ethical Declaration | 诚信宣言 | 君子之約

### English

> *The sword forged for the training hall shall not be drawn where honor hangs in the balance.*

This project exists as a crucible for learning — to witness the elegant dance of algorithms, to comprehend the silent poetry woven into logic. It is a mirror, not a mask; a teacher, not a surrogate.

To wield it in competition is to claim a crown of smoke, for victory without struggle is but the shadow of triumph. The laurels earned through borrowed wisdom shall wither before they are worn.

**Let your mind be the true solver. Let this tool be merely the whetstone upon which you sharpen your own blade.**

### 中文

> *习武之剑，不可执于论道之堂；练兵之器，不可持于争锋之场。*

此项目为学习而生——让你得以窥见算法的曼妙之舞，领悟逻辑深处的无声诗篇。它是一面镜子，而非一张面具；是一位导师，而非替身。

若以此器竞于赛场，所摘不过是烟云编织的桂冠。不经磨砺的胜利，不过是荣耀的倒影。借来的智慧所铸的勋章，未及佩戴便已黯然失色。

**愿君以心为剑，以此为砺石，磨砺属于自己的锋芒。**

### 文言

> *器者，習藝之資也，非爭勝之具也。*

此器之造，為明算理、窮邏輯之奧也。若持以赴試，竊人之功為己有，是欺世盜名之行，君子所不齒也。

古人云：「學如逆水行舟，不進則退。」又云：「君子務本，本立而道生。」

夫以械代心，猶飲鴆止渴，雖解一時之困，終貽無窮之患。所得者，虛名也；所失者，真學也。名可欺人，學不可欺己。

**願諸君以誠為本，以學為先。器可助學，不可代學；技可借鑒，不可竊取。慎之戒之。**

---

## License

MIT
