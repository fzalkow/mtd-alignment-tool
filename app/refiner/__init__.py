from flask import Blueprint

refiner = Blueprint('refiner', __name__)

from . import views, errors
