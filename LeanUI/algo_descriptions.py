"""
Algorithm Description Engine - generates Chinese descriptions for LEAN algorithms.
Parses algorithm names and source code to produce meaningful explanations.
"""
import re
import json
from pathlib import Path

# ---- Keyword → Chinese Description Mapping ----
FEATURE_MAP = {
    # Indicators
    "SMA|SimpleMovingAverage|MovingAverage": "使用简单移动平均线(SMA)作为核心信号指标",
    "EMA|ExponentialMovingAverage": "使用指数移动平均线(EMA)作为核心信号指标",
    "MACD": "基于MACD指标（异同移动平均线）的金叉死叉策略",
    "RSI|RelativeStrengthIndex": "基于RSI相对强弱指标的超买超卖策略",
    "Bollinger|BollingerBands": "基于布林带(Bollinger Bands)的均值回归策略",
    "ATR|AverageTrueRange": "使用ATR平均真实波幅进行止损和仓位管理",
    "Stochastic|Stoch": "基于随机指标(Stochastic Oscillator)的交易策略",
    "ADX|AverageDirectionalIndex": "使用ADX平均趋向指数判断趋势强度",
    "OBV|OnBalanceVolume": "基于OBV能量潮指标的成交量策略",
    "CCI|CommodityChannelIndex": "基于CCI商品通道指数的交易策略",
    "Ichimoku": "基于一目均衡表(Ichimoku Cloud)的趋势跟踪策略",
    "ParabolicSAR|PSAR": "基于抛物线转向指标的止损跟踪策略",
    "VWAP": "基于VWAP成交量加权平均价格的交易执行策略",
    "Williams.*R|WilliamsR": "基于威廉指标(Williams %R)的超买超卖策略",
    "ROC|RateOfChange": "使用ROC变动率指标判断价格动量",
    "MFI|MoneyFlowIndex": "基于MFI资金流量指数的量价分析策略",
    "KAMA|KaufmanAdaptive": "使用KAMA考夫曼自适应移动平均线的趋势策略",
    "TRIX": "基于TRIX三重指数平滑指标的策略",
    "MOM|MomentumPercent": "基于动量指标的策略",

    # Strategies
    "Momentum|MomentumEffect": "动量效应策略：买入近期表现强势的资产，卖出弱势资产",
    "MeanReversion|Reversal|MeanReversion": "均值回归策略：利用价格偏离均值后回归的特性进行交易",
    "TrendFollowing|Trend": "趋势跟踪策略：识别并跟随市场主要趋势方向进行交易",
    "Breakout": "突破策略：在价格突破关键支撑/阻力位时进场",
    "Arbitrage|Arb": "套利策略：利用不同市场或合约之间的价差获利",
    "Pair[s]?Trad": "配对交易策略：寻找两只高度相关的股票，利用价差回归获利",
    "Grid": "网格交易策略：在设定的价格区间内分批买卖",
    "Scalping|Scalp": "高频剥头皮策略：通过大量微小利润的快速交易积累收益",
    "Swing": "波段交易策略：捕捉价格中期波动的买卖机会",
    "Martingale": "马丁格尔策略：亏损后加倍下注以期望最终盈利（高风险）",
    "Delta|Hedging": "Delta对冲策略：通过动态调整持仓保持Delta中性",
    "Volatility|Vol": "波动率策略：利用波动率的变化进行交易",
    "Statistical|StatArb": "统计套利策略：基于统计模型的量化套利方法",
    "Cointegration|Cointegrat": "协整策略：利用具有协整关系的资产价格回归特性交易",
    "CalendarSpread|Calendar": "日历价差策略：利用不同到期日期权的时间价值衰减差异",
    "IronCondor": "铁秃鹰策略：同时卖出价外看涨和看跌期权价差获取权利金",
    "Butterfly": "蝶式价差期权策略：预期价格在一定范围内波动的中性策略",
    "Straddle": "跨式期权策略：同时买入看涨和看跌期权博取大幅波动",
    "Strangle": "宽跨式期权策略：买入不同行权价的看涨看跌期权",
    "CoveredCall": "备兑看涨期权策略：持有股票同时卖出看涨期权获取权利金",
    "ProtectivePut": "保护性看跌策略：持有股票同时买入看跌期权对冲下行风险",
    "Wheel": "滚轮策略：卖出看跌期权接货后卖出看涨期权的循环策略",
    "RiskParity": "风险平价策略：根据资产风险贡献度配置组合权重",
    "AllWeather": "全天候策略：在不同经济环境下都能表现稳定的资产配置",
    "MomentumAlpha": "Alpha动量模型：基于动量因子的Alpha信号生成",
    "VolumeWeighted|VWMA": "基于成交量加权价格的技术分析策略",

    # ML/AI
    "MachineLearning|ML": "使用机器学习模型预测价格走势",
    "NeuralNetwork|Neural|Deep": "使用神经网络/深度学习模型进行交易预测",
    "RandomForest|Forest": "使用随机森林(Random Forest)集成学习模型进行预测",
    "SVM|SupportVector": "使用支持向量机(SVM)进行市场分类预测",
    "Bayesian": "基于贝叶斯推断的概率预测交易策略",
    "Kalman": "使用卡尔曼滤波器(Kalman Filter)进行价格预测",
    "HiddenMarkov|HMM": "使用隐马尔可夫模型(HMM)识别市场状态",
    "Reinforcement|QLearn|Q[Ll]earning|DDPG|PPO": "基于强化学习的自适应交易策略",
    "Genetic|Evolutionary|Evolution": "使用遗传算法/进化算法进行策略参数优化",
    "LSTM|Transformer|Attention": "使用深度学习时序模型(LSTM/Transformer)预测行情",
    "XGBoost|XGB|LightGBM|GBM": "使用梯度提升树(XGBoost/LightGBM)进行预测建模",

    # Alpha/Framework
    "AlphaModel|Alpha": "Alpha信号模型：生成交易信号的量化模型",
    "Portfolio[Cc]onstruction|Portfolio": "投资组合构建模型：根据信号构建目标持仓",
    "RiskManagement|Risk": "风险管理模型：控制策略风险暴露和回撤",
    "ExecutionModel|Execution": "执行模型：优化订单执行策略和时机",
    "UniverseSelection|Universe|Selection": "选股/选品种模型：从市场中筛选交易标的",
    "Framework|FrameworkAlgorithm": "框架算法：使用模块化的Algorithm Framework架构",

    # Asset Classes
    "Option|OptionContract": "期权交易策略",
    "Future|Futures|FutureContract": "期货交易策略",
    "Crypto|Bitcoin|ETH|BTC": "加密货币交易策略",
    "Forex|FX": "外汇(Forex)交易策略",
    "ETF|ETFConstituent": "ETF相关策略",
    "IndexOption|SPX|VIX": "指数期权策略",
    "ContinuousContract|ContinuousFuture": "使用连续合约的期货策略",

    # Patterns
    "Candlestick|Candle|Pattern": "基于K线形态识别的技术分析策略",
    "SupportResistance|Support.*Resist": "基于支撑阻力位判断的择时策略",
    "Divergence|Convergence": "背离交易策略：利用价格与技术指标的背离信号",
    "GoldenCross|DeathCross": "金叉/死叉策略：基于均线交叉的交易信号",

    # Features
    "Warmup|WarmUp": "涉及指标预热(Warmup)处理",
    "Consolidat|Consolidator": "使用数据合并器(Consolidator)转换时间周期",
    "CustomData|AlternativeData": "使用自定义/另类数据源",
    "ScheduledEvent|Scheduled": "使用定时事件按日程执行交易逻辑",
    "MarginModel|Margin": "定制保证金模型",
    "FeeModel|Fee|Commission": "定制手续费/佣金模型",
    "SlippageModel|Slippage": "定制滑点模型模拟交易成本",
    "FillModel|Fill": "定制订单成交模型",
    "BrokerageModel|Brokerage": "定制券商模型模拟真实交易环境",
    "Benchmark|BenchmarkModel": "定制基准模型用于绩效比较",

    # Specific well-known algorithms
    "Renko": "Renko图策略：基于砖形图的价格突破交易",
    "HeikinAshi|HeikenAshi": "Heikin-Ashi平均K线图策略，平滑价格噪音",
    "Keltner|KeltnerChannels": "肯特纳通道策略：基于波动性的突破交易",
    "Donchian|DonchianChannel": "唐奇安通道策略：经典的突破交易系统（海龟交易基础）",
    "Supertrend": "超级趋势指标策略：基于ATR的趋势跟踪",
    "Hurst": "Hurst指数策略：基于分形市场假说的趋势判断",
    "HullMovingAverage|HMA": "Hull移动平均线策略：低滞后性的趋势跟踪",
    "ZLEMA|ZeroLag": "零滞后EMA策略：减少信号延迟的趋势跟踪",
    "T3MovingAverage|T3": "T3移动平均线策略：高平滑度的趋势指标",
    "MESA|MaximumEntropy": "MESA自适应移动平均策略：基于最大熵谱分析",
    "Ehlers|Ehler": "John Ehlers技术指标策略（先进的数字信号处理方法）",
    "Wilder|WilderMA": "Wilder平滑指标策略",
    "Chandelier|ChandelierExit": "吊灯止损策略：基于ATR的动态止损方法",
    "AdvanceDecline|Advance.*Decline": "涨跌线(AD Line)市场广度策略",
    "ArmsIndex|TRIN": "Arms指数(TRIN)市场情绪策略",
    "McClellan|McClellanOscillator": "McClellan市场广度振荡器策略",
    "Turtle": "海龟交易策略：经典的突破趋势跟踪系统",
    "DualThrust": "Dual Thrust策略：经典的双推力突破系统",
    "Aberration": "Aberration策略：基于布林带的突破交易系统",
}

# Algorithm type classifiers
TYPE_MAP = {
    r"RegressionAlgorithm$": {
        "type": "回归测试 (Regression Test)",
        "desc": "这是一个回归测试算法，用于验证特定引擎功能是否正常工作。"
    },
    r"TemplateAlgorithm$|BasicTemplate": {
        "type": "模板/示例算法",
        "desc": "基础模板算法，展示了编写LEAN策略的基本框架结构，适合初学者学习和参考。"
    },
}


def describe_algorithm(name):
    """
    Generate a Chinese description for an algorithm based on its name.
    Returns dict with: name, cn_title, description, features[], category, difficulty
    """
    features = []
    descriptions = []

    # Check regression/template classifiers first
    for pattern, info in TYPE_MAP.items():
        if re.search(pattern, name):
            return {
                "name": name,
                "cn_title": info.get("cn_title", name),
                "description": info["desc"],
                "features": [],
                "category": info.get("type", "unknown"),
                "difficulty": "beginner",
            }

    # Extract features from name
    for pattern, desc in FEATURE_MAP.items():
        if re.search(pattern, name):
            features.append(desc)
            descriptions.append(desc)

    # Infer category
    category = infer_category(name)

    # Infer difficulty
    difficulty = infer_difficulty(name)

    # Build description
    if descriptions:
        main_desc = "；".join(descriptions[:3]) + "。"
    else:
        main_desc = f"这是一个{category}相关的算法。"

    # Try to determine what problem it solves
    purpose = infer_purpose(name, features)

    return {
        "name": name,
        "cn_title": generate_cn_title(name),
        "description": main_desc,
        "purpose": purpose,
        "features": features,
        "category": category,
        "difficulty": difficulty,
    }


def infer_category(name):
    """Infer algorithm category from name"""
    if re.search(r"Option|OptionContract|Call|Put|Straddle|Strangle|Butterfly|IronCondor|Delta|Gamma", name):
        return "期权 (Options)"
    if re.search(r"Future|Futures|ContinuousContract|ContinuousFuture", name):
        return "期货 (Futures)"
    if re.search(r"Crypto|Bitcoin|ETH|BTC|Coinbase|Binance", name):
        return "加密货币 (Crypto)"
    if re.search(r"Forex|FX|Currency", name):
        return "外汇 (Forex)"
    if re.search(r"Alpha|AlphaModel|AlphaCreation|Insight", name):
        return "Alpha信号模型"
    if re.search(r"Risk|RiskManagement", name):
        return "风险管理"
    if re.search(r"Portfolio|PortfolioConstruction", name):
        return "投资组合构建"
    if re.search(r"Execution|ExecutionModel", name):
        return "执行模型"
    if re.search(r"Universe|Selection", name):
        return "选股/选品种"
    if re.search(r"Framework", name):
        return "算法框架"
    if re.search(r"ML|MachineLearning|Neural|Deep|RandomForest|SVM|Bayesian|Kalman|HMM|QLearn|LSTM|Transformer|XGBoost|Genetic|Evolution", name):
        return "机器学习/AI"
    if re.search(r"MACD|RSI|EMA|SMA|Bollinger|ATR|Ichimoku|Stochastic|CCI|ADX|OBV|VWAP|Keltner|Donchian|Parabolic|Supertrend|Renko|Heikin|Momentum|TrendFollowing|Trend.*Follow|Breakout|MeanReversion|Reversal", name):
        return "技术指标策略"
    if re.search(r"Arbitrage|PairsTrad|StatArb|Cointegration", name):
        return "统计套利"
    if re.search(r"Warmup|Consolidat|Consolidator|CustomData|ScheduledEvent|Margin|Fee|Slippage|Fill|Brokerage|Benchmark", name):
        return "引擎功能"
    if re.search(r"Regression|Add|Remove|Set|Update|Cancel|BasicTemplate|Template", name):
        return "基础/引擎功能"
    return "综合/其他"


def infer_difficulty(name):
    """Infer difficulty level"""
    if re.search(r"Basic|Simple|Template|Example|Tutorial|GettingStarted", name):
        return "beginner"
    if re.search(r"ML|MachineLearning|Neural|Deep|LSTM|Transformer|Q[Ll]earn|Reinforcement|Genetic|Bayesian|HMM|Kalman|XGBoost|RandomForest", name):
        return "advanced"
    if re.search(r"RegressionAlgorithm$", name):
        return "beginner"
    return "intermediate"


def infer_purpose(name, features):
    """Infer what problem the algorithm solves"""
    if re.search(r"Risk|Drawdown|StopLoss|TrailingStop", name):
        return "解决交易风险控制问题，帮助限制最大回撤和保护利润。"
    if re.search(r"Momentum|TrendFollowing|Trend.*Follow", name):
        return "捕捉市场趋势行情，在趋势形成时进场并持有至趋势结束。"
    if re.search(r"MeanReversion|Reversal|Mean.*Revers", name):
        return "利用价格过度偏离均值的现象，在极端价位反向交易博取回归利润。"
    if re.search(r"Arbitrage|PairsTrad|StatArb|CoIntegration", name):
        return "寻找市场定价错误或资产价格偏离均衡关系的机会进行套利。"
    if re.search(r"Portfolio|Allocation|RiskParity", name):
        return "优化资产配置结构，在收益和风险之间取得最佳平衡。"
    if re.search(r"Universe|Selection", name):
        return "从大量可交易标的中筛选出最有潜力的品种，缩小交易范围。"
    if re.search(r"Alpha|Signal", name):
        return "生成可量化的交易信号，帮助判断何时买入、何时卖出。"
    if re.search(r"Execution|Order|Fill", name):
        return "优化订单执行方式，降低交易成本和市场冲击。"
    if re.search(r"Option|Call|Put|Straddle|Strangle|Butterfly|IronCondor|CoveredCall", name):
        return "通过期权策略实现收益增强、风险对冲或波动率交易。"
    if re.search(r"Breakout", name):
        return "识别价格突破关键位置后的趋势性行情，及时跟进。"
    if re.search(r"Volatility|Vol", name):
        return "利用市场波动率的变化规律进行交易，在低波/高波环境间切换。"
    if re.search(r"ML|MachineLearning|Neural|Deep|RandomForest|SVM|Bayesian|Kalman|HMM|QLearn|LSTM|Transformer|XGBoost|Genetic", name):
        return "利用机器学习/AI技术从历史数据中学习交易规律，构建自适应的预测模型。"
    if re.search(r"Warmup|Consolidat|CustomData|ScheduledEvent|Margin|Fee|Slippage|Fill|Brokerage", name):
        return "验证LEAN引擎的特定功能特性是否正常工作（回归测试）。"
    if features:
        return "利用" + features[0][:50] + "等技术手段辅助交易决策。"
    return "提供量化交易策略的完整实现，可供学习和扩展。"


def generate_cn_title(name):
    """Generate a Chinese title from algorithm name"""
    # Remove common suffixes
    base = re.sub(
        r"(Algorithm|RegressionAlgorithm|Model|Template)$", "", name
    )

    # Split camelCase but keep known acronyms together
    # Insert spaces before uppercase letters, then rejoin known acronyms
    spaced = re.sub(r"([A-Z][a-z])", r" \1", base)
    spaced = re.sub(r"([A-Z]{2,})", r" \1 ", spaced)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    words = spaced.split()
    english_title = " ".join(words)

    # Try to give a Chinese translation
    cn_map = {
        "Basic": "基础",
        "Template": "模板",
        "Framework": "框架",
        "MACD": "MACD",
        "RSI": "RSI",
        "EMA": "EMA",
        "SMA": "SMA",
        "Bollinger": "布林带",
        "Momentum": "动量",
        "Mean": "均值",
        "Reversion": "回归",
        "Trend": "趋势",
        "Following": "跟踪",
        "Breakout": "突破",
        "Arbitrage": "套利",
        "Pairs": "配对",
        "Trading": "交易",
        "Option": "期权",
        "Future": "期货",
        "Crypto": "加密",
        "Forex": "外汇",
        "Risk": "风险",
        "Management": "管理",
        "Portfolio": "投资组合",
        "Construction": "构建",
        "Execution": "执行",
        "Alpha": "Alpha",
        "Universe": "选股",
        "Selection": "筛选",
        "Warmup": "预热",
        "Custom": "自定义",
        "Data": "数据",
        "Machine": "机器",
        "Learning": "学习",
        "Neural": "神经",
        "Network": "网络",
        "Volatility": "波动率",
        "Statistical": "统计",
    }

    # For short names, try to provide meaningful translation
    parts = []
    for word in words:
        parts.append(cn_map.get(word, word))
    cn_part = " ".join(parts)

    # Keep it concise
    if len(cn_part) > 25:
        return english_title if len(english_title) < 30 else name
    return cn_part


def scan_source_file(filepath):
    """Quick scan of source file for key patterns to enhance description"""
    try:
        content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        info = {}

        # Extract summary comment
        summary_match = re.search(r"<summary>\s*(.*?)\s*</summary>", content, re.DOTALL)
        if summary_match:
            info["summary"] = summary_match.group(1).strip()

        # Detect indicators used
        indicators = []
        indicator_patterns = {
            "SMA": r"\bSMA\b|SimpleMovingAverage",
            "EMA": r"\bEMA\b|ExponentialMovingAverage",
            "MACD": r"\bMACD\b",
            "RSI": r"\bRSI\b|RelativeStrengthIndex",
            "ATR": r"\bATR\b|AverageTrueRange",
            "BB": r"\bBB\b|BollingerBands",
            "ADX": r"\bADX\b|AverageDirectionalIndex",
            "Stochastic": r"\bSTO\b|Stochastic",
        }
        for ind, pattern in indicator_patterns.items():
            if re.search(pattern, content):
                indicators.append(ind)
        if indicators:
            info["indicators"] = indicators

        return info
    except Exception:
        return {}
