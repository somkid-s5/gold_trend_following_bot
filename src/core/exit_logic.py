from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(slots=True)
class ExitInstruction:
    new_sl: float
    partial_close_pct: float = 0.0 # 0.5 = 50%
    reason: str = ""

class ExitManager:
    def calculate_v20_managed_exit(
        self, 
        action: str, 
        entry: float, 
        current_sl: float, 
        current_price: float, 
        risk_dist: float, 
        point: float,
        config: dict[str, Any]
    ) -> ExitInstruction:
        """
        Titan v20 - Maximum Extraction Exit Logic:
        1. Lock Profit RR 1.0 (Same as v19)
        2. Partial TP at RR 3.0 (Close 50%)
        """
        if risk_dist <= 0:
            return ExitInstruction(current_sl)

        be_trigger_rr = 0.5 # SINGULARITY: Move to BE at RR 0.5 (Ultra Fast Protection)
        partial_tp_rr = 2.0 # SINGULARITY: Secure 50% profit at RR 2.0
        
        be_trigger = entry + (risk_dist * be_trigger_rr) if action.upper() == "BUY" else entry - (risk_dist * be_trigger_rr)
        partial_trigger = entry + (risk_dist * partial_tp_rr) if action.upper() == "BUY" else entry - (risk_dist * partial_tp_rr)
        
        instruction = ExitInstruction(current_sl)

        # 1. Check Partial TP (High Priority)
        if (action.upper() == "BUY" and current_price >= partial_trigger) or \
           (action.upper() == "SELL" and current_price <= partial_trigger):
            instruction.partial_close_pct = 0.5
            instruction.reason = f"Partial TP at RR {partial_tp_rr}"

        # 2. Check Lock Profit
        if (action.upper() == "BUY" and current_price >= be_trigger) or \
           (action.upper() == "SELL" and current_price <= be_trigger):
            new_sl = entry + (risk_dist * 1.0) if action.upper() == "BUY" else entry - (risk_dist * 1.0)
            instruction.new_sl = max(current_sl, new_sl) if action.upper() == "BUY" else min(current_sl, new_sl)
            if not instruction.reason: instruction.reason = "Lock Profit RR 1.0"
            
        return instruction

    # Legacy support
    def calculate_managed_sl(
        self, 
        action: str, 
        entry: float, 
        current_sl: float, 
        current_price: float, 
        risk_dist: float, 
        point: float,
        trigger_mult: float = 1.0
    ) -> float:
        inst = self.calculate_v20_managed_exit(action, entry, current_sl, current_price, risk_dist, point, {"breakeven_rr_trigger": trigger_mult})
        return inst.new_sl
