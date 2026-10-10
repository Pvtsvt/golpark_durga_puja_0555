import streamlit as st
from st_keyup import st_keyup
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

# Bade font / bada search box (elderly users ke liye) aur mobile par label + box ek hi line me
st.markdown(
    """
    <style>
    div[data-testid="stTextInput"] input,
    div[data-testid="stCustomComponentV1"] { font-size: 1.4rem; }
    div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center; }
    div[data-testid="stHorizontalBlock"] > div { min-width: 0 !important; }
    .qno-label { font-size: 1.3rem; font-weight: 700; margin: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# "Q.No." column dhundo (spelling/spaces thode alag ho to bhi chale)
qno_col = next(
    (c for c in df.columns if "".join(ch for ch in str(c).lower() if ch.isalnum()) == "qno"),
    None,
)

# 6. Search bar: type karte hi live filter (Enter ki zaroorat nahi)
label_col, input_col = st.columns([1, 2])
label_col.markdown('<p class="qno-label">Quarter No:</p>', unsafe_allow_html=True)
with input_col:
    typed = st_keyup(
        "Quarter No",
        placeholder="jaise C1, D2, D21",
        key="search_qno",
        label_visibility="collapsed",
    )
q = "".join((typed or "").split()).upper()

if qno_col is None:
    st.warning("Sheet me 'Q.No.' column nahi mila.")

# 7. Filter: Q.No. prefix match (C2 -> C2, C21, C22 ... ; C23 -> sirf C23)
mask = None
if q and qno_col is not None:
    mask = normalize(df[qno_col]).str.startswith(q)

filtered = df if mask is None else df[mask]
is_filtered = mask is not None

if is_filtered:
    st.caption(f"{len(filtered)} row mili")
    if filtered.empty:
        st.warning("Koi result nahi mila.")

# 8. View vs Edit Mode (dono me same search/filter)
if is_admin:
    st.session_state.setdefault("editor_ver", 0)
    top_bar = st.container()
    edited = st.data_editor(
        filtered,
        num_rows="fixed" if is_filtered else "dynamic",
        hide_index=True,
        use_container_width=True,
        # key badalne se editor reset hota hai -> sirf unsaved edits hatte hain
        key=f"editor_{q}_{st.session_state.editor_ver}",
    )
    bottom_bar = st.container()

    def action_buttons(where, suffix):
        with where:
            save_col, cancel_col, _ = st.columns([1, 1, 2])
            save = save_col.button(
                "Save Change", type="primary", key=f"save_{suffix}", use_container_width=True
            )
            cancel = cancel_col.button(
                "Cancel Changes", key=f"cancel_{suffix}", use_container_width=True
            )
        return save, cancel

    save_top, cancel_top = action_buttons(top_bar, "top")
    save_bottom, cancel_bottom = action_buttons(bottom_bar, "bottom")

    if cancel_top or cancel_bottom:
        # Sheet me jo already saved hai wo touch nahi hota, bas unsaved edits hat jaate hain
        st.session_state.editor_ver += 1
        st.rerun()

    if save_top or save_bottom:
        with st.spinner("Saving data to cloud..."):
            if is_filtered:
                updated = df.copy()
                updated.loc[edited.index] = edited
            else:
                updated = edited
            conn.update(data=updated)
            st.cache_data.clear()
            st.session_state.editor_ver += 1
            st.toast("Google Sheet successfully update ho gayi!")
            st.rerun()
else:
    st.dataframe(filtered, hide_index=True, use_container_width=True)
