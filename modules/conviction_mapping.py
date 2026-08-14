"""
Conviction Mapping Functions and Interfaces.
"""

from abc import ABC, abstractmethod
from typing import Union

import numpy as np
import pandas as pd


class ConvictionMapping(ABC):
    """
    Abstract interface for conviction strength mapping functions.
    Maps directional_strength x in [0.0, 1.0] to a mapped value in [0.0, 1.0].
    Natively supports both scalar floats and pandas Series.
    """

    @abstractmethod
    def __call__(self, x: Union[float, pd.Series]) -> Union[float, pd.Series]:
        pass


class LinearConvictionMapping(ConvictionMapping):
    """
    Linear mapping: mapping(x) = x.
    """

    def __call__(self, x: Union[float, pd.Series]) -> Union[float, pd.Series]:
        return x


class PowerConvictionMapping(ConvictionMapping):
    """
    Power mapping: mapping(x) = x ** gamma.

    Args:
        gamma (float): Power exponent governing non-linear scaling (default 1.0).
    """

    def __init__(self, gamma: float = 1.0):
        self.gamma = gamma

    def __call__(self, x: Union[float, pd.Series]) -> Union[float, pd.Series]:
        if isinstance(x, pd.Series):
            return x.pow(self.gamma)
        return float(x ** self.gamma)
