import json

import requests
from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, redirect, render_template, session, url_for, request, flash
from dotenv import load_dotenv
import os
import random
import string

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
        return render_template("mainpage.html", session=session.get("user"), pretty=json.dumps(session.get("user"), indent=4))
    else:
        abort(404)

@app.route('/login')
def login():
    if "user" in session:
        return redirect("/home")
    else:
        state = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        session['state'] = state
        return oauth.geocaching.authorize_redirect(redirect_uri=url_for('auth_callback', _external=True))

@app.route('/auth/callback')
def auth_callback():
    if "user" in session:
        return redirect("/home")
    if request.args.get('state') != session.get('state'):
        return  redirect("/")
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
        return redirect("/")
    else:
        abort(404)
@app.route("/new_game")
def newGame():
    if "user" in session:
        return render_template("newGame.html")
    else:
        abort(404)

@app.route("/add_game")
def addGame():
    if "user" in session:
        if request.method == "POST":
            gameName = request.form.get("gameName")
    else:
        abort(404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
