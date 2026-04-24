from abc import ABC, abstractmethod

class BaseFactor(ABC):
    def __init__(self, name:str, desc:str):
        self.name = name
        self.desc = desc

    @abstractmethod
    def compute(self):
        """计算因子值"""
        pass