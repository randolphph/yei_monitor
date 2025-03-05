import asyncio
from core.monitor import YEIMonitor
from utils.logger import setup_logger

logger = setup_logger(__name__)

def main():
    """主函数"""
    try:
        monitor = YEIMonitor()
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        logger.info("监控系统已停止")
    except Exception as e:
        logger.error(f"程序异常退出: {str(e)}")

if __name__ == "__main__":
    main() 