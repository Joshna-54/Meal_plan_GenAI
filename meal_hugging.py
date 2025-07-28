import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai
import pandas as pd
import requests
from PIL import Image
from io import BytesIO
import re

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_API_KEY")

if not GEMINI_API_KEY:
    st.error("Gemini API key not found in .env file")
    st.stop()
if not HUGGINGFACE_TOKEN:
    st.error("Hugging Face token not found in .env file")
    st.stop()

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="7-Day AI Diet Planner", layout="wide")
st.title("🍽️ AI Diet Planner – 7 Day Plan (Gemini + Hugging Face)")

@st.cache_data(show_spinner=False)
def generate_meal_image(prompt):
    url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"inputs": prompt}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
    except Exception as e:
        print("Image generation error:", e)
    return None

def enhance_meal_prompt(meal_line):
    return (
        f"A high-resolution food photo of {meal_line.lower()}, "
        "realistic and beautifully plated, served in a clean white ceramic dish. "
        "Top-down view, bright natural light, professional food photography style."
    )

# Sidebar inputs
with st.sidebar:
    st.header("User Profile")
    age = st.number_input("Age", min_value=1, max_value=120, value=25)
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    weight = st.number_input("Weight (kg)", min_value=30.0, value=65.0)
    height = st.number_input("Height (cm)", min_value=100.0, value=170.0)
    body_fat_percent = st.number_input("Body Fat %", min_value=5, max_value=50, value=20)
    activity_level = st.selectbox("Activity Level", ["Sedentary", "Light", "Moderate", "Active"])
    goal = st.radio("Health Goal", ["Fat Loss", "Muscle Gain", "Maintain Weight"])
    diet_type = st.multiselect("Diet Preference", ["Vegan", "Vegetarian", "Keto", "Low-Carb", "High-Protein"])
    allergies = st.text_input("Allergies")
    fav_cuisine = st.text_input("Preferred Cuisines")

    # Calculations
    height_m = height / 100
    bmi = weight / (height_m ** 2)
    if gender == "Male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    elif gender == "Female":
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age

    activity_factors = {
        "Sedentary": 1.2,
        "Light": 1.375,
        "Moderate": 1.55,
        "Active": 1.725
    }

    tdee = bmr * activity_factors[activity_level]
    calorie_goal = tdee * 0.7 if goal == "Fat Loss" else tdee

    lbm_kg = weight * (1 - body_fat_percent / 100)
    protein_target = round(lbm_kg * 1.8, 1)
    fat_min = 50
    fat_max = 60
    fiber_target = 30
    sugar_limit = round((calorie_goal * 0.06) / 4)

# Main execution
if st.button("Generate 7-Day Diet Plan"):
    with st.spinner("🧠 Gemini is creating your personalized 7-day plan..."):
        base_prompt = f"""
        Create a personalized **7-day meal plan** for the following individual:
        - Age: {age}
        - Gender: {gender}
        - Weight: {weight} kg
        - Height: {height} cm
        - Body Fat %: {body_fat_percent}%
        - Activity Level: {activity_level}
        - Goal: {goal}
        - Diet Preferences: {', '.join(diet_type) if diet_type else 'None'}
        - Allergies: {allergies or 'None'}
        - Preferred Cuisines: {fav_cuisine or 'Any'}
        - Daily Calorie Goal: approx {int(calorie_goal)} kcal

        Guidelines:
        - **Protein**: At least {protein_target}g/day
        - **Fat**: Between {fat_min}g and {fat_max}g per day
        - **Fiber**: At least {fiber_target}g/day
        - **Added Sugar**: No more than {sugar_limit}g/day

        Format:
        - Clearly specify "Day 1" through "Day 7"
        - For each day, include **Breakfast**, **Lunch**, **Dinner**, and **Snacks** (snacks should be grouped under one heading, not snack1, snack2)
        - Meal Type: Meal Name (Calories kcal, Protein g, Carbs g, Fat g, Fiber g, Sugar g) – Ingredient list
        """

        part1 = base_prompt + "\n\nGenerate plans for Day 1 to Day 3."
        part2 = base_prompt + "\n\nGenerate plans for Day 4 to Day 7."

        try:
            part1_response = model.generate_content(part1).text.strip()
            part2_response = model.generate_content(part2).text.strip()
            full_plan = f"{part1_response}\n\n{part2_response}"

            st.subheader("📅 Your 7-Day Diet Plan")
            days = re.split(r"(?=Day \d)\s*", full_plan)
            for day in days:
                lines = day.strip().splitlines()
                if not lines: continue
                heading = lines[0]
                content = lines[1:]
                with st.expander(heading):
                    for line in content:
                        if any(m in line.lower() for m in ["breakfast", "lunch", "dinner", "snack"]):
                            st.markdown(f"**{line}**")
                            prompt = enhance_meal_prompt(line)
                            img = generate_meal_image(prompt)
                            if img:
                                st.image(img, caption=line, use_container_width=True)
                            else:
                                st.caption("⚠️ Image not available")

            # Grocery List
            with st.spinner("🛒 Generating grocery list..."):
                grocery_prompt = f"Extract a grocery list (with quantities, grouped by category) from the following 7-day meal plan:\n{full_plan}"
                grocery_resp = model.generate_content(grocery_prompt)
                grocery_text = grocery_resp.text

                def parse_grocery(text):
                    sections = re.split(r"##\s*", text)
                    items = []
                    for section in sections:
                        if not section.strip(): continue
                        lines = section.strip().splitlines()
                        category = lines[0]
                        for item in lines[1:]:
                            match = re.match(r"-\s*(.+?)\s*[\u2013-]\s*(.+)", item)
                            name = match.group(1).strip() if match else item.strip("- ")
                            qty = match.group(2).strip() if match else ""
                            items.append({"Category": category, "Item": name, "Quantity": qty})
                    return pd.DataFrame(items)

                st.subheader("🛒 Grocery List")
                with st.expander("📋 View Grocery List"):
                    df = parse_grocery(grocery_text)
                    st.dataframe(df, use_container_width=True)
                    st.download_button("Download as CSV", data=df.to_csv(index=False), file_name="grocery_list.csv", mime="text/csv")

        except Exception as e:
            st.error(f"Error: {e}")
