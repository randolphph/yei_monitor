# YEI监控系统安装说明

## 环境要求
- Python 3.8+
- Windows Server 2019/2022 或 Windows 10/11

## 安装步骤

1. 安装Python依赖：
```bash
pip install -r requirements.txt
pip install pywin32
```

2. 安装Windows服务：
```bash
python install_service.py install
```

3. 启动服务：
```bash
python install_service.py start
```

## 服务管理命令

- 启动服务：
```bash
python install_service.py start
```

- 停止服务：
```bash
python install_service.py stop
```

- 重启服务：
```bash
python install_service.py restart
```

- 删除服务：
```bash
python install_service.py remove
```

## 日志查看
- 服务日志位于：`yei_monitor.log`
- Windows事件查看器中也可以查看服务日志

## 注意事项
1. 确保服务器有稳定的网络连接
2. 建议配置自动重启策略
3. 定期检查日志文件大小，必要时进行轮转
4. 确保服务器时间准确同步 