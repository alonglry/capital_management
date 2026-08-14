"""
Abstract Base Class for all Capital Management Risk Modules.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult


class BaseRiskModule(ABC):
    """
    Abstract Base Class for risk management modules.

    Every risk module must:
    1. Define a unique module `name`.
    2. Implement `_execute(state) -> state`.
    3. Have explicit inputs/outputs with no hidden state or direct cross-module coupling.
    4. Support being enabled/disabled gracefully without mutating calculation flow when disabled.
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
        Processes the state object through this risk module.

        If the module is disabled in `state.config`, it records a SKIPPED ModuleResult,
        adds a trace log, and leaves the risk calculation unchanged.
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
        Must record module result into `state.module_results[self.name]` and return `state`.
        """
        pass

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        """
        Extracts key input parameters for debugging/auditing.
        """
        return {}

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        """
        Extracts key output metrics updated by module.
        """
        return {}
