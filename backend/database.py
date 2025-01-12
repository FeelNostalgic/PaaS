import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import configparser
from datetime import datetime

from backend.statusEnum import Status

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
orden_status = ["In progress", "In revision", "Completed"]

class DatabaseAPI:
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
    def reset_game(game_name):
        collection = db[config['games']]
        result = collection.update_one(
            {"name": game_name},
            {"$set": {"status": Status.IN_PROGRESS.value, "date": datetime.now()},
                    "$unset": {"winner": ""}})

        collection = db[config['user_games']]
        result = collection.update_many(
            {'game': game_name},
                 {"$set": {"markers.$[].found": False},
                        "$unset": {"markers.$[].image": "", "markers.$[].date": ""}})
        return result

    @staticmethod
    def delete_game(game_name):
        collection = db[config['games']]
        collection.delete_one({"name": game_name})
        collection = db[config['user_games']]
        collection.delete_many({"game": game_name})
        return True

    @staticmethod
    def exist_game_name(game_name):
        collection = db[config['games']]
        return collection.count_documents({"name": game_name}) == 1

    @staticmethod
    def exist_game(game_name):
        return DatabaseAPI.exist_game_name(game_name) == 1

    @staticmethod
    def set_game_in_progress(game_name):
        """
        Set game to In progress and remove winner (not all his answers)
        :param game_name:
        :return:
        """
        collection = db[config['games']]
        result = collection.update_one(
            {"name": game_name},
            {"$set": {"status": Status.IN_PROGRESS.value}
                   ,"$unset": {"winner": ""}})
        return result

    @staticmethod
    def set_game_winner(game, winner_name, winner_id, status):
        collection = db[config['games']]
        result = collection.update_one(
            {"name": game["name"]},
            {"$set": {"winner.name": winner_name, "winner.id": winner_id,"status": status}}
        )
        return result

    @staticmethod
    def complete_game(game_name):
        collection = db[config['games']]
        result = collection.update_one(
            {"name": game_name},
            {"$set": {"status": Status.COMPLETED.value}}
        )
        return result

    @staticmethod
    def clear_winner(game_name, winner_id):
        collection = db[config['games']]
        collection.update_one(
            {"name": game_name},
            {"$set": {"status": Status.IN_PROGRESS.value}
                   ,"$unset": {"winner": ""}})
        collection = db[config['user_games']]
        collection.update_many(
            {'game': game_name, 'user': winner_id},
            {"$set": {"markers.$[].found": False},
                "$unset": {"markers.$[].image": "", "markers.$[].date": ""}}
        )
        return True

    @staticmethod
    def get_game_status(game_name):
        collection = db[config['games']]
        query = {"name": game_name}
        return collection.find_one(query).get("status")

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
        """
        Get all games that the user dont create
        Ordered by status and date
        :param user_id:
        :return:
        """
        collection = db[config['games']]

        pipeline = [
            {"$match": {"creator.sub": {"$ne": user_id}}},
            {
              "$addFields": {
                "status_order": { "$indexOfArray": [ orden_status, "$status" ] }
              }
            },
            {"$sort": {"status_order": 1, "date": -1}},
            {"$project": {"status_order": 0}}
        ]

        result = list(collection.aggregate(pipeline))
        return result

    @staticmethod
    def find_games_user_is_subscribed(game_names):
        """
        Get all games that the user is subscribed in
        Ordered by status and date
        :param game_names:
        :return:
        """
        collection = db[config['games']]

        pipeline = [
            {"$match": {"name": {"$in": game_names}}},
            {
              "$addFields": {
                "status_order": { "$indexOfArray": [ orden_status, "$status" ] }
              }
            },
            {"$sort": {"status_order": 1, "date": -1}},
            {"$project": {"status_order": 0}}
        ]

        result = list(collection.aggregate(pipeline))
        return result

    @staticmethod
    def find_all_games_created_by_user(user_id):
        """
        Get all games that the user had created
        Ordered by status and date
        :param user_id:
        :return:
        """
        collection = db[config['games']]

        pipeline = [
            {"$match": {"creator.sub": user_id}},
            {
                "$addFields": {
                    "status_order": {"$indexOfArray": [orden_status, "$status"]}
                }
            },
            {"$sort": {"status_order": 1, "date": -1}},
            {"$project": {"status_order": 0}}
        ]

        result = list(collection.aggregate(pipeline))
        return result

    @staticmethod
    def find_game_by_name(game_name):
        return DatabaseAPI.__find_one_game({'name': game_name})

    @staticmethod
    def find_user_game_by_game_name(game_name, user_sub):
        return DatabaseAPI.__find_one_user_game({'game': game_name, 'user': user_sub})

    @staticmethod
    def get_num_players_from_game(game_name):
        collection = db[config['user_games']]
        query = {"game": game_name}
        return len(list(collection.find(query)))

    @staticmethod
    def get_winner_data(game_name, winner_name):
        return DatabaseAPI.__find_one_user_game({"game": game_name, "user_name": winner_name})

    @staticmethod
    def saveFoundImage(user_game, marker_id, photo):
        collection = db[config['user_games']]
        result = collection.update_one(
            {"game": user_game["game"], "user": user_game["user"], "markers.id": marker_id},
            {"$set": {"markers.$[element].found": True, "markers.$[element].image": photo, "markers.$[element].date": datetime.now()}},
            array_filters=[{"element.id": marker_id}]
        )
        return result

    @staticmethod
    def get_caches_completed_in_game_by_user(game_name, user_id):
        documento = DatabaseAPI.__find_one_user_game({'game': game_name, 'user': user_id})
        if documento:
            markers_encontrados = sum(1 for marker in documento.get("markers", []) if marker.get("found"))
            return markers_encontrados
        else:
            return 0

    @staticmethod
    def find_all_user_games(user_id):
        collection = db[config['user_games']]
        return collection.distinct('game', {'user': user_id})

    @staticmethod
    def remove_user_game_by_game_name(game_name, user_id):
        collection = db[config['user_games']]
        return collection.delete_many({'user': user_id, 'game': game_name})

    @staticmethod
    def remove_user_image_from_game(game_name, user_id, marker_id):
        collection = db[config['user_games']]
        result = collection.update_one(
            {"game": game_name, "user": user_id, "markers.id": marker_id},
            {
                "$set": {"markers.$[element].found": False, "date": datetime.now()},
                "$unset": {"markers.$[element].image": "", "markers.$[element].date": ""}
            },
            array_filters=[{"element.id": marker_id}]
        )
        return result

    @staticmethod
    def get_users_that_found_caches(game_name, marker_id):
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
            {"$project": {"user": 1, "user_name": 1, "markers.image": 1, "markers.date":1, "_id": 0}}
        ]

        return list(collection.aggregate(pipeline))

    @staticmethod
    def __find_one_user_game(query):
        collection = db[config['user_games']]
        return collection.find_one(query)

    @staticmethod
    def __find_one_game(query):
        collection = db[config['games']]
        return collection.find_one(query)
