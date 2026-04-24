FACTOR_REGISTRY = {}

def register(name):
    def wrapper(cls):
        FACTOR_REGISTRY[name] = cls
        return cls
    return wrapper


def get_factor(name, **kwargs):
    cls = FACTOR_REGISTRY[name]
    return cls(**kwargs)


def auto_import(package_name):
    import importlib, pkgutil

    package = importlib.import_module(package_name)

    for _, module_name, _ in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        importlib.import_module(module_name)    