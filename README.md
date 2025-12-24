# AICodeforcer

Gemini-powered algorithm problem solver agent.

使用 Gemini AI 自动解决 Codeforces 等 OJ 平台的算法竞赛题目，支持自动对拍验证和 Python 转 C++ 翻译。

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

# 对拍测试次数
STRESS_TEST_NUM=1000                   # 标准模式对拍次数
INTERACTIVE_STRESS_TEST_NUM=100        # 交互模式对拍次数

# 重试配置
BRUTE_FORCE_CONSENSUS_RETRIES=3        # 暴力生成失败重试次数
```

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

1. **题意分析** - AI 重述题目，建立数学模型
2. **算法设计** - 提出候选方案，分析复杂度
3. **代码实现** - 编写 Python 解法
4. **样例测试** - 运行题目给出的样例
5. **暴力生成** - 三路共识生成暴力算法（3 个 Agent 必须一致）
6. **对拍验证** - 暴力算法 vs 优化算法，1000 组随机测试
7. **代码翻译** - Python 自动翻译为竞赛风格 C++
8. **反馈优化** - 根据 OJ 反馈继续迭代

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
