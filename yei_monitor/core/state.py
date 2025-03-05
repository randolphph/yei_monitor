from dataclasses import dataclass
from datetime import datetime

@dataclass
class ContractState:
    """合约状态类"""
    current_implementation: str = None
    last_upgrade_time: int = 0
    is_first_run: bool = True
    last_check_time: int = 0

    def update_implementation(self, new_implementation: str) -> bool:
        """更新实现地址"""
        if self.current_implementation != new_implementation:
            self.current_implementation = new_implementation
            self.last_upgrade_time = int(datetime.now().timestamp())
            return True
        return False 