import logging

from flask import Flask

from routes import routes

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.register_blueprint(routes)

if __name__ == "__main__":
    app.run(debug=True)
