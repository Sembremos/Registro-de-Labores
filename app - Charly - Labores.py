# =========================
# RLD – 2025 – App de Usuario (Charly)
# =========================

import time
import hashlib
from datetime import datetime, date
from typing import List, Dict

import streamlit as st
import pandas as pd

import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials

APP_TITLE = "RLD – Charly (Usuario)"
st.set_page_config(page_title="RLD – Charly", layout="wide")

# --- Config común ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1diLJ9ZuG1ZvBRICTQll1he3H1pnouikclGle2bKIk6E/edit?usp=sharing"
SHEET_USUARIOS   = "Usuarios"
SHEET_RESPUESTAS = "RLD_respuestas"
SHEET_TAREAS     = "RLD_tareas"
SHEET_LOGS       = "Logs"

TRABAJOS_CATALOGO = [
    "Patrullaje Preventivo", "Atención de Incidencias", "Charlas Comunitarias",
    "Reunión Interinstitucional", "Operativo Focalizado", "Apoyo a Otras Unidades",
    "Control de Vías", "Tareas Administrativas"
]

# --- helpers ---
def _rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

# --- conexión ---
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Faltan credenciales en st.secrets['gcp_service_account'].")
        st.stop()
    info = dict(st.secrets["gcp_service_account"])
    if isinstance(info.get("private_key"), str):
        info["private_key"] = info["private_key"].replace("\\n","\n").replace("\r\n","\n")
    st.session_state["_svc_email"] = info.get("client_email","desconocido")
    creds = Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    gc = get_gspread_client()
    key = SPREADSHEET_URL.split("/d/")[1].split("/")[0]
    try:
        return gc.open_by_key(key)
    except APIError:
        return gc.open_by_url(SPREADSHEET_URL)

def _ws(title: str, header: List[str]):
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=2000, cols=max(len(header), 12))
        ws.append_row(header)
    vals = ws.get_all_values()
    if not vals:
        ws.append_row(header)
    return ws

def ws_usuarios():   return _ws(SHEET_USUARIOS, ["id","nombre","usuario","rol","password_hash","activo","creado_en","ultimo_acceso"])
def ws_respuestas(): return _ws(SHEET_RESPUESTAS, [
    "uuid","task_id","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado",
    "localidad_delegacion","funcionario_responsable","observaciones","estado_validacion",
    "observacion_admin","creado_en","editado_en","creado_por","editado_por"
])
def ws_tareas():     return _ws(SHEET_TAREAS, [
    "task_id","titulo","descripcion","prioridad","estado","asignado_id","asignado_nombre",
    "fecha_asignacion","fecha_limite","creado_por","observ_admin","ultima_actualizacion"
])
def ws_logs():       return _ws(SHEET_LOGS, ["evento","quien","detalle","timestamp"])

# --- dataframes ---
def df_usuarios() -> pd.DataFrame:
    recs = ws_usuarios().get_all_records()
    df = pd.DataFrame(recs)
    if df.empty:
        df = pd.DataFrame(columns=["id","nombre","usuario","rol","password_hash","activo","creado_en","ultimo_acceso"])
    return df

def df_tareas() -> pd.DataFrame:
    recs = ws_tareas().get_all_records()
    df = pd.DataFrame(recs)
    if df.empty:
        df = pd.DataFrame(columns=[
            "task_id","titulo","descripcion","prioridad","estado","asignado_id","asignado_nombre",
            "fecha_asignacion","fecha_limite","creado_por","observ_admin","ultima_actualizacion"
        ])
    return df

def df_respuestas() -> pd.DataFrame:
    recs = ws_respuestas().get_all_records()
    df = pd.DataFrame(recs)
    if df.empty:
        df = pd.DataFrame(columns=[
            "uuid","task_id","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado",
            "localidad_delegacion","funcionario_responsable","observaciones","estado_validacion",
            "observacion_admin","creado_en","editado_en","creado_por","editado_por"
        ])
    return df

def log(evento: str, quien: str, detalle: str):
    ws_logs().append_row([evento, quien, detalle, iso_now()])

# --- auth (centrado en Charly, pero valida contra hoja) ---
def do_login():
    st.subheader("Ingreso – Charly")
    st.caption("Usuario sugerido: **charly** (contraseña inicial: **charly2025**) – luego puedes cambiarla desde tu app.")
    usuario = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")

    if st.button("Entrar", use_container_width=True):
        dfu = df_usuarios()
        if dfu.empty:
            st.error("No hay usuarios cargados aún.")
            return
        row = dfu[dfu["usuario"].astype(str).str.lower() == usuario.strip().lower()]
        if row.empty:
            st.error("Usuario no encontrado o inactivo.")
            return
        row = row.iloc[0]
        if not bool(row.get("activo", True)):
            st.error("Usuario inactivo.")
            return
        if row["rol"] != "user":
            st.error("Esta app es solo para usuarios tipo 'user'.")
            return
        # Opcional: bloquear a otro usuario distinto de Charly en esta app
        if str(row["usuario"]).strip().lower() != "charly":
            st.error("Esta app está configurada para **Charly**.")
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
        # marcar último acceso
        try:
            w = ws_usuarios()
            cell = w.find(str(row["id"]))
            if cell:
                w.update_cell(cell.row, 8, iso_now())
        except Exception:
            pass

        log("login_user", row["usuario"], "Ingreso a su app")
        _rerun()

def logout_btn():
    with st.sidebar:
        st.caption(f"Conectado como **{st.session_state['auth']['nombre']}**")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("auth", None)
            _rerun()

# --- vistas ---
def portada():
    st.title(APP_TITLE)
    st.info("Aquí Charly ve **sus tareas** asignadas por Viviana y registra las **labores** de cada guardia. "
            "Sólo puede editar/eliminar sus propios registros mientras no hayan sido validados/rechazados.")

def view_tareas(user: Dict):
    st.subheader("Mis Tareas")
    dft = df_tareas()
    mias = dft[dft["asignado_id"].astype(str) == str(user["id"])].copy()

    c1, c2 = st.columns(2)
    with c1:
        estado = st.selectbox("Estado", ["(Todos)","Nueva","En Progreso","Completada","Rechazada"])
    with c2:
        prioridad = st.selectbox("Prioridad", ["(Todas)","Alta","Media","Baja"])

    if estado != "(Todos)":
        mias = mias[mias["estado"] == estado]
    if prioridad != "(Todas)":
        mias = mias[mias["prioridad"] == prioridad]

    st.dataframe(mias, use_container_width=True, hide_index=True)

    st.markdown("### Cambiar estado de una tarea mía")
    tid = st.text_input("ID de tarea (task_id)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Nueva", use_container_width=True, disabled=tid.strip()==""):
            _user_cambiar_estado_tarea(tid, "Nueva", user)
    with c2:
        if st.button("En Progreso", use_container_width=True, disabled=tid.strip()==""):
            _user_cambiar_estado_tarea(tid, "En Progreso", user)
    with c3:
        if st.button("Completada", use_container_width=True, disabled=tid.strip()==""):
            _user_cambiar_estado_tarea(tid, "Completada", user)
    with c4:
        if st.button("Rechazada", use_container_width=True, disabled=tid.strip()==""):
            _user_cambiar_estado_tarea(tid, "Rechazada", user)

def _user_cambiar_estado_tarea(tid: str, nuevo: str, user: Dict):
    w = ws_tareas()
    cell = w.find(tid)
    if not cell:
        st.error("No se encontró la tarea.")
        return
    row = cell.row
    asignado_id = str(w.cell(row, 6).value)
    if asignado_id != str(user["id"]):
        st.error("No puedes modificar tareas asignadas a otra persona.")
        return
    w.update_cell(row, 5, nuevo)      # estado
    w.update_cell(row, 12, iso_now()) # última actualización
    log("user_tarea_estado", user["usuario"], f"{tid} -> {nuevo}")
    st.success("Estado actualizado.")

def view_registro(user: Dict):
    st.subheader("Registrar Labor y Vincular a Tarea")
    dft = df_tareas()
    mias = dft[dft["asignado_id"].astype(str) == str(user["id"])]

    tid = st.selectbox("Tarea relacionada (opcional)", ["(sin tarea)"] + mias["task_id"].tolist())
    col1, col2 = st.columns(2)
    with col1:
        f_fecha = st.date_input("Fecha", value=date.today())
    with col2:
        f_hora = st.time_input("Hora", value=datetime.now().time())

    trabajo = st.selectbox("Trabajo Realizado", TRABAJOS_CATALOGO)
    localidad = st.text_input("Localidad / Delegación")
    obs = st.text_area("Observaciones", help="Detalle las actividades realizadas por guardia.")

    if st.button("Guardar", type="primary", use_container_width=True):
        w = ws_respuestas()
        uid = f"rld-{int(time.time()*1000)}"
        w.append_row([
            uid,
            (tid if tid != "(sin tarea)" else ""),
            user["id"], user["nombre"],
            str(f_fecha), str(f_hora),
            trabajo, localidad, user["nombre"],
            obs, "Pendiente", "",
            iso_now(), "", user["usuario"], ""
        ])
        log("crear_respuesta", user["usuario"], f"{uid} (task:{tid})")
        st.success("Registro guardado.")
        _rerun()

def view_mis_labores(user: Dict):
    st.subheader("Mis Labores")
    dfr = df_respuestas()
    mine = dfr[dfr["usuario_id"].astype(str) == str(user["id"])].copy()

    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        f_ini = st.date_input("Desde", value=None)
    with colf2:
        f_fin = st.date_input("Hasta", value=None)
    with colf3:
        estado = st.selectbox("Estado", ["(Todos)","Pendiente","Validada","Rechazada"])

    if not mine.empty:
        mine["fecha_dt"] = pd.to_datetime(mine["fecha"], errors="coerce")
        if f_ini:
            mine = mine[mine["fecha_dt"] >= pd.to_datetime(f_ini)]
        if f_fin:
            mine = mine[mine["fecha_dt"] <= pd.to_datetime(f_fin)]
        if estado != "(Todos)":
            mine = mine[mine["estado_validacion"] == estado]
        mine = mine.drop(columns=["fecha_dt"], errors="ignore")

    st.dataframe(mine, use_container_width=True, hide_index=True)

    st.markdown("### Editar / Eliminar")
    uid = st.text_input("ID (uuid) de la fila a modificar/eliminar")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Editar seleccionado", use_container_width=True, disabled=mine.empty or uid.strip()==""):
            editar_fila(uid, user)
    with c2:
        if st.button("Eliminar seleccionado", use_container_width=True, disabled=mine.empty or uid.strip()==""):
            eliminar_fila(uid, user)

def editar_fila(uid: str, user: Dict):
    dfr = df_respuestas()
    row = dfr[dfr["uuid"] == uid]
    if row.empty:
        st.error("No se encontró el registro.")
        return
    row = row.iloc[0]
    if str(row["usuario_id"]) != str(user["id"]):
        st.error("No puede editar registros de otros usuarios.")
        return
    if row["estado_validacion"] in ("Validada","Rechazada"):
        st.warning("No puede editar registros ya validados/rechazados.")
        return

    st.info(f"Editando registro: {uid}")
    col1, col2 = st.columns(2)
    with col1:
        f_fecha = st.date_input("Fecha", value=pd.to_datetime(row["fecha"]).date() if row["fecha"] else date.today())
    with col2:
        try:
            h = pd.to_datetime(row["hora"]).time() if row["hora"] else datetime.now().time()
        except Exception:
            h = datetime.now().time()
        f_hora = st.time_input("Hora", value=h)

    trabajo = st.selectbox(
        "Trabajo Realizado",
        TRABAJOS_CATALOGO,
        index=max(0, TRABAJOS_CATALOGO.index(row["trabajo_realizado"])) if row["trabajo_realizado"] in TRABAJOS_CATALOGO else 0
    )
    localidad = st.text_input("Localidad / Delegación", value=str(row["localidad_delegacion"]))
    obs = st.text_area("Observaciones", value=str(row["observaciones"]))

    # permitir re-vincular a una tarea propia
    dft = df_tareas()
    mias = dft[dft["asignado_id"].astype(str) == str(user["id"])]
    tid_actual = str(row.get("task_id","") or "")
    opciones = ["(sin tarea)"] + mias["task_id"].tolist()
    try:
        idx = opciones.index(tid_actual if tid_actual else "(sin tarea)")
    except Exception:
        idx = 0
    tid = st.selectbox("Tarea relacionada", opciones, index=idx)

    if st.button("Guardar cambios", type="primary"):
        w = ws_respuestas()
        cell = w.find(uid)
        if not cell:
            st.error("No se encontró la fila en la hoja.")
            return
        r = cell.row
        w.update(f"B{r}:O{r}", [[
            (tid if tid != "(sin tarea)" else ""),
            user["id"], user["nombre"], str(f_fecha), str(f_hora),
            trabajo, localidad, user["nombre"], obs,
            row["estado_validacion"], row["observacion_admin"],
            row["creado_en"], iso_now(), row["creado_por"], user["usuario"]
        ]])
        log("editar_respuesta", user["usuario"], f"{uid}")
        st.success("Cambios guardados.")
        _rerun()

def eliminar_fila(uid: str, user: Dict):
    dfr = df_respuestas()
    row = dfr[dfr["uuid"] == uid]
    if row.empty:
        st.error("No se encontró el registro.")
        return
    row = row.iloc[0]
    if str(row["usuario_id"]) != str(user["id"]):
        st.error("No puede eliminar registros de otros usuarios.")
        return
    if row["estado_validacion"] in ("Validada","Rechazada"):
        st.warning("No puede eliminar registros ya validados/rechazados.")
        return

    w = ws_respuestas()
    cell = w.find(uid)
    if cell:
        w.delete_rows(cell.row)
        log("eliminar_respuesta", user["usuario"], f"{uid}")
        st.success("Registro eliminado.")
        _rerun()
    else:
        st.error("No se encontró la fila en la hoja.")

# --- perfil (cambio de contraseña) ---
def view_perfil(user: Dict):
    st.subheader("Mi Perfil")
    st.write(f"**Nombre:** {user['nombre']}  |  **Usuario:** `{user['usuario']}`")

    st.markdown("### Cambiar mi contraseña")
    pwd_actual = st.text_input("Contraseña actual", type="password")
    pwd_nueva = st.text_input("Nueva contraseña", type="password", help="Mínimo 6 caracteres.")
    pwd_conf  = st.text_input("Confirmar nueva contraseña", type="password")

    if st.button("Actualizar contraseña", type="primary"):
        if len(pwd_nueva) < 6:
            st.error("La nueva contraseña debe tener al menos 6 caracteres.")
            return
        if pwd_nueva != pwd_conf:
            st.error("La confirmación no coincide.")
            return

        dfu = df_usuarios()
        row = dfu[dfu["usuario"].astype(str) == user["usuario"]]
        if row.empty:
            st.error("No se encontró el usuario.")
            return
        row = row.iloc[0]
        if hash_password(pwd_actual) != row["password_hash"]:
            st.error("La contraseña actual es incorrecta.")
            return

        w = ws_usuarios()
        cell = w.find(str(row["id"]))
        if not cell:
            st.error("No se pudo ubicar el registro del usuario en la hoja.")
            return
        w.update_cell(cell.row, 5, hash_password(pwd_nueva))
        log("cambio_password_user", user["usuario"], "Actualizó su contraseña")
        st.success("Contraseña actualizada correctamente. Vuelve a iniciar sesión.")
        if st.button("Cerrar sesión ahora"):
            st.session_state.pop("auth", None)
            _rerun()

# --- main ---
def main():
    portada()

    if "auth" not in st.session_state:
        do_login()
        return

    user = st.session_state["auth"]
    logout_btn()

    vista = st.sidebar.radio("Secciones", ["Mis Tareas", "Registrar Labor", "Mis Labores", "Mi Perfil"])
    if vista == "Mis Tareas":
        view_tareas(user)
    elif vista == "Registrar Labor":
        view_registro(user)
    elif vista == "Mis Labores":
        view_mis_labores(user)
    else:
        view_perfil(user)

if __name__ == "__main__":
    main()
