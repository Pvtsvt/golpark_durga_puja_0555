import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Golpark Durga Puja 2026", layout="wide")

# 1. Google Sheets se data read karna
# ttl=0 lagane se har refresh par real-time fresh data aayega (caching band rahegi)
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl=0)

# 2. Allowed PINs (Streamlit secrets se aayenge)
allowed_pins = [str(p) for p in st.secrets.get("ADMIN_PINS", ["12345"])]

# 3. Session state
st.session_state.setdefault("role", "User")
st.session_state.setdefault("admin_ok", False)
st.session_state.setdefault("selected_row", None)
st.session_state.setdefault("pin_error", False)


def cancel_admin():
    st.session_state.role = "User"
    st.session_state.admin_ok = False
    st.session_state.pin_error = False
    st.session_state.pin_input = ""


def normalize(series):
    # spaces hata do aur uppercase kar do -> "c1 3" == "C13"
    return series.astype(str).str.replace(r"\s+", "", regex=True).str.upper()


# 4. Sidebar: User / Admin toggle
st.sidebar.title("Access Control")
st.sidebar.radio("Mode", ["User", "Admin"], key="role", horizontal=True)

if st.session_state.role == "User":
    st.session_state.admin_ok = False
    st.sidebar.info("User Mode: View Only")
elif st.session_state.admin_ok:
    st.sidebar.success("Admin Mode: Active")
else:
    st.sidebar.text_input("Enter Admin PIN", type="password", key="pin_input")
    ok_col, cancel_col = st.sidebar.columns(2)
    if ok_col.button("OK", type="primary", use_container_width=True):
        if st.session_state.pin_input in allowed_pins:
            st.session_state.admin_ok = True
            st.session_state.pin_error = False
            st.rerun()
        else:
            st.session_state.pin_error = True
    cancel_col.button("Cancel", on_click=cancel_admin, use_container_width=True)
    if st.session_state.pin_error:
        st.sidebar.error("Galat PIN hai!")

is_admin = st.session_state.role == "Admin" and st.session_state.admin_ok

# 5. Header
st.title("Golpark Durga Puja 2026")

# 6. Search bar (Quarter number: C1, D21, ...)

# Bade font / bada search box, taaki elderly users ko aasani ho
st.markdown(
    """
    <style>
    div[data-testid="stTextInput"] input { font-size: 1.4rem; padding: 0.7rem; }
    div[data-testid="stTextInput"] label p { font-size: 1.2rem; font-weight: 600; }
    div[data-testid="stButton"] button { font-size: 1.1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# "Q.No." column dhundo (spelling/spaces thode alag ho to bhi chale)
qno_col = next(
    (c for c in df.columns if "".join(ch for ch in str(c).lower() if ch.isalnum()) == "qno"),
    None,
)


def show_results(q, columns, key_prefix):
    """Prefix match karke result buttons dikhao; click par row select ho jati hai."""
    norm_df = df[columns].apply(normalize)
    matches = df[norm_df.apply(lambda col: col.str.startswith(q)).any(axis=1)]
    if matches.empty:
        st.warning("Koi result nahi mila.")
        return
    st.caption(f"{len(matches)} result mile - row kholne ke liye click karein")
    max_show = 40
    cols = st.columns(8)
    for i, idx in enumerate(matches.index[:max_show]):
        # jis cell se match hua uski value button par dikhao
        hit = next(c for c in columns if norm_df.at[idx, c].startswith(q))
        label = str(df.at[idx, hit]).strip()
        if cols[i % 8].button(label, key=f"{key_prefix}_{idx}", use_container_width=True):
            st.session_state.selected_row = idx
    if len(matches) > max_show:
        st.caption(f"Sirf pehle {max_show} dikhaye gaye, search aur specific karein.")


# Main search: sirf Q.No. column me
q_qno = ""
if qno_col is not None:
    query = st.text_input(
        "Apna Quarter Number likhiye",
        placeholder="jaise C1, D2, D21",
        key="search_qno",
    )
    q_qno = "".join(query.split()).upper()
    if q_qno:
        show_results(q_qno, [qno_col], "qno")
else:
    st.warning("Sheet me 'Q.No.' column nahi mila.")

# Alag se: poori sheet me search (naam, phone, etc.)
with st.expander("Dusre details se search karein (poori sheet me)"):
    query_all = st.text_input(
        "Kuch bhi likhiye",
        placeholder="naam, number, ...",
        key="search_all",
    )
    q_all = "".join(query_all.split()).upper()
    if q_all:
        show_results(q_all, list(df.columns), "all")

if not q_qno and not q_all:
    st.session_state.selected_row = None

selected = st.session_state.selected_row
if selected is not None and selected not in df.index:
    selected = st.session_state.selected_row = None


def clear_selection():
    st.session_state.selected_row = None


# 7. View vs Edit Mode
if is_admin:
    st.info("Niche table me double click karke edit karein, ya nayi row add karein.")

    if selected is not None:
        st.subheader("Selected Row")
        st.button("Show all rows", on_click=clear_selection)
        edited_row = st.data_editor(
            df.loc[[selected]],
            hide_index=True,
            use_container_width=True,
            key=f"edit_row_{selected}",
        )
        if st.button("Save Changes to Google Sheet", type="primary"):
            with st.spinner("Saving data to cloud..."):
                updated = df.copy()
                updated.loc[selected] = edited_row.iloc[0]
                conn.update(data=updated)
                st.success("Google Sheet successfully update ho gayi!")
                st.cache_data.clear()
                st.rerun()
    else:
        edited_df = st.data_editor(
            df, num_rows="dynamic", hide_index=True, use_container_width=True
        )
        if st.button("Save Changes to Google Sheet", type="primary"):
            with st.spinner("Saving data to cloud..."):
                conn.update(data=edited_df)
                st.success("Google Sheet successfully update ho gayi!")
                st.cache_data.clear()
                st.rerun()
else:
    if selected is not None:
        st.subheader("Selected Row")
        st.dataframe(df.loc[[selected]], hide_index=True, use_container_width=True)
        st.button("Show all rows", on_click=clear_selection)
        st.subheader("All Records")
        highlighted = df.style.apply(
            lambda row: [
                "background-color: #ffe08a; color: black" if row.name == selected else ""
                for _ in row
            ],
            axis=1,
        )
        st.dataframe(highlighted, hide_index=True, use_container_width=True)
    else:
        st.dataframe(df, hide_index=True, use_container_width=True)
