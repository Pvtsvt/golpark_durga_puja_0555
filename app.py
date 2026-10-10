import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Data Management Portal", layout="wide")

# 1. Google Sheets se data read karna
# ttl=0 lagane se har refresh par real-time fresh data aayega (caching band rahegi)
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl=0)

# 2. Allowed PINs (Streamlit secrets se aayenge)
allowed_pins = st.secrets.get("ADMIN_PINS", ["12345"])

# 3. Sidebar UI
st.sidebar.title("Access Control")
pin_input = st.sidebar.text_input("Enter Admin PIN", type="password")

# 4. View vs Edit Mode Logic
if pin_input in allowed_pins:
    st.sidebar.success("Admin Mode: Active")
    st.title("Data Records (Admin Edit Mode)")
    st.info("Niche table me double click karke edit karein, ya nayi row add karein.")
    
    # Dynamic editable table
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    
    # Save button
    if st.button("Save Changes to Google Sheet", type="primary"):
        with st.spinner("Saving data to cloud..."):
            conn.update(data=edited_df)
            st.success("Google Sheet successfully update ho gayi!")
            st.cache_data.clear()
            st.rerun()
else:
    if pin_input:
        st.sidebar.error("Galat PIN hai!")
    else:
        st.sidebar.info("Guest / View Only")
        
    st.title("Data Records (Read-Only)")
    # Viewers ke liye non-editable display
    st.dataframe(df, use_container_width=True)