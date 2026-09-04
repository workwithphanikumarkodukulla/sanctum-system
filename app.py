
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from sanctum_locker import restrict_file, unrestrict_file
import os
import uuid

app = Flask(__name__)

# Flask secret key
app.secret_key = "sanctum-locker-secret-key"

# Folder names
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"

# Create folders automatically if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ---------------- HOME PAGE ----------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------- LOCK PAGE ----------------

@app.route("/lock")
def lock_page():
    return render_template("lock.html")


@app.route("/lock", methods=["POST"])
def lock_file():

    # Check whether a file was uploaded
    if "file" not in request.files:
        flash("Please select a file.")
        return redirect(url_for("lock_page"))

    file = request.files["file"]

    # Get password from form
    password = request.form.get("password", "")

    # Check file name
    if file.filename == "":
        flash("Please select a file.")
        return redirect(url_for("lock_page"))

    # Check password
    if password == "":
        flash("Please enter a password.")
        return redirect(url_for("lock_page"))

    # Create a unique filename
    unique_name = str(uuid.uuid4()) + "_" + file.filename

    input_path = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    # Save uploaded file
    file.save(input_path)

    try:

        # Lock the file using Sanctum Locker
        locked_file = restrict_file(
            input_path,
            password
        )

        # Send locked file to the user
        return send_file(
            locked_file,
            as_attachment=True,
            download_name=file.filename + ".locked"
        )

    except Exception as error:

        flash("Could not lock the file: " + str(error))

        return redirect(url_for("lock_page"))


# ---------------- UNLOCK PAGE ----------------

@app.route("/unlock")
def unlock_page():
    return render_template("unlock.html")


@app.route("/unlock", methods=["POST"])
def unlock_file():

    # Check whether a file was uploaded
    if "file" not in request.files:
        flash("Please select a locked file.")
        return redirect(url_for("unlock_page"))

    file = request.files["file"]

    # Get password
    password = request.form.get("password", "")

    # Check file
    if file.filename == "":
        flash("Please select a locked file.")
        return redirect(url_for("unlock_page"))

    # Check password
    if password == "":
        flash("Please enter the password.")
        return redirect(url_for("unlock_page"))

    # Create unique uploaded filename
    unique_name = str(uuid.uuid4()) + "_" + file.filename

    input_path = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    # Save uploaded locked file
    file.save(input_path)

    try:

        # Remove .locked from filename
        original_name = file.filename

        if original_name.endswith(".locked"):
            original_name = original_name[:-7]

        output_path = os.path.join(
            OUTPUT_FOLDER,
            original_name
        )

        # Unlock the file
        restored_file = unrestrict_file(
            input_path,
            password,
            output_path
        )

        # Send restored file to user
        return send_file(
            restored_file,
            as_attachment=True,
            download_name=original_name
        )

    except Exception:

        flash(
            "Unable to unlock the file. "
            "Check the password and make sure the locked file is valid."
        )

        return redirect(url_for("unlock_page"))


# ---------------- START FLASK ----------------

if __name__ == "__main__":
    app.run(debug=True)

