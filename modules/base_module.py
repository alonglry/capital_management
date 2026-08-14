"""
Abstract Base Classes for Capital Management Risk Modules, Transformers, and Constraints.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult


class BaseRiskModule(ABC):
    """
    Abstract Base Class for all risk management modules.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for the module (matches configuration keys).
        """
        pass

    def process(self, state: CapitalManagementState) -> CapitalManagementState:
        """
        Processes state through risk module. Handles configuration toggling and state logging.
        """
        enabled = state.config.is_module_enabled(self.name)

        if not enabled:
            state.add_trace(self.name, f"Module disabled in config. Status = SKIPPED")
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=False,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="SKIPPED",
                reason="Module is disabled in configuration.",
            )
            return state

        return self._execute(state)

    @abstractmethod
    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        """
        Domain execution logic for enabled module.
        """
        pass

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {}

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {}


class RiskTransformer(BaseRiskModule, ABC):
    """
    Base class for soft risk governors that scale/modify a risk budget (risk_out = risk_in * multiplier).
    Examples: conviction, drawdown, volatility, strategy allocation.
    """
    pass


class RiskConstraint(BaseRiskModule, ABC):
    """
    Base class for hard risk constraints that calculate maximum permissible risk capacity (risk_capacity).
    Examples: portfolio heat, correlation risk, factor exposure, stress risk.
    """
    pass
