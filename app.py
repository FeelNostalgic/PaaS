import json

from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, redirect, render_template, session, url_for, request, flash, jsonify
from dotenv import load_dotenv
import os
from backend.database import DatabaseAPI
from backend.statusEnum import Status

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
                "date": game["date"].strftime("%Y-%m-%d %H:%M"),
                "status": game["status"],
                "winner": game.get("winner"),
                "markers": len(game["markers"]),
                "area": game["area"],
                "players": DatabaseAPI.get_num_players_from_game(game["name"])
            }
            games_list.append(game_data)

        return render_template("mainpage.html", session=session.get("user"), games=games_list)
    else:
        abort(404)


@app.route('/game/<string:game_name>')
def game_detail(game_name):
    if "user" in session:
        game = DatabaseAPI.find_game_by_name(game_name)
        user_game = DatabaseAPI.find_user_game_by_game_name(game_name, session.get("user")["userinfo"]["sub"])

        caches = DatabaseAPI.get_caches_completed_in_game_by_user(game["name"], session.get("user")["userinfo"]["sub"])

        game_data = {
            "id": str(game["_id"]),
            "name": game["name"],
            "creator": game["creator"]["name"],
            "date": game["date"].strftime("%Y-%m-%d %H:%M"),
            "status": game["status"],
            "winner": game.get("winner"),
            "markers": user_game['markers'] if user_game else game['markers'],
            "area": game["area"],
            "participating": user_game is not None,
            "players": DatabaseAPI.get_num_players_from_game(game["name"]),
            "cachesFound": caches,
        }

        return render_template("game.html", session=session.get("user"), game=game_data)
    else:
        abort(404)


@app.route('/participate/<string:game_name>')
def participate(game_name):
    if "user" in session:
        if not DatabaseAPI.exist_game(game_name): # check if game was not delete by creator
            return jsonify({"message": "Game was deleted. Redirecting to hunt...", "error": True})

        game = DatabaseAPI.find_game_by_name(game_name)

        status = DatabaseAPI.get_game_status(game_name)
        if status != Status.IN_PROGRESS.value:
            return jsonify({"message": "There is already a winner", "error": True})

        DatabaseAPI.insert_new_user_game(game, session.get("user")["userinfo"]["sub"], session.get("user")["userinfo"]["given_name"])
        return jsonify({"error": False})
    else:
        abort(404)


@app.route('/unsubscribe/<string:game_name>')
def unsubscribe(game_name):
    if "user" in session:
        if not DatabaseAPI.exist_game(game_name):   # check if game was not delete by creator
            return jsonify({"message": "Game was deleted. Redirecting to hunt...", "error": True})

        status = DatabaseAPI.get_game_status(game_name)
        if status != Status.IN_PROGRESS.value:
            return jsonify({"message": "There is already a winner", "error": True})

        result = DatabaseAPI.remove_user_game_by_game_name(game_name, session.get("user")["userinfo"]["sub"])
        if result:
                return jsonify({"error": False})
    else:
        abort(404)


@app.route('/uploadFoundImage', methods=['POST'])
def uploadFoundImage():
    if "user" in session:
        if request.method == "POST":
            data = request.get_json()
            game_name = data.get('game_name')
            user_id = session.get("user")["userinfo"]["sub"]
            marker_id = data.get('markerId')
            photo = data.get('photo')

            if not DatabaseAPI.exist_game(game_name): # check if game was not delete by creator
                return jsonify({"message": "Game was deleted. Redirecting to hunt...", "error": True})

            user_game = DatabaseAPI.find_user_game_by_game_name(game_name, user_id)
            status = DatabaseAPI.get_game_status(game_name)

            if status != Status.IN_PROGRESS.value:
                return jsonify({'message': 'There is already a winner', 'winner': True})

            DatabaseAPI.saveFoundImage(user_game, marker_id, photo)

            game = DatabaseAPI.find_game_by_name(game_name)
            num_caches_found = DatabaseAPI.get_caches_completed_in_game_by_user(game_name, session.get("user")["userinfo"]["sub"])

            if len(game['markers']) == num_caches_found:
                DatabaseAPI.set_game_winner(game, user_game['user_name'], user_game['user'], Status.IN_REVISION.value)

            return jsonify({'message': 'Image saved successfully!', 'markerId': marker_id, 'winner': False, 'refresh': len(game['markers']) == num_caches_found})


@app.route("/remove_user_image", methods=["POST"])
def removeUserImage():
    if "user" in session:
        if request.method == "POST":
            data = request.get_json()
            game_name = data.get('game_name')
            user_id = session.get("user")["userinfo"]["sub"]
            marker_id = data.get('markerId')

            if not DatabaseAPI.exist_game(game_name):  # check if game was not delete by creator
                return jsonify({"message": "Game was deleted. Redirecting to hunt...", "error": True})

            result = DatabaseAPI.remove_user_image_from_game(game_name, user_id, marker_id)
            if not result:
                return jsonify({"message": "Game was reset. Reloading page...", "error": True})

            return jsonify({"error": False})
    else:
        abort(404)


@app.route('/delete_game/<string:game_name>')
def deleteGame(game_name):
    if "user" in session:
        game = DatabaseAPI.find_game_by_name(game_name)
        if session.get("user")["userinfo"]["sub"] == game["creator"]["sub"]:
            DatabaseAPI.delete_game(game_name)
            return redirect("/huntCreations")
        else:
            abort(404)
    else:
        abort(404)


@app.route('/reset_game/<string:game_name>')
def resetGame(game_name):
    if "user" in session:
        game = DatabaseAPI.find_game_by_name(game_name)
        if session.get("user")["userinfo"]["sub"] == game["creator"]["sub"]:
            DatabaseAPI.reset_game(game_name)
            return redirect(f"/view_game/{game_name}")
        else:
            abort(404)
    else:
        abort(404)

@app.route('/view_game/<string:game_name>')
def editGame(game_name):
    if "user" in session:
        game = DatabaseAPI.find_game_by_name(game_name)
        if session.get("user")["userinfo"]["sub"] == game.get("creator").get("sub"):
            for marker in game["markers"]:
                marker['foundBy'] = []
                users = DatabaseAPI.get_users_that_found_caches(game_name, marker['id'])
                for user in users:
                    marker['foundBy'].append({
                        'user_id': user['user'],
                        'user_name': user['user_name'],
                        'image': user.get("markers").get("image"),
                        'date': user.get("markers").get("date").strftime("%Y-%m-%d %H:%M")
                    })

            winner = game.get("winner")
            game_data = {
                "id": str(game["_id"]),
                "name": game["name"],
                "date": game["date"].strftime("%Y-%m-%d %H:%M"),
                "status": game["status"],
                "winner": winner,
                "winnerMarkers": DatabaseAPI.get_winner_data(game["name"], winner.get("name")).get("markers") if winner else None,
                "markers": game["markers"],
                "area": game["area"],
                "players": DatabaseAPI.get_num_players_from_game(game["name"])
            }
            return render_template("SuperviseGame.html", session=session.get("user"), game=game_data)
        else:
            abort(404)
    else:
        abort(404)


@app.route('/clear_winner/<string:game_name>')
def clearWinner(game_name):
    if "user" in session:
        game = DatabaseAPI.find_game_by_name(game_name)
        if session.get("user")["userinfo"]["sub"] == game["creator"]["sub"]:
            DatabaseAPI.clear_winner(game_name, game["winner"]["id"])
            return redirect(f"/view_game/{game_name}")
        else:
            abort(404)
    else:
        abort(404)

@app.route('/validate_winner', methods=['POST'])
def validateGame():
    if "user" in session:
        if request.method == "POST":
            data = request.get_json()
            game_name = data.get('game_name')
            game = DatabaseAPI.find_game_by_name(game_name)
            if session.get("user")["userinfo"]["sub"] == game["creator"]["sub"]:
                DatabaseAPI.complete_game(game["name"])
                return redirect(f"/view_game/{game_name}")
            else:
                abort(404)
    else:
        abort(404)


@app.route("/remove_player_image", methods=["POST"])
def removePlayerImage():
    if "user" in session:
        if request.method == "POST":
            data = request.get_json()
            game_name = data.get('game_name')
            game = DatabaseAPI.find_game_by_name(game_name)
            if session.get("user")["userinfo"]["sub"] == game.get("creator").get("sub"):
                user_id = data.get('playerId')
                if game.get("winner").get("id") == user_id:
                    DatabaseAPI.set_game_in_progress(game_name)

                marker_id = data.get('markerId')
                DatabaseAPI.remove_user_image_from_game(game_name, user_id, marker_id)
                return redirect(f"/view_game/{game_name}")
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

            user = session.get('user')['userinfo']

            if DatabaseAPI.exist_game_name(game_name):
                return jsonify({'message': f'The name {game_name} already exists', 'error': True})

            DatabaseAPI.insert_new_game(user['sub'], user['given_name'], game_name, lat1, lon1, lat2, lon2, markers, Status.IN_PROGRESS.value)

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
                "date": game["date"].strftime("%Y-%m-%d %H:%M"),
                "status": game["status"],
                "winner": game.get("winner"),
                "markers": len(game["markers"]),
                "area": game["area"],
                "cachesFound": DatabaseAPI.get_caches_completed_in_game_by_user(game["name"], session.get("user")["userinfo"]["sub"]),
                "players": DatabaseAPI.get_num_players_from_game(game["name"])
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
                "date": game["date"].strftime("%Y-%m-%d %H:%M"),
                "status": game["status"],
                "winner": game.get("winner"),
                "markers": len(game["markers"]),
                "area": game["area"],
                "players": DatabaseAPI.get_num_players_from_game(game["name"])
            }
            games_list.append(game_data)

        return render_template("HuntCreations.html", session=session.get("user"), games=games_list)
    else:
        abort(404)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
