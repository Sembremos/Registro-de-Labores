# =========================
# RLD – 2025 – App de Usuario (Charly) – con Google Sheets
# =========================
import time, hashlib
from datetime import datetime, date
from typing import Dict, List
import streamlit as st
import pandas as pd

# Google Sheets
import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="RLD – Charly", layout="wide")
APP_TITLE = "RLD – Charly (Usuario)"

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1LiHP1V5PMzt13yX_zgSeVFmZ7r-HM6PPEI5Ej46ziPk/edit?usp=sharing"

SHEET_USUARIOS   = "Usuarios"
SHEET_TAREAS     = "RLD_tareas"
SHEET_RESPUESTAS = "RLD_respuestas"
SHEET_LOGS       = "Logs"

TRABAJOS_CATALOGO = [
    "Patrullaje Preventivo","Atención de Incidencias","Charlas Comunitarias",
    "Reunión Interinstitucional","Operativo Focalizado","Apoyo a Otras Unidades",
    "Control de Vías","Tareas Administrativas"
]

def iso_now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def hash_password(p): return hashlib.sha256(p.encode("utf-8")).hexdigest()
def _as_bool(x): return str(x).strip().lower() in ("true","1","yes","si","sí")

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Faltan credenciales en st.secrets['gcp_service_account']."); st.stop()
    info=dict(st.secrets["gcp_service_account"])
    if isinstance(info.get("private_key"), str):
        info["private_key"]=info["private_key"].replace("\\n","\n").replace("\r\n","\n")
    st.session_state["_svc_email"]=info.get("client_email","desconocido")
    creds=Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    gc=get_gspread_client()
    key=SPREADSHEET_URL.split("/d/")[1].split("/")[0]
    try: return gc.open_by_key(key)
    except APIError: return gc.open_by_url(SPREADSHEET_URL)

def _ensure_ws(title: str, header: List[str]):
    sh=get_spreadsheet()
    try: ws=sh.worksheet(title)
    except WorksheetNotFound:
        ws=sh.add_worksheet(title=title, rows=2000, cols=max(len(header),12)); ws.append_row(header)
    vals=ws.get_all_values()
    if not vals: ws.append_row(header)
    return ws

def ws_usuarios():   return _ensure_ws(SHEET_USUARIOS, ["id","nombre","usuario","rol","password_hash","activo","creado_en","ultimo_acceso"])
def ws_tareas():
    ws=_ensure_ws(SHEET_TAREAS, ["tarea_id","titulo","descripcion","prioridad","estado","asignado_id","asignado_nombre","fecha_asignacion","fecha_limite","creado_por","observ_admin","ultima_actualizacion"])
    try:
        hdr=ws.row_values(1)
        if hdr and hdr[0].strip().lower()=="task_id":
            ws.update_cell(1,1,"tarea_id")
    except Exception: pass
    return ws
def ws_respuestas(): return _ensure_ws(SHEET_RESPUESTAS, ["uuid","tarea_id","usuario_id","usuario_nombre","fecha","hora","trabajo_realizado","localidad_delegacion","funcionario_responsable","observaciones","estado_validacion","observacion_admin","creado_en","editado_en","creado_por","editado_por"])
def ws_logs():       return _ensure_ws(SHEET_LOGS,       ["evento","quien","detalle","timestamp"])

def df_usuarios(): return pd.DataFrame(ws_usuarios().get_all_records())

def df_tareas():
    df=pd.DataFrame(ws_tareas().get_all_records())
    needed=["tarea_id","titulo","descripcion","prioridad","estado","asignado_id","asignado_nombre","fecha_asignacion","fecha_limite","creado_por","observ_admin","ultima_actualizacion"]
    for c in needed:
        if c not in df.columns: df[c]=""
    if "task_id" in df.columns and "tarea_id" not in df.columns:
        df=df.rename(columns={"task_id":"tarea_id"})
    df["tarea_id_num"]=pd.to_numeric(df.get("tarea_id"), errors="coerce")
    return df

def df_respuestas():
    df=pd.DataFrame(ws_respuestas().get_all_records())
    for c in ["usuario_id","tarea_id","uuid","usuario_nombre","fecha","hora","trabajo_realizado","localidad_delegacion","funcionario_responsable","observaciones","estado_validacion","observacion_admin","creado_en","editado_en","creado_por","editado_por"]:
        if c not in df.columns: df[c]=""
    if "task_id" in df.columns and "tarea_id" not in df.columns:
        df=df.rename(columns={"task_id":"tarea_id"})
    return df

def log(e,q,d): ws_logs().append_row([e,q,d,iso_now()])

def portada():
    st.title(APP_TITLE)
    st.info("Aquí Charly ve **sus tareas**, registra **labores** y cambia su **usuario/contraseña**.")

def do_login():
    st.subheader("Ingreso – Charly")
    st.caption("Usuario: **charly** (clave inicial: **charly2025**)")
    usuario=st.text_input("Usuario"); pwd=st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        dfu=df_usuarios()
        row=dfu[dfu["usuario"].astype(str).str.lower()==usuario.strip().lower()]
        if row.empty: st.error("Usuario no encontrado."); return
        row=row.iloc[0]
        if str(row.get("rol","")).lower()!="user": st.error("Solo usuarios tipo 'user'."); return
        if not _as_bool(row.get("activo", True)): st.error("Tu usuario está INACTIVO. Contacta a la administradora."); return
        if hash_password(pwd) != str(row.get("password_hash","")): st.error("Contraseña incorrecta."); return
        st.session_state.auth={"id":str(row["id"]),"nombre":row["nombre"],"usuario":row["usuario"],"rol":row["rol"]}
        w=ws_usuarios(); c=w.find(str(row["id"]))
        if c: w.update_cell(c.row,8,iso_now())
        log("login_user","charly","OK"); st.rerun()

def logout_btn():
    with st.sidebar:
        st.caption(f"Conectado como **{st.session_state['auth']['nombre']}**")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("auth",None); st.rerun()

def _tag_prioridad(p):
    p=(p or "").strip().title()
    color="#22c55e"
    if p=="Alta": color="#f59e0b"
    elif p=="Media": color="#ef4444"
    return f"<span style='background:{color};color:white;padding:2px 8px;border-radius:999px;font-size:12px'>{p}</span>"

def view_mis_tareas(user: Dict):
    st.subheader("Mis Tareas")
    dft=df_tareas()
    if dft.empty:
        st.info("No hay tareas aún."); return
    if "asignado_id" not in dft.columns:
        st.warning("La hoja de tareas no tiene columna 'asignado_id'. Avise a admin."); return
    mias=dft[dft["asignado_id"].astype(str)==str(user["id"])].copy()
    if mias.empty:
        st.warning("Aún no te han asignado tareas."); return

    mias["prioridad_tag"]=mias["prioridad"].apply(_tag_prioridad)
    st.write(mias[["tarea_id","titulo","prioridad_tag","estado","fecha_limite","fecha_asignacion"]].to_html(escape=False,index=False), unsafe_allow_html=True)

    st.markdown("### Cambiar estado")
    mias=mias.copy()
    mias["tarea_id_num"]=pd.to_numeric(mias["tarea_id"], errors="coerce")
    mias=mias.dropna(subset=["tarea_id_num"]).sort_values("tarea_id_num")

    opciones=[f"#{int(r.tarea_id_num)} — {r.titulo}" for _,r in mias.iterrows()]
    sel=st.selectbox("Selecciona una tarea", opciones) if opciones else ""
    sel_id=None
    if sel:
        try: sel_id=int(sel.split("—")[0].replace("#","").strip())
        except Exception: sel_id=None

    c1,c2,c3,c4=st.columns(4)
    def _set_estado(nvo):
        if sel_id is None: st.error("Selecciona una tarea válida."); return
        w=ws_tareas(); recs=w.get_all_records()
        for i,r in enumerate(recs,start=2):
            try:
                if int(pd.to_numeric(r.get("tarea_id"), errors="coerce"))==sel_id and str(r.get("asignado_id"))==str(user["id"]):
                    w.update_cell(i,5,nvo); w.update_cell(i,12,iso_now())
                    log("user_tarea_estado", user["usuario"], f"{sel_id}->{nvo}"); st.success("Estado actualizado."); return
            except Exception: pass
        st.error("No se encontró la tarea.")
    with c1:
        if st.button("Nueva", use_container_width=True): _set_estado("Nueva")
    with c2:
        if st.button("En Progreso", use_container_width=True): _set_estado("En Progreso")
    with c3:
        if st.button("Completada", use_container_width=True): _set_estado("Completada")
    with c4:
        if st.button("Rechazada", use_container_width=True): _set_estado("Rechazada")

def view_registro(user: Dict):
    st.subheader("Registrar Labor y Vincular a Tarea")
    dft=df_tareas()
    if "asignado_id" not in dft.columns:
        st.warning("La hoja de tareas no tiene columna 'asignado_id'. Avise a admin."); return
    mias=dft[dft["asignado_id"].astype(str)==str(user["id"])].copy()
    mias["tarea_id_num"]=pd.to_numeric(mias["tarea_id"], errors="coerce")
    mias=mias.dropna(subset=["tarea_id_num"]).sort_values("tarea_id_num")
    opciones=["(sin tarea)"]+[f"#{int(r.tarea_id_num)} — {r.titulo}" for _,r in mias.iterrows()]
    sel=st.selectbox("Tarea relacionada (opcional)", opciones)
    if sel=="(sin tarea)": sel_id=""
    else:
        try: sel_id=int(sel.split("—")[0].replace("#","").strip())
        except Exception: sel_id=""

    c1,c2=st.columns(2)
    with c1: f_fecha=st.date_input("Fecha", value=date.today())
    with c2: f_hora =st.time_input("Hora", value=datetime.now().time())
    trabajo=st.selectbox("Trabajo Realizado", TRABAJOS_CATALOGO)
    localidad=st.text_input("Localidad / Delegación")
    obs=st.text_area("Observaciones")

    if st.button("Guardar", type="primary", use_container_width=True):
        w=ws_respuestas()
        uid=f"rld-{int(time.time()*1000)}"
        w.append_row([uid, sel_id, user["id"], user["nombre"], str(f_fecha), str(f_hora),
                      trabajo, localidad, user["nombre"], obs, "Pendiente", "",
                      iso_now(), "", user["usuario"], ""])
        log("crear_respuesta", user["usuario"], f"{uid}")
        st.success("Registro guardado.")

def view_mis_labores(user: Dict):
    st.subheader("Mis Labores")
    dfr=df_respuestas()
    mine=dfr[dfr.get("usuario_id","").astype(str)==str(user["id"])] if not dfr.empty else pd.DataFrame()
    if mine.empty: st.info("Aún no has registrado labores.")
    else: st.dataframe(mine, use_container_width=True, hide_index=True)

def view_perfil(user: Dict):
    st.subheader("Mi Perfil")
    st.write(f"**Nombre:** {user['nombre']}  |  **Usuario actual:** `{user['usuario']}`")

    nuevo_usuario=st.text_input("Nuevo usuario (opcional)", placeholder="dejar vacío para no cambiar")
    pwd_actual=st.text_input("Contraseña actual", type="password")
    pwd_nueva =st.text_input("Nueva contraseña", type="password", help="Mínimo 6 caracteres.")
    pwd_conf  =st.text_input("Confirmar nueva contraseña", type="password")

    if st.button("Guardar cambios", type="primary"):
        dfu=df_usuarios(); row=dfu[dfu["usuario"].astype(str)==user["usuario"]]
        if row.empty: st.error("No se encontró el usuario."); return
        row=row.iloc[0]
        if hash_password(pwd_actual)!=str(row.get("password_hash","")):
            st.error("La contraseña actual es incorrecta."); return
        if pwd_nueva and len(pwd_nueva)<6:
            st.error("La nueva contraseña debe tener al menos 6 caracteres."); return
        if nuevo_usuario.strip():
            existe=dfu[dfu["usuario"].astype(str).str.lower()==nuevo_usuario.strip().lower()]
            if not existe.empty: st.error("Ese usuario ya existe."); return
        w=ws_usuarios(); cell=w.find(str(row["id"]))
        if not cell: st.error("No se pudo ubicar tu fila en la hoja."); return
        if nuevo_usuario.strip():
            w.update_cell(cell.row,3,nuevo_usuario.strip()); st.session_state.auth["usuario"]=nuevo_usuario.strip()
        if pwd_nueva and pwd_nueva==pwd_conf:
            w.update_cell(cell.row,5,hash_password(pwd_nueva))
        elif pwd_nueva or pwd_conf:
            st.error("La confirmación no coincide."); return
        log("user_update_profile", user["usuario"], "OK")
        st.success("Cambios guardados.")

def main():
    portada()
    if "auth" not in st.session_state:
        do_login(); return
    user=st.session_state["auth"]; logout_btn()

    vista=st.sidebar.radio("Secciones", ["Mis Tareas","Registrar Labor","Mis Labores","Mi Perfil"])
    if vista=="Mis Tareas":        view_mis_tareas(user)
    elif vista=="Registrar Labor": view_registro(user)
    elif vista=="Mis Labores":     view_mis_labores(user)
    else:                          view_perfil(user)

if __name__=="__main__":
    main()




