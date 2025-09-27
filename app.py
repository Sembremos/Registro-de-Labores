# =========================
# RLD – 2025 (Versión 1.0) – APP PRINCIPAL (VIVIANA)
# =========================

import time
import hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

import streamlit as st
import pandas as pd

# Google Sheets
import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials

APP_TITLE = "REGISTRO DE LABORES DIARIAS (RLD) – 2025 (Versión 1.0)"
st.set_page_config(page_title="RLD 2025 – Viviana", layout="wide")

# ---------- helper de recarga (compatibilidad) ----------
def _rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# === URL del Spreadsheet ===
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1diLJ9ZuG1ZvBRICTQll1he3H1pnouikclGle2bKIk6E/edit?usp=sharing"

# ---------- Usuarios iniciales ----------
USUARIOS_INICIALES = [
    ("001", "Jeremy",  "jeremy",  "user"),
    ("002", "Jannia",  "jannia",  "user"),
    ("003", "Manfred", "manfred", "user"),
    ("004", "Luis",    "luis",    "user"),
    ("005", "Adrian",  "adrian",  "user"),
    ("006", "Esteban", "esteban", "user"),
    ("007", "Pamela",  "pamela",  "user"),
    ("008", "Carlos",  "carlos",  "user"),
    ("009", "Viviana Peraza", "vperaza", "admin"),
    ("010", "Charly",  "charly",  "user"),
]

# Contraseñas FIJAS (para entregar). Se guardan como HASH en la hoja.
PASSWORDS_FIJAS = {
    "jeremy":  "jeremy2025",
    "jannia":  "jannia2025",
    "manfred": "manfred2025",
    "luis":    "luis2025",
    "adrian":  "adrian2025",
    "esteban": "esteban2025",
    "pamela":  "pamela2025",
    "carlos":  "carlos2025",
    "charly":  "charly2025",
    "vperaza": "viviana2025",  # Admin
}

# ---------- Nombres de pestañas en Sheets ----------
SHEET_USUARIOS   = "Usuarios"
SHEET_RESPUESTAS = "RLD_respuestas"   # respuestas/partes de guardia (con task_id)
SHEET_TAREAS     = "RLD_tareas"       # NUEVA: delegación de tareas
SHEET_RESUMEN    = "RLD_por_usuario"
SHEET_LOGS       = "Logs"

# ---------- Catálogo ----------
TRABAJOS_CATALOGO = [
    "Patrullaje Preventivo", "Atención de Incidencias", "Charlas Comunitarias",
    "Reunión Interinstitucional", "Operativo Focalizado", "Apoyo a Otras Unidades",
    "Control de Vías", "Tareas Administrativas"
]

# ========= Utilidades =========
def iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def password_fija_de(usuario: str) -> str:
    return PASSWORDS_FIJAS[usuario.strip().lower()]

# ========= Conexión Google Sheets =========
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Faltan credenciales en st.secrets['gcp_service_account'].")
        st.stop()

    info = dict(st.secrets["gcp_service_account"])
    if isinstance(info.get("private_key"), str):
        info["private_key"] = info["private_key"].replace("\\n", "\n").replace("\r\n", "\n")
    st.session_state["_svc_email"] = info.get("client_email", "desconocido")

    try:
        creds = Credentials.from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        return gspread.authorize(creds)
    except Exception:
        st.error("No se pudieron cargar las credenciales del Service Account.")
        st.stop()

@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    gc = get_gspread_client()
    key = SPREADSHEET_URL.split("/d/")[1].split("/")[0]
    try:
        return gc.open_by_key(key)
    except APIError:
        pass
    try:
        return gc.open_by_url(SPREADSHEET_URL)
    except Exception:
        svc = st.session_state.get("_svc_email", "(sin email)")
        st.error("No se pudo abrir el Spreadsheet.")
        st.markdown(
            f"- Comparte la hoja con **{svc}** como *Editor*.\n"
            f"- Confirma que la URL/KEY es correcta.\n"
            f"- Habilita **Google Sheets API** y **Google Drive API**."
        )
        st.stop()

def _ensure_ws(sh, title: str, header: List[str]):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=2000, cols=max(len(header), 12))
        ws.append_row(header)
    vals = ws.get_all_values()
    if not vals:
        ws.append_row(header)
    return ws

def _ws_usuarios():
    sh = get_spreadsheet()
    header = ["id", "nombre", "usuario", "rol", "password_hash", "activo", "creado_en", "ultimo_acceso"]
    return _ensure_ws(sh, SHEET_USUARIOS, header)

def _ws_respuestas():
    sh = get_spreadsheet()
    # NOTA: Se añadió task_id como segunda columna para enlazar con la tarea
    header = [
        "uuid", "task_id", "usuario_id", "usuario_nombre", "fecha", "hora",
        "trabajo_realizado", "localidad_delegacion", "funcionario_responsable",
        "observaciones", "estado_validacion", "observacion_admin",
        "creado_en", "editado_en", "creado_por", "editado_por"
    ]
    return _ensure_ws(sh, SHEET_RESPUESTAS, header)

def _ws_tareas():
    sh = get_spreadsheet()
    header = [
        "task_id", "titulo", "descripcion", "prioridad", "estado",
        "asignado_id", "asignado_nombre",
        "fecha_asignacion", "fecha_limite",
        "creado_por", "observ_admin", "ultima_actualizacion"
    ]
    return _ensure_ws(sh, SHEET_TAREAS, header)

def _ws_resumen():
    sh = get_spreadsheet()
    header = ["usuario_id", "usuario_nombre", "total", "pendientes", "validadas", "rechazadas", "ultima_actividad"]
    return _ensure_ws(sh, SHEET_RESUMEN, header)

def _ws_logs():
    sh = get_spreadsheet()
    header = ["evento", "quien", "detalle", "timestamp"]
    return _ensure_ws(sh, SHEET_LOGS, header)

# ========= Utilidades de datos =========
def df_usuarios() -> pd.DataFrame:
    ws = _ws_usuarios()
    recs = ws.get_all_records()
    df = pd.DataFrame(recs)
    if df.empty:
        df = pd.DataFrame(columns=["id","nombre","usuario","rol","password_hash","activo","creado_en","ultimo_acceso"])
    return df

def df_respuestas() -> pd.DataFrame:
    ws = _ws_respuestas()
    recs = ws.get_all_records()
    df = pd.DataFrame(recs)
    if df.empty:
        df = pd.DataFrame(columns=[
            "uuid","task_id","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado",
            "localidad_delegacion","funcionario_responsable","observaciones",
            "estado_validacion","observacion_admin","creado_en","editado_en",
            "creado_por","editado_por"
        ])
    return df

def df_tareas() -> pd.DataFrame:
    ws = _ws_tareas()
    recs = ws.get_all_records()
    df = pd.DataFrame(recs)
    if df.empty:
        df = pd.DataFrame(columns=[
            "task_id","titulo","descripcion","prioridad","estado",
            "asignado_id","asignado_nombre","fecha_asignacion","fecha_limite",
            "creado_por","observ_admin","ultima_actualizacion"
        ])
    return df

def write_log(evento: str, quien: str, detalle: str):
    _ws_logs().append_row([evento, quien, detalle, iso_now()])

# ========= Seed y Migración =========
def seed_usuarios_si_vacio() -> bool:
    ws = _ws_usuarios()
    recs = ws.get_all_records()
    if recs:
        return False
    for (id_, nombre, usuario, rol) in USUARIOS_INICIALES:
        pwd_fija = password_fija_de(usuario)
        ws.append_row([id_, nombre, usuario, rol, hash_password(pwd_fija), True, iso_now(), ""])
    write_log("seed_usuarios", "sistema", f"Sembró {len(USUARIOS_INICIALES)} usuarios con contraseñas fijas")
    return True

def migrate_passwords_a_fijas() -> int:
    ws = _ws_usuarios()
    recs = ws.get_all_records()
    if not recs:
        return 0
    actualizados = 0
    for i, r in enumerate(recs, start=2):
        usuario = str(r.get("usuario", "")).strip().lower()
        if usuario in PASSWORDS_FIJAS:
            hash_actual = str(r.get("password_hash", ""))
            hash_fijo = hash_password(PASSWORDS_FIJAS[usuario])
            if hash_actual != hash_fijo:
                ws.update_cell(i, 5, hash_fijo)
                actualizados += 1
    if actualizados:
        write_log("migracion_passwords", "sistema", f"Actualizó {actualizados} usuarios a contraseñas fijas")
    return actualizados

def set_ultimo_acceso(usuario_id: str):
    ws = _ws_usuarios()
    cell = ws.find(usuario_id)
    if cell:
        ws.update_cell(cell.row, 8, iso_now())

def actualizar_resumen():
    ws = _ws_resumen()
    df_u = df_usuarios()
    df_r = df_respuestas()

    ws.clear()
    ws.append_row(["usuario_id","usuario_nombre","total","pendientes","validadas","rechazadas","ultima_actividad"])
    if df_u.empty:
        return

    rows = []
    for _, u in df_u.iterrows():
        uid = str(u.get("id", ""))
        uname = str(u.get("nombre", ""))

        sub = df_r[df_r.get("usuario_id", "").astype(str) == uid] if not df_r.empty else pd.DataFrame()

        total = int(len(sub))
        pend = int((sub["estado_validacion"] == "Pendiente").sum()) if not sub.empty else 0
        vali = int((sub["estado_validacion"] == "Validada").sum())  if not sub.empty else 0
        rech = int((sub["estado_validacion"] == "Rechazada").sum()) if not sub.empty else 0

        if not sub.empty and sub["creado_en"].notna().any():
            try:
                ultima_val = pd.to_datetime(sub["creado_en"], errors="coerce").max()
                ultima = "" if pd.isna(ultima_val) else str(ultima_val)
            except Exception:
                ultima = ""
        else:
            ultima = ""
        rows.append([uid, uname, total, pend, vali, rech, ultima])

    if rows:
        safe_rows = [
            [str(r[0]), str(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5]), str(r[6])]
            for r in rows
        ]
        ws.append_rows(safe_rows)

# ========= Autenticación =========
def do_login():
    st.subheader("Ingreso (Solo Admin)")
    usuario = st.text_input("Usuario", placeholder="vperaza")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        dfu = df_usuarios()
        if dfu.empty:
            st.error("No hay usuarios cargados.")
            return
        row = dfu[dfu["usuario"].astype(str).str.lower() == usuario.strip().lower()]
        if row.empty:
            st.error("Usuario no encontrado o inactivo.")
            return
        row = row.iloc[0]
        if not bool(row.get("activo", True)):
            st.error("Usuario inactivo.")
            return
        if row["rol"] != "admin":
            st.error("Acceso restringido a administradores.")
            return
        if hash_password(pwd) != row["password_hash"]:
            st.error("Contraseña incorrecta.")
            return
        st.session_state["auth"] = {
            "id": str(row["id"]),
            "nombre": row["nombre"],
            "usuario": row["usuario"],
            "rol": row["rol"]
        }
        set_ultimo_acceso(str(row["id"]))
        write_log("login", row["usuario"], "Inicio de sesión (admin)")
        _rerun()

def logout_btn():
    with st.sidebar:
        st.caption(f"Conectada como **{st.session_state['auth']['nombre']}** ({st.session_state['auth']['rol']})")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("auth", None)
            _rerun()

# ========= UI comunes =========
def view_portada():
    st.title(APP_TITLE)
    st.info(
        "Esta app principal es de **Viviana** (admin). Desde aquí se **administran usuarios** y se **delegan tareas** "
        "a los funcionarios. Cada funcionario trabaja con su propia app (por nombre) para ver sus tareas y registrar labores."
    )
    st.divider()

# -------- Usuarios (Admin) --------
def view_admin_usuarios(usuario_ctx: Dict):
    dfu = df_usuarios()
    st.subheader("Usuarios")
    st.dataframe(dfu, use_container_width=True, hide_index=True)

    with st.expander("Ver credenciales iniciales (fijas)"):
        df_creds = pd.DataFrame(
            [{"nombre": n, "usuario": u, "password_inicial": PASSWORDS_FIJAS[u], "rol": r}
             for _, n, u, r in USUARIOS_INICIALES]
        )
        st.dataframe(df_creds, use_container_width=True, hide_index=True)

    uid = st.text_input("ID de usuario")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Reiniciar a contraseña fija", use_container_width=True, disabled=uid.strip()==""):
            reset_password_fija(uid, usuario_ctx)
    with c2:
        if st.button("Alternar activo/inactivo", use_container_width=True, disabled=uid.strip()==""):
            toggle_activo(uid, usuario_ctx)

def reset_password_fija(usuario_id: str, usuario_ctx: Dict):
    ws = _ws_usuarios()
    cell = ws.find(usuario_id)
    if not cell:
        st.error("No se encontró el ID.")
        return
    r = cell.row
    usuario = ws.cell(r, 3).value
    pwd = password_fija_de(usuario)
    ws.update_cell(r, 5, hash_password(pwd))
    write_log("reset_password_fija", usuario_ctx["usuario"], f"Reseteó {usuario} a su clave fija")
    st.success(f"Contraseña reiniciada a la fija de {usuario}: **{pwd}**")

def toggle_activo(usuario_id: str, usuario_ctx: Dict):
    ws = _ws_usuarios()
    cell = ws.find(usuario_id)
    if not cell:
        st.error("No se encontró el ID.")
        return
    r = cell.row
    val = str(ws.cell(r, 6).value).upper()
    nuevo = "FALSE" if val in ("TRUE","1") else "TRUE"
    ws.update_cell(r, 6, nuevo)
    write_log("toggle_activo", usuario_ctx["usuario"], f"ID {usuario_id} -> {nuevo}")
    st.success("Estado actualizado.")

# -------- Tareas (Admin) --------
def view_admin_tareas(usuario_ctx: Dict):
    st.subheader("Delegar Tareas")
    dfu = df_usuarios()
    dfu_activos = dfu[(dfu["rol"]=="user") & (dfu["activo"]==True)].copy()

    col = st.columns(2)
    with col[0]:
        titulo = st.text_input("Título de la tarea")
        descripcion = st.text_area("Descripción / Instrucciones")
        prioridad = st.selectbox("Prioridad", ["Alta","Media","Baja"], index=1)
    with col[1]:
        persona = st.selectbox("Asignar a", dfu_activos["nombre"].tolist() or ["(sin usuarios)"])
        fecha_lim = st.date_input("Fecha límite", value=date.today() + timedelta(days=3))

    if st.button("Crear y asignar tarea", type="primary", use_container_width=True, disabled=dfu_activos.empty or not titulo.strip()):
        ws = _ws_tareas()
        asig = dfu_activos[dfu_activos["nombre"]==persona].iloc[0]
        tid = f"T{int(time.time()*1000)}"
        ws.append_row([
            tid, titulo, descripcion, prioridad, "Nueva",
            str(asig["id"]), asig["nombre"],
            iso_now(), str(fecha_lim),
            usuario_ctx["usuario"], "", iso_now()
        ])
        write_log("crear_tarea", usuario_ctx["usuario"], f"{tid} -> {asig['nombre']}")
        st.success(f"Tarea {tid} creada para {asig['nombre']}.")

    st.markdown("---")
    st.markdown("### Listado / Gestión")
    dft = df_tareas()
    f1, f2, f3 = st.columns(3)
    with f1:
        f_estado = st.selectbox("Estado", ["(Todos)","Nueva","En Progreso","Completada","Rechazada"])
    with f2:
        f_usuario = st.selectbox("Asignado", ["(Todos)"] + dft.get("asignado_nombre", pd.Series(dtype=str)).dropna().unique().tolist())
    with f3:
        solo_vigentes = st.checkbox("Solo no vencidas", value=False)

    data = dft.copy()
    if f_estado != "(Todos)":
        data = data[data["estado"] == f_estado]
    if f_usuario != "(Todos)":
        data = data[data["asignado_nombre"] == f_usuario]
    if solo_vigentes and not data.empty:
        data = data[pd.to_datetime(data["fecha_limite"], errors="coerce") >= pd.Timestamp(date.today())]

    st.dataframe(data, use_container_width=True, hide_index=True)

    st.markdown("#### Cambiar estado / Observación")
    tid = st.text_input("ID de tarea (task_id)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Nueva", use_container_width=True, disabled=tid.strip()==""):
            _admin_cambiar_estado_tarea(tid, "Nueva", usuario_ctx)
    with c2:
        if st.button("En Progreso", use_container_width=True, disabled=tid.strip()==""):
            _admin_cambiar_estado_tarea(tid, "En Progreso", usuario_ctx)
    with c3:
        if st.button("Completada", use_container_width=True, disabled=tid.strip()==""):
            _admin_cambiar_estado_tarea(tid, "Completada", usuario_ctx)
    with c4:
        if st.button("Rechazada", use_container_width=True, disabled=tid.strip()==""):
            _admin_cambiar_estado_tarea(tid, "Rechazada", usuario_ctx)

    obs = st.text_area("Observación administrativa para la tarea")
    if st.button("Guardar observación", disabled=tid.strip()==""):
        _admin_guardar_observacion_tarea(tid, obs, usuario_ctx)

    st.markdown("#### Respuestas vinculadas a la tarea seleccionada")
    if tid.strip():
        dfr = df_respuestas()
        st.dataframe(dfr[dfr["task_id"] == tid], use_container_width=True, hide_index=True)

def _admin_cambiar_estado_tarea(tid: str, nuevo: str, usuario_ctx: Dict):
    ws = _ws_tareas()
    cell = ws.find(tid)
    if not cell:
        st.error("No se encontró la tarea.")
        return
    r = cell.row
    ws.update_cell(r, 5, nuevo)           # estado
    ws.update_cell(r, 12, iso_now())      # ultima_actualizacion
    write_log("tarea_estado", usuario_ctx["usuario"], f"{tid} -> {nuevo}")
    st.success("Estado actualizado.")

def _admin_guardar_observacion_tarea(tid: str, texto: str, usuario_ctx: Dict):
    ws = _ws_tareas()
    cell = ws.find(tid)
    if not cell:
        st.error("No se encontró la tarea.")
        return
    r = cell.row
    ws.update_cell(r, 11, texto)          # observ_admin
    ws.update_cell(r, 12, iso_now())
    write_log("tarea_obs_admin", usuario_ctx["usuario"], f"{tid}")
    st.success("Observación guardada.")

# -------- Resumen (Admin) --------
def view_admin_resumen():
    if st.button("Recalcular resumen"):
        actualizar_resumen()
        st.success("Resumen actualizado.")
    recs = _ws_resumen().get_all_records()
    st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)

# ========= Main =========
def main():
    seed_usuarios_si_vacio()
    migrados = migrate_passwords_a_fijas()
    if migrados:
        st.toast(f"Actualizados {migrados} usuarios a contraseñas fijas.", icon="✅")

    view_portada()

    if "auth" not in st.session_state:
        do_login()
        return

    logout_btn()
    user = st.session_state["auth"]  # Viviana (admin)

    vista = st.sidebar.radio("Secciones", ["Usuarios", "Tareas", "Resumen"])
    if vista == "Usuarios":
        view_admin_usuarios(user)
    elif vista == "Tareas":
        view_admin_tareas(user)
    else:
        view_admin_resumen()

if __name__ == "__main__":
    main()






