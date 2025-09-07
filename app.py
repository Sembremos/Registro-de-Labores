# =========================
# RLD – 2025 (Versión 1.0)
# =========================
# Streamlit app con:
# - Login por usuario y rol (user / admin)
# - CRUD de RLD por usuario (cada quien solo ve/edita/borra lo suyo)
# - Admin (Sargento Viviana Peraza) ve todo, valida/rechaza, deja observación
# - Resumen por usuario y logs de auditoría
# - Google Sheets vía gspread (Service Account en st.secrets)
# - Zona horaria America/Costa_Rica

import os
import time
import json
import hashlib
import random
from datetime import datetime, date, time as dtime
from typing import List, Dict, Optional

import streamlit as st
import pandas as pd

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

APP_TITLE = "REGISTRO DE LABORES DIARIAS (RLD) – 2025 (Versión 1.0)"
TZ = "America/Costa_Rica"

# ============== CONFIG ==============
st.set_page_config(page_title="RLD 2025", layout="wide")

# === URL del Spreadsheet (el que enviaste) ===
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1diLJ9ZuG1ZvBRICTQll1he3H1pnouikclGle2bKIk6E/edit?usp=sharing"

# Nombres base
USUARIOS_INICIALES = ["Jeremy", "Jannia", "Manfred", "Luis", "Adrian", "Esteban", "Pamela", "Carlos"]
ADMIN_NOMBRE = "Viviana Peraza"   # Sargento – rol admin

# Nombres de pestañas
SHEET_USUARIOS = "Usuarios"
SHEET_RESPUESTAS = "RLD_respuestas"
SHEET_RESUMEN = "RLD_por_usuario"
SHEET_LOGS = "Logs"

# Selects (puedes ajustar luego desde Admin si deseas)
TRABAJOS_CATALOGO = [
    "Patrullaje Preventivo", "Atención de Incidencias", "Charlas Comunitarias",
    "Reunión Interinstitucional", "Operativo Focalizado", "Apoyo a Otras Unidades",
    "Control de Vías", "Tareas Administrativas"
]

# ========= Helpers de tiempo =========
def now_cr() -> datetime:
    # Guardaremos siempre timestamp ISO local legible
    # (Google Sheets no maneja TZ; registramos string)
    return datetime.now()

def iso_now() -> str:
    return now_cr().strftime("%Y-%m-%d %H:%M:%S")

# ========= Seguridad / contraseñas =========
def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def generar_password(nombre: str, pool: List[str]) -> str:
    # Ej: "jeremy-Jannia-Esteban"
    otros = [n for n in pool if n.lower() != nombre.lower()]
    pick = random.sample(otros, 2) if len(otros) >= 2 else otros
    base = nombre.strip().lower()
    return f"{base}-{ '-'.join(pick) }" if pick else base

# ========= Conexión Google Sheets =========
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    if "gcp_service_account" in st.secrets:
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ])
    else:
        raise RuntimeError("Faltan credenciales en st.secrets['gcp_service_account']")
    return gspread.authorize(creds)

def _open_sheet():
    gc = get_gspread_client()
    return gc.open_by_url(SPREADSHEET_URL)

def _ensure_ws(sh, title: str, header: List[str]):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(len(header), 10))
        ws.append_row(header)
    # Si la hoja existe pero sin encabezado
    vals = ws.get_all_values()
    if not vals:
        ws.append_row(header)
    return ws

def _ws_usuarios():
    sh = _open_sheet()
    header = ["id", "nombre", "usuario", "rol", "password_hash", "activo", "creado_en", "ultimo_acceso"]
    return _ensure_ws(sh, SHEET_USUARIOS, header)

def _ws_respuestas():
    sh = _open_sheet()
    header = [
        "uuid", "usuario_id", "usuario_nombre", "fecha", "hora",
        "trabajo_realizado", "localidad_delegacion", "funcionario_responsable",
        "observaciones", "estado_validacion", "observacion_admin",
        "creado_en", "editado_en", "creado_por", "editado_por"
    ]
    return _ensure_ws(sh, SHEET_RESPUESTAS, header)

def _ws_resumen():
    sh = _open_sheet()
    header = ["usuario_id", "usuario_nombre", "total", "pendientes", "validadas", "rechazadas", "ultima_actividad"]
    return _ensure_ws(sh, SHEET_RESUMEN, header)

def _ws_logs():
    sh = _open_sheet()
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
            "uuid","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado",
            "localidad_delegacion","funcionario_responsable","observaciones",
            "estado_validacion","observacion_admin","creado_en","editado_en",
            "creado_por","editado_por"
        ])
    return df

def write_log(evento: str, quien: str, detalle: str):
    ws = _ws_logs()
    ws.append_row([evento, quien, detalle, iso_now()])

def seed_usuarios_si_vacio() -> List[Dict]:
    """Si Usuarios está vacío, crea usuarios iniciales + admin.
       Devuelve credenciales en texto plano SOLO esta ejecución (para mostrarlas una vez)."""
    ws = _ws_usuarios()
    recs = ws.get_all_records()
    if recs:
        return []

    # Generar IDs y usuarios
    todos = USUARIOS_INICIALES[:] + [ADMIN_NOMBRE]
    credenciales_mostrables = []
    next_id = 1
    for nombre in USUARIOS_INICIALES:
        usuario = nombre.strip().split()[0].lower()
        pwd = generar_password(nombre, USUARIOS_INICIALES)
        ws.append_row([f"{next_id:03d}", nombre, usuario, "user", hash_password(pwd), True, iso_now(), ""])
        credenciales_mostrables.append({"nombre": nombre, "usuario": usuario, "password": pwd, "rol": "user"})
        next_id += 1

    # Admin
    usuario_admin = "vperaza"
    pwd_admin = generar_password("Viviana", USUARIOS_INICIALES + ["Viviana"])
    ws.append_row([f"{next_id:03d}", ADMIN_NOMBRE, usuario_admin, "admin",
                   hash_password(pwd_admin), True, iso_now(), ""])
    credenciales_mostrables.append({"nombre": ADMIN_NOMBRE, "usuario": usuario_admin, "password": pwd_admin, "rol": "admin"})

    write_log("seed_usuarios", "sistema", f"Creó {len(credenciales_mostrables)} usuarios")
    return credenciales_mostrables

def set_ultimo_acceso(usuario_id: str):
    ws = _ws_usuarios()
    cell = ws.find(usuario_id)
    if cell:
        row = cell.row
        # columnas: id, nombre, usuario, rol, password_hash, activo, creado_en, ultimo_acceso
        ws.update_cell(row, 8, iso_now())  # col 8 = ultimo_acceso

def actualizar_resumen():
    ws = _ws_resumen()
    df_u = df_usuarios()
    df_r = df_respuestas()

    if df_u.empty:
        ws.clear()
        ws.append_row(["usuario_id","usuario_nombre","total","pendientes","validadas","rechazadas","ultima_actividad"])
        return

    rows = []
    for _, u in df_u.iterrows():
        uid = str(u["id"])
        uname = u["nombre"]
        sub = df_r[df_r["usuario_id"].astype(str) == uid]
        total = len(sub)
        pend = (sub["estado_validacion"] == "Pendiente").sum() if not sub.empty else 0
        vali = (sub["estado_validacion"] == "Validada").sum() if not sub.empty else 0
        rech = (sub["estado_validacion"] == "Rechazada").sum() if not sub.empty else 0
        ultima = ""
        if not sub.empty and "creado_en" in sub.columns and sub["creado_en"].notna().any():
            ultima = str(sub["creado_en"].max())
        rows.append([uid, uname, total, pend, vali, rech, ultima])

    ws.clear()
    ws.append_row(["usuario_id","usuario_nombre","total","pendientes","validadas","rechazadas","ultima_actividad"])
    if rows:
        ws.append_rows(rows)

# ========= Autenticación UI =========
def do_login():
    st.subheader("Ingreso")
    usuario = st.text_input("Usuario", placeholder="p.ej. jeremy / vperaza")
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

        if hash_password(pwd) != row["password_hash"]:
            st.error("Contraseña incorrecta.")
            return

        # OK
        st.session_state["auth"] = {
            "id": str(row["id"]),
            "nombre": row["nombre"],
            "usuario": row["usuario"],
            "rol": row["rol"]
        }
        set_ultimo_acceso(str(row["id"]))
        write_log("login", row["usuario"], "Inicio de sesión")
        st.experimental_rerun()

def logout_btn():
    with st.sidebar:
        st.caption(f"Conectado como **{st.session_state['auth']['nombre']}** ({st.session_state['auth']['rol']})")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("auth", None)
            st.experimental_rerun()

# ========= Vistas =========
def view_portada():
    st.title(APP_TITLE)
    st.info(
        "Es una herramienta fundamental para garantizar la eficiencia, efectividad y compromiso en el cumplimiento "
        "de nuestras metas institucionales. Su objetivo principal es verificar el nivel de cumplimiento y desempeño "
        "en las tareas registradas, lo que la convierte en un recurso clave tanto para la planificación como para el "
        "seguimiento de las metas establecidas. Asimismo, proporciona información precisa y consistente, indispensable "
        "para realizar evaluaciones semestrales de desempeño, facilitando un análisis objetivo y detallado de las actividades realizadas."
    )
    st.divider()

def form_registro(usuario_ctx: Dict):
    st.subheader("Registrar Labor (RLD)")
    col1, col2 = st.columns(2)
    with col1:
        f_fecha = st.date_input("Fecha", value=date.today())
    with col2:
        f_hora = st.time_input("Hora", value=datetime.now().time())

    trabajo = st.selectbox("Trabajo Realizado", TRABAJOS_CATALOGO)
    localidad = st.text_input("Localidad / Delegación")
    # Funcionario Responsable = catálogo de usuarios activos (user)
    dfu = df_usuarios()
    opciones_func = dfu[(dfu["rol"]=="user") & (dfu["activo"]==True)]["nombre"].tolist()
    func_resp = st.selectbox("Funcionario Responsable", opciones_func or [usuario_ctx["nombre"]])

    obs = st.text_area(
        "Observaciones",
        help="Detalle las actividades realizadas **por guardia** e indique si alguna quedó pendiente."
    )

    if st.button("Guardar", type="primary", use_container_width=True):
        ws = _ws_respuestas()
        uid = f"rld-{int(time.time()*1000)}-{random.randint(100,999)}"
        row = [
            uid, usuario_ctx["id"], usuario_ctx["nombre"],
            str(f_fecha), str(f_hora),
            trabajo, localidad, func_resp,
            obs, "Pendiente", "",  # validación/obs admin
            iso_now(), "", usuario_ctx["usuario"], ""  # creado/ editado
        ]
        ws.append_row(row)
        write_log("crear", usuario_ctx["usuario"], f"Nuevo rld {uid}")
        actualizar_resumen()
        st.success("Registro guardado.")
        st.experimental_rerun()

def table_mis_labores(usuario_ctx: Dict):
    st.subheader("Mis Labores")
    dfr = df_respuestas()
    mine = dfr[dfr["usuario_id"].astype(str) == str(usuario_ctx["id"])].copy()

    # Filtros
    colf1, colf2, colf3 = st.columns([1,1,1])
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
        mine = mine.drop(columns=["fecha_dt"])

    st.dataframe(mine, use_container_width=True, hide_index=True)

    st.markdown("### Editar / Eliminar")
    uid = st.text_input("ID (uuid) de la fila a modificar/eliminar")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Editar seleccionado", use_container_width=True, disabled=mine.empty or uid.strip()==""):
            editar_fila(uid, usuario_ctx, es_admin=False)
    with c2:
        if st.button("Eliminar seleccionado", use_container_width=True, disabled=mine.empty or uid.strip()==""):
            eliminar_fila(uid, usuario_ctx, es_admin=False)

def editar_fila(uid: str, usuario_ctx: Dict, es_admin: bool):
    dfr = df_respuestas()
    row = dfr[dfr["uuid"] == uid]
    if row.empty:
        st.error("No se encontró el registro.")
        return
    row = row.iloc[0]

    # Permisos
    if (not es_admin) and str(row["usuario_id"]) != str(usuario_ctx["id"]):
        st.error("No puede editar registros de otros usuarios.")
        return
    if row["estado_validacion"] in ("Validada", "Rechazada") and not es_admin:
        st.warning("No puede editar registros ya validados/rechazados. Contacte a admin.")
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

    trabajo = st.selectbox("Trabajo Realizado", TRABAJOS_CATALOGO, index=max(0, TRABAJOS_CATALOGO.index(row["trabajo_realizado"])) if row["trabajo_realizado"] in TRABAJOS_CATALOGO else 0)
    localidad = st.text_input("Localidad / Delegación", value=str(row["localidad_delegacion"]))

    dfu = df_usuarios()
    opciones_func = dfu[(dfu["rol"]=="user") & (dfu["activo"]==True)]["nombre"].tolist()
    try:
        idx = opciones_func.index(row["funcionario_responsable"]) if row["funcionario_responsable"] in opciones_func else 0
    except Exception:
        idx = 0
    func_resp = st.selectbox("Funcionario Responsable", opciones_func or [usuario_ctx["nombre"]], index=idx)

    obs = st.text_area("Observaciones", value=str(row["observaciones"]), help="Detalle las actividades realizadas **por guardia** e indique si alguna quedó pendiente.")

    if st.button("Guardar cambios", type="primary"):
        ws = _ws_respuestas()
        cell = ws.find(uid)
        if not cell:
            st.error("No se encontró la fila en la hoja.")
            return
        r = cell.row
        # columnas según header de _ws_respuestas():
        ws.update(f"B{r}:O{r}", [[
            usuario_ctx["id"], usuario_ctx["nombre"], str(f_fecha), str(f_hora),
            trabajo, localidad, func_resp, obs,
            row["estado_validacion"], row["observacion_admin"],
            row["creado_en"], iso_now(), row["creado_por"], usuario_ctx["usuario"]
        ]])
        write_log("editar", usuario_ctx["usuario"], f"Editó {uid}")
        actualizar_resumen()
        st.success("Cambios guardados.")
        st.experimental_rerun()

def eliminar_fila(uid: str, usuario_ctx: Dict, es_admin: bool):
    dfr = df_respuestas()
    row = dfr[dfr["uuid"] == uid]
    if row.empty:
        st.error("No se encontró el registro.")
        return
    row = row.iloc[0]
    if (not es_admin) and str(row["usuario_id"]) != str(usuario_ctx["id"]):
        st.error("No puede eliminar registros de otros usuarios.")
        return
    if row["estado_validacion"] in ("Validada","Rechazada") and not es_admin:
        st.warning("No puede eliminar registros ya validados/rechazados. Contacte a admin.")
        return

    if st.confirm("¿Eliminar definitivamente este registro?"):
        ws = _ws_respuestas()
        cell = ws.find(uid)
        if cell:
            ws.delete_rows(cell.row)
            write_log("eliminar", usuario_ctx["usuario"], f"Eliminó {uid}")
            actualizar_resumen()
            st.success("Registro eliminado.")
            st.experimental_rerun()
        else:
            st.error("No se encontró la fila en la hoja.")

# -------- Admin --------
def view_admin(usuario_ctx: Dict):
    st.header("Administración – Sargento Viviana Peraza")
    tabs = st.tabs(["Panel General", "Usuarios", "Resumen"])
    # ---- Panel General ----
    with tabs[0]:
        dfr = df_respuestas()
        # Filtros
        dfu = df_usuarios()
        usuarios_map = dict(zip(dfu["id"].astype(str), dfu["nombre"]))
        colf1, colf2, colf3 = st.columns([1,1,1])
        with colf1:
            usr = st.selectbox("Usuario", ["(Todos)"] + dfu["nombre"].tolist())
        with colf2:
            estado = st.selectbox("Estado", ["(Todos)","Pendiente","Validada","Rechazada"])
        with colf3:
            rango = st.date_input("Rango de fechas", value=None)

        data = dfr.copy()
        if usr != "(Todos)":
            data = data[data["usuario_nombre"] == usr]
        if estado != "(Todos)":
            data = data[data["estado_validacion"] == estado]
        if rango:
            if isinstance(rango, tuple) or isinstance(rango, list):
                if len(rango) == 2 and rango[0] and rango[1]:
                    ini, fin = pd.to_datetime(rango[0]), pd.to_datetime(rango[1])
                    data["fecha_dt"] = pd.to_datetime(data["fecha"], errors="coerce")
                    data = data[(data["fecha_dt"] >= ini) & (data["fecha_dt"] <= fin)]
                    data = data.drop(columns=["fecha_dt"], errors="ignore")

        st.dataframe(data, use_container_width=True, hide_index=True)

        st.markdown("### Validar / Rechazar / Editar / Eliminar")
        uid = st.text_input("ID (uuid) de la fila")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("Validar", use_container_width=True, disabled=uid.strip()==""):
                cambiar_estado(uid, "Validada", usuario_ctx)
        with c2:
            if st.button("Rechazar", use_container_width=True, disabled=uid.strip()==""):
                cambiar_estado(uid, "Rechazada", usuario_ctx)
        with c3:
            if st.button("Editar", use_container_width=True, disabled=uid.strip()==""):
                editar_fila(uid, usuario_ctx, es_admin=True)
        with c4:
            if st.button("Eliminar", use_container_width=True, disabled=uid.strip()==""):
                eliminar_fila(uid, usuario_ctx, es_admin=True)

        obs_admin = st.text_area("Observación administrativa")
        if st.button("Guardar observación en la fila", disabled=uid.strip()==""):
            guardar_observacion_admin(uid, obs_admin, usuario_ctx)

        # Export
        if st.download_button("Exportar CSV", data.to_csv(index=False).encode("utf-8"), file_name="rld_2025_export.csv"):
            pass

    # ---- Usuarios ----
    with tabs[1]:
        dfu = df_usuarios()
        st.subheader("Usuarios")
        st.dataframe(dfu, use_container_width=True, hide_index=True)
        st.caption("Para reiniciar la contraseña de un usuario, ingrese el ID:")
        uid = st.text_input("ID de usuario")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Reiniciar contraseña", use_container_width=True, disabled=uid.strip()==""):
                reset_password(uid, usuario_ctx)
        with c2:
            if st.button("Alternar activo/inactivo", use_container_width=True, disabled=uid.strip()==""):
                toggle_activo(uid, usuario_ctx)

    # ---- Resumen ----
    with tabs[2]:
        if st.button("Recalcular resumen"):
            actualizar_resumen()
            st.success("Resumen actualizado.")
        ws = _ws_resumen()
        recs = ws.get_all_records()
        dfrs = pd.DataFrame(recs)
        st.dataframe(dfrs, use_container_width=True, hide_index=True)

def cambiar_estado(uid: str, nuevo_estado: str, usuario_ctx: Dict):
    ws = _ws_respuestas()
    cell = ws.find(uid)
    if not cell:
        st.error("No se encontró el registro.")
        return
    r = cell.row
    # estado_validacion = col 10
    ws.update_cell(r, 10, nuevo_estado)
    ws.update_cell(r, 14, iso_now())  # editado_en
    ws.update_cell(r, 16, usuario_ctx["usuario"])  # editado_por
    write_log("validacion", usuario_ctx["usuario"], f"{nuevo_estado} {uid}")
    actualizar_resumen()
    st.success(f"Estado actualizado a {nuevo_estado}.")

def guardar_observacion_admin(uid: str, texto: str, usuario_ctx: Dict):
    ws = _ws_respuestas()
    cell = ws.find(uid)
    if not cell:
        st.error("No se encontró el registro.")
        return
    r = cell.row
    # observacion_admin = col 11
    ws.update_cell(r, 11, texto)
    ws.update_cell(r, 14, iso_now())  # editado_en
    ws.update_cell(r, 16, usuario_ctx["usuario"])  # editado_por
    write_log("obs_admin", usuario_ctx["usuario"], f"{uid}")
    st.success("Observación guardada.")

def reset_password(usuario_id: str, usuario_ctx: Dict):
    ws = _ws_usuarios()
    cell = ws.find(usuario_id)
    if not cell:
        st.error("No se encontró el ID.")
        return
    r = cell.row
    nombre = ws.cell(r, 2).value
    usuario = ws.cell(r, 3).value
    rol = ws.cell(r, 4).value
    pool = USUARIOS_INICIALES[:] + (["Viviana"] if rol == "admin" else [])
    pwd = generar_password(nombre, pool)
    ws.update_cell(r, 5, hash_password(pwd))  # password_hash
    write_log("reset_password", usuario_ctx["usuario"], f"Reseteó {usuario}")
    st.success(f"Nueva contraseña temporal para {usuario}: **{pwd}** (muéstrala al usuario y cámbienla si desean)")

def toggle_activo(usuario_id: str, usuario_ctx: Dict):
    ws = _ws_usuarios()
    cell = ws.find(usuario_id)
    if not cell:
        st.error("No se encontró el ID.")
        return
    r = cell.row
    val = ws.cell(r, 6).value  # activo
    nuevo = "FALSE" if str(val).upper() in ("TRUE","1") else "TRUE"
    ws.update_cell(r, 6, nuevo)
    write_log("toggle_activo", usuario_ctx["usuario"], f"ID {usuario_id} -> {nuevo}")
    st.success("Estado actualizado.")

# ========= Main =========
def main():
    # Semilla inicial si vacío (y mostrar credenciales SOLO una vez)
    credenciales = seed_usuarios_si_vacio()
    if credenciales:
        with st.expander("⚠️ Credenciales iniciales (mostradas solo en esta ejecución)"):
            st.write(pd.DataFrame(credenciales))

    view_portada()

    if "auth" not in st.session_state:
        do_login()
        return

    logout_btn()
    user = st.session_state["auth"]
    if user["rol"] == "admin":
        # Menú admin y usuario
        vista = st.sidebar.radio("Secciones", ["Registrar Labor", "Mis Labores", "Administración"])
        if vista == "Registrar Labor":
            form_registro(user)
        elif vista == "Mis Labores":
            table_mis_labores(user)
        else:
            view_admin(user)
    else:
        # Solo vistas de usuario
        vista = st.sidebar.radio("Secciones", ["Registrar Labor", "Mis Labores"])
        if vista == "Registrar Labor":
            form_registro(user)
        else:
            table_mis_labores(user)

if __name__ == "__main__":
    main()
