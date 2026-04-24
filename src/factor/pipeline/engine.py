from src.factor.registry import get_factor

class Engine:  
    def fetch(self, factor_configs, data):
        results = {}

        for factorClass, params in factor_configs:

            f = get_factor(factorClass, **params)
            df = f.compute(data)

            save_name = params.get('save_name', f"{factorClass}")
            category = params.get('category', 'default')

            results[save_name] = (df, category)

        return results
    
    def save(self, results, path):
        import os

        os.makedirs(path, exist_ok=True)

        for save_name, (df, category) in results.items():

            # 创建类别文件夹
            category_path = os.path.join(path, category)
            os.makedirs(category_path, exist_ok=True)

            file_path = os.path.join(category_path, f"{save_name}.parquet")

            df.to_parquet(file_path)


    def fetch_and_save(self, factor_configs, data):
        results = self.fetch(factor_configs, data)
        self.save(results, '../data/factors')

        print(results)