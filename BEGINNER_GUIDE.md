# QuantConnect LEAN 新手引导

## 一、这是什么？

**LEAN** 是一个开源的专业级**量化交易引擎**，由 [QuantConnect](https://www.quantconnect.com) 开发和维护。

简单来说，它能让你：
- **用代码编写交易策略**（支持 C# 和 Python）
- **在历史数据上回测**策略表现
- **连接真实券商进行自动交易**（实盘）

支持股票、期货、期权、外汇、加密货币等多种资产。

---

## 二、核心概念（5 分钟速通）

### 事件驱动

LEAN 是"事件驱动"的引擎。你的策略代码不需要循环等待——引擎在行情数据到达时**自动调用**你的处理函数。

```
行情Tick → 引擎 → 调用 OnData() → 你的交易逻辑
订单成交 → 引擎 → 调用 OnOrderEvent() → 你的后续处理
```

### 最简单的策略长这样

```python
class MyFirstStrategy(QCAlgorithm):

    def initialize(self):
        # 初始化：设置回测时间和启动资金
        self.set_start_date(2023, 1, 1)
        self.set_end_date(2023, 12, 31)
        self.set_cash(100000)  # 10万美元
        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol

    def on_data(self, data):
        # 每次收到日线数据时执行
        if not self.portfolio.invested:
            self.set_holdings(self.spy, 1.0)  # 全仓买入 SPY
```

### 关键术语

| 术语 | 含义 |
|------|------|
| Algorithm | 你的交易策略 |
| Backtesting | 回测 - 在历史数据上测试策略 |
| Paper Trading | 模拟交易 - 用实时行情模拟，不涉及真钱 |
| Live Trading | 实盘交易 - 连接券商真实下单 |
| Tick | 每笔成交数据 |
| Equity | 股票 |
| Option | 期权 |
| Future | 期货 |
| Resolution | 数据精度（Tick/Second/Minute/Hour/Daily） |
| Alpha | 超额收益信号 |

---

## 三、三种使用方式

### 方式 1：Web UI 控制台（推荐新手）

双击 `start.command` → 选择 **1**，打开浏览器访问 `http://localhost:5555`

功能包括：
- **控制台** - 查看系统状态
- **回测中心** - 配置并运行回测，实时查看日志
- **算法管理** - 浏览所有示例算法，支持搜索
- **实盘交易** - 配置券商连接
- **数据管理** - 浏览本地市场数据
- **配置编辑** - 在线编辑 config.json
- **日志查看** - 查看引擎运行日志

### 方式 2：命令行

```bash
# 双击 start.command → 选择 2

# 或手动：
cd Launcher/bin/Debug
dotnet QuantConnect.Lean.Launcher.dll
```

### 方式 3：LEAN CLI（官方工具）

```bash
pip install lean
lean project-create "MyStrategy"   # 创建项目
lean backtest "MyStrategy"         # 回测
lean live "MyStrategy"             # 实盘
```

---

## 四、运行你的第一个回测

### 步骤 1：启动 UI

双击项目根目录的 **`start.command`**，选择 **1**

### 步骤 2：选择算法

点击左侧 **回测中心** → 在算法下拉框中选择 `BasicTemplateFrameworkAlgorithm`

### 步骤 3：运行

点击 **▶ 启动回测** 按钮

### 步骤 4：查看结果

- **实时日志输出** - 滚动显示引擎运行日志
- **回测结果** - 完成后显示统计数据和图表

---

## 五、写自己的策略

### Python 示例

在 `Algorithm.Python/` 目录下新建文件，例如 `MyMovingAverageCross.py`：

```python
from AlgorithmImports import *

class MyMovingAverageCross(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2021, 1, 1)
        self.set_cash(100000)

        self.symbol = self.add_equity("SPY", Resolution.HOUR).symbol

        # 创建均线指标
        self.fast_ma = self.sma(self.symbol, 50, Resolution.HOUR)
        self.slow_ma = self.sma(self.symbol, 200, Resolution.HOUR)

    def on_data(self, data):
        # 等慢速均线准备好
        if not self.slow_ma.is_ready:
            return

        # 金叉买入
        if self.fast_ma.current.value > self.slow_ma.current.value:
            if not self.portfolio.invested:
                self.set_holdings(self.symbol, 1.0)

        # 死叉卖出
        elif self.portfolio.invested:
            self.liquidate(self.symbol)
```

### C# 示例

在 `Algorithm.CSharp/` 目录下新建 `.cs` 文件。

---

## 六、配置说明

编辑 `Launcher/config.json`（或通过 Web UI 配置页编辑）：

```json
{
  "environment": "backtesting",          // 运行环境
  "algorithm-type-name": "示例算法名称",
  "algorithm-language": "Python",       // 或 "CSharp"
  "algorithm-location": "../../../Algorithm.Python/MyAlgo.py",
  "data-folder": "../../../Data/"
}
```

环境选项：
- `backtesting` - 历史回测
- `live-paper` - 模拟实盘
- `live-interactive` - Interactive Brokers 实盘
- 以及其他券商环境（Binance、Alpaca、Coinbase 等）

---

## 七、项目结构速查

```
Lean/
├── start.command              ← 一键启动！
├── LeanUI/                    ← Web 控制台
│   └── app.py                 ← Flask 服务端
├── Launcher/                  ← 引擎启动入口
│   ├── Program.cs             ← Main 函数
│   └── config.json            ← 运行配置
├── Algorithm.CSharp/          ← C# 算法（800+示例）
├── Algorithm.Python/          ← Python 算法（800+示例）
├── Algorithm.Framework/       ← 算法框架（Alpha/风控/执行）
├── Engine/                    ← 核心引擎
├── Indicators/                ← 技术指标库
├── Data/                      ← 本地市场数据
└── Tests/                     ← 测试
```

---

## 八、下一步

1. **学习官方文档** → https://www.lean.io/docs/
2. **加入社区** → https://www.quantconnect.com/forum/discussions/1/lean
3. **Bootcamp 教程** → https://www.quantconnect.com/learn
4. **YouTube 视频** → https://www.youtube.com/@QuantConnect

### 实用链接

| 资源 | 地址 |
|------|------|
| GitHub | https://github.com/QuantConnect/Lean |
| 文档 | https://www.lean.io/docs/ |
| 论坛 | https://www.quantconnect.com/forum |
| Discord | https://www.quantconnect.com/discord |
| API 参考 | https://www.lean.io/docs/algorithm-reference/index |
| CLI 速查 | https://cdn.quantconnect.com/i/tu/cli-cheat-sheet.pdf |

---

## 九、常见问题

**Q: 回测数据从哪里来？**
A: 需要将市场数据放入 `Data/` 目录。可以从 QuantConnect 下载，或用其他数据源。

**Q: 如何获取更多市场数据？**
A: 在 quantconnect.com 注册账号，使用 Data Library 下载。

**Q: 能否不联网使用？**
A: 可以。只要 `Data/` 目录有本地数据，回测完全离线。

**Q: Python 和 C# 哪个好？**
A: Python 更简洁，适合快速开发；C# 性能更好，适合高频策略。初学者建议 Python。
