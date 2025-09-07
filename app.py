# =========================
# RLD – 2025 (Versión 1.0)
# =========================
# - Contraseñas INICIALES FIJAS para entregar (sin aleatorios)
# - Migración automática: actualiza password_hash existentes a las claves fijas
# - Cada usuario puede CAMBIAR su contraseña en "Mi Perfil"
# - CRUD por usuario (solo ve/edita/borra lo propio)
# - Admin (vperaza) ve todo, valida/rechaza, observa, resetea a contraseña fija
# - Resumen por usuario y logs
# - Google Sheets vía gspread (Service Account en st.secrets)
# - Compatibilidad Streamlit 1.30+: _rerun() usa st.rerun() y fallback a experimental_rerun

import time
import hashlib
from datetime import datetime, date
from typing import List, Dict

import streamlit as st
import pandas as pd

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

APP_TITLE = "REGISTRO DE LABORES DIARIAS (RLD) – 2025 (Versión 1.0)"

st.set_page_config(page_title="RLD 2025", layout="wide")

# ---------- helper de recarga (compatibilidad) ----------
def _rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# === URL del Spreadsheet (el que enviaste) ===
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
    "vperaza": "viviana2025",  # Admin
}

# ---------- Nombres de pestañas en Sheets ----------
SHEET_USUARIOS  = "Usuarios"
SHEET_RESPUESTAS = "RLD_respuestas"
SHEET_RESUMEN   = "RLD_por_usuario"
SHEET_LOGS      = "Logs"

# ---------- Catálogo (ajústalo si deseas) ----------
TRABAJOS_CATALOGO = [
    "Patrullaje Preventivo", "Atención de Incidencias", "Charlas Comunitarias",
    "Reunión Interinstitucional", "Operativo Focalizado", "Apoyo a Otras Unidades",
    "Control de Vías", "Tareas Administrativas"
]

# ========= Utilidades de tiempo =========
def iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ========= Seguridad / contraseñas =========
def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def password_fija_de(usuario: str) -> str:
    """Devuelve la contraseña fija definida arriba (texto plano)."""
    return PASSWORDS_FIJAS[usuario.strip().lower()]

# ========= Conexión Google Sheets =========
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Faltan credenciales en st.secrets['gcp_service_account']")
    info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(info, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    return gspread.authorize(creds)

def _open_sheet():
    return get_gspread_client().open_by_url(SPREADSHEET_URL)

def _ensure_ws(sh, title: str, header: List[str]):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(len(header), 10))
        ws.append_row(header)
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
    _ws_logs().append_row([evento, quien, detalle, iso_now()])

# ========= Seed y Migración =========
def seed_usuarios_si_vacio() -> bool:
    """Si no hay usuarios en la hoja, crea los usuarios con las CONTRASEÑAS FIJAS (hasheadas)."""
    ws = _ws_usuarios()
    recs = ws.get_all_records()
    if recs:
        return False

    for (id_, nombre, usuario, rol) in USUARIOS_INICIALES:
        pwd_fija = password_fija_de(usuario)  # texto plano
        ws.append_row([id_, nombre, usuario, rol, hash_password(pwd_fija), True, iso_now(), ""])

    write_log("seed_usuarios", "sistema", f"Sembró {len(USUARIOS_INICIALES)} usuarios con contraseñas fijas")
    return True

def migrate_passwords_a_fijas() -> int:
    """
    Actualiza los password_hash de la hoja Usuarios a las contraseñas FIJAS
    definidas en PASSWORDS_FIJAS. Devuelve la cantidad de usuarios actualizados.
    """
    ws = _ws_usuarios()
    recs = ws.get_all_records()
    if not recs:
        return 0

    actualizados = 0
    for i, r in enumerate(recs, start=2):  # datos comienzan en la fila 2
        usuario = str(r.get("usuario", "")).strip().lower()
        if usuario in PASSWORDS_FIJAS:
            hash_actual = str(r.get("password_hash", ""))
            hash_fijo = hash_password(PASSWORDS_FIJAS[usuario])
            if hash_actual != hash_fijo:
                ws.update_cell(i, 5, hash_fijo)  # col 5 = password_hash
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
        uid = str(u["id"]); uname = u["nombre"]
        sub = df_r[df_r["usuario_id"].astype(str) == uid]
        total = len(sub)
        pend = (sub["estado_validacion"] == "Pendiente").sum() if not sub.empty else 0
        vali = (sub["estado_validacion"] == "Validada").sum() if not sub.empty else 0
        rech = (sub["estado_validacion"] == "Rechazada").sum() if not sub.empty else 0
        ultima = str(sub["creado_en"].max()) if not sub.empty and sub["creado_en"].notna().any() else ""
        rows.append([uid, uname, total, pend, vali, rech, ultima])
    if rows:
        ws.append_rows(rows)

# ========= Autenticación =========
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

        st.session_state["auth"] = {
            "id": str(row["id"]),
            "nombre": row["nombre"],
            "usuario": row["usuario"],
            "rol": row["rol"]
        }
        set_ultimo_acceso(str(row["id"]))
        write_log("login", row["usuario"], "Inicio de sesión")
        _rerun()

def logout_btn():
    with st.sidebar:
        st.caption(f"Conectado como **{st.session_state['auth']['nombre']}** ({st.session_state['auth']['rol']})")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("auth", None)
            _rerun()

# ========= UI comunes =========
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

    dfu = df_usuarios()
    opciones_func = dfu[(dfu["rol"]=="user") & (dfu["activo"]==True)]["nombre"].tolist()
    func_resp = st.selectbox("Funcionario Responsable", opciones_func or [usuario_ctx["nombre"]])

    obs = st.text_area(
        "Observaciones",
        help="Detalle las actividades realizadas **por guardia** e indique si alguna quedó pendiente."
    )

    if st.button("Guardar", type="primary", use_container_width=True):
        ws = _ws_respuestas()
        uid = f"rld-{int(time.time()*1000)}"
        ws.append_row([
            uid, usuario_ctx["id"], usuario_ctx["nombre"],
            str(f_fecha), str(f_hora),
            trabajo, localidad, func_resp,
            obs, "Pendiente", "",
            iso_now(), "", usuario_ctx["usuario"], ""
        ])
        write_log("crear", usuario_ctx["usuario"], f"Nuevo rld {uid}")
        actualizar_resumen()
        st.success("Registro guardado.")
        _rerun()

def table_mis_labores(usuario_ctx: Dict):
    st.subheader("Mis Labores")
    dfr = df_respuestas()
    mine = dfr[dfr["usuario_id"].astype(str) == str(usuario_ctx["id"])].copy()

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
        mine = mine.drop(columns=["fecha_dt"], errors="ignore")

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

    trabajo = st.selectbox(
        "Trabajo Realizado",
        TRABAJOS_CATALOGO,
        index=max(0, TRABAJOS_CATALOGO.index(row["trabajo_realizado"])) if row["trabajo_realizado"] in TRABAJOS_CATALOGO else 0
    )
    localidad = st.text_input("Localidad / Delegación", value=str(row["localidad_delegacion"]))

    dfu = df_usuarios()
    opciones_func = dfu[(dfu["rol"]=="user") & (dfu["activo"]==True)]["nombre"].tolist()
    try:
        idx = opciones_func.index(row["funcionario_responsable"])
    except Exception:
        idx = 0
    func_resp = st.selectbox("Funcionario Responsable", opciones_func or [usuario_ctx["nombre"]], index=idx)

    obs = st.text_area("Observaciones", value=str(row["observaciones"]),
                       help="Detalle las actividades realizadas **por guardia** e indique si alguna quedó pendiente.")

    if st.button("Guardar cambios", type="primary"):
        ws = _ws_respuestas()
        cell = ws.find(uid)
        if not cell:
            st.error("No se encontró la fila en la hoja.")
            return
        r = cell.row
        ws.update(f"B{r}:O{r}", [[
            usuario_ctx["id"], usuario_ctx["nombre"], str(f_fecha), str(f_hora),
            trabajo, localidad, func_resp, obs,
            row["estado_validacion"], row["observacion_admin"],
            row["creado_en"], iso_now(), row["creado_por"], usuario_ctx["usuario"]
        ]])
        write_log("editar", usuario_ctx["usuario"], f"Editó {uid}")
        actualizar_resumen()
        st.success("Cambios guardados.")
        _rerun()

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

    ws = _ws_respuestas()
    cell = ws.find(uid)
    if cell:
        ws.delete_rows(cell.row)
        write_log("eliminar", usuario_ctx["usuario"], f"Eliminó {uid}")
        actualizar_resumen()
        st.success("Registro eliminado.")
        _rerun()
    else:
        st.error("No se encontró la fila en la hoja.")

# -------- Admin --------
def view_admin(usuario_ctx: Dict):
    st.header("Administración – Sargento Viviana Peraza")
    tabs = st.tabs(["Panel General", "Usuarios", "Resumen"])

    with tabs[0]:
        dfr = df_respuestas()
        dfu = df_usuarios()
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
            try:
                ini, fin = rango
                if ini:
                    data["fecha_dt"] = pd.to_datetime(data["fecha"], errors="coerce")
                    data = data[data["fecha_dt"] >= pd.to_datetime(ini)]
                if fin:
                    data["fecha_dt"] = pd.to_datetime(data["fecha"], errors="coerce")
                    data = data[data["fecha_dt"] <= pd.to_datetime(fin)]
                data = data.drop(columns=["fecha_dt"], errors="ignore")
            except Exception:
                pass

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

        st.download_button("Exportar CSV", data.to_csv(index=False).encode("utf-8"), file_name="rld_2025_export.csv")

    with tabs[1]:
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

    with tabs[2]:
        if st.button("Recalcular resumen"):
            actualizar_resumen()
            st.success("Resumen actualizado.")
        recs = _ws_resumen().get_all_records()
        st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)

def cambiar_estado(uid: str, nuevo_estado: str, usuario_ctx: Dict):
    ws = _ws_respuestas()
    cell = ws.find(uid)
    if not cell:
        st.error("No se encontró el registro.")
        return
    r = cell.row
    ws.update_cell(r, 10, nuevo_estado)  # estado_validacion
    ws.update_cell(r, 14, iso_now())      # editado_en
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
    ws.update_cell(r, 11, texto)          # observacion_admin
    ws.update_cell(r, 14, iso_now())      # editado_en
    ws.update_cell(r, 16, usuario_ctx["usuario"])  # editado_por
    write_log("obs_admin", usuario_ctx["usuario"], f"{uid}")
    st.success("Observación guardada.")

def reset_password_fija(usuario_id: str, usuario_ctx: Dict):
    ws = _ws_usuarios()
    cell = ws.find(usuario_id)
    if not cell:
        st.error("No se encontró el ID.")
        return
    r = cell.row
    usuario = ws.cell(r, 3).value  # username
    pwd = password_fija_de(usuario)
    ws.update_cell(r, 5, hash_password(pwd))  # password_hash
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

# ========= Mi Perfil (cambio de contraseña) =========
def view_perfil(usuario_ctx: Dict):
    st.subheader("Mi Perfil")
    st.write(f"**Nombre:** {usuario_ctx['nombre']}  |  **Usuario:** `{usuario_ctx['usuario']}`  |  **Rol:** `{usuario_ctx['rol']}`")

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
        row = dfu[dfu["usuario"].astype(str) == usuario_ctx["usuario"]]
        if row.empty:
            st.error("No se encontró el usuario.")
            return
        row = row.iloc[0]
        if hash_password(pwd_actual) != row["password_hash"]:
            st.error("La contraseña actual es incorrecta.")
            return

        ws = _ws_usuarios()
        cell = ws.find(str(row["id"]))
        if not cell:
            st.error("No se pudo ubicar el registro del usuario en la hoja.")
            return
        ws.update_cell(cell.row, 5, hash_password(pwd_nueva))
        write_log("cambio_password", usuario_ctx["usuario"], "Actualizó su contraseña")
        st.success("Contraseña actualizada correctamente. Vuelva a iniciar sesión.")
        if st.button("Cerrar sesión ahora"):
            st.session_state.pop("auth", None)
            _rerun()

# ========= Main =========
def main():
    seeded = seed_usuarios_si_vacio()           # crea usuarios con contraseñas FIJAS si hoja está vacía
    migrados = migrate_passwords_a_fijas()      # fuerza que los existentes usen las contraseñas fijas
    if seeded or migrados:
        with st.expander("✅ Credenciales iniciales/fijas"):
            st.write(pd.DataFrame(
                [{"nombre": n, "usuario": u, "password_inicial": PASSWORDS_FIJAS[u], "rol": r}
                 for _, n, u, r in USUARIOS_INICIALES]
            ))
            if migrados:
                st.success(f"Se actualizaron {migrados} usuarios a las contraseñas fijas.")

    view_portada()

    if "auth" not in st.session_state:
        do_login()
        return

    logout_btn()
    user = st.session_state["auth"]

    if user["rol"] == "admin":
        vista = st.sidebar.radio("Secciones", ["Registrar Labor", "Mis Labores", "Administración", "Mi Perfil"])
        if vista == "Registrar Labor":
            form_registro(user)
        elif vista == "Mis Labores":
            table_mis_labores(user)
        elif vista == "Administración":
            view_admin(user)
        else:
            view_perfil(user)
    else:
        vista = st.sidebar.radio("Secciones", ["Registrar Labor", "Mis Labores", "Mi Perfil"])
        if vista == "Registrar Labor":
            form_registro(user)
        elif vista == "Mis Labores":
            table_mis_labores(user)
        else:
            view_perfil(user)

if __name__ == "__main__":
    main()






