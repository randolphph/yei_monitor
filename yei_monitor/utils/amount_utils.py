from decimal import Decimal, getcontext
from typing import Union, Dict, Optional

# 设置高精度小数运算
getcontext().prec = 36

# 资产符号与精度的映射（常见ERC20代币的精度）
DEFAULT_DECIMALS = 18  # 大多数ERC20代币使用18位精度

# 常见稳定币和资产的精度映射
# 所有地址均使用小写，便于查询
TOKEN_DECIMALS: Dict[str, dict] = {
    # 初始预设常见代币，将由动态获取的数据补充
    # 如果合约调用失败，至少有这些基础代币信息
    "0x3894085ef7ff0f0aedf52e2a2704928d1ec074f1": {"symbol": "USDC", "decimals": 6, "limit": 50000},
    "0xe30fedd158a2e3b13e9badaeabafc5516e95e8c7": {"symbol": "WSEI", "decimals": 18, "limit": 250000},
    "0x5cf6826140c1c56ff49c808a1a75407cd1df9423": {"symbol": "ISEI", "decimals": 6, "limit": 250000 },
    "0x160345fc359604fc6e70e3c5facbde5f7a9342d8": {"symbol": "WETH", "decimals": 18, "limit": 25},
    "0x0555e30da8f98308edb960aa94c0db47230d2b9c": {"symbol": "WBTC", "decimals": 8, "limit": 0.5},
    "0x37a4dd9ced2b19cfe8fac251cd727b5787e45269": {"symbol": "fastUSD", "decimals": 18, "limit": 50000},
    "0x541fd749419ca806a8bc7da8ac23d346f2df8b77": {"symbol": "SolvBTC", "decimals": 18, "limit": 0.5},
    "0xb75d0b03c06a926e488e2659df1a861f860bd3d1": {"symbol": "USDT", "decimals": 6, "limit": 50000},
    "0xdf77686d99667ae56bc18f539b777dbc2bbe3e9f": {"symbol": "sfastUSD", "decimals": 18, "limit": 50000},
    "0x80eede496655fb9047dd39d9f418d5483ed600df": {"symbol": "frxUSD", "decimals": 18, "limit": 50000},
    "0x3ec3849c33291a9ef4c5db86de593eb4a37fde45": {"symbol": "sfrxETH", "decimals": 18, "limit": 25},
    "0x5bff88ca1442c2496f7e475e9e7786383bc070c0": {"symbol": "sfrxUSD", "decimals": 18, "limit": 50000},
    "0x43edd7f3831b08fe70b7555ddd373c8bf65a9050": {"symbol": "frxETH", "decimals": 18, "limit": 250000},
}

def get_token_name(asset_address: str) -> str:
    """
    从合约地址获取代币名称
    
    Args:
        asset_address: 资产合约地址
        
    Returns:
        代币名称/符号，如果未知则返回缩短的地址
    """
    # 直接使用小写地址查找
    token_info = TOKEN_DECIMALS.get(asset_address.lower())
    if token_info:
        return token_info["symbol"]
    
    # 如果找不到对应的代币符号，返回缩短的地址
    return f"{asset_address[:6]}...{asset_address[-4:]}"

def format_large_number(number: Decimal) -> str:
    """
    将大数字格式化为易读的形式，使用K、M、B等单位
    
    Args:
        number: 要格式化的数字
        
    Returns:
        格式化后的字符串
    """
    abs_num = abs(number)
    if abs_num >= Decimal('1e9'):
        return f"{(number / Decimal('1e9')).quantize(Decimal('0.01'))}B"
    elif abs_num >= Decimal('1e6'):
        return f"{(number / Decimal('1e6')).quantize(Decimal('0.01'))}M"
    elif abs_num >= Decimal('1e3'):
        return f"{(number / Decimal('1e3')).quantize(Decimal('0.01'))}K"
    else:
        return str(number.quantize(Decimal('0.01')))

def format_amount(amount: Union[int, str], asset_address: Optional[str] = None) -> str:
    """
    格式化代币金额，将链上金额转换为可读格式
    
    Args:
        amount: 链上金额（整数）
        asset_address: 资产合约地址，用于确定精度
        
    Returns:
        格式化后的金额字符串
    """
    try:
        # 转换为Decimal以确保精度
        raw_amount = Decimal(str(amount))
        
        # 获取资产的精度
        decimals = DEFAULT_DECIMALS
        symbol = ""
        
        if asset_address:
            # 直接使用小写地址查找
            token_info = TOKEN_DECIMALS.get(asset_address.lower())
            if token_info:
                decimals = token_info["decimals"]
                symbol = token_info["symbol"]
        
        # 应用精度转换
        formatted_amount = raw_amount / (Decimal(10) ** decimals)
        
        # 使用新的格式化函数
        result = format_large_number(formatted_amount)
        
        # 添加代币符号
        if symbol:
            result = f"{result} {symbol}"
            
        return result
    except Exception as e:
        return f"{amount} (转换错误: {str(e)})"

def format_amount_with_raw(amount: Union[int, str], asset_address: Optional[str] = None) -> str:
    """
    格式化代币金额，同时显示原始金额和转换后的金额
    
    Args:
        amount: 链上金额（整数）
        asset_address: 资产合约地址，用于确定精度
        
    Returns:
        格式化后的金额字符串，包含原始金额和转换后的金额
    """
    formatted = format_amount(amount, asset_address)
    return f"{formatted} ({amount} wei)"

def format_interest_rate(rate: Union[int, str]) -> str:
    """
    格式化借贷利率，将链上利率数据转换为百分比形式
    
    大多数借贷协议使用以下精度:
    - RAY: 27位精度 (10^27)
    - WAD: 18位精度 (10^18)
    
    Args:
        rate: 链上利率（整数）
        
    Returns:
        格式化后的利率字符串（百分比）
    """
    try:
        # 转换为Decimal以确保精度
        raw_rate = Decimal(str(rate))
        
        # 尝试确定精度
        if raw_rate > Decimal('1e20'):  # 可能是RAY (10^27)
            formatted_rate = raw_rate / Decimal('1e27') * 100
        else:  # 假设是WAD (10^18)
            formatted_rate = raw_rate / Decimal('1e18') * 100
        
        # 格式化输出，保留2位小数
        result = str(formatted_rate.quantize(Decimal('0.01')))
        result = result.rstrip('0').rstrip('.') if '.' in result else result
        
        return f"{result}%"
    except Exception as e:
        return f"{rate} (转换错误: {str(e)})" 