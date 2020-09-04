import os
import json
from flask import Flask
from flask_bootstrap import Bootstrap


def create_app(fn_config):

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'queesh7iojeiChoe3eth'  # change for production
    app.config['HOME'] = os.path.dirname(os.path.abspath(__file__))

    with open(fn_config, 'r') as stream:
        config = json.load(stream)
    for key, value in config.items():
        app.config[key] = value

    bootstrap = Bootstrap()
    bootstrap.init_app(app)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .refiner import refiner as refiner_blueprint
    app.register_blueprint(refiner_blueprint, url_prefix='/refine')

    return app
