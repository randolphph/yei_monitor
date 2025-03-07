import asyncio
import logging
import time
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取Bark推送URL
BARK_URL = os.getenv("BARK_URL", "")
if not BARK_URL:
    logging.warning("未配置Bark URL，心跳通知将不会发送")

class HeartbeatMonitor:
    def __init__(self):
        self.logger = logging.getLogger("HeartbeatMonitor")
        self.morning_sent = False
        self.noon_sent = False
        self.evening_sent = False
        
    async def start(self):
        """启动心跳监控"""
        self.logger.info("心跳监控已启动")
        while True:
            try:
                await self._check_heartbeat()
                # 每10分钟检查一次
                await asyncio.sleep(600)
            except Exception as e:
                self.logger.error(f"心跳检测出错: {str(e)}")
                await asyncio.sleep(300)
    
    async def _check_heartbeat(self):
        """检查是否需要发送心跳通知"""
        now = datetime.now()
        current_hour = now.hour
        
        # 早上8点发送
        if 8 <= current_hour < 9 and not self.morning_sent:
            await self._send_heartbeat("早间")
            self.morning_sent = True
            self.noon_sent = False
            self.evening_sent = False
        
        # 中午12点发送
        elif 12 <= current_hour < 13 and not self.noon_sent:
            await self._send_heartbeat("午间")
            self.noon_sent = True
        
        # 晚上8点发送
        elif 20 <= current_hour < 21 and not self.evening_sent:
            await self._send_heartbeat("晚间")
            self.evening_sent = True
        
        # 重置状态（第二天）
        elif current_hour < 8:
            self.morning_sent = False
            self.noon_sent = False
            self.evening_sent = False
    
    async def _send_heartbeat(self, time_period):
        """发送心跳通知"""
        if not BARK_URL:
            self.logger.warning(f"{time_period}心跳通知未发送：未配置Bark URL")
            return
            
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = f"YEI监控系统 - {time_period}心跳"
            content = f"系统正常运行中\n时间: {current_time}"
            
            # 发送Bark通知（普通消息，使用轻微提示音）
            response = requests.post(
                BARK_URL,
                json={
                    "title": title,
                    "body": content,
                    "group": "YEI监控-心跳",
                    "icon": "https://sei.io/favicon.ico",
                    "sound": "bell",  # 使用轻微的提示音
                    "level": "passive"  # 设置为被动通知级别
                },
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"{time_period}心跳通知发送成功")
            else:
                self.logger.error(f"{time_period}心跳通知发送失败: {response.text}")
                
        except Exception as e:
            self.logger.error(f"{time_period}心跳通知发送出错: {str(e)}")
            
    def send_immediate_heartbeat(self):
        """立即发送一次心跳通知"""
        loop = asyncio.get_event_loop()
        loop.create_task(self._send_heartbeat("即时")) 