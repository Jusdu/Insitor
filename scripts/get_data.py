# scripts/get_data.py
from src.data.manager import DataManager

def get_data():
    data_manager = DataManager('gm')
    data = data_manager.fetch_and_save()
    return data

if __name__ == '__main__':
    get_data()
