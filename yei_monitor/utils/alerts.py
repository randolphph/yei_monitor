import aiohttp
import urllib.parse
import json
import requests
import logging
from typing import Dict, Any, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AlertManager:
    def __init__(self, bark_key: str, bark_server: str):
        self.bark_key = bark_key
        self.bark_server = bark_server.rstrip('/')  # 移除末尾的斜杠
        # 构建完整的Bark URL
        self.bark_url = f"{self.bark_server}/{self.bark_key}" if self.bark_key else ""
        logger.info(f"初始化AlertManager，Bark URL: {self.bark_url}")

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
                
                # 尝试使用aiohttp发送（异步方式）
                try:
                    logger.debug(f"尝试使用aiohttp发送Bark通知: {self.bark_url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.post(self.bark_url, json=bark_data, timeout=10) as response:
                            if response.status != 200:
                                response_text = await response.text()
                                logger.error(f"Bark API 返回错误: {response.status} - {response_text}")
                                # 如果异步请求失败，尝试同步请求
                                raise Exception("异步请求失败，将尝试同步请求")
                            else:
                                logger.info(f"成功发送Bark{'高风险' if is_high_risk else ''}警报通知")
                                return
                except Exception as e:
                    logger.warning(f"使用aiohttp发送Bark通知失败: {str(e)}，尝试使用requests")
                    
                    # 尝试使用requests发送（同步方式）
                    try:
                        # 构建GET请求URL（备用方式）
                        encoded_title = urllib.parse.quote(title)
                        encoded_message = urllib.parse.quote(message)
                        get_url = f"{self.bark_server}/{self.bark_key}/{encoded_title}/{encoded_message}"
                        
                        # 添加参数
                        params = {
                            "group": "YEI监控-警报",
                            "sound": "alarm" if is_high_risk else "warning",
                            "level": "timeSensitive" if is_high_risk else "active",
                            "icon": "https://sei.io/favicon.ico"
                        }
                        
                        # 构建完整URL
                        get_url += "?" + "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
                        
                        logger.debug(f"尝试使用GET请求发送Bark通知: {get_url}")
                        response = requests.get(get_url, timeout=10)
                        
                        if response.status_code != 200:
                            logger.error(f"Bark API GET请求返回错误: {response.status_code} - {response.text}")
                        else:
                            logger.info(f"成功使用GET请求发送Bark{'高风险' if is_high_risk else ''}警报通知")
                            return
                    except Exception as e2:
                        logger.error(f"使用requests发送Bark通知失败: {str(e2)}")
                        
                        # 最后尝试最简单的URL
                        try:
                            simple_url = f"{self.bark_server}/{self.bark_key}/{encoded_title}/{encoded_message}"
                            logger.debug(f"尝试使用最简单的URL发送Bark通知: {simple_url}")
                            simple_response = requests.get(simple_url, timeout=10)
                            
                            if simple_response.status_code == 200:
                                logger.info("成功使用简单URL发送Bark通知")
                                return
                            else:
                                logger.error(f"简单URL请求失败: {simple_response.status_code}")
                        except Exception as e3:
                            logger.error(f"使用简单URL发送通知失败: {str(e3)}")
                        
        except Exception as e:
            logger.error(f"发送警报失败: {str(e)}") 