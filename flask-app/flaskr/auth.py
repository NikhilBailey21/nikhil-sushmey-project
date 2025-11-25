import functools
import json

from flask import Blueprint
from flask import current_app
from flask import flash
from flask import g
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from google.auth.transport import requests
from google.oauth2 import id_token

from flaskr.db import get_db

# User table column indices for tuple access:
# 0: id, 1: username, 2: email, 3: google_id, 4: name, 5: picture, 6: created

bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(view):
    """View decorator that redirects anonymous users to the login page."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view


@bp.before_app_request
def load_logged_in_user():
    """If a user id is stored in the session, load the user object from
    the database into ``g.user``.
    
    Returns tuple: (id, username, email, google_id, name, picture, created)
    For templates, converts to dict for easier access.
    """
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM "user" WHERE id = %s', (user_id,))
        user_tuple = cursor.fetchone()
        cursor.close()
        
        # Convert tuple to dict for template access
        # Tuple: (id, username, email, google_id, name, picture, created)
        if user_tuple:
            g.user = {
                'id': user_tuple[0],
                'username': user_tuple[1],
                'email': user_tuple[2],
                'google_id': user_tuple[3],
                'name': user_tuple[4],
                'picture': user_tuple[5],
                'created': user_tuple[6] if len(user_tuple) > 6 else None
            }
        else:
            g.user = None


@bp.route("/login")
def login():
    """Show the Google Sign-In page."""
    google_client_id = current_app.config.get("GOOGLE_CLIENT_ID", "")
    if not google_client_id:
        flash("Google authentication is not configured. Please contact the administrator.")
    return render_template("auth/login.html", google_client_id=google_client_id)


@bp.route("/google-callback", methods=["POST"])
def google_callback():
    """Handle Google Sign-In callback and authenticate user."""
    try:
        data = request.get_json()
        credential = data.get("credential")
        
        if not credential:
            return jsonify({"success": False, "error": "No credential provided"}), 400

        google_client_id = current_app.config.get("GOOGLE_CLIENT_ID")
        if not google_client_id:
            return jsonify({"success": False, "error": "Google OAuth not configured"}), 500

        # Verify the token
        try:
            idinfo = id_token.verify_oauth2_token(
                credential, requests.Request(), google_client_id
            )
        except ValueError:
            return jsonify({"success": False, "error": "Invalid token"}), 401

        # Extract user information
        google_id = idinfo.get("sub")
        email = idinfo.get("email")
        name = idinfo.get("name")
        picture = idinfo.get("picture")

        if not google_id:
            return jsonify({"success": False, "error": "Invalid user information"}), 400

        db = get_db()
        
        # Check if user exists by google_id or email
        cursor = db.cursor()
        cursor.execute('SELECT * FROM "user" WHERE google_id = %s OR email = %s', (google_id, email))
        user = cursor.fetchone()
        cursor.close()
        
        if user is None:
            # Create new user with Google account
            # User tuple: (id, username, email, google_id, name, picture, created)
            try:
                username = email or f"user_{google_id[:8]}"
                cursor = db.cursor()
                cursor.execute(
                    'INSERT INTO "user" (username, email, google_id, name, picture) VALUES (%s, %s, %s, %s, %s) RETURNING id',
                    (username, email, google_id, name, picture),
                )
                result = cursor.fetchone()
                user_id = result[0]  # id is first column
                db.commit()
                cursor.close()
            except Exception as e:
                # User might have been created between check and insert
                cursor = db.cursor()
                cursor.execute('SELECT * FROM "user" WHERE google_id = %s OR email = %s', (google_id, email))
                user = cursor.fetchone()
                cursor.close()
                if user:
                    user_id = user[0]  # id is first column (index 0)
                else:
                    current_app.logger.error(f"Failed to create user: {str(e)}")
                    return jsonify({"success": False, "error": "Failed to create user"}), 500
        else:
            # Update existing user with Google info if needed
            # User tuple: (id, username, email, google_id, name, picture, created)
            # Check if google_id is None or empty (index 3)
            if not user[3]:  # google_id is at index 3
                cursor = db.cursor()
                cursor.execute(
                    'UPDATE "user" SET google_id = %s, name = %s, picture = %s WHERE id = %s',
                    (google_id, name, picture, user[0]),  # user[0] is id
                )
                db.commit()
                cursor.close()
            user_id = user[0]  # id is first column (index 0)

        # Store user id in session
        session.clear()
        session["user_id"] = user_id

        return jsonify({
            "success": True,
            "redirect_url": url_for("index")
        })

    except Exception as e:
        current_app.logger.error(f"Google callback error: {str(e)}")
        return jsonify({"success": False, "error": "Authentication failed"}), 500


@bp.route("/logout")
def logout():
    """Clear the current session, including the stored user id."""
    session.clear()
    return redirect(url_for("index"))
