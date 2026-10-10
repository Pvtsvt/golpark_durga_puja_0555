import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
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
st.session_state.setdefault("close_sidebar", False)

# "Done" dabane par mode User banana hai (radio banne se pehle hi set karna padta hai)
if st.session_state.pop("go_user", False):
    st.session_state.role = "User"
    st.session_state.admin_ok = False


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
            st.session_state.close_sidebar = True
            st.rerun()
        else:
            st.session_state.pin_error = True
    cancel_col.button("Cancel", on_click=cancel_admin, use_container_width=True)
    if st.session_state.pin_error:
        st.sidebar.error("Galat PIN hai!")

is_admin = st.session_state.role == "Admin" and st.session_state.admin_ok

# Background: Maa Durga ki halki (transparent) photo, data ke peeche
@st.cache_resource
def background_css():
    img = Path(__file__).parent / "MaaDurga2026.jpeg"
    if not img.exists():
        return ""
    b64 = base64.b64encode(img.read_bytes()).decode()
    # Photo ke upar safed/kaala parda (overlay) - isse photo halki dikhti hai, data saaf
    return (
        "<style>"
        ".stApp{background-image:linear-gradient(rgba(255,255,255,0.62),rgba(255,255,255,0.62)),"
        f"url('data:image/jpeg;base64,{b64}');"
        "background-size:cover;background-position:center top;background-repeat:no-repeat;}"
        "@media (prefers-color-scheme: dark){"
        ".stApp{background-image:linear-gradient(rgba(14,17,23,0.88),rgba(14,17,23,0.88)),"
        f"url('data:image/jpeg;base64,{b64}');}}"
        "}"
        "</style>"
    )


st.markdown(background_css(), unsafe_allow_html=True)

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
def apply_filter(data, query):
    """(filtered_df, is_filtered) wapas karta hai."""
    query = "".join((query or "").split()).upper()
    if query and qno_col is not None and qno_col in data.columns:
        return data[normalize(data[qno_col]).str.startswith(query)], True
    return data, False


def show_summary(filtered, is_filtered):
    if is_filtered:
        st.caption(f"{len(filtered)} row mili")
        if filtered.empty:
            st.warning("Koi result nahi mila.")


filtered, is_filtered = apply_filter(df, q)

# 8. View vs Edit Mode (dono me same search/filter)
if is_admin:
    show_summary(filtered, is_filtered)
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
            c_save, c_cancel, c_done = st.columns(3)
            save = c_save.button(
                "Save", type="primary", key=f"save_{suffix}", use_container_width=True
            )
            cancel = c_cancel.button("Cancel", key=f"cancel_{suffix}", use_container_width=True)
            done = c_done.button("Done", key=f"done_{suffix}", use_container_width=True)
        return save, cancel, done

    def save_to_sheet():
        with st.spinner("Saving data to cloud..."):
            if is_filtered:
                updated = df.copy()
                updated.loc[edited.index] = edited
            else:
                updated = edited
            conn.update(data=updated)
            st.cache_data.clear()
            st.session_state.editor_ver += 1

    save_top, cancel_top, done_top = action_buttons(top_bar, "top")
    save_bottom, cancel_bottom, done_bottom = action_buttons(bottom_bar, "bottom")

    if cancel_top or cancel_bottom:
        # Sheet me jo already saved hai wo touch nahi hota, bas unsaved edits hat jaate hain
        st.session_state.editor_ver += 1
        st.rerun()

    if done_top or done_bottom:
        # Save + User mode me wapas
        save_to_sheet()
        st.session_state.go_user = True
        st.toast("Saved! User mode me wapas aa gaye.")
        st.rerun()

    if save_top or save_bottom:
        save_to_sheet()
        st.toast("Google Sheet successfully update ho gayi!")
        st.rerun()
else:
    # User mode: har 5 minute me sheet se naya data apne aap aa jata hai
    @st.fragment(run_every=300)
    def live_table():
        fresh = conn.read(ttl=0)
        view, filt = apply_filter(fresh, st.session_state.get("search_qno", ""))
        show_summary(view, filt)
        st.dataframe(view, hide_index=True, use_container_width=True)

    live_table()

# PIN OK ke baad sidebar band karna (mobile par sidebar poori screen gher leta hai)
if st.session_state.pop("close_sidebar", False):
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const btn = doc.querySelector('[data-testid="stSidebarCollapseButton"] button')
                 || doc.querySelector('button[kind="header"]');
        if (btn) btn.click();
        </script>
        """,
        height=0,
    )
