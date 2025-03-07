import asyncio
from core.monitor import YEIMonitor
from utils.logger import setup_logger
from utils.heartbeat import HeartbeatMonitor

logger = setup_logger(__name__)

async def async_main():
    """异步主函数"""
    try:
        # 创建心跳监控
        heartbeat = HeartbeatMonitor()
        
        # 发送启动通知
        await heartbeat._send_heartbeat("系统启动")
        
        # 启动心跳监控
        heartbeat_task = asyncio.create_task(heartbeat.start())
        
        # 启动主监控
        monitor = YEIMonitor()
        monitor_task = asyncio.create_task(monitor.run())
        
        # 等待任务完成
        await asyncio.gather(monitor_task, heartbeat_task)
        
    except Exception as e:
        logger.error(f"程序异常退出: {str(e)}")

def main():
    """主函数"""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("监控系统已停止")
    except Exception as e:
        logger.error(f"程序异常退出: {str(e)}")

if __name__ == "__main__":
    main() 