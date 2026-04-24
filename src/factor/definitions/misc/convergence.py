from ..base import BaseFactor
from src.factor.registry import register

import pandas as pd
import numpy as np

@register('CONVERGENCE')
class CONVERGENCE(BaseFactor):
    """
    收敛因子

    params:
    - use_col: 用于计算收敛的列名，默认为'amount'
    - n_list: 计算收敛的窗口长度列表，默认为[5, 10, 20, 60, 120]
    """
    def __init__(self, **kwargs):

        self.use_col = kwargs.get("use_col", 'amount')    # ['open', 'high', 'low', 'close', 'amount']
        self.n_list = kwargs.get("n_list", [5, 10, 20, 60, 120])
        self.f = kwargs.get("f", 'd')
        super().__init__(
            name='CONVERGENCE',
            desc='收敛因子，衡量价格变动的收敛性'
        )

    def compute(self, data:pd.DataFrame):
        """计算收敛因子值"""
        return self.N_convergence(data)


    def N_convergence(self, data:pd.DataFrame):
        """前 N 日的收敛性"""
        # y
        df = data[self.use_col].unstack()
        # arr = df.values

        # x
        df_lst = []
        for n in self.n_list:
            df_lst.append(df.rolling(n).mean().shift(1))

        std_df = pd.concat(
                df_lst,
            keys=range(len(self.n_list)),
        ).groupby(level=1).std()
        factor = -np.log(1 + std_df)


        # 对齐 index/columns
        factors = pd.DataFrame(factor.stack())
        factors.index.names = ['date', 'symbol']
        factors.columns = [f'{self.name.lower()}_{self.use_col}']
        return factors
    