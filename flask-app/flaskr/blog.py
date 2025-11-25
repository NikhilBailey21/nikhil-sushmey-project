from flask import Blueprint
from flask import render_template

bp = Blueprint("blog", __name__)


@bp.route("/")
def index():
    """Hello World page."""
    return render_template("blog/index.html")
