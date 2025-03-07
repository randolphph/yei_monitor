import aiohttp
import urllib.parse
import json
from typing import Dict, Any, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AlertManager:
    def __init__(self, bark_key: str, bark_server: str):
        self.bark_key = bark_key
        self.bark_server = bark_server.rstrip('/')  # 移除末尾的斜杠
        # 构建完整的Bark URL
        self.bark_url = f"{self.bark_server}/{self.bark_key}" if self.bark_key else ""

    async def send_alert(self, message: str, data: Optional[Dict[str, Any]] = None, is_high_risk: bool = False):
        """发送警报
        
        Args:
            message: 警报消息
            data: 详细数据
            is_high_risk: 是否为高风险警报
        """
        try:
            # 记录日志
            logger.warning(f"警报: {message}")
            if data:
                logger.warning(f"详细信息: {data}")

            # 发送 Bark 消息
            if self.bark_url:
                # 构建通知内容
                title = "⚠️ YEI安全警报 ⚠️" if is_high_risk else "YEI监控警报"
                
                # 构建请求数据
                bark_data = {
                    "title": title,
                    "body": message,
                    "group": "YEI监控-警报",
                    "icon": "https://sei.io/favicon.ico"
                }
                
                # 根据风险级别设置不同的提示音和通知级别
                if is_high_risk:
                    # 高风险警报：使用持续的警报声音，设置为时效性通知
                    bark_data.update({
                        "sound": "alarm",
                        "level": "timeSensitive",  # 时效性通知，可能会打断用户
                        "badge": 1,
                        "autoCopy": 1,  # 自动复制内容
                        "isArchive": 1   # 保存到通知历史
                    })
                else:
                    # 普通警报：使用标准警报声音
                    bark_data.update({
                        "sound": "warning",
                        "level": "active"  # 活跃通知，但不会打断用户
                    })
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.bark_url, json=bark_data) as response:
                        if response.status != 200:
                            response_text = await response.text()
                            raise Exception(f"Bark API 返回错误: {response.status} - {response_text}")
                        else:
                            logger.info(f"成功发送Bark{'高风险' if is_high_risk else ''}警报通知")
                        
        except Exception as e:
            logger.error(f"发送警报失败: {str(e)}") 