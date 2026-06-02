#!/bin/bash
# ============================================================
#  QuantConnect LEAN - 一键启动脚本
#  双击 .command 即可自动打开可视化控制台
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║         QuantConnect LEAN 引擎启动器         ║"
echo "  ║         Algorithmic Trading Platform         ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# ---- 检查 .NET SDK ----
echo -e "${BLUE}[1/3]${NC} 检查 .NET SDK..."
if command -v dotnet &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} .NET SDK: $(dotnet --version)"
else
    echo -e "  ${RED}✗${NC} .NET SDK 未安装! 请访问 https://dotnet.microsoft.com/download"
    read -p "按回车键退出..."
    exit 1
fi

# ---- 检查 Python ----
echo -e "${BLUE}[2/3]${NC} 检查 Python..."
VENV_PYTHON=""
if [ -f ".venv/bin/python3" ]; then
    VENV_PYTHON=".venv/bin/python3"
elif [ -f ".venv/bin/python" ]; then
    VENV_PYTHON=".venv/bin/python"
elif command -v python3 &>/dev/null; then
    VENV_PYTHON="python3"
fi

if [ -z "$VENV_PYTHON" ]; then
    echo -e "  ${RED}✗${NC} Python3 未安装!"
    read -p "按回车键退出..."
    exit 1
fi
echo -e "  ${GREEN}✓${NC} $($VENV_PYTHON --version)"

# ---- 配置 Python.NET 桥接 ----
echo -e "${BLUE}[3/4]${NC} 配置 Python 环境..."
PYTHON_DYLIB=""
if [ -n "$VENV_PYTHON" ]; then
    PYTHON_HOME=$($VENV_PYTHON -c "import sys; print(sys.prefix)" 2>/dev/null)
    PYTHON_VER=$($VENV_PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    # Find libpython dylib
    PYTHON_DYLIB=$(find "$(dirname "$(dirname "$(which $VENV_PYTHON 2>/dev/null || echo /usr)")")" \
        /opt/homebrew /usr/local -name "libpython${PYTHON_VER}.dylib" -not -path "*/config-*/*" 2>/dev/null | head -1)
fi
if [ -n "$PYTHON_DYLIB" ]; then
    export PYTHONNET_PYDLL="$PYTHON_DYLIB"
    echo -e "  ${GREEN}✓${NC} Python.NET 桥接: ${PYTHON_DYLIB}"
else
    echo -e "  ${YELLOW}⚠${NC} 未找到 libpython, Python 策略可能无法运行"
fi

# ---- 安装 Python 依赖 ----
if ! $VENV_PYTHON -c "import flask" 2>/dev/null; then
    echo -e "  ${YELLOW}⚠${NC} 正在安装 Flask..."
    $VENV_PYTHON -m pip install flask -q 2>/dev/null
fi
if ! $VENV_PYTHON -c "import pandas" 2>/dev/null; then
    echo -e "  ${YELLOW}⚠${NC} 正在安装 pandas/numpy..."
    $VENV_PYTHON -m pip install pandas numpy matplotlib -q 2>/dev/null
fi
echo -e "  ${GREEN}✓${NC} Python 依赖就绪"

echo ""

# ---- 构建项目（后台静默） ----
echo -e "${BLUE}[4/4]${NC} 构建项目..."
dotnet build QuantConnect.Lean.sln --nologo -v q 2>&1 | tail -1
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "  ${RED}✗${NC} 构建失败!"
    read -p "按回车键退出..."
    exit 1
fi
echo -e "  ${GREEN}✓${NC} 构建成功"
echo ""

# ---- 启动 Web UI ----
echo -e "${GREEN}▶ 正在启动可视化控制台...${NC}"
echo -e "  浏览器即将打开: ${CYAN}http://localhost:5555${NC}"
echo -e "  按 ${YELLOW}Ctrl+C${NC} 或关闭此窗口停止"
echo ""

# 打开浏览器
sleep 1
open "http://localhost:5555" 2>/dev/null || true

# 启动 Flask UI（前台运行，Ctrl+C 即退出）
if [ "$VENV_PYTHON" = "${VENV_PYTHON#/}" ]; then
    # 不是绝对路径，直接用
    cd LeanUI && $VENV_PYTHON app.py
else
    cd LeanUI && "$VENV_PYTHON" app.py
fi
