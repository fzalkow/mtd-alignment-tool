import os
from flask_script import Manager

from app import create_app


app = create_app('config.json')
manager = Manager(app)


@manager.command
def run():
    """ Run website """
    app.run(debug=True)


if __name__ == '__main__':
    manager.run()
