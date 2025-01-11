import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import configparser
from datetime import datetime

load_dotenv()
MONGODB_URI = os.environ['MONGODB_URI']
client = MongoClient(MONGODB_URI)

config_parser = configparser.ConfigParser()
config_parser.read('appConfig.ini')

config = {
    'database': config_parser['MONGO']['MONGO_DB'],
    'games': config_parser['MONGO']['GAMES_COLLECTION'],
    'user_games': config_parser['MONGO']['USER_GAMES_COLLECTION']
}

db = client[config['database']]


class DatabaseAPI:
    def __init__(self):
        pass

    @staticmethod
    def insert_new_game(user_sub, user_name, game_name, lat1, lon1, lat2, lon2, markers):
        collection = db[config['games']]
        data = {
            'creator': {
                'sub': user_sub,
                'name': user_name
            },
            'name': game_name,
            'area': {
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
    def insert_new_user_game(game, user_sub):
        collection = db[config['user_games']]
        markers = game['markers']
        for marker in markers:
            marker['found'] = False
        data = {
            'game': game['_id'],
            'user': user_sub,
            'date': datetime.now(),
            'markers': markers
        }
        return collection.insert_one(data)

    @staticmethod
    def find_all_games(user_id):
        collection = db[config['games']]
        return collection.find({"creator.sub": {"$ne": user_id}}).sort('date', -1)

    @staticmethod
    def find_games_by_id(game_ids):
        collection = db[config['games']]
        return collection.find({"_id": {"$in": game_ids}}).sort('date', -1)

    @staticmethod
    def find_game_by_id(game_id):
        return DatabaseAPI.__find_the_most_recent_game({'_id': ObjectId(game_id)})

    @staticmethod
    def find_user_game_by_game_id(game_id, user_sub):
        return DatabaseAPI.__find_the_most_recent_user_game({'game': ObjectId(game_id), 'user': user_sub})

    @staticmethod
    def saveFoundImage(user_game, marker_id, photo):
        collection = db[config['user_games']]
        markers = user_game['markers']
        marker = next((m for m in markers if m['id'] == marker_id), None)
        marker['found'] = True
        marker['image'] = photo

        data = {
            'game': user_game['game'],
            'user': user_game['user'],
            'date': datetime.now(),
            'markers': markers
        }
        return collection.insert_one(data)

    @staticmethod
    def find_all_user_games(user_id):
        collection = db[config['user_games']]
        return collection.distinct('game', {'user': user_id})

    @staticmethod
    def remove_user_game_by_game_id(game_id, user_id):
        collection = db[config['user_games']]
        return collection.delete_many({'user': user_id, 'game':ObjectId(game_id)})

    @staticmethod
    def __find_the_most_recent_user_game(query):
        collection = db[config['user_games']]
        try:
            return collection.find(query).sort('date', -1).limit(1).next()
        except StopIteration:
            return None

    @staticmethod
    def __find_the_most_recent_game(query):
        collection = db[config['games']]
        try:
            return collection.find(query).sort('date', -1).limit(1).next()
        except StopIteration:
            return None
