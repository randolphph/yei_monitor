import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, level=logging.DEBUG) -> logging.Logger:
    """设置日志"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 文件处理器
    file_handler = RotatingFileHandler(
        'yei_monitor.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'  # 添加UTF-8编码设置
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    file_handler.setLevel(level)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )
    console_handler.setLevel(level)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger 