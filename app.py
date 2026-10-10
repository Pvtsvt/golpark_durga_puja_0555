import base64
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from st_keyup import st_keyup
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Golpark Durga Puja 2026", layout="wide")

# --- Column helpers: Status / 2025 / 2026 / Date ---
STATUS_OPTIONS = ["Pending", "Paid"]
DATE_FMT = "%d/%m/%Y"


def find_col(data, pred):
    for c in data.columns:
        if pred(str(c).strip().lower()):
            return c
    return None


def special_cols(data):
    return {
        "status": find_col(data, lambda n: n == "status"),
        "y2025": find_col(data, lambda n: n == "2025"),
        "y2026": find_col(data, lambda n: n == "2026"),
        "date": find_col(data, lambda n: n == "date" or n.endswith(" date") or n.startswith("date ")),
    }


def _num_text(v):
    if pd.isna(v):
        return None
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip() or None


def prep(data):
    """Sheet ke data ko editor ke layak banao (Status/2026/Date ke types)."""
    data = data.copy()
    c = special_cols(data)
    if c["status"] is not None:
        # sirf Pending / Paid; baaki kuch ho to khaali dikhega
        norm = data[c["status"]].astype(str).str.strip().str.capitalize()
        data[c["status"]] = norm.where(norm.isin(STATUS_OPTIONS), None).astype("object")
    if c["y2026"] is not None:
        data[c["y2026"]] = data[c["y2026"]].map(_num_text).astype("object")
    if c["date"] is not None:
        col = data[c["date"]]
        parsed = pd.to_datetime(col, dayfirst=True, errors="coerce")
        # sirf tab convert karo jab saari bhari hui dates sahi parse hui ho (data loss se bachne ke liye)
        if parsed.notna().sum() == col.notna().sum():
            data[c["date"]] = parsed.dt.date.where(parsed.notna(), None).astype("object")
    return data


def to_sheet(data):
    """Editor ke data ko Sheet me likhne layak banao."""
    data = data.copy()
    c = special_cols(data)
    if c["date"] is not None:
        data[c["date"]] = data[c["date"]].map(
            lambda v: v.strftime(DATE_FMT) if hasattr(v, "strftime") and not pd.isna(v) else v
        )
    return data


def editor_config(data):
    c = special_cols(data)
    cfg = {}
    if c["status"] is not None:
        cfg[c["status"]] = st.column_config.SelectboxColumn(
            "Status", options=STATUS_OPTIONS, required=False
        )
    if c["y2025"] is not None:
        cfg[c["y2025"]] = st.column_config.Column(disabled=True)
    if c["y2026"] is not None:
        # sirf digits aur comma (jaise 500 ya 1,500)
        cfg[c["y2026"]] = st.column_config.TextColumn(
            str(c["y2026"]),
            validate=r"^[0-9]+(,[0-9]+)*$",
            help="Sirf number ya comma",
        )
    if c["date"] is not None and data[c["date"]].map(lambda v: hasattr(v, "strftime")).any():
        cfg[c["date"]] = st.column_config.DateColumn(str(c["date"]), format="DD/MM/YYYY")
    return cfg


# 1. Google Sheets se data read karna
# ttl=0 lagane se har refresh par real-time fresh data aayega (caching band rahegi)
conn = st.connection("gsheets", type=GSheetsConnection)
df = prep(conn.read(ttl=0))

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
        ".stApp{background-image:linear-gradient(rgba(255,255,255,0.7),rgba(255,255,255,0.7)),"
        f"url('data:image/jpeg;base64,{b64}');"
        "background-size:cover;background-position:center top;background-repeat:no-repeat;}"
        "@media (prefers-color-scheme: dark){"
        ".stApp{background-image:linear-gradient(rgba(14,17,23,0.7),rgba(14,17,23,0.7)),"
        f"url('data:image/jpeg;base64,{b64}');}}"
        "}"
        "</style>"
    )


st.markdown(background_css(), unsafe_allow_html=True)

# 5. Header
st.title("Golpark Durga Puja 2026")

# Save / Cancel / Done ke baad ka message (rerun ke baad bhi dikhe)
_flash = st.session_state.pop("flash", None)
if _flash:
    st.success(_flash)

# Bade font / bada search box (elderly users ke liye) aur mobile par label + box ek hi line me
st.markdown(
    """
    <style>
    div[data-testid="stTextInput"] input,
    div[data-testid="stCustomComponentV1"] { font-size: 1.4rem; }
    div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center; }
    div[data-testid="stHorizontalBlock"] > div { min-width: 0 !important; }
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] { opacity: 0.7; }
    /* label aur search box ek hi line me, upar se barabar */
    .qno-label { font-size: 1.6rem; font-weight: 800; margin: 0 !important; padding: 0;
                 white-space: nowrap; height: 2.9rem; line-height: 2.9rem; color: #000; }
    div[data-testid="stHorizontalBlock"]:has(.qno-label) { gap: 0.4rem; align-items: flex-start; }
    div[data-testid="stHorizontalBlock"]:has(.qno-label) > div:first-child {
        flex: 0 0 auto !important; width: auto !important; min-width: max-content !important; }
    div[data-testid="stHorizontalBlock"]:has(.qno-label) > div:last-child {
        flex: 1 1 0 !important; width: auto !important; }
    div[data-testid="stHorizontalBlock"]:has(.qno-label) [data-testid="stMarkdownContainer"] p {
        margin: 0 !important; }
    .stApp h1 { font-weight: 900 !important; color: #000 !important; }
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
label_col, input_col = st.columns([1, 3])
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
        column_config=editor_config(filtered),
        column_order=list(df.columns),  # sheet wala order hi rahe
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
            conn.update(data=to_sheet(updated))
            st.cache_data.clear()
            st.session_state.editor_ver += 1

    save_top, cancel_top, done_top = action_buttons(top_bar, "top")
    save_bottom, cancel_bottom, done_bottom = action_buttons(bottom_bar, "bottom")

    if cancel_top or cancel_bottom:
        # Sheet me jo already saved hai wo touch nahi hota, bas unsaved edits hat jaate hain
        st.session_state.editor_ver += 1
        st.session_state.flash = "Cancelled!"
        st.rerun()

    if done_top or done_bottom:
        # Save + User mode me wapas
        save_to_sheet()
        st.session_state.go_user = True
        st.session_state.flash = "Saved! Back to User mode"
        st.rerun()

    if save_top or save_bottom:
        save_to_sheet()
        st.session_state.flash = "Data Saved!"
        st.rerun()
else:
    # User mode: har 5 minute me sheet se naya data apne aap aa jata hai
    @st.fragment(run_every=300)
    def live_table():
        fresh = prep(conn.read(ttl=0))
        view, filt = apply_filter(fresh, st.session_state.get("search_qno", ""))
        show_summary(view, filt)
        st.dataframe(
            view,
            hide_index=True,
            use_container_width=True,
            column_order=list(fresh.columns),  # sheet wala order hi rahe
            column_config={
                k: v for k, v in editor_config(view).items() if k == special_cols(view)["date"]
            },
        )

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
