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
    def insert_new_game(user_sub, user_name, game_name, lat1, lon1, lat2, lon2, markers, status):
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
            'status': status
        }
        return collection.insert_one(data)

    @staticmethod
    def exist_game_name(game_name):
        collection = db[config['games']]
        return collection.count_documents({"name": game_name}) == 1

    @staticmethod
    def change_game_status(game, winner, status):
        collection = db[config['games']]
        data = {
            'creator': {
                'sub': game['creator']['sub'],
                'name': game['creator']['name']
            },
            'name': game['name'],
            'area': {
                'lat1': game['area']['lat1'],
                'lon1': game['area']['lon1'],
                'lat2': game['area']['lat2'],
                'lon2': game['area']['lon2']
            },
            'markers': game['markers'],
            'date': datetime.now(),
            'winner': winner,
            'status': status
        }
        return collection.insert_one(data)

    @staticmethod
    def insert_new_user_game(game, user_sub, user_name):
        collection = db[config['user_games']]
        markers = game['markers']
        for marker in markers:
            marker['found'] = False
        data = {
            'game': game['name'],
            'user': user_sub,
            'user_name': user_name,
            'date': datetime.now(),
            'markers': markers
        }
        return collection.insert_one(data)

    @staticmethod
    def find_all_games(user_id):
        collection = db[config['games']]
        pipeline = [
            {"$match": {"creator.sub": {"$ne": user_id}}},
            {"$sort": {"date": -1}},
            {
                "$group": {
                    "_id": "$name",
                    "doc": {"$first": "$$ROOT"}
                }
            },
            {"$replaceRoot": {"newRoot": "$doc"}}
        ]

        return list(collection.aggregate(pipeline))

    @staticmethod
    def find_games_user_is_subscribed(game_names):
        collection = db[config['games']]
        pipeline = [
            {"$match": {"name": {"$in": game_names}}},
            {"$sort": {"date": -1}},
            {
                "$group": {
                    "_id": "$name",
                    "doc": {"$first": "$$ROOT"}
                }
            },
            {"$replaceRoot": {"newRoot": "$doc"}}
        ]

        return list(collection.aggregate(pipeline))

    @staticmethod
    def find_game_by_name(game_name):
        return DatabaseAPI.__find_the_most_recent_game({'name' : game_name})

    @staticmethod
    def find_user_game_by_game_name(game_name, user_sub):
        return DatabaseAPI.__find_the_most_recent_user_game({'game': game_name, 'user': user_sub})

    @staticmethod
    def get_num_players_from_game(game_name):
        collection = db[config['user_games']]
        pipeline = [
            {"$match": {"game": game_name}},
            {"$sort": {"date": -1}},
            {
                "$group": {
                    "_id": "$user",
                    "doc": {"$first": "$$ROOT"}
                }
            },
            {"$replaceRoot": {"newRoot": "$doc"}}
        ]
        return len(list(collection.aggregate(pipeline)))


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
            'user_name': user_game['user_name'],
            'date': datetime.now(),
            'markers': markers
        }
        return collection.insert_one(data)

    @staticmethod
    def get_caches_completed_in_game_by_user(game_name, user_id):
        documento = DatabaseAPI.__find_the_most_recent_user_game({'game': game_name, 'user':user_id})
        if documento:
            markers_encontrados = sum(1 for marker in documento.get("markers", []) if marker.get("found"))
            return markers_encontrados
        else:
           return 0

    @staticmethod
    def find_all_games_created_by_user(user_id):
        collection = db[config['games']]
        return collection.find({"creator.sub": user_id}).sort('date', -1)

    @staticmethod
    def find_all_user_games(user_id):
        collection = db[config['user_games']]
        return collection.distinct('game', {'user': user_id})

    @staticmethod
    def remove_user_game_by_game_name(game_name, user_id):
        collection = db[config['user_games']]
        return collection.delete_many({'user': user_id, 'game': game_name})

    @staticmethod
    def get_user_that_found_cache(game_name, marker_id):
        collection = db[config['user_games']]
        pipeline = [
            {"$match": {"game": game_name}},
            {"$unwind": "$markers"},
            {
                "$match": {
                    "markers.found": True,
                    "markers.id": marker_id
                }
            },
            {"$sort": {"date": -1}},
            {
                "$group": {
                    "_id": "$user",
                    "lastDocument": {"$first": "$$ROOT"}
                }
            },
            {"$replaceRoot": {"newRoot": "$lastDocument"}},
            {"$project": {"user":1, "user_name": 1, "markers.image":1, "_id": 0}}
        ]

        return list(collection.aggregate(pipeline))

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
