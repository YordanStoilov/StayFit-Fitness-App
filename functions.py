from functools import wraps
from flask import redirect, session
import requests
import json
from dotenv import load_dotenv
import os
import base64

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")

# Login required decorator:
def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function

# Class User to store functions about user vitals:
class User:
    activities_mets = {
        "walking": 4.5,
        "swimming": 7,
        "jogging": 7,
        "stretching": 4,
        "running": 9,
        "yoga": 3,
        "weightlifting": 8
    }

    def __init__(self, name: str, age: int, weight: float, height: int, blood_pressure: tuple):
        self.name = name
        self.age = age
        self.weight = weight
        self.height = height
        self.blood_pressure = blood_pressure
        self.max_heartrate = 0

    def get_bmi(self):
        height_in_m = self.height / 100
        bmi_value = self.weight / (height_in_m ** 2)
        return round(bmi_value, 2)

    def get_blood_pressure_status(self):
        status = ""
        if self.blood_pressure[0] < 110 and self.blood_pressure[1] < 70:
            status = "Low Blood Pressure"
        elif self.blood_pressure[0] < 120 and self.blood_pressure[1] <= 80:
            status = "Normal Blood Pressure"
        elif 120 <= self.blood_pressure[0] < 130 and self.blood_pressure[1] <= 90:
            status = "Elevated Blood Pressure"
        elif 130 <= self.blood_pressure[0] < 140 and self.blood_pressure[1] <= 90:
            status = "Pre-Hypertension"
        elif 140 <= self.blood_pressure[0] < 160 and self.blood_pressure[1] >= 90:
            status = "Stage 1 Hypertension"
        elif self.blood_pressure[0] >= 160 and self.blood_pressure[1] > 100:
            status = "Stage 2 Hypertension"

        return status

    def get_max_heartrate(self):
        self.max_heartrate = 220 - self.age
        return self.max_heartrate

    def get_goal_pulse(self):
        low_threshold = 0.5 * self.max_heartrate
        high_threshold = 0.85 * self.max_heartrate
        return (round(low_threshold), round(high_threshold))

    def get_burned_calories(self, activity: str, minutes: int):
        try:
            calories_per_minute = self.activities_mets[activity.lower()] * (self.weight / 2.2) / 200
            total_calories = round(calories_per_minute * minutes, 2)
            return total_calories
        
        except KeyError:
            return "Invalid activity!"
        
# Getting API data about exercises:
def get_exercises(exercise=None, muscle=None, difficulty=None):

    api_url = "https://api.api-ninjas.com/v1/exercises"

    dict_inputs = {"type": exercise, "muscle": muscle, "difficulty": difficulty}

    first = True
    for key, value in dict_inputs.items():

        if value is not None:
            if first:
                api_url += f"?{key}={value}"
                first = False
            else:
                api_url += f"&{key}={value}"


    response = requests.get(api_url, headers={'X-Api-Key': '+6tQp0+ZJwDYePUcZsXFgQ==hrcw2cmc1M6VPrPh'})
    if response.status_code == requests.codes.ok:
        return json.loads(response.text)
    else:
        return f"Error: {response.status_code, response.text}"

def format_results(results: list):

    for result in results:
        result["exercise_id"] = f'{result["name"]}&{result["type"]}&{result["muscle"]}&{result["difficulty"]}'
        result["muscle"] = result["muscle"].replace("_", " ").capitalize()
        result["equipment"] = result["equipment"].replace("_", " ").capitalize()

    return results

# Getting API data from Spotify:
def get_token():
    auth_string = f"{client_id}:{client_secret}"
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {"grant_type": "client_credentials"}
    result = requests.post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    print(json_result)
    token = json_result["access_token"]
    return token


def get_auth_header(token):
    return {"Authorization": f"Bearer {token}"}

def search_for_playlist(token, genre, limit=5):

    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    query = f"?q={genre}&type=playlist&limit={limit}"
    query_url = f"{url}{query}"

    result = requests.get(query_url, headers=headers)
    json_result = json.loads(result.content)["playlists"]["items"]

    if len(json_result) == 0:
        return None

    return json_result
    
def get_needed_data_from_json(json_data):
    necessary_data = []

    for item in json_data:
        necessary_data.append({
        "name": item["name"], 
        "description": item["description"], 
        "music_link": get_spotify_embed_url(item["external_urls"]["spotify"]),
        "image_link": item["images"][0]["url"]})

    return necessary_data

def get_spotify_embed_url(url):
    left_side = url[:24]
    right_side = url[24:]
    return f"{left_side}/embed{right_side}"