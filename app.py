import logging

from flask import Flask

import translations
from routes import routes

logging.basicConfig(level=logging.INFO)
translations.write_template()

app = Flask(__name__)
app.register_blueprint(routes)

if __name__ == "__main__":
    app.run(debug=True)
