# YEI 监控系统

这是一个用于监控YEI协议在SEI链上的智能合约的工具。该系统可以监控合约事件和状态变化，并通过Bark推送通知。

## 功能特点

- 监控YEI协议合约事件（存款、提款、借款、还款、清算等）
- 监控合约状态变化
- 通过Bark推送通知
- 支持SEI链EVM模式

## 安装

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/yei-monitor.git
cd yei-monitor
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 配置环境变量：

创建一个`.env`文件，包含以下内容：

```
BARK_KEY=your_bark_key
BARK_SERVER=https://api.day.app
RPC_URL=https://evm-rpc.sei-apis.com
```

## 使用方法

运行监控系统：

```bash
python main.py
```

## 项目结构

```
yei_monitor/
├── config/
│   └── settings.py     # 配置文件
├── core/
│   ├── contract.py     # 合约管理
│   ├── monitor.py      # 监控系统
│   └── state.py        # 状态管理
├── utils/
│   ├── alerts.py       # 通知管理
│   └── logger.py       # 日志管理
├── main.py             # 主程序
└── requirements.txt    # 依赖列表
```

## 日志

日志文件位于项目根目录下的`yei_monitor.log`。

## 许可证

MIT 