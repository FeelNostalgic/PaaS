import json

from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, redirect, render_template, session, url_for, request, flash, jsonify
from dotenv import load_dotenv
import os
from backend.database import DatabaseAPI
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave_por_defecto')

oauth = OAuth(app)
oauth.register(
    name='geocaching',
    client_id=os.getenv('CLIENT_ID', 'clave_por_defecto'),
    client_secret=os.getenv('CLIENT_SECRET', 'clave_por_defecto'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
    }
)


@app.route('/')
def index():
    if "user" not in session:
        return render_template("login.html")
    else:
        return redirect("/home")


@app.route('/login')
def login():
    if "user" in session:
        return redirect("/home")
    else:
        return oauth.geocaching.authorize_redirect(redirect_uri=url_for('auth_callback', _external=True))


@app.route('/auth/callback')
def auth_callback():
    if "user" in session:
        return redirect("/home")
    try:
        token = oauth.geocaching.authorize_access_token()
        session["user"] = token
        return redirect("/home")
    except Exception as e:
        return redirect("/")


@app.route("/logout")
def logout():
    if "user" in session:
        session.pop("user", None)
        session.pop("state", None)
        return redirect("/")
    else:
        abort(404)


@app.route('/home')
def home():
    if "user" in session:
        games = DatabaseAPI.find_all_games(session.get("user")["userinfo"]["sub"])
        games_list = []
        for game in games:
            game_data = {
                "id": str(game["_id"]),
                "name": game["name"],
                "creator": game["creator"]["name"],
                "date": game["date"].strftime("%Y-%m-%d"),
                "status": game["status"],
                "markers": len(game["markers"]),
                "area": game["area"],
            }
            games_list.append(game_data)

        return render_template("mainpage.html", session=session.get("user"), games=games_list)
    else:
        abort(404)


@app.route('/game/<string:game_id>')
def game_detail(game_id):
    if "user" in session:
        game = DatabaseAPI.find_game_by_id(game_id)
        user_game = DatabaseAPI.find_user_game_by_game_id(game_id, session.get("user")["userinfo"]["sub"])

        game_data = {
            "id": str(game["_id"]),
            "name": game["name"],
            "creator": game["creator"]["name"],
            "date": game["date"].strftime("%Y-%m-%d"),
            "status": game["status"],
            "markers": user_game['markers'] if user_game else game['markers'],
            "area": game["area"],
            "participating": user_game is not None
        }

        return render_template("game.html", session=session.get("user"), game=game_data)
    else:
        abort(404)


@app.route('/participate/<string:game_id>')
def participate(game_id):
    if "user" in session:
        game = DatabaseAPI.find_game_by_id(game_id)
        DatabaseAPI.insert_new_user_game(game, session.get("user")["userinfo"]["sub"], session.get("user")["userinfo"]["given_name"])
        return redirect(f"/game/{game_id}")
    else:
        abort(404)


@app.route('/unsubscribe/<string:game_id>')
def unsubscribe(game_id):
    if "user" in session:
        DatabaseAPI.remove_user_game_by_game_id(game_id, session.get("user")["userinfo"]["sub"])
        return redirect(f"/game/{game_id}")
    else:
        abort(404)


@app.route('/uploadFoundImage', methods=['POST'])
def uploadFoundImage():
    if "user" in session:
        if request.method == "POST":
            data = request.get_json()
            game_id = data.get('gameId')
            user_id = session.get("user")["userinfo"]["sub"]
            marker_id = data.get('markerId')
            photo = data.get('photo')
            user_game = DatabaseAPI.find_user_game_by_game_id(game_id, user_id)

            DatabaseAPI.saveFoundImage(user_game, marker_id, photo)

            game = DatabaseAPI.find_game_by_id(game_id)
            num_caches_found = DatabaseAPI.get_caches_completed_in_game_by_user(game_id, session.get("user")["userinfo"]["sub"])

            if len(game['markers']) == num_caches_found:
                DatabaseAPI.change_game_status(game, 'In Revision')

            return jsonify({'message': 'Image saved successfully!', 'markerId': marker_id})


@app.route('/delete_game/<int:game_id>')
def deleteGame(game_id):
    if "user" in session:
        return render_template("newGame.html", session=session.get("user"))
    else:
        abort(404)

@app.route('/reset_game/<string:game_id>')
def resetGame(game_id):
    pass

@app.route('/view_game/<string:game_id>')
def editGame(game_id):
    if "user" in session:
        game = DatabaseAPI.find_game_by_id(game_id)
        if session.get("user")["userinfo"]["sub"] == game["creator"]["sub"]:
            for marker in game["markers"]:
                marker['foundBy'] = []
                users = DatabaseAPI.get_user_that_found_cache(game_id, marker['id'])
                for user in users:
                    marker['foundBy'].append({
                        'user_id': user['user'],
                        'user_name': user['user_name'],
                        'image' : user['markers']['image']
                    })

            game_data = {
                "id": str(game["_id"]),
                "name": game["name"],
                "creator": game["creator"]["name"],
                "date": game["date"].strftime("%Y-%m-%d"),
                "status": game["status"],
                "markers": game["markers"],
                "area": game["area"],
                "participating": False
            }
            return render_template("SuperviseGame.html", session=session.get("user"), game=game_data)
        else:
            abort(404)
    else:
        abort(404)


@app.route("/newGame")
def newGame():
    if "user" in session:
        return render_template("newGame.html", session=session.get("user"))
    else:
        abort(404)


@app.route("/add_game", methods=["POST"])
def addGame():
    if "user" in session:
        if request.method == "POST":
            data = request.get_json()

            game_name = data.get('gameName')
            area = data.get('area')
            lat1 = area.get('lat1')
            lon1 = area.get('lon1')
            lat2 = area.get('lat2')
            lon2 = area.get('lon2')
            markers = data.get('markers')

            user = session.get('user')['userinfo']['sub']

            if DatabaseAPI.exist_game_name(game_name):
                return jsonify({'message': f'The name {game_name} already exists', 'error': True})

            DatabaseAPI.insert_new_game(user['sub'], user['given_name'], game_name, lat1, lon1, lat2, lon2, markers, 'In progress')

            return jsonify({'message': 'Game saved successfully.', 'error': False})
    else:
        abort(404)


@app.route('/myHunts')
def myHunts():
    if "user" in session:
        user_games = DatabaseAPI.find_all_user_games(session.get("user")["userinfo"]["sub"])
        games = DatabaseAPI.find_games_user_is_subscribed(user_games)
        games_list = []
        for game in games:
            game_data = {
                "id": str(game["_id"]),
                "name": game["name"],
                "creator": game["creator"]["name"],
                "date": game["date"].strftime("%Y-%m-%d"),
                "status": game["status"],
                "markers": len(game["markers"]),
                "area": game["area"],
            }
            games_list.append(game_data)

        return render_template("HuntGames.html", session=session.get("user"), games=games_list)
    else:
        abort(404)


@app.route('/huntCreations')
def huntCreations():
    if "user" in session:
        games = DatabaseAPI.find_all_games_created_by_user(session.get("user")["userinfo"]["sub"])
        games_list = []
        for game in games:
            game_data = {
                "id": str(game["_id"]),
                "name": game["name"],
                "creator": game["creator"]["name"],
                "date": game["date"].strftime("%Y-%m-%d"),
                "status": game["status"],
                "markers": len(game["markers"]),
                "area": game["area"],
            }
            games_list.append(game_data)

        return render_template("HuntCreations.html", session=session.get("user"), games=games_list)
    else:
        abort(404)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
