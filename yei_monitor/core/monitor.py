import asyncio
from datetime import datetime
from config.settings import Config
from core.contract import ContractManager
from core.state import ContractState
from utils.alerts import AlertManager
from utils.logger import setup_logger
from utils.amount_utils import format_amount, format_interest_rate, get_token_name, TOKEN_DECIMALS

logger = setup_logger(__name__)

class YEIMonitor:
    def __init__(self):
        self.config = Config()
        self.state = ContractState()
        self.contract_manager = ContractManager(self.config)
        self.alert_manager = AlertManager(
            self.config.BARK_KEY,
            self.config.BARK_SERVER
        )
        self.last_checked_block = 0

    async def initialize(self) -> bool:
        """初始化监控系统"""
        try:
            logger.info("正在初始化监控系统...")
            
            # 测试RPC连接
            if not await self.contract_manager.test_rpc_connection():
                logger.error("RPC连接测试失败")
                await self.alert_manager.send_alert("监控系统初始化失败: RPC连接测试失败")
                return False
            
            # 获取初始状态
            self.state.current_implementation = await self.contract_manager.get_implementation_address()
            
            # 获取当前区块号作为起始监控点
            self.last_checked_block = await self.contract_manager.w3.eth.block_number

            logger.info(f"初始状态: 代理合约地址={self.state.current_implementation}, 开始监控区块: {self.last_checked_block}")
            
            return True
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            await self.alert_manager.send_alert("监控系统初始化失败", {"error": str(e)})
            return False

    async def monitor_implementation_events(self):
        """监控合约事件
        
        在可升级代理模式中，我们监控代理合约地址发出的事件，
        但使用实现合约的ABI来解析这些事件
        """
        try:
            logger.info(f"开始监控合约事件，从区块 {self.last_checked_block} 开始")
            while True:
                try:
                    # 获取当前区块
                    current_block = await self.contract_manager.w3.eth.block_number
                    
                    # 如果有新区块，检查事件
                    if current_block > self.last_checked_block:
                        # 获取这段时间内的所有事件
                        events = await self.contract_manager.get_all_events(
                            self.last_checked_block + 1, 
                            current_block
                        )
                        
                        # 处理事件
                        for event in events:
                            await self.handle_implementation_event(event)
                        
                        # 更新最后检查的区块
                        self.last_checked_block = current_block
                    
                    # 等待15秒再检查
                    await asyncio.sleep(15)
                    
                except Exception as e:
                    logger.error(f"区块事件检查错误: {str(e)}")
                    await asyncio.sleep(30)  # 出错后等待较长时间再重试
                    
        except Exception as e:
            logger.error(f"合约事件监控错误: {str(e)}")
            await self.alert_manager.send_alert("合约事件监控发生错误", {"error": str(e)})

    def _get_event_type(self, event_name: str) -> dict:
        """获取事件类型信息
        
        Args:
            event_name: 事件名称
            
        Returns:
            dict: 包含事件类型信息的字典
        """
        return {
            'is_fund_event': event_name in ['Supply', 'Withdraw', 'Borrow', 'Repay', 'LiquidationCall'],
            'is_high_risk_event': event_name in ['LiquidationCall', 'FlashLoan']
        }
    
    async def _get_asset_addresses(self, event) -> list:
        """从事件中获取需要查询的资产地址列表
        
        Args:
            event: 事件对象
            
        Returns:
            list: 资产地址列表
        """
        addresses = []
        if hasattr(event.args, 'reserve'):
            addresses.append(event.args.reserve)
        elif hasattr(event.args, 'asset'):
            addresses.append(event.args.asset)
        elif hasattr(event.args, 'collateralAsset') and hasattr(event.args, 'debtAsset'):
            addresses.extend([event.args.collateralAsset, event.args.debtAsset])
        return addresses

    async def _get_asset_liquidity_data(self, event) -> dict:
        """获取事件相关的资产流动性数据
        
        Args:
            event: 事件对象
            
        Returns:
            dict: 资产流动性数据字典 {asset_address: liquidity_data}
        """
        asset_liquidity_data = {}
        try:
            addresses = await self._get_asset_addresses(event)
            for address in addresses:
                try:
                    liquidity_data = await self.contract_manager.get_asset_liquidity(address)
                    if liquidity_data:
                        asset_liquidity_data[address.lower()] = liquidity_data
                    else:
                        logger.warning(f"获取资产 {address} 的流动性数据为空")
                except Exception as e:
                    logger.error(f"获取资产 {address} 的流动性数据失败: {str(e)}")
        except Exception as e:
            logger.error(f"处理资产地址失败: {str(e)}")
        return asset_liquidity_data

    async def _should_send_notification(self, event_name: str) -> tuple:
        """判断是否需要发送通知
        
        Args:
            event_name: 事件名称
            
        Returns:
            tuple: (是否发送通知, 通知原因)
        """
        event_types = self._get_event_type(event_name)
        need_notification = (
            self.config.NOTIFY_ALL_EVENTS or 
            event_types['is_high_risk_event']
        )
        reason = "高风险事件" if event_types['is_high_risk_event'] else "根据配置发送所有事件"
        return need_notification, reason

    async def handle_implementation_event(self, event):
        """处理合约事件"""
        try:
            event_name = event.event
            timestamp = datetime.now()
            
            # 检查是否为基本解析的事件
            is_basic_event = not hasattr(event, 'args') or not event.args
            logger.info(f"处理事件: {event_name}, 是否为基本解析事件: {is_basic_event}")
            
            # 获取事件类型信息
            event_types = self._get_event_type(event_name)
            
            # 获取资产流动性数据
            asset_liquidity_data = {}
            if not is_basic_event:
                asset_liquidity_data = await self._get_asset_liquidity_data(event)
                if not asset_liquidity_data:
                    logger.warning(f"未能获取到任何资产流动性数据: {event_name}")
            
            try:
                # 构建事件消息
                message = self._build_event_message(event, is_basic_event, timestamp, asset_liquidity_data)
                
                # 记录事件到日志
                logger.info(f"检测到事件: {event_name}")
                logger.info(f"事件详情: {message}")
                
                # 检查流动性状况（仅针对资金变动事件）
                if event_types['is_fund_event'] and not is_basic_event and asset_liquidity_data:
                    await self.check_liquidity(event, message, asset_liquidity_data)
                
                # 发送通知
                need_notification, reason = await self._should_send_notification(event_name)
                if need_notification:
                    logger.info(f"发送通知 ({reason}): {event_name}")
                    
                    # 判断事件金额是否超过limit阈值
                    is_important = False
                    call_value = "0"  # 默认不进行语音通知
                    
                    # 获取事件金额和资产地址
                    event_amount = 0
                    asset_address = None
                    
                    if hasattr(event.args, 'amount'):
                        event_amount = event.args.amount
                    elif hasattr(event.args, 'debtToCover'):
                        event_amount = event.args.debtToCover
                    elif hasattr(event.args, 'value'):
                        event_amount = event.args.value
                        
                    if hasattr(event.args, 'reserve'):
                        asset_address = event.args.reserve
                    elif hasattr(event.args, 'asset'):
                        asset_address = event.args.asset
                    elif hasattr(event.args, 'debtAsset'):
                        asset_address = event.args.debtAsset
                    
                    # 如果有资产地址和事件金额，检查是否超过limit
                    if asset_address and event_amount > 0:
                        token_info = TOKEN_DECIMALS.get(asset_address.lower())
                        
                        if token_info and "limit" in token_info and "decimals" in token_info:
                            # 将事件金额转换为实际金额（考虑代币精度）
                            decimals = token_info["decimals"]
                            actual_amount = event_amount / (10 ** decimals)
                            limit = token_info["limit"]
                            
                            # 判断是否超过limit
                            if actual_amount >= limit:
                                is_important = True
                                call_value = "1"  # 进行语音通知
                                logger.info(f"事件金额 {actual_amount} {token_info['symbol']} 超过阈值 {limit}，发送重要通知")
                            else:
                                logger.info(f"事件金额 {actual_amount} {token_info['symbol']} 未超过阈值 {limit}，发送普通通知")
                    
                    # 根据优先级发送不同级别的通知
                    if is_important:
                        # 发送重要通知（带语音提醒）
                        await self.alert_manager.send_alert(message, is_high_risk=True, call_value=call_value)
                    else:
                        # 发送普通通知
                        await self.alert_manager.send_alert(message)
                    
            except Exception as e:
                error_msg = f"处理事件消息失败: {str(e)}"
                logger.error(error_msg)
                await self.alert_manager.send_alert(f"事件处理异常\n事件: {event_name}\n错误: {error_msg}")
                
        except Exception as e:
            error_msg = f"处理合约事件发生严重错误: {str(e)}"
            logger.error(error_msg)
            await self.alert_manager.send_alert(f"严重错误\n事件: {event_name}\n错误: {error_msg}", is_high_risk=True)

    def _build_event_message(self, event, is_basic_event, timestamp, asset_liquidity_data):
        """构建事件消息
        
        Args:
            event: 事件对象
            is_basic_event: 是否为基本解析事件
            timestamp: 时间戳
            asset_liquidity_data: 资产流动性数据字典 {asset_address: liquidity_data}
        
        Returns:
            str: 格式化的消息文本
        """
        event_name = event.event
        
        def get_liquidity_info(asset_address):
            """获取资产流动性信息的格式化文本"""
            liquidity_data = asset_liquidity_data.get(asset_address.lower())
            if liquidity_data:
                return f"剩余流动性: {format_amount(liquidity_data['availableLiquidity'], asset_address)}\n利用率: {liquidity_data['utilizationRate']:.2f}%"
            return ""
        
        if event_name == "Supply":
            if is_basic_event:
                message = (
                    f"📥 存款事件 (基本信息)\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"交易: {getattr(event, 'transactionHash', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                asset_name = get_token_name(event.args.reserve)
                liquidity_info = get_liquidity_info(event.args.reserve)
                message = (
                    f"📥 存款事件\n"
                    f"资产: {asset_name}\n"
                    f"用户: {event.args.user}\n"
                    f"代表: {event.args.onBehalfOf}\n"
                    f"金额: {format_amount(event.args.amount, event.args.reserve)}\n"
                    f"{liquidity_info}\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        elif event_name == "Withdraw":
            if is_basic_event:
                message = (
                    f"📤 提款事件 (基本信息)\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"交易: {getattr(event, 'transactionHash', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                asset_name = get_token_name(event.args.reserve)
                liquidity_info = get_liquidity_info(event.args.reserve)
                message = (
                    f"📤 提款事件\n"
                    f"资产: {asset_name}\n"
                    f"用户: {event.args.user}\n"
                    f"接收: {event.args.to}\n"
                    f"金额: {format_amount(event.args.amount, event.args.reserve)}\n"
                    f"{liquidity_info}\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        elif event_name == "Borrow":
            if is_basic_event:
                message = (
                    f"💰 借款事件 (基本信息)\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"交易: {getattr(event, 'transactionHash', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                asset_name = get_token_name(event.args.reserve)
                liquidity_info = get_liquidity_info(event.args.reserve)
                message = (
                    f"💰 借款事件\n"
                    f"资产: {asset_name}\n"
                    f"用户: {event.args.user}\n"
                    f"代表: {event.args.onBehalfOf}\n"
                    f"金额: {format_amount(event.args.amount, event.args.reserve)}\n"
                    f"{liquidity_info}\n"
                    f"利率模式: {event.args.interestRateMode}\n"
                    f"借款利率: {format_interest_rate(event.args.borrowRate)}\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        elif event_name == "Repay":
            if is_basic_event:
                message = (
                    f"💸 还款事件 (基本信息)\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"交易: {getattr(event, 'transactionHash', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                asset_name = get_token_name(event.args.reserve)
                liquidity_info = get_liquidity_info(event.args.reserve)
                message = (
                    f"💸 还款事件\n"
                    f"资产: {asset_name}\n"
                    f"用户: {event.args.user}\n"
                    f"还款人: {event.args.repayer}\n"
                    f"金额: {format_amount(event.args.amount, event.args.reserve)}\n"
                    f"{liquidity_info}\n"
                    f"使用AToken: {event.args.useATokens}\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        elif event_name == "LiquidationCall":
            if is_basic_event:
                message = (
                    f"⚠️ 清算事件 (基本信息)\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"交易: {getattr(event, 'transactionHash', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                collateral_asset_name = get_token_name(event.args.collateralAsset)
                debt_asset_name = get_token_name(event.args.debtAsset)
                
                collateral_liquidity_info = get_liquidity_info(event.args.collateralAsset)
                debt_liquidity_info = get_liquidity_info(event.args.debtAsset)
                
                message = (
                    f"⚠️ 清算事件\n"
                    f"抵押品: {collateral_asset_name}\n"
                    f"债务资产: {debt_asset_name}\n"
                    f"用户: {event.args.user}\n"
                    f"清算金额: {format_amount(event.args.debtToCover, event.args.debtAsset)}\n"
                    f"清算抵押品数量: {format_amount(event.args.liquidatedCollateralAmount, event.args.collateralAsset)}\n"
                    f"清算人: {event.args.liquidator}\n"
                    f"抵押品资产状态:\n{collateral_liquidity_info}\n"
                    f"债务资产状态:\n{debt_liquidity_info}\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        elif event_name == "FlashLoan":
            if is_basic_event:
                message = (
                    f"⚡ 闪电贷事件 (基本信息)\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"交易: {getattr(event, 'transactionHash', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                asset_name = get_token_name(event.args.asset)
                liquidity_info = get_liquidity_info(event.args.asset)
                message = (
                    f"⚡ 闪电贷事件\n"
                    f"目标: {event.args.target}\n"
                    f"发起人: {event.args.initiator}\n"
                    f"资产: {asset_name}\n"
                    f"金额: {format_amount(event.args.amount, event.args.asset)}\n"
                    f"{liquidity_info}\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        else:
            # 对于未知事件或其他事件
            if is_basic_event:
                message = (
                    f"📝 {event_name} (基本信息)\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"交易: {getattr(event, 'transactionHash', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                message = (
                    f"📝 其他事件: {event_name}\n"
                    f"区块: {getattr(event, 'blockNumber', '未知')}\n"
                    f"时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"详情: {event.args}"
                )
                
        return message

    async def check_liquidity(self, event, event_message, liquidity_cache):
        """检查流动性状况"""
        try:
            # 获取事件相关的资产地址
            asset_addresses = await self._get_asset_addresses(event)
            if not asset_addresses:
                logger.warning(f"无法获取事件相关的资产地址: {event.event}")
                return
            
            # 获取事件名称和金额
            event_name = event.event
            
            # 获取事件金额
            event_amount = 0
            if hasattr(event.args, 'amount'):
                event_amount = event.args.amount
            elif hasattr(event.args, 'debtToCover'):
                event_amount = event.args.debtToCover
            elif hasattr(event.args, 'value'):
                event_amount = event.args.value
            
            # 遍历所有相关资产
            for asset_address in asset_addresses:
                # 获取资产信息
                asset_symbol = get_token_name(asset_address)
                
                # 获取当前流动性数据
                current_liquidity_data = await self.contract_manager.get_asset_liquidity(asset_address)
                if not current_liquidity_data:
                    logger.warning(f"无法获取资产 {asset_symbol} 的流动性数据")
                    continue
                
                # 获取当前利用率
                current_utilization = current_liquidity_data.get('utilizationRate', 0)
                
                # 计算事件对流动性的影响
                event_impact_percentage = 0
                
                # 使用aToken总量计算变化百分比
                atoken_total_supply = current_liquidity_data.get('totalSupply', 0)
                if atoken_total_supply > 0 and event_amount > 0:
                    event_impact_percentage = (event_amount / atoken_total_supply) * 100
                
                # 确定流动性变化方向
                impact_direction = ""
                impact_sign = ""
                if event_name in ["Supply", "Repay"]:
                    impact_direction = "增加"  # 这些事件增加流动性
                    impact_sign = "+"
                elif event_name in ["Withdraw", "Borrow"]:
                    impact_direction = "减少"  # 这些事件减少流动性
                    impact_sign = "-"
                else:  # LiquidationCall等复杂事件
                    impact_direction = "变化"
                    impact_sign = "±"
                
                logger.info(f"事件'{event_name}'导致{asset_symbol}流动性{impact_direction}{event_impact_percentage:.8f}%")
                
                # 标记是否触发了流动性异常波动阈值
                liquidity_change_triggered = event_impact_percentage >= self.config.LIQUIDITY_CHANGE_THRESHOLD
                
                # 如果流动性变化超过阈值，发送通知
                if liquidity_change_triggered:
                    # 判断事件金额是否超过limit阈值
                    is_important = False
                    call_value = "0"  # 默认不进行语音通知
                    
                    # 检查是否超过limit
                    if asset_address and event_amount > 0:
                        token_info = TOKEN_DECIMALS.get(asset_address.lower())
                        
                        if token_info and "limit" in token_info and "decimals" in token_info:
                            # 将事件金额转换为实际金额（考虑代币精度）
                            decimals = token_info["decimals"]
                            actual_amount = event_amount / (10 ** decimals)
                            limit = token_info["limit"]
                            
                            # 判断是否超过limit
                            if actual_amount >= limit:
                                is_important = True
                                call_value = "1"  # 进行语音通知
                                logger.info(f"流动性检查: 事件金额 {actual_amount} {token_info['symbol']} 超过阈值 {limit}，发送重要通知")
                            else:
                                logger.info(f"流动性检查: 事件金额 {actual_amount} {token_info['symbol']} 未超过阈值 {limit}，发送普通通知")
                    
                    await self.alert_manager.send_alert(
                        f"⚠️ {asset_symbol}资产流动性{impact_direction}超过阈值\n"
                        f"当前利用率: {current_utilization:.2f}%\n"
                        f"变化幅度: {impact_sign}{event_impact_percentage:.2f}%\n"
                        f"事件类型: {event_name}\n"
                        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"\n--- 触发事件 ---\n{event_message}",
                        is_high_risk=is_important,
                        call_value=call_value
                    )
                    logger.warning(f"{asset_symbol}资产流动性{impact_direction}超过阈值: {impact_sign}{event_impact_percentage:.2f}%, 当前利用率: {current_utilization:.2f}%")
            
                    # 只有在流动性异常波动阈值被触发后才检测资金池利用率
                    if current_utilization >= self.config.ASSET_UTILIZATION_WARNING_THRESHOLD:
                        # 计算当前流动性百分比
                        liquidity_percentage = 100 - current_utilization
                        
                        # 准备事件影响信息
                        event_impact_info = ""
                        if event_impact_percentage > 0:
                            event_impact_info = f"本次事件流动性影响: {impact_sign}{event_impact_percentage:.2f}%\n"
                        
                        await self.alert_manager.send_alert(
                            f"⚠️ {asset_symbol}资金利用率超过阈值\n"
                            f"当前利用率: {current_utilization:.2f}%\n"
                            f"警戒线: {self.config.ASSET_UTILIZATION_WARNING_THRESHOLD:.2f}%\n"
                            f"当前流动性: {liquidity_percentage:.2f}%\n"
                            f"{event_impact_info}"
                            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"\n--- 触发事件 ---\n{event_message}",
                            is_high_risk=is_important,
                            call_value=call_value
                        )
                        logger.warning(f"{asset_symbol}资产利用率达到警戒线: {current_utilization:.2f}%, 剩余流动性: {liquidity_percentage:.2f}%")
                else:
                    # 如果没有触发流动性异常波动阈值，记录日志但不检查利用率
                    logger.info(f"{asset_symbol}流动性变化未超过阈值({event_impact_percentage:.2f}% < {self.config.LIQUIDITY_CHANGE_THRESHOLD:.2f}%)，跳过利用率检查")
            
                logger.info(f"资产流动性检查完成 - {asset_symbol}利用率: {current_utilization:.2f}%")
            
        except Exception as e:
            logger.error(f"检查流动性状况失败: {str(e)}")

    async def check_contract_state(self):
        """检查合约状态"""
        try:
            # 检查代理合约地址
            current_implementation = await self.contract_manager.get_implementation_address()
            if self.state.update_implementation(current_implementation) and not self.state.is_first_run:
                await self.alert_manager.send_alert(
                    f"⚠️ 代理合约地址变更确认\n"
                    f"原地址: {self.state.current_implementation}\n"
                    f"新地址: {current_implementation}\n"
                    f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

            self.state.is_first_run = False
            self.state.last_check_time = int(datetime.now().timestamp())

        except Exception as e:
            logger.error(f"状态检查错误: {str(e)}")
            await self.alert_manager.send_alert("状态检查失败", {"error": str(e)})

    async def periodic_check(self):
        """定期检查"""
        while True:
            await self.check_contract_state()
            await asyncio.sleep(self.config.CHECK_INTERVAL)

    async def run(self):
        """运行监控系统"""
        if not await self.initialize():
            logger.error("初始化失败，监控系统退出")
            return

        try:
            tasks = [
                self.monitor_implementation_events(),
                self.periodic_check()
            ]
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"监控系统运行错误: {str(e)}")
            await self.alert_manager.send_alert("监控系统发生错误", {"error": str(e)}) 