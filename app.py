
import os
import uuid
from io import BytesIO

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_session import Session
from supabase import create_client


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

BUCKET_NAME = "cloudvault-files"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

if not SUPABASE_URL or not SUPABASE_KEY or not FLASK_SECRET_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL, SUPABASE_KEY, or FLASK_SECRET_KEY "
        "in your .env file."
    )

app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE + 1024 * 1024

# Keep authentication tokens in server-side sessions.
session_directory = os.path.join(app.instance_path, "flask_session")
os.makedirs(session_directory, exist_ok=True)

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = session_directory
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

Session(app)


# --------------------------------------------------
# Supabase helpers
# --------------------------------------------------

def new_supabase_client():
    """Create a fresh Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def authenticated_client():
    """Create a client using the logged-in user's session."""
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")

    if not access_token or not refresh_token:
        return None

    client = new_supabase_client()

    try:
        client.auth.set_session(access_token, refresh_token)

        # Save refreshed tokens if the SDK has updated the session.
        current_session = client.auth.get_session()

        if current_session:
            session["access_token"] = current_session.access_token
            session["refresh_token"] = current_session.refresh_token

        return client

    except Exception:
        app.logger.warning(
            "The saved authentication session is invalid or expired."
        )
        return None


def login_required():
    """Return an authenticated client or redirect to login."""
    client = authenticated_client()

    if client is None:
        session.clear()
        flash("Please log in to continue.", "error")
        return None

    return client


def current_user_id():
    return session.get("user_id")


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.route("/")
def index():
    if not current_user_id():
        return redirect(url_for("login"))

    client = login_required()

    if client is None:
        return redirect(url_for("login"))

    try:
        response = (
            client.table("files")
            .select("*")
            .eq("user_id", current_user_id())
            .order("created_at", desc=True)
            .execute()
        )

        files = []

        for item in response.data or []:
            files.append({
                "id": item["id"],
                "file_name": item["file_name"],
                "storage_path": item["storage_path"],
                "file_size": int(item.get("file_size") or 0),
                "content_type": (
                    item.get("content_type")
                    or "application/octet-stream"
                ),
                "created_at": item.get("created_at"),
            })

        total_files = len(files)
        total_bytes = sum(item["file_size"] for item in files)

        return render_template(
            "index.html",
            files=files,
            total_files=total_files,
            total_bytes=total_bytes,
            user_email=session.get("email", ""),
        )

    except Exception:
        app.logger.exception("Could not load the CloudVault dashboard.")
        flash("Could not load your files. Please try again.", "error")

        return render_template(
            "index.html",
            files=[],
            total_files=0,
            total_bytes=0,
            user_email=session.get("email", ""),
        )


# --------------------------------------------------
# Registration
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user_id():
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Enter your email and password.", "error")
            return render_template("auth.html", mode="register")

        if len(password) < 8:
            flash(
                "Your password must contain at least 8 characters.",
                "error",
            )
            return render_template("auth.html", mode="register")

        try:
            client = new_supabase_client()
            response = client.auth.sign_up({
                "email": email,
                "password": password,
            })

            user = response.user
            auth_session = response.session

            if user and auth_session:
                session.clear()
                session["user_id"] = user.id
                session["email"] = user.email or email
                session["access_token"] = auth_session.access_token
                session["refresh_token"] = auth_session.refresh_token

                flash("Welcome to CloudVault!", "success")
                return redirect(url_for("index"))

            flash(
                "Registration received. Check your email to confirm "
                "your account, then log in.",
                "success",
            )
            return redirect(url_for("login"))

        except Exception:
            app.logger.exception("CloudVault registration failed.")
            flash(
                "Registration failed. Check whether your email is "
                "already registered, and try again later if rate-limited.",
                "error",
            )

    return render_template("auth.html", mode="register")


# --------------------------------------------------
# Login
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user_id():
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Enter your email and password.", "error")
            return render_template("auth.html", mode="login")

        try:
            client = new_supabase_client()
            response = client.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })

            user = response.user
            auth_session = response.session

            if not user or not auth_session:
                flash("Login failed. Please try again.", "error")
                return render_template("auth.html", mode="login")

            session.clear()
            session["user_id"] = user.id
            session["email"] = user.email or email
            session["access_token"] = auth_session.access_token
            session["refresh_token"] = auth_session.refresh_token

            flash("Welcome back to CloudVault!", "success")
            return redirect(url_for("index"))

        except Exception:
            app.logger.exception("CloudVault login failed.")
            flash(
                "Login failed. Check your credentials and confirm "
                "your email address if required.",
                "error",
            )

    return render_template("auth.html", mode="login")


# --------------------------------------------------
# Logout
# --------------------------------------------------

@app.route("/logout", methods=["POST"])
def logout():
    client = authenticated_client()

    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            app.logger.warning("Supabase sign-out did not complete.")

    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# --------------------------------------------------
# Upload to private Supabase Storage
# --------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():
    if not current_user_id():
        return redirect(url_for("login"))

    client = login_required()

    if client is None:
        return redirect(url_for("login"))

    uploaded_file = request.files.get("file")

    if uploaded_file is None or not uploaded_file.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("index"))

    # Remove any directory components from the submitted filename.
    file_name = os.path.basename(
        uploaded_file.filename.replace("\\", "/")
    )

    if not file_name or file_name in {".", ".."}:
        flash("Invalid file name.", "error")
        return redirect(url_for("index"))

    file_content = uploaded_file.read(MAX_FILE_SIZE + 1)

    if len(file_content) > MAX_FILE_SIZE:
        flash("The maximum file size is 10 MB.", "error")
        return redirect(url_for("index"))

    if not file_content:
        flash("The selected file is empty.", "error")
        return redirect(url_for("index"))

    content_type = (
        uploaded_file.mimetype or "application/octet-stream"
    )

    # Store each user's objects inside their own UUID folder.
    storage_path = (
        f"{current_user_id()}/{uuid.uuid4().hex}__{file_name}"
    )

    try:
        client.storage.from_(BUCKET_NAME).upload(
            storage_path,
            file_content,
            {
                "content-type": content_type,
                "upsert": "false",
            },
        )

        try:
            client.table("files").insert({
                "user_id": current_user_id(),
                "file_name": file_name,
                "storage_path": storage_path,
                "file_size": len(file_content),
                "content_type": content_type,
            }).execute()

        except Exception:
            # Avoid leaving an unlisted object if metadata insertion fails.
            try:
                client.storage.from_(BUCKET_NAME).remove([storage_path])
            except Exception:
                app.logger.exception(
                    "Could not clean up an uploaded object."
                )
            raise

        flash(f"{file_name} uploaded successfully!", "success")

    except Exception:
        app.logger.exception("CloudVault upload failed.")
        flash(
            "Upload failed. Check your Storage bucket and Supabase "
            "policies, then review the terminal error.",
            "error",
        )

    return redirect(url_for("index"))


# --------------------------------------------------
# Download from private Supabase Storage
# --------------------------------------------------

@app.route("/download/<file_id>", methods=["GET"])
def download(file_id):
    if not current_user_id():
        return redirect(url_for("login"))

    client = login_required()

    if client is None:
        return redirect(url_for("login"))

    try:
        response = (
            client.table("files")
            .select("*")
            .eq("id", file_id)
            .eq("user_id", current_user_id())
            .limit(1)
            .execute()
        )

        if not response.data:
            flash("File not found or you do not have access.", "error")
            return redirect(url_for("index"))

        file_record = response.data[0]

        content = client.storage.from_(BUCKET_NAME).download(
            file_record["storage_path"]
        )

        return send_file(
            BytesIO(content),
            as_attachment=True,
            download_name=file_record["file_name"],
            mimetype=(
                file_record.get("content_type")
                or "application/octet-stream"
            ),
        )

    except Exception:
        app.logger.exception("CloudVault download failed.")
        flash("Could not download this file. Please try again.", "error")
        return redirect(url_for("index"))


# --------------------------------------------------
# Delete from private Supabase Storage
# --------------------------------------------------

@app.route("/delete/<file_id>", methods=["POST"])
def delete(file_id):
    if not current_user_id():
        return redirect(url_for("login"))

    client = login_required()

    if client is None:
        return redirect(url_for("login"))

    try:
        response = (
            client.table("files")
            .select("*")
            .eq("id", file_id)
            .eq("user_id", current_user_id())
            .limit(1)
            .execute()
        )

        if not response.data:
            flash("File not found or you do not have access.", "error")
            return redirect(url_for("index"))

        file_record = response.data[0]
        storage_path = file_record["storage_path"]

        # Remove the cloud object first. If this fails, keep its metadata.
        client.storage.from_(BUCKET_NAME).remove([storage_path])

        (
            client.table("files")
            .delete()
            .eq("id", file_id)
            .eq("user_id", current_user_id())
            .execute()
        )

        flash(
            f"{file_record['file_name']} deleted successfully.",
            "success",
        )

    except Exception:
        app.logger.exception("CloudVault deletion failed.")
        flash("Could not delete this file. Please try again.", "error")

    return redirect(url_for("index"))


# --------------------------------------------------
# Request too large
# --------------------------------------------------

@app.errorhandler(413)
def request_entity_too_large(_error):
    flash("The upload is too large. The maximum file size is 10 MB.", "error")
    return redirect(url_for("index")), 303


# --------------------------------------------------
# Run locally
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1",
    )
