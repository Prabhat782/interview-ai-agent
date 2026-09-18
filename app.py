import streamlit as st
import subprocess
import sqlite3
import pandas as pd
import re
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Interview AI Agent", layout="wide")

# --- Background Image (Free Unsplash Gradient) ---
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://images.unsplash.com/photo-1508780709619-79562169bc64");
    background-size: cover;
    background-repeat: no-repeat;
    background-attachment: fixed;
}
[data-testid="stHeader"] {
    background: rgba(0,0,0,0);
}
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.85);
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("⚙️ Settings")
role = st.sidebar.selectbox("Select Role:", ["Software Engineer", "Data Analyst", "Web Developer", "AI Researcher"])
target = st.sidebar.slider("Set target average score:", 1, 10, 8)
export_role = st.sidebar.selectbox("Export Role Filter:", ["All", "Software Engineer", "Data Analyst", "Web Developer", "AI Researcher"])

# --- Dictionary of questions ---
questions = {
    "Software Engineer": [
        "Explain a challenging coding problem you solved.",
        "How do you ensure code quality?",
        "Describe a time you worked in a team project."
    ],
    "Data Analyst": [
        "How do you handle missing data?",
        "Explain a time you used SQL.",
        "What visualization tools do you prefer?"
    ],
    "Web Developer": [
        "What’s your approach to responsive design?",
        "How do you optimize website performance?",
        "Describe a project where you used JavaScript frameworks."
    ],
    "AI Researcher": [
        "Tell me about a recent AI paper that inspired you.",
        "How do you evaluate model performance?",
        "What ethical concerns do you see in AI research?"
    ]
}

# --- Reset q_index when role changes ---
if "last_role" not in st.session_state or st.session_state.last_role != role:
    st.session_state.q_index = 0
    st.session_state.last_role = role

question = questions[role][st.session_state.q_index]
st.header(f"🎤 Interview Question for {role}")
st.write(question)

user_input = st.text_area("Your Answer:")

# --- SQLite setup ---
conn = sqlite3.connect("interview.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS history (role TEXT, question TEXT, answer TEXT, feedback TEXT, timestamp TEXT)")

def save_response(role, question, answer, feedback):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO history VALUES (?, ?, ?, ?, ?)", (role, question, answer, feedback, ts))
    conn.commit()

# --- Submit button ---
if st.button("Submit Answer"):
    prompt = f"Evaluate this {role} interview answer and give a score (1-10) with feedback: {user_input}"
    result = subprocess.run(["ollama", "run", "llama3", prompt], capture_output=True, text=True)
    feedback = result.stdout.strip()
    st.success("✅ Feedback & Score:")
    st.write(feedback)
    save_response(role, question, user_input, feedback)
    if st.session_state.q_index < len(questions[role]) - 1:
        st.session_state.q_index += 1
    else:
        st.info("Interview complete for this role!")

# --- Export & Analytics ---
if st.sidebar.button("Export to CSV"):
    if export_role == "All":
        c.execute("SELECT * FROM history")
    else:
        c.execute("SELECT * FROM history WHERE role=?", (export_role,))
    rows = c.fetchall()
    if rows:
        df = pd.DataFrame(rows, columns=["Role", "Question", "Answer", "Feedback", "Timestamp"])
        scores = []
        for fb in df["Feedback"]:
            match = re.search(r"\b([1-9]|10)\b", fb)
            scores.append(int(match.group(1)) if match else None)
        df["Score"] = scores

        # --- Average score summary per role ---
        summary = df.groupby("Role")["Score"].mean().reset_index()
        summary["Question"] = "AVERAGE SCORE"
        summary["Answer"] = "-"
        summary["Feedback"] = "-"
        summary["Timestamp"] = "-"
        df = pd.concat([df, summary], ignore_index=True)

        # --- CSV download ---
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.sidebar.download_button("📥 Download Interview History", csv_data, "interview_history.csv", "text/csv")

        # --- Tabs for analytics ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Scores", "📈 Charts", "🔥 Heatmap", "🎯 Goals", "📅 Weekly Trends"])

        with tab1:
            st.subheader("Average Score per Role")
            st.bar_chart(summary.set_index("Role")["Score"])
            st.subheader("Leaderboard")
            leaderboard = summary[["Role", "Score"]].sort_values(by="Score", ascending=False)
            st.dataframe(leaderboard.style.background_gradient(cmap="Blues"))

            st.subheader("Progress Tracker")
            progress = df[df["Question"] != "AVERAGE SCORE"].groupby("Role")["Question"].count().reset_index()
            progress["Total Questions"] = progress["Role"].map(lambda r: len(questions[r]))
            progress["Completion %"] = (progress["Question"] / progress["Total Questions"]) * 100
            st.dataframe(progress[["Role", "Question", "Total Questions", "Completion %"]])

        with tab2:
            st.subheader("Scores Over Time")
            df_time = df[df["Timestamp"] != "-"].copy()
            df_time["Timestamp"] = pd.to_datetime(df_time["Timestamp"])
            st.line_chart(df_time.set_index("Timestamp")["Score"])
            st.subheader("Radar Chart")
            fig = px.line_polar(summary, r="Score", theta="Role", line_close=True, title="Skill Profile Across Roles")
            st.plotly_chart(fig)

        with tab3:
            st.subheader("Heatmap of Scores by Role & Question")
            heatmap = df.pivot_table(index="Question", columns="Role", values="Score", aggfunc="mean")
            st.dataframe(heatmap.style.background_gradient(cmap="RdYlGn", axis=None))

        with tab4:
            st.subheader("Goal Tracker")
            below_target_roles = []
            for _, row in summary.iterrows():
                if row["Question"] == "AVERAGE SCORE":
                    role_name, score = row["Role"], row["Score"]
                    st.write(f"{role_name}: {score:.2f}/10 (Target: {target})")
                    st.progress(min(score / target, 1.0))
                    if score < target:
                        below_target_roles.append(role_name)
            if below_target_roles:
                st.write("💡 Personalized Tips")
                for r in below_target_roles:
                    if r == "Software Engineer":
                        st.write("- Practice explaining algorithms clearly and mock coding problems.")
                    elif r == "Data Analyst":
                        st.write("- Strengthen SQL queries and handling missing data with real datasets.")
                    elif r == "Web Developer":
                        st.write("- Revise responsive design and optimize performance with Lighthouse.")
                    elif r == "AI Researcher":
                        st.write("- Read recent AI papers and articulate ethical concerns simply.")
            else:
                st.success("🎉 All roles are meeting/exceeding your target score!")

        with tab5:
            st.subheader("Weekly Improvement Tracker")
            df_time["Week"] = df_time["Timestamp"].dt.to_period("W").apply(lambda r: r.start_time)
            weekly_scores = df_time.groupby("Week")["Score"].mean().reset_index()
            st.line_chart(weekly_scores.set_index("Week")["Score"])

            st.subheader("Role-wise Weekly Tracker")
            weekly_role_scores = df_time.groupby(["Week", "Role"])["Score"].mean().reset_index()
            fig2 = px.line(weekly_role_scores, x="Week", y="Score", color="Role", markers=True,
                           title="Weekly Average Scores by Role")
            st.plotly_chart(fig2)

            st.subheader("Weekly Role Trends")
            for role_name in weekly_role_scores["Role"].unique():
                role_data = weekly_role_scores[weekly_role_scores["Role"] == role_name]
                if len(role_data) > 1:
                    if role_data["Score"].iloc[-1] > role_data["Score"].iloc[0]:
                        st.success(f"{role_name}: 📈 Improving compared to earlier weeks.")
                    elif role_data["Score"].iloc[-1] < role_data["Score"].iloc[0]:
                        st.warning(f"{role_name}: 📉 Scores dipped — focus on weak areas.")
                    else:
                        st.info(f"{role_name}: ➖ Steady performance — aim higher.")
    else:
        st.write("No data to export yet.")
