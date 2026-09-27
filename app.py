import logging

from flask import Flask

import lists
import translations
from routes import routes, run_in_background

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.register_blueprint(routes)


def run_startup_tasks():
    """Regenerate the language template and migrate old lists to the current model."""
    translations.write_template()
    for outdated_list in lists.migrate_lists():
        run_in_background(lambda name=outdated_list: lists.refresh_list_data(name))


if __name__ == "__main__":
    run_startup_tasks()
    app.run(debug=True)
