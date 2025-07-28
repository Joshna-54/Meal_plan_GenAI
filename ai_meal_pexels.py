import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai
import pandas as pd
import requests
import re

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("Gemini API key not found in .env file")
    st.stop()

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ----------- PEXELS IMAGE HELPERS -------------
def simplify(text):
    return text.lower().split(",")[0].split("with")[0].strip()

def call_pexels_api(query):
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    if not PEXELS_API_KEY:
        return None
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(
        f"https://api.pexels.com/v1/search?query={query}&per_page=1",
        headers=headers
    )
    if response.status_code == 200:
        data = response.json()
        if data["photos"]:
            return data["photos"][0]["src"]["medium"]
    return None

def search_pexels(meal_name):
    fallback_queries = [meal_name, simplify(meal_name), "healthy food"]
    for q in fallback_queries:
        result = call_pexels_api(q)
        if result:
            return result
    return None

def get_meal_image(meal_name):
    return search_pexels(meal_name)

# ------------------- UI -------------------------
st.set_page_config(page_title="7-Day AI Diet Planner", layout="wide")
st.title("🍽️ AI Diet Planner – 7 Day Plan (Gemini + Pexels)")

# Sidebar inputs
with st.sidebar:
    st.header("User Profile")
    age = st.number_input("Age", min_value=1, max_value=120, value=20)
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    weight = st.number_input("Weight (kg)", min_value=10.0, value=50.0)
    height = st.number_input("Height (cm)", min_value=100.0, value=170.0)
    body_fat_percent=st.number_input("Body Fat %",min_value=5,max_value=50,value=10)
    activity_level = st.selectbox("Activity Level", ["Sedentary", "Light", "Moderate", "Active", "Extra_Active"])
    goal = st.radio("Health Goal", ["Fat Loss", "Muscle Gain", "Maintain Weight"])
    diet_type = st.multiselect("Diet Preference", ["Vegan", "Vegetarian", "Keto", "Low-Carb", "High-Protein"])
    allergies = st.text_input("Allergies")
    fav_cuisine = st.text_input("Preferred Cuisines")

    height_m = height / 100
    bmi = weight / (height_m ** 2)
    if gender == "Male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    elif gender == "Female":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age

    activity_factors = {
        "Sedentary": 1.2,
        "Light": 1.375,
        "Moderate": 1.55,
        "Active": 1.725,
        "Extra_Active": 1.9
    }

    tdee = bmr * activity_factors[activity_level]
    calorie_goal = tdee * 0.7 if goal == "Fat Loss" else tdee
    fat_percent=body_fat_percent/100
    lbm_kg = weight * (1-fat_percent)
    protein_target = round(lbm_kg*1.8, 1)
    fat_min=50
    fat_max=60
    fiber_target=30
    sugar_limit=round((calorie_goal*0.06)/4)

# Generate Meal Plan
if st.button("Generate 7-Day Diet Plan"):
    with st.spinner("🧠 Gemini is creating your personalized 7-day plan..."):

        prompt = f"""
        Create a personalized **7-day meal plan** for the following individual:
        - Age: {age}
        - Gender: {gender}
        - Weight: {weight} kg
        - Height: {height} cm
        - Body Fat %: {body_fat_percent}%
        - Activity Level: {activity_level}
        - Goal: {goal}
        - Diet Preferences: {', '.join(diet_type) if diet_type else 'None'}
        - Allergies: {allergies if allergies else 'None'}
        - Preferred Cuisines: {fav_cuisine if fav_cuisine else 'Any'}
        - Daily Calorie Goal: approximately {calorie_goal:.0f} Kcal
        
        Nutrition Guidelines (strictly follow):
        - **Protein**: Minimum **{protein_target} grams/day**, based on lean body mass
        - **Fat**: Between **{fat_min}–{fat_max} grams/day**
        - **Fiber**: Minimum **{fiber_target} grams/day**
        - **Added Sugar**: No more than **{sugar_limit} grams/day** (6% of daily calorie intake)
        Meal Plan Rules:
        - provide meal plan for 7 days with **Breakfast, Lunch, Dinner, and Snacks** for each day
        - Include for **each meal**: calories, protein, carbs, fats, fiber, added sugar
        - Use diet preferences, allergies, and preferred cuisines to personalize meals
        - Ensure meals are nutritionally balanced
        - Format clearly with "Day 1", "Day 2",...., "Day 7" etc.
        """

        try:
            # Split into 2 parts
            first_half_prompt = prompt + "\n\nPlease generate meal plans for Day 1 to Day 3 only."
            second_half_prompt = prompt + "\n\nPlease generate meal plans for Day 4 to Day 7 only."
            # Generate first 3 days
            first_response = model.generate_content(first_half_prompt)
            first_plan = first_response.text.strip()
            # Generate next 4 days
            second_response = model.generate_content(second_half_prompt)
            second_plan = second_response.text.strip()
            # Combine plans
            plan = f"{first_plan}\n\n{second_plan}"
            #response = model.generate_content(prompt)
            #plan = response.text
            days = re.findall(r"Day\s*\d",plan)
            if len(days) < 7:
                st.warning("The model did not generate a full 7-day plan. Try regenerating")
            st.subheader("📅 Your 7-Day Diet Plan")
            days = re.split(r"(?=Day \d)", plan.strip())
            for day_text in days:
                lines = day_text.strip().splitlines()
                if not lines:
                    continue

                heading = lines[0].strip()
                content = "\n".join(lines[1:])

                with st.expander(heading):
                    meals = re.findall(r"\*\*(.*?)\*\*:?\s*(.*)", content)
                    for meal_type, meal_desc in meals:
                        if meal_desc:
                            cols = st.columns([1, 3])
                            with cols[0]:
                                image_url = get_meal_image(meal_desc)
                                if image_url:
                                    st.image(image_url, use_container_width=True)
                                else:
                                    st.markdown("🚫 No image found")
                            with cols[1]:
                                st.markdown(f"**{meal_type}:** {meal_desc}")

            # Grocery list
            with st.spinner("🛒 Generating your weekly grocery list..."):
                grocery_prompt = f"""
                Here is a 7-day diet plan:
                {plan}

                Please extract a grocery shopping list for this 7-day plan. Group items by categories such as:
                - Vegetables
                - Fruits
                - Grains
                - Dairy
                - Proteins
                - Spices & Condiments
                - Others

                Include quantities where possible. Format it as a readable, bullet-point list grouped by category with headers like ## Vegetables.
                """
                grocery_response = model.generate_content(grocery_prompt)
                grocery_list = grocery_response.text

                def parse_grocery_list(text):
                    sections = re.split(r'##\s*', text)
                    items_by_category = []
                    for section in sections:
                        if not section.strip():
                            continue
                        lines = section.strip().splitlines()
                        category = lines[0].strip()
                        for item in lines[1:]:
                            match = re.match(r"-\s*(.+?)\s*[–-]\s*(.+)", item)
                            if match:
                                item_name = match.group(1).strip()
                                qty = match.group(2).strip()
                            else:
                                item_name = item.strip().lstrip("- ")
                                qty = ""
                            items_by_category.append({
                                "Category": category,
                                "Item": item_name,
                                "Quantity": qty
                            })
                    return pd.DataFrame(items_by_category)

                st.subheader("🛒 Weekly Grocery List")
                with st.expander("📋 Click to view grocery list as a table"):
                    grocery_df = parse_grocery_list(grocery_list)
                    st.dataframe(grocery_df, use_container_width=True)

                    st.download_button(
                        label="Download Grocery List as CSV",
                        data=grocery_df.to_csv(index=False),
                        file_name="grocery_list.csv",
                        mime="text/csv"
                    )

        except Exception as e:
            st.error(f"Error: {e}")
