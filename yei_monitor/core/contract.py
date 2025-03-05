from web3 import AsyncWeb3
from config.settings import Config
from utils.logger import setup_logger
from utils.amount_utils import TOKEN_DECIMALS
import json

logger = setup_logger(__name__)

class ContractManager:
    def __init__(self, config: Config):
        self.config = config
        # 使用EVM兼容的RPC端点
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(
            config.RPC_URL,
            request_kwargs={
                'headers': {
                    'Content-Type': 'application/json',
                }
            }
        ))
        
        # 注意：在可升级代理模式中，我们使用代理地址但使用实现合约的ABI
        # 这是因为事件从代理合约地址发出，但事件的结构和定义来自实现合约
        self.contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(config.PROXY_ADDRESS),
            abi=config.IMPLEMENTATION_ABI
        )

    async def test_rpc_connection(self) -> bool:
        """测试RPC连接和合约调用"""
        try:
            # 测试基本RPC连接
            logger.info(f"正在测试RPC连接: {self.config.RPC_URL}")
            chain_id = await self.w3.eth.chain_id
            latest_block = await self.w3.eth.block_number
            logger.info(f"链ID: {chain_id}, 最新区块: {latest_block}")

            # 测试合约调用
            logger.info("正在测试合约调用...")
            try:
                # 尝试获取池版本
                pool_revision = await self.contract.functions.POOL_REVISION().call()
                logger.info(f"池版本: {pool_revision}")
                
                logger.info("合约调用测试成功")
            except Exception as e:
                logger.error(f"合约调用失败: {str(e)}")
                raise

            logger.info("RPC连接测试完成，一切正常")
            return True

        except Exception as e:
            logger.error(f"RPC连接测试失败: {str(e)}")
            return False

    async def get_implementation_address(self) -> str:
        """获取实现合约地址"""
        return self.config.PROXY_ADDRESS
        
    async def create_event_filter(self, event_name, from_block):
        """创建事件过滤器
        
        在可升级代理模式中，我们监控代理合约地址发出的事件，
        但使用实现合约的ABI来解析这些事件
        
        Args:
            event_name: 要监控的事件名称
            from_block: 起始区块
            
        Returns:
            事件过滤器对象
        """
        try:
            # 获取当前区块
            latest_block = await self.w3.eth.block_number
            to_block = min(latest_block, from_block + 1000)  # 限制区块范围
            
            # 获取事件函数对象
            event_function = getattr(self.contract.events, event_name)
            
            # 创建过滤器参数
            filter_params = {
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': self.w3.to_checksum_address(self.config.PROXY_ADDRESS)
            }
            
            return {
                'filter': filter_params,
                'event_name': event_name,
                'event_function': event_function
            }
        except Exception as e:
            return None
    
    async def get_all_events(self, from_block, to_block=None):
        """获取关键资金安全相关事件
        
        只监听与资金安全相关的特定事件类型，减少解析错误并提高系统效率
        
        Args:
            from_block: 起始区块
            to_block: 结束区块，默认为当前区块
            
        Returns:
            事件列表
        """
        try:
            if to_block is None:
                to_block = await self.w3.eth.block_number
                
            # 限制区块范围，避免请求过大
            if to_block - from_block > 1000:
                logger.warning(f"区块范围过大，限制为1000个区块")
                to_block = from_block + 1000
                
            logger.info(f"获取事件，区块范围: {from_block} - {to_block}")
            
            # 存储所有事件的列表
            all_events = []
            
            # 定义关键安全事件列表
            key_events = [
                'Supply',      # 存款事件
                'Withdraw',    # 提款事件
                'Borrow',      # 借款事件
                'Repay',       # 还款事件
                'LiquidationCall',  # 清算事件
                'FlashLoan'    # 闪电贷事件
            ]
            
            # 只监听关键事件
            for event_name in key_events:
                try:
                    # 创建特定事件的过滤器信息
                    filter_info = await self.create_event_filter(event_name, from_block)
                    if filter_info:
                        # 获取事件
                        try:
                            # 使用Web3的getLogs方法获取日志
                            logs = await self.w3.eth.get_logs(filter_info['filter'])
                            
                            # 解析日志为事件
                            events = []
                            for log in logs:
                                try:
                                    # 使用相应的事件函数处理日志
                                    parsed_event = filter_info['event_function']().process_log(log)
                                    events.append(parsed_event)
                                except:
                                    # 尝试使用基本解析作为备用方法
                                    basic_event = await self.basic_decode_log(log)
                                    if basic_event and basic_event.event == event_name:
                                        events.append(basic_event)
                            
                            all_events.extend(events)
                        except Exception as e:
                            logger.error(f"获取 {event_name} 事件日志失败: {str(e)}")
                except Exception as e:
                    logger.error(f"获取 {event_name} 事件失败: {str(e)}")
            
            logger.info(f"总共获取到 {len(all_events)} 个关键安全事件")
            return all_events
        except Exception as e:
            logger.error(f"获取事件失败: {str(e)}")
            return []
            
    async def decode_log(self, log):
        """解码日志事件
        
        使用实现合约的ABI解析从代理合约发出的事件
        """
        try:
            # 尝试解码日志
            for event_name in self.contract.events:
                try:
                    decoded_event = self.contract.events[event_name]().process_log(log)
                    return decoded_event
                except:
                    continue
            
            # 如果标准解码失败，尝试低级别解析
            return await self.basic_decode_log(log)
        except Exception as e:
            logger.error(f"解码日志失败: {str(e)}")
            return None
        
    async def basic_decode_log(self, log):
        """基本日志解析
        
        当标准解析失败时，尝试从topics中提取基本信息
        """
        try:
            # 常见事件签名 - 只保留关键安全事件
            event_signatures = {
                # Supply事件的签名
                "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61": "Supply",
                # Withdraw事件的签名
                "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7": "Withdraw",
                # Borrow事件的签名
                "0xc6a898309e823ee50bac40dbae5b8d3b9fede325bbcba08b4a4c1896cd62dfab": "Borrow",
                # Repay事件的签名
                "0x4cdde6e09bb755c9a5589ebaec640bbfedff1362d4b255ebf8339782b9942faa": "Repay",
                # LiquidationCall事件的签名
                "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286": "LiquidationCall",
                # FlashLoan事件的签名
                "0x631042c832b07452973831137f2d73e395028b44b250dedc5abb0ee766e168ac": "FlashLoan",
            }
            
            if not log.get('topics') or len(log.get('topics', [])) == 0:
                return None
            
            # 获取事件签名（第一个topic）
            event_signature = log['topics'][0].hex()
            event_name = event_signatures.get(event_signature)
            
            if not event_name:
                return None  # 忽略非关键事件
            
            # 创建一个基本的事件对象
            basic_event = {
                'event': event_name,
                'address': log.get('address', ''),
                'blockNumber': log.get('blockNumber', 0),
                'transactionHash': log.get('transactionHash', '').hex() if log.get('transactionHash') else '',
                'topics': [t.hex() for t in log.get('topics', [])],
                'data': log.get('data', ''),
                'args': {}  # 空参数，因为我们无法解析
            }
            
            # 尝试从topics提取一些基本参数
            if len(log.get('topics', [])) > 1:
                try:
                    # 第二个topic通常是地址（如用户地址）
                    address = '0x' + log['topics'][1].hex()[-40:]
                    basic_event['args']['address'] = self.w3.to_checksum_address(address)
                except:
                    pass
            
            return type('BasicEvent', (), basic_event)  # 创建一个简单的对象
        except Exception as e:
            logger.error(f"基本日志解析失败: {str(e)}")
            return None

    async def get_reserve_data(self, asset_address):
        """获取特定资产的储备数据
        
        Args:
            asset_address: 资产合约地址
            
        Returns:
            dict: 包含资产储备数据的字典
        """
        try:
            asset_address = self.w3.to_checksum_address(asset_address)
            reserve_data = await self.contract.functions.getReserveData(asset_address).call()
            
            # 根据YEI合约的getReserveData返回结构调整字段映射
            # 参考实现合约ABI中的ReserveData结构
            data = {
                "configuration": reserve_data[0],
                "liquidityIndex": reserve_data[1],
                "currentLiquidityRate": reserve_data[2],
                "variableBorrowIndex": reserve_data[3],
                "currentVariableBorrowRate": reserve_data[4],
                "currentStableBorrowRate": reserve_data[5],
                "lastUpdateTimestamp": reserve_data[6],
                "id": reserve_data[7],
                "aTokenAddress": reserve_data[8],
                "stableDebtTokenAddress": reserve_data[9],
                "variableDebtTokenAddress": reserve_data[10],
                "interestRateStrategyAddress": reserve_data[11],
                "accruedToTreasury": reserve_data[12] if len(reserve_data) > 12 else 0,
                "unbacked": reserve_data[13] if len(reserve_data) > 13 else 0,
                "isolationModeTotalDebt": reserve_data[14] if len(reserve_data) > 14 else 0
            }
            
            logger.debug(f"获取到资产储备数据 - 地址: {asset_address}")
            return data
        except Exception as e:
            logger.error(f"获取资产储备数据失败 - 地址: {asset_address}, 错误: {str(e)}")
            return None
            
    async def get_asset_liquidity(self, asset_address):
        """获取特定资产的流动性信息
        
        Args:
            asset_address: 资产合约地址
            
        Returns:
            dict: 包含流动性信息的字典
        """
        try:
            asset_address = self.w3.to_checksum_address(asset_address)
            
            # 获取资产的代币信息 - 将地址转为小写进行查询
            token_info = TOKEN_DECIMALS.get(asset_address.lower())
            if not token_info:
                logger.error(f"未找到资产信息 - 地址: {asset_address}")
                return None
            
            # 获取资产的AToken合约地址
            reserve_data = await self.get_reserve_data(asset_address)
            if not reserve_data:
                logger.error(f"无法获取资产储备数据 - 地址: {asset_address}")
                return None
                
            a_token_address = reserve_data.get('aTokenAddress')
            if not a_token_address:
                logger.error(f"无法获取AToken地址 - 资产: {asset_address}")
                return None
                
            # 获取AToken的总供应量（等于总存款量）
            a_token = self.w3.eth.contract(
                address=self.w3.to_checksum_address(a_token_address),
                abi=self.config.ATOKEN_ABI  # 使用完整的aToken ABI
            )
            
            try:
                total_supply = await a_token.functions.totalSupply().call()
                logger.debug(f"成功获取totalSupply: {total_supply}")
            except Exception as e:
                # 尝试使用简化ABI
                try:
                    logger.debug("尝试使用简化ABI")
                    simple_abi = [{"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
                    simple_contract = self.w3.eth.contract(
                        address=self.w3.to_checksum_address(a_token_address),
                        abi=simple_abi
                    )
                    total_supply = await simple_contract.functions.totalSupply().call()
                except Exception as simple_error:
                    # 尝试使用不同的方法获取totalSupply
                    try:
                        logger.debug("尝试通过其他方式调用")
                        total_supply = await self.w3.eth.call(
                            {"to": self.w3.to_checksum_address(a_token_address), 
                             "data": self.w3.keccak(text="totalSupply()")[0:4].hex()})
                        total_supply = int(total_supply.hex(), 16)
                        logger.debug(f"通过raw call获取totalSupply成功: {total_supply}")
                    except Exception as raw_error:
                        logger.error(f"通过raw call调用失败: {str(raw_error)}")
                        total_supply = 0
            
            # 获取借款代币合约地址
            variable_debt_token_address = reserve_data.get('variableDebtTokenAddress')
            stable_debt_token_address = reserve_data.get('stableDebtTokenAddress')
            
            # 获取借款总额
            total_borrows = 0
            if variable_debt_token_address:
                variable_debt_token = self.w3.eth.contract(
                    address=self.w3.to_checksum_address(variable_debt_token_address),
                    abi=self.config.ATOKEN_ABI  # 使用ATOKEN_ABI替代ERC20_ABI
                )
                try:
                    variable_borrows = await variable_debt_token.functions.totalSupply().call()
                    total_borrows += variable_borrows
                except Exception as e:
                    logger.error(f"获取可变利率借款总额失败: {str(e)}")
            
            if stable_debt_token_address:
                stable_debt_token = self.w3.eth.contract(
                    address=self.w3.to_checksum_address(stable_debt_token_address),
                    abi=self.config.ATOKEN_ABI  # 使用ATOKEN_ABI替代ERC20_ABI
                )
                try:
                    stable_borrows = await stable_debt_token.functions.totalSupply().call()
                    total_borrows += stable_borrows
                except Exception as e:
                    logger.error(f"获取固定利率借款总额失败: {str(e)}")
            
            # 计算利用率
            utilization_rate = 0
            if total_supply > 0:
                utilization_rate = (total_borrows / total_supply) * 100
            
            # 返回资产流动性信息
            return {
                "symbol": token_info["symbol"],
                "decimals": token_info["decimals"],
                "totalSupply": total_supply,
                "totalBorrows": total_borrows,
                "availableLiquidity": total_supply - total_borrows,
                "utilizationRate": utilization_rate
            }
            
        except Exception as e:
            logger.error(f"获取资产流动性信息失败: {str(e)}")
            return None
            