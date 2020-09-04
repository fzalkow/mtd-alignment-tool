import os

import pandas as pd
from flask import render_template, current_app

from . import main


@main.route('/')
def index():
    fn_csv = os.path.join(current_app.config['dir_mtd'], '03_MTD-medium.csv')
    df = pd.read_csv(fn_csv, sep=';')
    df = df.fillna('')

    return render_template('index.html', data=df)
