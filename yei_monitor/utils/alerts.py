import aiohttp
import urllib.parse
from typing import Dict, Any, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AlertManager:
    def __init__(self, bark_key: str, bark_server: str):
        self.bark_key = bark_key
        self.bark_server = bark_server.rstrip('/')  # 移除末尾的斜杠

    async def send_alert(self, message: str, data: Optional[Dict[str, Any]] = None):
        """发送警报"""
        try:
            # 记录日志
            logger.warning(f"警报: {message}")
            if data:
                logger.warning(f"详细信息: {data}")

            # 发送 Bark 消息
            if self.bark_key:
                # 对消息内容进行URL编码，保留换行符为%0A
                encoded_message = urllib.parse.quote(message)
                
                # 构建Bark通知URL
                url = f"{self.bark_server}/{self.bark_key}/YEI监控/{encoded_message}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            response_text = await response.text()
                            raise Exception(f"Bark API 返回错误: {response.status} - {response_text}")
                        else:
                            logger.info("成功发送Bark通知")
                        
        except Exception as e:
            logger.error(f"发送警报失败: {str(e)}") 