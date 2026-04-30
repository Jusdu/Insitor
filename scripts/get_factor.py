'''use type - 1 : manual import factors'''
# from src.factor.definitions.momentum.slope import SLOPE
# from src.factor.pipeline.engine import Engine

# if __name__ == '__main__':
#     engine = Engine()

#     factors = [
#         SLOPE(n=14),
#         SLOPE(n=28),
#     ]

#     import pandas as pd
#     data = pd.read_parquet('./data/raw/all_stock_data.parquet')
#     result = engine.run(factors, data)
#     print(result)



'''use type - 2 : auto import all factors'''
import pandas as pd
from src.factor.registry import auto_import
from src.factor.pipeline.engine import Engine

if __name__ == '__main__':
    # auto load all factors in the definitions folder, and register them to the registry
    auto_import("src.factor.definitions")

    # define the factor configurations, each config is a tuple of (factor_name, factor_params)
    configs = [
        # ("SLOPE", {'n': 14, 'f': 'd'}),
        # ("SLOPE", {'n': 28, 'f': 'd'}),

        ("CONVERGENCE", {
                'use_col': 'amount', 
                'n_list': [5, 10, 20, 60, 120], 
                'save_name': 'convergence_amount',
                "category": "momentum"
            }
        ),
        ("CONVERGENCE", {
                'use_col': 'close', 
                'n_list': [5, 10, 20, 60, 120], 
                'save_name': 'convergence_close',
                "category": "momentum"
            }
        ),
    ]

    # load raw data
    data = pd.read_parquet('../data/raw/all_stock_data.parquet')
    # create engine and run
    engine = Engine()
    engine.fetch_and_save(configs, data)
