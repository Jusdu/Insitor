from ..base import BaseFactor
from src.factor.registry import register

import pandas as pd
import numpy as np

@register('SLOPE')
class SLOPE(BaseFactor):
    """
    斜率因子

    params:
    - n: 计算斜率的窗口长度，默认为14
    """
    def __init__(self, **kwargs):

        self.n = kwargs.get("n", 14)
        self.f = kwargs.get("f", 'd')
        super().__init__(
            name='SLOPE',
            desc='斜率因子，衡量价格变动的趋势和强度'
        )

    def compute(self, data:pd.DataFrame):
        """计算斜率因子值"""
        return self.N_slope(data)


    def N_slope(self, data:pd.DataFrame):
        """前 N 日的斜率"""
        # y
        Close_df = data.close.unstack()
        arr = Close_df.values

        # x
        x = np.arange(self.n)
        weights = x - x.mean()
        denom = np.sum(weights**2)

        # 每列窗口标准化
        y_mean = Close_df.rolling(self.n).mean().to_numpy()
        y_std = Close_df.rolling(self.n).std(ddof=0).to_numpy()
        y_norm = (arr - y_mean) / y_std

        # 卷积计算 slope
        slopes = np.apply_along_axis(
            lambda col: np.convolve(col, weights[::-1], mode="valid") / denom,
            axis=0,
            arr=y_norm
        )

        # 对齐 index/columns
        factors = pd.DataFrame(np.full_like(arr, np.nan, dtype=float),
                        index=Close_df.index, columns=Close_df.columns)
        factors.iloc[self.n-1:, :] = slopes


        factors = factors.shift(1)
        factors = pd.DataFrame(factors.stack())
        factors.columns = [f'slope_{self.n}{self.f}']
        return factors