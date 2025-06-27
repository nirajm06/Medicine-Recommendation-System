from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import pickle
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
from sklearn.svm import SVC 
from sklearn.preprocessing import LabelEncoder

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key"

# Load Datasets
sym_des = pd.read_csv("datasets/symptoms_df.csv")
precautions = pd.read_csv("datasets/precautions_df.csv")
workout = pd.read_csv("datasets/workout_df.csv")
description = pd.read_csv("datasets/description.csv")
medications = pd.read_csv("datasets/medications.csv")
diets = pd.read_csv("datasets/diets.csv")

symptoms_dict = {symptom: index for index, symptom in enumerate(sym_des.columns[1:])}
disease_dict = {disease: index for index, disease in enumerate(description['Disease'].unique())}

# MySQL Database Configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "flask_app"
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            return conn
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        return None

train_data = pd.read_csv("datasets/Train.csv")

X = train_data.iloc[:, 1:-1]  
y = train_data['prognosis']

le = LabelEncoder() #chnage categorial column to numercial
y_encoded = le.fit_transform(y)

X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.3, random_state=20)

from imblearn.over_sampling import SMOTE
sm = SMOTE(random_state=42)
X_resampled, y_resampled = sm.fit_resample(X, y_encoded)

import joblib

# Train model
svc_model = SVC(kernel="rbf", C=1, gamma="scale", probability=True)
svc_model.fit(X_train, y_train)

#model accuracy
y_pred = svc_model.predict(X_test)
print("Test Accuracy:", accuracy_score(y_test, y_pred))

# Save model
with open("models/svc.pkl", "wb") as f:
    pickle.dump(svc_model, f)

joblib.dump(list(X.columns), "models/features_names.pkl")  # Save feature names

print("✅ Model & features saved correctly!")

# Load Model
def load_model():
    global svc_model, feature_names
    with open("models/svc.pkl", "rb") as f:
        svc_model = pickle.load(f)

    feature_names = joblib.load("models/feature_names.pkl")  # Load features
    print("✅ Model and features loaded!")

# Load model on startup
load_model()

# Helper function to get disease details
def helper(disease):
    desc = " ".join(description[description['Disease'] == disease]['Description'])
    pre = precautions[precautions['Disease'] == disease].values.flatten()[1:].tolist()
    med = medications[medications['Disease'] == disease]['Medication'].tolist()
    diet = diets[diets['Disease'] == disease]['Diet'].tolist()
    wrkout = workout[workout['disease'] == disease]['workout'].values[0] if not workout[workout['disease'] == disease].empty else "No specific workout recommended."
    return desc, pre, med, diet, wrkout

# ✅ Fix get_predicted_value function
def get_predicted_value(patient_symptoms):
    input_vector = np.zeros(len(feature_names))  # Use feature length

    matched_symptoms = []
    for symptom in patient_symptoms:
        if symptom in feature_names:
            index = feature_names.index(symptom)
            input_vector[index] = 1
            matched_symptoms.append(symptom)

    print("✅ Matched Symptoms:", matched_symptoms)

    input_df = pd.DataFrame([input_vector], columns=feature_names)
    predicted_label = svc_model.predict(input_df)[0]  # Use `svc_model`
    
    predicted_disease = le.inverse_transform([predicted_label])[0]
    return predicted_disease


# Routes
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("register.html", message="Enter valid username and password")

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        if not conn:
            return render_template("register.html", message="Database connection error")

        cursor = conn.cursor()

        try:
            # ✅ Check if the user exists in EITHER table
            cursor.execute("""
                SELECT * FROM users WHERE username = %s 
                UNION 
                SELECT * FROM register WHERE username = %s
            """, (username, username))

            existing_user = cursor.fetchone()

            if existing_user:
                cursor.close()
                conn.close()
                return render_template("register.html", message="Username already exists!")

            # ✅ Insert into 'register' table
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            conn.commit()

        except mysql.connector.IntegrityError:
            cursor.close()
            conn.close()
            return render_template("register.html", message="Error registering user")

        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("login"))  # ✅ Always return a response

    return render_template("register.html")  # ✅ Always return for GET request

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        conn = get_db_connection()
        if not conn:
            return render_template("login.html", message="Database connection error")
        
        cursor = conn.cursor(dictionary=True)
        
        # ✅ Check both 'users' and 'register' tables for username
        cursor.execute("""
            SELECT * FROM users WHERE username = %s 
            UNION 
            SELECT * FROM register WHERE username = %s
        """, (username, username))
        
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()

        if user:
            stored_password = user["password"]  # Hashed password from DB
            
            print("Stored Hash:", stored_password)  # Debugging
            print("Entered Password:", password)  # Debugging
            
            if check_password_hash(stored_password, password):  # ✅ Check hashed password
                session["user"] = username
                return redirect(url_for("home"))
            else:
                print("❌ Password Mismatch!")  # Debugging
                return render_template("login.html", message="Invalid Credentials")
        else:
            print("❌ User Not Found!")  # Debugging
            return render_template("login.html", message="Invalid Credentials")
    
    return render_template("login.html")


@app.route("/home", methods=["GET", "POST"])
def home():
    # Ensure the user is logged in
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        symptoms = request.form.get("symptoms")

        if symptoms:
            symptoms_list = [s.strip() for s in symptoms.split(",")]

            try:
                predicted_disease = get_predicted_value(symptoms_list)
                desc, pre, med, die, wrkout = helper(predicted_disease)

                return render_template(
                    "home.html",
                    predicted_disease=predicted_disease,
                    dis_des=desc,
                    my_precautions=pre,
                    medications=med,
                    my_diet=die,
                    workout=wrkout
                )

                return redirect(url_for("result"))  # ✅ Redirect to a new page

            except Exception as e:
                return render_template("home.html", message=f"Error: {str(e)}")

    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")  # No authentication required for about page

@app.route("/result")
def result():
    if "user" not in session:
        return redirect(url_for("login"))

    predicted_disease = session.get("predicted_disease")
    desc = session.get("desc")
    precautions = session.get("precautions")
    medications = session.get("medications")
    diet = session.get("diet")
    workout = session.get("workout")

    if not predicted_disease:
        return redirect(url_for("home"))

    return render_template(
        "result.html",
        predicted_disease=predicted_disease,
        dis_des=desc,
        my_precautions=precautions,
        medications=medications,
        my_diet=diet,
        workout=workout
    )


@app.route('/predict', methods=['POST'])
def predict():
    if "user" not in session:
        return redirect(url_for("login"))

    symptoms = request.form.get('symptoms')
    if not symptoms:
        return render_template('home.html', message="Please enter valid symptoms.")

    user_symptoms = [s.strip() for s in symptoms.split(',')]
    user_symptoms = [symptom.strip("[]' ") for symptom in user_symptoms]

    predicted_disease = get_predicted_value(user_symptoms)
    dis_des, precautions, medications, rec_diet, workout = helper(predicted_disease)


    # ✅ Debugging: Print values before inserting
    print("\n--- DATABASE INSERT DEBUGGING ---")
    print("Predicted Disease:", predicted_disease)
    print("Description:", dis_des)
    print("Precautions:", precautions)
    print("Medications:", medications)
    print("Diet:", rec_diet)
    print("Workout:", workout)
    print("---------------------------------\n")

    # ✅ Save prediction details in MySQL
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # ✅ Insert into the 'predictions' table
            cursor.execute("""
                INSERT INTO predictions 
                (predicted_disease, description, precaution, medication, recommended_diet, workout_plan) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (predicted_disease, dis_des, ", ".join(precautions), ", ".join(medications), ", ".join(rec_diet), workout))

            conn.commit()
            print("✅ Prediction saved to database!")
        except mysql.connector.Error as err:
            print("❌ Database Insert Error:", err)
        finally:
            cursor.close()
            conn.close()

    return render_template(
        'result.html',
        predicted_disease=predicted_disease,
        dis_des=dis_des,
        my_precautions=precautions,
        medications=medications,
        my_diet=rec_diet,
        workout=workout
    )


@app.route("/reload_model")
def reload_model():
    global SVC
    SVC = load_model()
    return "Model reloaded successfully!"

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        message = request.form.get("message")

        if not (first_name and last_name and email and message):
            return render_template("contact.html", error="Please fill in all required fields.")

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO contact (first_name, last_name, email, phone, message)
                    VALUES (%s, %s, %s, %s, %s)
                """, (first_name, last_name, email, phone, message))
                conn.commit()
                return render_template("contact.html", success="Thank you! Your message has been sent.")
            except mysql.connector.Error as err:
                print("❌ Contact Form Insert Error:", err)
                return render_template("contact.html", error="Database error. Please try again later.")
            finally:
                cursor.close()
                conn.close()
        else:
            return render_template("contact.html", error="Database connection failed.")
    
    return render_template("contact.html")


@app.route("/developer")
def developer():
    return render_template("developer.html")

# Run Flask App
if __name__ == '__main__':
    app.run(debug=True)
