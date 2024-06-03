import os

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functions import login_required, get_exercises, User, get_exercise_id, get_token, get_needed_data_from_json, search_for_playlist

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///database.db")

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@app.route("/login", methods = ["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("warning.html", message="Please fill in the forms!")
        
        user_data = db.execute("SELECT * FROM users WHERE username = ?", username)
        data = user_data[0]

        if not data:
            return render_template("warning.html", message="User does not exist!")

        if not check_password_hash(data["password_hash"], password) or not username == data["username"]:
            return render_template("warning.html", message="Incorrect username or password!")
        
        session["user_id"] = data["user_id"]

        app.logger.debug(f"Session user_id set to: {session['user_id']}")

        return redirect("/")
    
    return render_template("index.html")

@app.route("/logout", methods = ["GET", "POST"])
@login_required
def logout():
    session.clear()
    return redirect("/")

@app.route("/register", methods = ["GET", "POST"])
def register():
    session.clear()
    
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")

        # if not email or not username or not password:
        #     return render_template("warning.html", message="Please fill in the fields")

        if db.execute("SELECT * FROM users WHERE username = ?", username):
            return render_template("warning.html", message="Username already exists")
        
        db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", username, email, generate_password_hash(password))
        return render_template("warning.html", message="Successfully registered!")

    return render_template("register.html")

@app.route("/workouts", methods=["GET", "POST"])
@login_required
def workouts():
    if request.method == "POST":
        exercise = request.form.get("exercise")
        muscle = request.form.get("muscle")
        difficulty = request.form.get("difficulty")
        results_number = int(request.form.get("results_number"))

        if not exercise and not muscle and not difficulty:
            return render_template("warning.html", message="You need to input at least one value!")

        results = get_exercises(exercise=exercise, muscle=muscle, difficulty=difficulty)

        if not results:
            return render_template("warning.html", message="No results.")

        if not results_number:
            results_number = 10

        results = results[:results_number]
        results = get_exercise_id(results)

        return render_template("workout_results.html", results=results)
    
    return render_template("workouts.html")


@app.route("/add_favourite", methods=["POST", "GET"])
@login_required
def add_favourite():
    user_id = session["user_id"]
    if request.method == "POST":
        selected = request.form.getlist("favourite_exercises")
        
        for result in selected:
            result = result.split("|")
            equipment = result[0] 
            instructions = result[1]
            exercise_id = result[2]
            exercise_name, exercise_type, muscle_group, difficulty = exercise_id.split("&")

            if not db.execute("SELECT * FROM favourites WHERE user_id = ? AND exercise_id = ?", user_id, result[2]):
                db.execute("INSERT INTO favourites (exercise_name, exercise_type, exercise_difficulty, muscle_group, exercise_id, equipment, instructions, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                           exercise_name, exercise_type, difficulty, muscle_group, exercise_id, equipment, instructions, user_id)
                
            return redirect("/profile")


@app.route("/health_test", methods=["GET", "POST"])
@login_required
def health_test():
    if request.method == "POST":
        name = request.form.get("name")
        age = int(request.form.get("age"))
        weight = float(request.form.get("weight"))
        height = int(request.form.get("height"))
        upper_bound_bp = int(request.form.get("blood_pressure_systolic"))
        lower_bound_bp = int(request.form.get("blood_pressure_diastolic"))

        if not name or not age or not weight or not height or not upper_bound_bp or not lower_bound_bp:
            return render_template("/warning.html", message="Please fill in all forms!")
        
        user = User(name, age, weight, height, (upper_bound_bp, lower_bound_bp))

        user_id = session["user_id"]

        if db.execute("SELECT * FROM user_vitals WHERE user_id = ?", user_id):
            db.execute("UPDATE user_vitals SET name = ?, age = ?, weight = ?, height = ?, upper_bp = ?, lower_bp = ? WHERE user_id = ?", 
                       name, age, weight, height, upper_bound_bp, lower_bound_bp, user_id)
        
        else:
            db.execute("INSERT INTO user_vitals (user_id, name, age, weight, height, upper_bp, lower_bp) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                    user_id, name, age, weight, height, upper_bound_bp, lower_bound_bp)
        
        bmi = user.get_bmi()
        bps = user.get_blood_pressure_status()
        max_heartrate = user.get_max_heartrate()
        goal_pulse = user.get_goal_pulse()

        if db.execute("SELECT * FROM user_results WHERE user_id = ?", user_id):
            db.execute("UPDATE user_results SET bmi = ?, bps = ?, max_heartrate = ?, gp_upper = ?, gp_lower = ?", 
                       bmi, bps, max_heartrate, goal_pulse[1], goal_pulse[0])
        
        else:
            db.execute("INSERT INTO user_results (user_id, bmi, bps, max_heartrate, gp_upper, gp_lower) VALUES (?, ?, ?, ?, ?, ?)", 
                       user_id, bmi, bps, max_heartrate, goal_pulse[1], goal_pulse[0])

        return render_template("health_results.html", bmi=bmi, bps=bps, max_heartrate=max_heartrate, goal_pulse=goal_pulse)

    return render_template("health_test.html")

@app.route("/profile", methods=["POST", "GET"])
@login_required
def profile():
    user_id = session["user_id"]
    try:
        user_data = db.execute("SELECT * FROM user_results WHERE user_id = ?", session["user_id"])[0]
        name = db.execute("SELECT name FROM user_vitals WHERE user_id = ?", session["user_id"])[0]

    except(IndexError):
        return render_template("profile.html", user_data=[])
    
    favourites = db.execute("SELECT * FROM favourites WHERE user_id = ?", user_id)
    return render_template("profile.html", user_data=user_data, name=name["name"], favourites=favourites)


@app.route("/motivated", methods=["GET", "POST"])
@login_required
def motivated():
    token = get_token()
    results = get_needed_data_from_json(search_for_playlist(token, "workout", limit=10))

    return render_template("motivated.html", results=results)


if __name__ == '__main__':
    app.run(debug=True, port=5001)