# =========================
# RLD – 2025 (Google Sheets) – APP ADMIN (VIVIANA)
# =========================
import time, hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict
import streamlit as st
import pandas as pd

# Google Sheets
import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="RLD 2025 – Admin (Sheets)", layout="wide")
APP_TITLE = "REGISTRO DE LABORES DIARIAS – Admin"

# === TU SPREADSHEET ===
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

# ---------- Nombres de hojas ----------
SHEET_USUARIOS   = "Usuarios"
SHEET_TAREAS     = "RLD_tareas"
SHEET_RESPUESTAS = "RLD_respuestas"
SHEET_RESUMEN    = "RLD_por_usuario"
SHEET_LOGS       = "Logs"

PRIORIDADES   = ["Alta","Media","Baja"]            # Alta=naranja, Media=rojo, Baja=verde
ESTADOS_TAREA = ["Nueva","En Progreso","Completada","Rechazada"]

# ========= Utilidades =========
def iso_now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def hash_password(p): return hashlib.sha256(p.encode("utf-8")).hexdigest()
def _as_bool(x): return str(x).strip().lower() in ("true","1","yes","si","sí")
def _tag_prioridad(p: str) -> str:
    p = (p or "").strip().title()
    color = "#22c55e"           # verde = Baja
    if p == "Alta":  color = "#f59e0b"   # naranja = máxima
    if p == "Media": color = "#ef4444"   # rojo = urge
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
        return gc.open_by_url(SPREADSHEET_URL)

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

def ws_usuarios():   return _ensure_ws(SHEET_USUARIOS,   ["id","nombre","usuario","rol","password_hash","activo","creado_en","ultimo_acceso"])

def ws_tareas():
    header = ["tarea_id","titulo","descripcion","prioridad","estado","asignado_id",
              "asignado_nombre","fecha_asignacion","fecha_limite","creado_por",
              "observ_admin","ultima_actualizacion"]
    ws = _ensure_ws(SHEET_TAREAS, header)
    # migrar encabezado si quedó "task_id"
    try:
        hdr = ws.row_values(1)
        if hdr and len(hdr) >= 1 and hdr[0].strip().lower() == "task_id":
            ws.update_cell(1, 1, "tarea_id")
    except Exception:
        pass
    return ws

def ws_respuestas(): return _ensure_ws(SHEET_RESPUESTAS, ["uuid","tarea_id","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado","localidad_delegacion","funcionario_responsable","observaciones","estado_validacion","observacion_admin","creado_en","editado_en","creado_por","editado_por"])
def ws_resumen():    return _ensure_ws(SHEET_RESUMEN,    ["usuario_id","usuario_nombre","total","pendientes","validadas","rechazadas","ultima_actividad"])
def ws_logs():       return _ensure_ws(SHEET_LOGS,       ["evento","quien","detalle","timestamp"])

# ========= DataFrames =========
def df_usuarios():
    recs = ws_usuarios().get_all_records()
    df = pd.DataFrame(recs) if recs else pd.DataFrame(columns=["id","nombre","usuario","rol","password_hash","activo","creado_en","ultimo_acceso"])
    if not df.empty:
        df["rol_norm"] = df["rol"].astype(str).str.lower()
        df["activo_norm"] = df["activo"].apply(_as_bool)
    return df

def df_tareas():
    recs = ws_tareas().get_all_records()
    df = pd.DataFrame(recs) if recs else pd.DataFrame(columns=[
        "tarea_id","titulo","descripcion","prioridad","estado","asignado_id",
        "asignado_nombre","fecha_asignacion","fecha_limite","creado_por",
        "observ_admin","ultima_actualizacion"
    ])
    if "task_id" in df.columns and "tarea_id" not in df.columns:
        df = df.rename(columns={"task_id":"tarea_id"})
    df["tarea_id_num"] = pd.to_numeric(df.get("tarea_id"), errors="coerce")
    return df

def df_respuestas():
    recs = ws_respuestas().get_all_records()
    df = pd.DataFrame(recs) if recs else pd.DataFrame(columns=[
        "uuid","tarea_id","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado",
        "localidad_delegacion","funcionario_responsable","observaciones","estado_validacion",
        "observacion_admin","creado_en","editado_en","creado_por","editado_por"
    ])
    if "task_id" in df.columns and "tarea_id" not in df.columns:
        df = df.rename(columns={"task_id":"tarea_id"})
    return df

def log(evento, quien, detalle): ws_logs().append_row([evento, quien, detalle, iso_now()])

# ========= Seed/Migración =========
def seed_usuarios_si_vacio():
    ws = ws_usuarios()
    if ws.get_all_records(): return False
    for (id_, nombre, usuario, rol) in USUARIOS_INICIALES:
        ws.append_row([id_, nombre, usuario, rol, hash_password(PASSWORDS_FIJAS[usuario]), True, iso_now(), ""])
    log("seed_usuarios","sistema","OK")
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
                ws.update_cell(i, 5, nuevo); actualizados += 1
    if actualizados: log("migracion_passwords","sistema",f"{actualizados}")
    return actualizados

def migrate_tarea_ids():
    """Asigna IDs numéricos a tareas que no los tengan."""
    df = df_tareas()
    if df.empty:
        return 0
    ws = ws_tareas()
    recs = ws.get_all_records()
    usados = set(int(x) for x in pd.to_numeric(df["tarea_id"], errors="coerce").dropna().astype(int).tolist())
    next_id = 1
    asignados = 0
    for i, r in enumerate(recs, start=2):
        cur = pd.to_numeric(r.get("tarea_id"), errors="coerce")
        if pd.isna(cur):
            while next_id in usados:
                next_id += 1
            ws.update_cell(i, 1, next_id)
            usados.add(next_id)
            asignados += 1
    return asignados

# === Secuenciador de nuevos IDs ===
def next_tarea_id() -> int:
    df = df_tareas()
    if df.empty or df["tarea_id_num"].dropna().empty:
        return 1
    return int(df["tarea_id_num"].max()) + 1

# ========= Auth =========
def do_login():
    st.subheader("Ingreso (Solo Admin)")
    usuario = st.text_input("Usuario (p.ej. vperaza)")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        dfu = df_usuarios()
        row = dfu[dfu["usuario"].astype(str).str.lower()==usuario.strip().lower()]
        if row.empty: st.error("Usuario no encontrado."); return
        row = row.iloc[0]
        if not _as_bool(row.get("activo", True)): st.error("Usuario inactivo."); return
        if str(row["rol"]).lower()!="admin": st.error("Acceso solo admin."); return
        if hash_password(pwd) != str(row.get("password_hash","")): st.error("Contraseña incorrecta."); return
        st.session_state.auth = {"id":str(row["id"]), "nombre":row["nombre"], "usuario":row["usuario"], "rol":row["rol"]}
        w = ws_usuarios(); c = w.find(str(row["id"])); 
        if c: w.update_cell(c.row, 8, iso_now())
        log("login_admin", row["usuario"], "OK"); st.rerun()

def logout_btn():
    with st.sidebar:
        st.caption(f"Conectada como **{st.session_state['auth']['nombre']}**")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("auth", None); st.rerun()

# ========= Mi Perfil (Admin) =========
def view_perfil_admin(user: Dict):
    st.subheader("Mi Perfil (Admin)")
    st.write(f"**Nombre:** {user['nombre']}  |  **Usuario:** `{user['usuario']}`  |  **Rol:** `{user['rol']}`")

    pwd_actual = st.text_input("Contraseña actual", type="password")
    pwd_nueva  = st.text_input("Nueva contraseña", type="password", help="Mínimo 6 caracteres.")
    pwd_conf   = st.text_input("Confirmar nueva contraseña", type="password")

    if st.button("Actualizar contraseña", type="primary"):
        if len(pwd_nueva) < 6:
            st.error("La nueva contraseña debe tener al menos 6 caracteres."); return
        if pwd_nueva != pwd_conf:
            st.error("La confirmación no coincide."); return
        dfu = df_usuarios()
        row = dfu[dfu["usuario"].astype(str) == user["usuario"]]
        if row.empty:
            st.error("No se encontró el usuario."); return
        row = row.iloc[0]
        if hash_password(pwd_actual) != str(row.get("password_hash","")):
            st.error("La contraseña actual es incorrecta."); return
        w = ws_usuarios(); cell = w.find(str(row["id"]))
        if not cell:
            st.error("No se pudo ubicar el registro del usuario en la hoja."); return
        w.update_cell(cell.row, 5, hash_password(pwd_nueva))
        log("admin_cambio_password", user["usuario"], "OK")
        st.success("Contraseña actualizada. Vuelve a iniciar sesión si deseas.")

# ========= Vistas =========
def portada():
    st.title(APP_TITLE)
    st.info("Viviana **activa/inactiva usuarios**, **crea** tareas con **ID incremental** (1,2,3…), "
            "**edita**, **elimina**, cambia **estado** y agrega **observación**.\n"
            "Prioridad: **Alta=naranja**, **Media=rojo**, **Baja=verde**.")
    st.divider()

def view_usuarios():
    st.subheader("Usuarios (activar/inactivar)")
    dfu = df_usuarios()
    mostrar = dfu[["id","nombre","usuario","activo"]].sort_values("nombre")
    st.dataframe(mostrar, use_container_width=True, hide_index=True)

    sel = st.selectbox("Selecciona usuario", mostrar["nombre"].tolist())
    if st.button("Alternar activo/inactivo", use_container_width=True):
        w = ws_usuarios(); recs = w.get_all_records()
        for i, r in enumerate(recs, start=2):
            if r.get("nombre")==sel:
                val = str(r.get("activo","TRUE")).upper()
                nuevo = "FALSE" if val in ("TRUE","1") else "TRUE"
                w.update_cell(i, 6, nuevo)
                st.success(f"{sel} -> {'Activo' if nuevo=='TRUE' else 'Inactivo'}")
                log("toggle_activo", st.session_state['auth']['usuario'], f"{sel}:{nuevo}")
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
        base_id = next_tarea_id()
        created = 0
        for idx, nom in enumerate(asignados_nombres):
            u = dfu_activos[dfu_activos["nombre"]==nom].iloc[0]
            tid = base_id + idx
            w.append_row([tid, titulo.strip(), descripcion.strip(), prioridad, "Nueva",
                          str(u["id"]), u["nombre"], iso_now(), str(fecha_lim),
                          usuario_ctx["usuario"], "", iso_now()])
            created += 1
        st.success(f"Se crearon {created} tareas (IDs desde #{base_id}).")
        log("crear_tareas", usuario_ctx["usuario"], f"{created}")

    st.markdown("---")
    st.markdown("### Listado / Gestión")
    dft = df_tareas()

    f1,f2,f3,f4 = st.columns(4)
    with f1: f_estado = st.selectbox("Estado", ["(Todos)"]+ESTADOS_TAREA)
    with f2: f_prior  = st.selectbox("Prioridad", ["(Todas)"]+PRIORIDADES)
    with f3: f_user   = st.selectbox("Asignado", ["(Todos)"] + (sorted(dft["asignado_nombre"].dropna().unique()) if not dft.empty else []))
    with f4: q_titulo = st.text_input("Buscar por título", "")

    data = dft.copy()
    if not data.empty:
        if f_estado!="(Todos)": data = data[data["estado"]==f_estado]
        if f_prior!="(Todas)":  data = data[data["prioridad"]==f_prior]
        if f_user!="(Todos)":   data = data[data["asignado_nombre"]==f_user]
        if q_titulo.strip():    data = data[data["titulo"].astype(str).str.contains(q_titulo.strip(), case=False, na=False)]

    if not data.empty:
        data = data.copy()
        data["prioridad_tag"] = data["prioridad"].apply(_tag_prioridad)
        cols = ["tarea_id","titulo","prioridad_tag","estado","asignado_nombre","fecha_limite","fecha_asignacion"]
        st.write(data[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("Sin tareas.")

    st.markdown("#### Editar / Eliminar / Estado / Observación")
    # Selector amigable por título (robusto a IDs vacíos)
    opciones = []
    if not dft.empty:
        dft_sorted = dft.dropna(subset=["tarea_id_num"]).sort_values("tarea_id_num")
        opciones = [f"#{int(r.tarea_id_num)} — {r.titulo} — {r.asignado_nombre}" for _, r in dft_sorted.iterrows()]

    sel_opt = st.selectbox("Selecciona una tarea", opciones) if opciones else ""
    sugerido = int(dft["tarea_id_num"].max() + 1) if not dft.empty and not dft["tarea_id_num"].dropna().empty else 1
    tarea_id_input = st.number_input("…o escribe el ID (#)", min_value=1, value=sugerido, step=1)
    def _resolver_id():
        if sel_opt:
            try:
                return int(sel_opt.split("—")[0].replace("#","").strip())
            except Exception:
                pass
        return int(tarea_id_input)

    c1,c2,c3,c4 = st.columns(4)
    with c1:
        if st.button("Nueva", use_container_width=True, disabled=dft.empty):
            _admin_set_estado(_resolver_id(), "Nueva", usuario_ctx)
    with c2:
        if st.button("En Progreso", use_container_width=True, disabled=dft.empty):
            _admin_set_estado(_resolver_id(), "En Progreso", usuario_ctx)
    with c3:
        if st.button("Completada", use_container_width=True, disabled=dft.empty):
            _admin_set_estado(_resolver_id(), "Completada", usuario_ctx)
    with c4:
        if st.button("Rechazada", use_container_width=True, disabled=dft.empty):
            _admin_set_estado(_resolver_id(), "Rechazada", usuario_ctx)

    st.markdown("##### Editar campos")
    with st.form("editar_tarea"):
        et_titulo = st.text_input("Título")
        et_desc   = st.text_area("Descripción")
        et_prior  = st.selectbox("Prioridad", PRIORIDADES)
        et_user   = st.selectbox("Asignado a", dfu[(dfu["rol_norm"]=="user") & (dfu["activo_norm"])]["nombre"].tolist())
        et_flim   = st.date_input("Fecha límite", value=date.today()+timedelta(days=3))
        enviado = st.form_submit_button("Guardar cambios en tarea seleccionada", use_container_width=True, disabled=dft.empty)
    if enviado:
        _admin_editar_tarea(_resolver_id(), et_titulo, et_desc, et_prior, et_user, et_flim, usuario_ctx)

    st.markdown("##### Eliminar")
    if st.button("Eliminar tarea seleccionada", disabled=dft.empty, type="secondary"):
        _admin_eliminar_tarea(_resolver_id(), usuario_ctx)

    st.markdown("##### Observación administrativa")
    obs = st.text_area("Observación")
    if st.button("Guardar observación", disabled=dft.empty):
        _admin_guardar_observacion(_resolver_id(), obs, usuario_ctx)

def _admin_set_estado(tid: int, nuevo: str, usuario_ctx: Dict):
    w = ws_tareas(); recs = w.get_all_records()
    for i, r in enumerate(recs, start=2):
        try:
            if int(pd.to_numeric(r.get("tarea_id"), errors="coerce")) == int(tid):
                w.update_cell(i, 5, nuevo)      # estado
                w.update_cell(i, 12, iso_now()) # ultima_actualizacion
                st.success("Estado actualizado.")
                log("tarea_estado", usuario_ctx["usuario"], f"{tid}->{nuevo}")
                return
        except Exception:
            pass
    st.error("No se encontró la tarea.")

def _admin_guardar_observacion(tid: int, texto: str, usuario_ctx: Dict):
    w = ws_tareas(); recs = w.get_all_records()
    for i, r in enumerate(recs, start=2):
        try:
            if int(pd.to_numeric(r.get("tarea_id"), errors="coerce")) == int(tid):
                w.update_cell(i, 11, texto)     # observ_admin
                w.update_cell(i, 12, iso_now())
                st.success("Observación guardada.")
                log("tarea_obs", usuario_ctx["usuario"], f"{tid}")
                return
        except Exception:
            pass
    st.error("No se encontró la tarea.")

def _admin_editar_tarea(tid: int, titulo: str, desc: str, prior: str, asignado_nombre: str, fecha_limite: date, usuario_ctx: Dict):
    dfu = df_usuarios()
    rowu = dfu[(dfu["nombre"]==asignado_nombre) & (dfu["rol_norm"]=="user") & (dfu["activo_norm"])]
    if rowu.empty:
        st.error("Usuario destino inválido o inactivo.")
        return
    asig = rowu.iloc[0]
    w = ws_tareas(); recs = w.get_all_records()
    for i, r in enumerate(recs, start=2):
        try:
            if int(pd.to_numeric(r.get("tarea_id"), errors="coerce")) == int(tid):
                w.update(f"A{i}:L{i}", [[
                    tid, titulo.strip(), desc.strip(), prior, r.get("estado","Nueva"),
                    str(asig["id"]), asig["nombre"], r.get("fecha_asignacion", iso_now()), str(fecha_limite),
                    usuario_ctx["usuario"], r.get("observ_admin",""), iso_now()
                ]])
                st.success("Tarea actualizada.")
                log("tarea_editar", usuario_ctx["usuario"], f"{tid}")
                return
        except Exception:
            pass
    st.error("No se encontró la tarea.")

def _admin_eliminar_tarea(tid: int, usuario_ctx: Dict):
    w = ws_tareas(); recs = w.get_all_records()
    for i, r in enumerate(recs, start=2):
        try:
            if int(pd.to_numeric(r.get("tarea_id"), errors="coerce")) == int(tid):
                w.delete_rows(i)
                st.success("Tarea eliminada.")
                log("tarea_eliminar", usuario_ctx["usuario"], f"{tid}")
                return
        except Exception:
            pass
    st.error("No se encontró la tarea.")

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

# ========= Main =========
def main():
    seed_usuarios_si_vacio()
    mig = migrate_passwords_a_fijas()
    if mig: st.toast(f"{mig} contraseñas normalizadas.", icon="✅")
    mig_ids = migrate_tarea_ids()
    if mig_ids: st.toast(f"Normalicé {mig_ids} tarea(s) sin ID.", icon="🧩")

    portada()

    if "auth" not in st.session_state:
        do_login(); return
    logout_btn()
    user = st.session_state["auth"]

    vista = st.sidebar.radio("Secciones", ["Usuarios", "Tareas", "Resumen", "Mi Perfil"])
    if vista == "Usuarios":   view_usuarios()
    elif vista == "Tareas":   view_tareas(user)
    elif vista == "Resumen":  st.dataframe(pd.DataFrame(ws_resumen().get_all_records()), use_container_width=True, hide_index=True)
    else:                     view_perfil_admin(user)

if __name__ == "__main__":
    main()






