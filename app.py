import streamlit as st

st.set_page_config(page_title="NBA Analytics", layout="wide")

st.markdown(
    """<style>
    .block-container{padding:0.5rem 0.4rem 0 0.4rem !important; max-width:100% !important;}
    iframe[title="streamlit_components.html"]{width:100% !important; min-width:100% !important;}
    </style>""",
    unsafe_allow_html=True,
)

pages = [
    st.Page("pages/Box_Scores.py", title="Box Scores"),
    st.Page("pages/Team_Rotation.py", title="Team Rotation"),
    st.Page("pages/Shooting_Breakdown.py", title="Shooting Breakdown"),
]

pg = st.navigation(pages)
pg.run()
