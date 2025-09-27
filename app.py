# =========================
# RLD – 2025 (con Google Sheets) – APP PRINCIPAL (VIVIANA)
# =========================
import time, hashlib, json
from datetime import datetime, date, timedelta
from typing import List, Dict
import streamlit as st
import pandas as pd

# Google Sheets
import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="RLD 2025 – Viviana (Admin)", layout="wide")
APP_TITLE = "REGISTRO DE LABORES DIARIAS – Admin (Sheets)"

# === URL del Spreadsheet (el tuyo) ===
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1LiHP1V5PMzt13yX_zgSeVFmZ7r-HM6PPEI5Ej46ziPk/edit?usp=sharing"

# ---------- Usuarios iniciales ----------
USUARIOS_INICIALES = [
    ("001", "Jeremy",  "jeremy",  "user"),
    ("002", "Jannia",  "jannia",  "user"),
    ("003", "Manfred", "manfred", "user"),
    ("004", "Luis",    "luis",    "user"),
    ("005", "Adrian",  "adrian",  "user"),
    ("006", "Esteban", "esteban", "user"),
    ("007", "Pamela",  "pamela",  "user"),
    ("009", "Viviana Peraza", "vperaza", "admin"),
    ("010", "Charly",  "charly",  "user"),
]

PASSWORDS_FIJAS = {
    "jeremy":"jeremy2025","jannia":"jannia2025","manfred":"manfred2025","luis":"luis2025",
    "adrian":"adrian2025","esteban":"esteban2025","pamela":"pamela2025",
    "charly":"charly2025","vperaza":"viviana2025"
}

SHEET_USUARIOS   = "Usuarios"
SHEET_TAREAS     = "RLD_tareas"
SHEET_RESPUESTAS = "RLD_respuestas"
SHEET_RESUMEN    = "RLD_por_usuario"
SHEET_LOGS       = "Logs"

PRIORIDADES = ["Alta","Media","Baja"]          # Alta=naranja, Media=rojo, Baja=verde
ESTADOS_TAREA = ["Nueva","En Progreso","Completada","Rechazada"]

# ========= Utilidades =========
def iso_now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def hash_password(p): return hashlib.sha256(p.encode("utf-8")).hexdigest()
def _as_bool(x): return str(x).strip().lower() in ("true","1","yes","si","sí")
def tag_prioridad_html(p: str) -> str:
    p = (p or "").strip().title()
    color = "#22c55e"  # Baja = verde
    if p == "Alta":   color = "#f59e0b"  # naranja (máxima)
    elif p == "Media": color = "#ef4444"  # rojo (urge)
    return f"<span style='background:{color};color:white;padding:2px 8px;border-radius:999px;font-size:12px'>{p}</span>"

# ========= Conexión Google Sheets =========
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
        try:
            return gc.open_by_url(SPREADSHEET_URL)
        except Exception:
            svc = st.session_state.get("_svc_email","(sin email)")
            st.error("No se pudo abrir el Spreadsheet.")
            st.markdown(f"- Comparte la hoja con **{svc}** como *Editor*.")
            st.stop()

def _ensure_ws(title: str, header: List[str]):
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=2000, cols=max(len(header), 12))
        ws.append_row(header)
    vals = ws.get_all_values()
    if not vals:
        ws.append_row(header)
    return ws

def ws_usuarios():   return _ensure_ws(SHEET_USUARIOS, ["id","nombre","usuario","rol","password_hash","activo","creado_en","ultimo_acceso"])
def ws_tareas():     return _ensure_ws(SHEET_TAREAS,   ["task_id","titulo","descripcion","prioridad","estado","asignado_id","asignado_nombre","fecha_asignacion","fecha_limite","creado_por","observ_admin","ultima_actualizacion"])
def ws_respuestas(): return _ensure_ws(SHEET_RESPUESTAS,["uuid","task_id","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado","localidad_delegacion","funcionario_responsable","observaciones","estado_validacion","observacion_admin","creado_en","editado_en","creado_por","editado_por"])
def ws_resumen():    return _ensure_ws(SHEET_RESUMEN,  ["usuario_id","usuario_nombre","total","pendientes","validadas","rechazadas","ultima_actividad"])
def ws_logs():       return _ensure_ws(SHEET_LOGS,     ["evento","quien","detalle","timestamp"])

# ========= DataFrames =========
def df_usuarios():
    recs = ws_usuarios().get_all_records()
    df = pd.DataFrame(recs) if recs else pd.DataFrame(columns=["id","nombre","usuario","rol","password_hash","activo","creado_en","ultimo_acceso"])
    if not df.empty:
        df["activo_norm"] = df["activo"].apply(_as_bool)
        df["rol_norm"] = df["rol"].astype(str).str.lower()
    return df

def df_tareas():
    recs = ws_tareas().get_all_records()
    return pd.DataFrame(recs) if recs else pd.DataFrame(columns=["task_id","titulo","descripcion","prioridad","estado","asignado_id","asignado_nombre","fecha_asignacion","fecha_limite","creado_por","observ_admin","ultima_actualizacion"])

def df_respuestas():
    recs = ws_respuestas().get_all_records()
    return pd.DataFrame(recs) if recs else pd.DataFrame(columns=["uuid","task_id","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado","localidad_delegacion","funcionario_responsable","observaciones","estado_validacion","observacion_admin","creado_en","editado_en","creado_por","editado_por"])

def log(evento, quien, detalle): ws_logs().append_row([evento, quien, detalle, iso_now()])

# ========= Seed/Migración =========
def seed_usuarios_si_vacio():
    ws = ws_usuarios()
    if ws.get_all_records(): return False
    for (id_, nombre, usuario, rol) in USUARIOS_INICIALES:
        pwd_fija = PASSWORDS_FIJAS[usuario]
        ws.append_row([id_, nombre, usuario, rol, hash_password(pwd_fija), True, iso_now(), ""])
    log("seed_usuarios","sistema",f"{len(USUARIOS_INICIALES)} sembrados")
    return True

def migrate_passwords_a_fijas():
    ws = ws_usuarios()
    recs = ws.get_all_records()
    if not recs: return 0
    actualizados = 0
    for i, r in enumerate(recs, start=2):
        usuario = str(r.get("usuario","")).strip().lower()
        if usuario in PASSWORDS_FIJAS:
            nuevo = hash_password(PASSWORDS_FIJAS[usuario])
            if str(r.get("password_hash","")) != nuevo:
                ws.update_cell(i, 5, nuevo)
                actualizados += 1
    if actualizados:
        log("migracion_passwords","sistema",f"{actualizados} actualizados")
    return actualizados

def actualizar_resumen():
    wsr = ws_resumen()
    wsr.clear()
    wsr.append_row(["usuario_id","usuario_nombre","total","pendientes","validadas","rechazadas","ultima_actividad"])
    dfu = df_usuarios()
    dfr = df_respuestas()
    for _, u in dfu.iterrows():
        uid, uname = str(u["id"]), str(u["nombre"])
        sub = dfr[dfr.get("usuario_id","").astype(str)==uid] if not dfr.empty else pd.DataFrame()
        tot = int(len(sub))
        pen = int((sub["estado_validacion"]=="Pendiente").sum()) if not sub.empty else 0
        val = int((sub["estado_validacion"]=="Validada").sum())  if not sub.empty else 0
        rec = int((sub["estado_validacion"]=="Rechazada").sum()) if not sub.empty else 0
        ult = ""
        if not sub.empty and sub["creado_en"].notna().any():
            try:
                m = pd.to_datetime(sub["creado_en"], errors="coerce").max()
                ult = "" if pd.isna(m) else str(m)
            except: pass
        wsr.append_row([uid, uname, tot, pen, val, rec, ult])

# ========= Auth =========
def do_login():
    st.subheader("Ingreso (Solo Admin)")
    usuario = st.text_input("Usuario", placeholder="vperaza")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        dfu = df_usuarios()
        if dfu.empty: st.error("No hay usuarios."); return
        row = dfu[dfu["usuario"].astype(str).str.lower()==usuario.strip().lower()]
        if row.empty: st.error("Usuario no encontrado o inactivo."); return
        row = row.iloc[0]
        if not _as_bool(row.get("activo", True)): st.error("Usuario inactivo."); return
        if str(row["rol"]).lower()!="admin": st.error("Acceso solo admin."); return
        if hash_password(pwd) != str(row["password_hash"]): st.error("Contraseña incorrecta."); return
        st.session_state.auth = {"id":str(row["id"]), "nombre":row["nombre"], "usuario":row["usuario"], "rol":row["rol"]}
        # último acceso
        cell = ws_usuarios().find(str(row["id"])); 
        if cell: ws_usuarios().update_cell(cell.row, 8, iso_now())
        log("login_admin", row["usuario"], "OK"); st.rerun()

def logout_btn():
    with st.sidebar:
        st.caption(f"Conectada como **{st.session_state['auth']['nombre']}**")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("auth", None); st.rerun()

# ========= Vistas =========
def portada():
    st.title(APP_TITLE)
    st.info("Desde aquí Viviana **activa/inactiva usuarios** y **delegará tareas a múltiples usuarios**.\n"
            "Prioridad: **Alta=naranja**, **Media=rojo**, **Baja=verde**.")
    st.divider()

def view_usuarios():
    st.subheader("Usuarios (activar/inactivar)")
    dfu = df_usuarios()
    mostrar = dfu[["id","nombre","usuario","activo"]].sort_values("nombre")
    st.dataframe(mostrar, use_container_width=True, hide_index=True)

    sel = st.selectbox("Selecciona usuario", mostrar["nombre"].tolist())
    if st.button("Alternar activo/inactivo", use_container_width=True):
        w = ws_usuarios()
        recs = w.get_all_records()
        for i, r in enumerate(recs, start=2):
            if r.get("nombre")==sel:
                val = str(r.get("activo","TRUE")).upper()
                nuevo = "FALSE" if val in ("TRUE","1") else "TRUE"
                w.update_cell(i, 6, nuevo)
                st.success(f"{sel} -> {'Activo' if nuevo=='TRUE' else 'Inactivo'}")
                log("toggle_activo", st.session_state['auth']['usuario'], f"{sel} -> {nuevo}")
                break

def view_tareas(usuario_ctx: Dict):
    st.subheader("Delegar tareas a múltiples usuarios")

    dfu = df_usuarios()
    dfu_activos = dfu[(dfu["rol_norm"]=="user") & (dfu["activo_norm"])]
    lista = dfu_activos["nombre"].tolist()

    c1, c2 = st.columns(2)
    with c1:
        titulo = st.text_input("Título de la tarea")
        descripcion = st.text_area("Descripción / Instrucciones")
        prioridad = st.selectbox("Prioridad", PRIORIDADES, index=0)  # Alta por defecto
    with c2:
        asignados_nombres = st.multiselect("Asignar a (múltiples)", lista, default=["Charly"] if "Charly" in lista else None)
        fecha_lim = st.date_input("Fecha límite", value=date.today() + timedelta(days=3))

    if st.button("Crear y asignar", type="primary", use_container_width=True, disabled=not titulo.strip() or not asignados_nombres):
        w = ws_tareas()
        base = int(time.time()*1000)
        for nom in asignados_nombres:
            urow = dfu_activos[dfu_activos["nombre"]==nom].iloc[0]
            tid = f"T{base}-{urow['id']}"
            w.append_row([tid, titulo.strip(), descripcion.strip(), prioridad, "Nueva",
                          str(urow["id"]), urow["nombre"], iso_now(), str(fecha_lim),
                          usuario_ctx["usuario"], "", iso_now()])
        st.success(f"Creada(s) {len(asignados_nombres)} tarea(s).")
        log("crear_tareas", usuario_ctx["usuario"], f"{len(asignados_nombres)}")
    
    st.markdown("---")
    st.markdown("### Listado / Gestión")
    dft = df_tareas()
    # filtros
    f1,f2,f3,f4 = st.columns(4)
    with f1: f_estado = st.selectbox("Estado", ["(Todos)"]+ESTADOS_TAREA)
    with f2: f_prior  = st.selectbox("Prioridad", ["(Todas)"]+PRIORIDADES)
    with f3: f_user   = st.selectbox("Asignado", ["(Todos)"] + (sorted(dft["asignado_nombre"].unique()) if not dft.empty else []))
    with f4: solo_vig = st.checkbox("Solo no vencidas", value=False)

    data = dft.copy()
    if not data.empty:
        if f_estado!="(Todos)": data = data[data["estado"]==f_estado]
        if f_prior!="(Todas)":  data = data[data["prioridad"]==f_prior]
        if f_user!="(Todos)":   data = data[data["asignado_nombre"]==f_user]
        if solo_vig:
            data = data[pd.to_datetime(data["fecha_limite"], errors="coerce") >= pd.Timestamp(date.today())]

    if not data.empty:
        data = data.copy()
        data["prioridad_tag"] = data["prioridad"].apply(tag_prioridad_html)
        cols = ["task_id","titulo","prioridad_tag","estado","asignado_id","asignado_nombre","fecha_limite","fecha_asignacion"]
        st.write(data[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("Sin tareas.")

    st.markdown("#### Cambiar estado / Observación")
    tid = st.text_input("ID de tarea (task_id)")
    c1,c2,c3,c4 = st.columns(4)
    def _admin_set_estado(nvo):
        w = ws_tareas(); c = w.find(tid)
        if not c: st.error("No se encontró la tarea."); return
        w.update_cell(c.row, 5, nvo); w.update_cell(c.row, 12, iso_now())
        st.success("Estado actualizado."); log("tarea_estado", usuario_ctx["usuario"], f"{tid}->{nvo}")
    with c1:
        if st.button("Nueva", use_container_width=True, disabled=not tid.strip()): _admin_set_estado("Nueva")
    with c2:
        if st.button("En Progreso", use_container_width=True, disabled=not tid.strip()): _admin_set_estado("En Progreso")
    with c3:
        if st.button("Completada", use_container_width=True, disabled=not tid.strip()): _admin_set_estado("Completada")
    with c4:
        if st.button("Rechazada", use_container_width=True, disabled=not tid.strip()): _admin_set_estado("Rechazada")

    obs = st.text_area("Observación administrativa")
    if st.button("Guardar observación", disabled=not tid.strip()):
        w = ws_tareas(); c = w.find(tid)
        if not c: st.error("No se encontró la tarea.")
        else:
            w.update_cell(c.row, 11, obs); w.update_cell(c.row, 12, iso_now())
            st.success("Observación guardada."); log("tarea_obs", usuario_ctx["usuario"], tid)

def view_resumen():
    if st.button("Recalcular resumen"):
        actualizar_resumen(); st.success("Resumen actualizado.")
    st.dataframe(pd.DataFrame(ws_resumen().get_all_records()), use_container_width=True, hide_index=True)

# ========= Main =========
def main():
    seed_usuarios_si_vacio()
    mig = migrate_passwords_a_fijas()
    if mig: st.toast(f"{mig} contraseñas normalizadas.", icon="✅")

    portada()

    if "auth" not in st.session_state:
        do_login(); return

    logout_btn()
    user = st.session_state["auth"]

    vista = st.sidebar.radio("Secciones", ["Usuarios", "Tareas", "Resumen"])
    if vista == "Usuarios":   view_usuarios()
    elif vista == "Tareas":   view_tareas(user)
    else:                     view_resumen()

if __name__ == "__main__":
    main()


