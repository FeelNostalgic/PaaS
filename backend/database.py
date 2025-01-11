import os
from dotenv import load_dotenv
from pymongo import MongoClient
import configparser
from datetime import datetime

load_dotenv()
MONGODB_URI = os.environ['MONGODB_URI']
client = MongoClient(MONGODB_URI)

config_parser = configparser.ConfigParser()
config_parser.read('appConfig.ini')

config = {
    'database': config_parser['MONGO']['MONGO_DB'],
    'games' : config_parser['MONGO']['GAMES_COLLECTION']
}

db = client[config['database']]

class DatabaseAPI:
    def __init__(self):
        pass

    @staticmethod
    def insert_new_game(user_sub, user_name, game_name, lat1, lon1, lat2, lon2, markers):
        collection = db[config['games']]
        data = {
            'creator':{
                'sub': user_sub,
                'name': user_name
            },
            'name': game_name,
            'area':{
                'lat1': lat1,
                'lon1': lon1,
                'lat2': lat2,
                'lon2': lon2
            },
            'markers': markers,
            'date': datetime.now(),
            'status': 'In progress'
        }
        return collection.insert_one(data)

    @staticmethod
    def find_one(query):
        collection = db[config['games']]
        return collection.find_one(query)

    @staticmethod
    def printCollections():
        collections = client.list_collection_names()
        for collection in collections:
            print(collection)