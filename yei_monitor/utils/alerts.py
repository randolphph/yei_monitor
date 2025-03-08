import urllib.parse
import requests
import time
import logging
from typing import Dict, Any, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AlertManager:
    def __init__(self, bark_key: str, bark_server: str):
        self.bark_key = bark_key
        self.bark_server = bark_server.rstrip('/')  # 移除末尾的斜杠
        # 构建完整的Bark URL基础部分
        self.bark_base_url = f"{self.bark_server}/{self.bark_key}" if self.bark_key else ""
        logger.info(f"初始化AlertManager，Bark基础URL: {self.bark_base_url}")
        
    def send_bark_notification(self, title: str, message: str, group: str = "YEI监控", 
                              sound: str = "bell", level: str = "active", is_high_risk: bool = False, call: str = "0"):
        """通用的Bark通知发送函数
        
        Args:
            title: 通知标题
            message: 通知内容
            group: 通知分组
            sound: 提示音
            level: 通知级别 (passive/active/timeSensitive)
            is_high_risk: 是否为高风险通知
        
        Returns:
            bool: 是否发送成功
        """
        if not self.bark_base_url:
            logger.warning("未配置Bark URL，无法发送通知")
            return False
            
        try:
            # URL编码标题和消息
            encoded_title = urllib.parse.quote(title)
            encoded_message = urllib.parse.quote(message)
            
            # 构建基本URL
            url = f"{self.bark_base_url}/{encoded_title}/{encoded_message}"
            
            # 添加参数
            params = {
                "group": group,
                "sound": sound,
                "icon": "https://sei.io/favicon.ico",
                "level": level,
                "call": call
            }
            
            # 添加高风险参数
            if is_high_risk:
                params["badge"] = "1"
                params["isArchive"] = "1"
            
            # 构建查询字符串
            query_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
            full_url = f"{url}?{query_string}"
            
            logger.debug(f"发送Bark通知，URL: {full_url}")
            
            # 使用requests发送GET请求
            response = requests.get(full_url, timeout=15)
            
            if response.status_code == 200:
                logger.info(f"成功发送Bark通知: {title}")
                return True
            else:
                logger.error(f"Bark API返回错误: {response.status_code} - {response.text}")
                
                # 尝试最简单的URL格式
                simple_url = f"{self.bark_base_url}/{encoded_title}/{encoded_message}"
                logger.debug(f"尝试使用最简单的URL: {simple_url}")
                simple_response = requests.get(simple_url, timeout=15)
                
                if simple_response.status_code == 200:
                    logger.info("使用简单URL成功发送Bark通知")
                    return True
                else:
                    logger.error(f"简单URL也失败: {simple_response.status_code}")
                    return False
                
        except Exception as e:
            logger.error(f"发送Bark通知失败: {str(e)}")
            
            # 尝试使用最简单的URL格式作为最后的尝试
            try:
                simple_url = f"{self.bark_base_url}/{urllib.parse.quote(title)}/{urllib.parse.quote(message)}"
                logger.debug(f"最后尝试: {simple_url}")
                last_response = requests.get(simple_url, timeout=15)
                return last_response.status_code == 200
            except Exception as e2:
                logger.error(f"最后尝试也失败: {str(e2)}")
                return False

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

            # 构建通知内容
            title = "⚠️ YEI安全警报 ⚠️" if is_high_risk else "YEI监控警报"
            
            # 使用通用函数发送通知
            sound = "shake"
            
            success = self.send_bark_notification(
                title=title,
                message=message,
                group="YEI监控-警报",
                sound=sound,
                level="critical",
                is_high_risk=is_high_risk,
                call="1"
            )
            
            if success:
                logger.info(f"成功发送{'高风险' if is_high_risk else ''}警报通知")
            else:
                logger.error("发送警报通知失败")
                
        except Exception as e:
            logger.error(f"发送警报过程中发生错误: {str(e)}")
            
    