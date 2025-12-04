import os

from flask import Flask

# Load environment variables from .env file if python-dotenv is installed
# Flask 2.0+ does this automatically, but we make it explicit
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, environment variables must be set manually


def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    app.config.from_mapping(
        # a default secret that should be overridden by .env
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        # Google OAuth Client ID (can be overridden by environment variable)
        GOOGLE_CLIENT_ID=os.environ.get("GOOGLE_CLIENT_ID", ""),
    )

    if test_config is not None:
        # load the test config if passed in
        app.config.update(test_config)

    @app.route("/hello")
    def hello():
        return "Hello, World!"

    # register the database commands
    from flaskr import db

    db.init_app(app)

    # apply the blueprints to the app
    from flaskr import auth, blog

    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)

    # make url_for('index') == url_for('blog.index')
    # in another app, you might define a separate main index here with
    # app.route, while giving the blog blueprint a url_prefix, but for
    # the tutorial the blog will be the main index
    app.add_url_rule("/", endpoint="index")

    return app
