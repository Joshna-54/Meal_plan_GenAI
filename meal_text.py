import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai
import pandas as pd
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

st.set_page_config(page_title="7-Day AI Diet Planner", layout="wide")
st.title("🍽️ AI Diet Planner – 7 Day Plan (Gemini Powered)")

# Sidebar inputs
with st.sidebar:
    st.header("User Profile")
    age = st.number_input("Age",min_value=1,max_value=120,value=20)
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    weight = st.number_input("Weight (kg)", min_value=10.0, value=50.0)
    height = st.number_input("Height (cm)", min_value=100.0, value=170.0)
    activity_level = st.selectbox("Activity Level", ["Sedentary", "Light", "Moderate", "Active"])
    goal = st.radio("Health Goal", ["Fat Loss", "Muscle Gain", "Maintain Weight"])
    diet_type = st.multiselect("Diet Preference", ["Vegan", "Vegetarian", "Keto", "Low-Carb", "High-Protein"])
    allergies = st.text_input("Allergies")
    fav_cuisine = st.text_input("Preferred Cuisines")
    height_m=height/100
    bmi=weight/(height_m ** 2)
    if gender=="Male":
        bmr=10*weight+6.25*height-5*age+5
    elif gender=="Female":
        bmr=10*weight+6.25*height-5*age-161
    else:
        bmr=10*weight+6.25*height-5*age
    #Activity Multiplier
    activity_factors = {
        "Sedentary":1.2,
        "Light":1.375,
        "Moderate":1.55,
        "Active":1.725
    }
    tdee=bmr * activity_factors[activity_level]
    if goal=="Fat Loss":
        calorie_goal = tdee*0.7
    else:
        calorie_goal=tdee

# Main execution
if st.button("Generate 7-Day Diet Plan"):
    with st.spinner("🧠 Gemini is creating your personalized 7-day plan..."):

        prompt = f"""
        Create a personalized **7-day meal plan** for the following individual:
        - Age: {age}
        - Gender: {gender}
        - Weight: {weight} kg
        - Height: {height} cm
        - Activity Level: {activity_level}
        - Goal: {goal}
        - Diet Preferences: {', '.join(diet_type) if diet_type else 'None'}
        - Allergies: {allergies if allergies else 'None'}
        - Preferred Cuisines: {fav_cuisine if fav_cuisine else 'Any'}
        - Daily Calorie Goal: approximately {calorie_goal:.0f} Kcal

        Each day should include:
        - Breakfast
        - Lunch
        - Dinner
        - Snacks
        
        Ensure that the **total daily calories stay close to the daily goal
        Distribute csalories across meals
        Include calories and macronutrients (protein, carbs, fats) for each meal if possible.
        Make sure meals Follow diet preferences, Allergies, Preferred Cuisines
        Format clearly with headings like "Day 1", "Day 2", etc.
        """

        try:
            response = model.generate_content(prompt)
            plan = response.text

            # Display 7-day plan
            st.subheader("📅 Your 7-Day Diet Plan")
            days = plan.split("\n\n")
            for day in days:
                if day.strip():
                    lines = day.strip().splitlines()
                    heading = lines[0] if lines else "Day"
                    body = "\n".join(lines[1:]) if len(lines) > 1 else ""
                    with st.expander(heading):
                        st.markdown(body)

            # Generate grocery list
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

                # Parse grocery list
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

                # Show grocery list
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