import json

from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, redirect, render_template, session, url_for, request, flash, jsonify
from dotenv import load_dotenv
import os
from backend.database import DatabaseAPI

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

@app.route('/home')
def home():
    if "user" in session:
        games = DatabaseAPI.find_all()
        games_list = []
        for game in games:
            print(str(game["name"]))
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

@app.route('/game/<int:game_id>')
def game_detail(game_id):
    # Aquí deberías buscar el juego con el ID proporcionado y mostrar detalles
    return f"Detalles del juego {game_id}"

@app.route("/new_game")
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

            # TODO:  check if gamename exist

            DatabaseAPI.insert_new_game(user['sub'], user['given_name'], game_name, lat1, lon1, lat2, lon2, markers)

            # Responder con un mensaje de éxito
            return jsonify({'message': 'Datos guardados correctamente'})
    else:
        abort(404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
