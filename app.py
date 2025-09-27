# =========================
# RLD 2025 – APP PRINCIPAL (VIVIANA) – SIN SHEETS (MEMORIA + JSON)
# =========================
import json, time, hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict
import streamlit as st
import pandas as pd

st.set_page_config(page_title="RLD 2025 – Viviana (Pruebas)", layout="wide")
APP_TITLE = "REGISTRO DE LABORES DIARIAS 2025 – Viviana (Pruebas sin Sheets)"

# ---------- Utilidades ----------
def iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def _as_bool(x) -> bool:
    return str(x).strip().lower() in ("true", "1", "yes", "si", "sí")

def _usuarios_activos_y_users(dfu: pd.DataFrame) -> pd.DataFrame:
    if dfu.empty:
        return dfu
    df = dfu.copy()
    df["rol_norm"] = df["rol"].astype(str).str.strip().str.lower()
    df["activo_norm"] = df["activo"].apply(_as_bool)
    return df[(df["rol_norm"] == "user") & (df["activo_norm"] == True)]

# ---------- Datos base en memoria ----------
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
PASSWORDS_FIJAS = {
    "jeremy":"jeremy2025","jannia":"jannia2025","manfred":"manfred2025","luis":"luis2025",
    "adrian":"adrian2025","esteban":"esteban2025","pamela":"pamela2025","carlos":"carlos2025",
    "charly":"charly2025","vperaza":"viviana2025"
}
TRABAJOS_CATALOGO = [
    "Patrullaje Preventivo","Atención de Incidencias","Charlas Comunitarias",
    "Reunión Interinstitucional","Operativo Focalizado","Apoyo a Otras Unidades",
    "Control de Vías","Tareas Administrativas"
]

def _ensure_memory():
    if "MEM_USERS" not in st.session_state:
        st.session_state.MEM_USERS = [
            dict(id=i, nombre=n, usuario=u, rol=r, password_hash=hash_password(PASSWORDS_FIJAS[u]),
                 activo=True, creado_en=iso_now(), ultimo_acceso="")
            for (i,n,u,r) in USUARIOS_INICIALES
        ]
    if "MEM_TASKS" not in st.session_state:
        st.session_state.MEM_TASKS = []   # dict(task_id,titulo,descripcion,prioridad,estado,asignado_id,asignado_nombre,fecha_asignacion,fecha_limite,creado_por,observ_admin,ultima_actualizacion)
    if "MEM_RESP" not in st.session_state:
        st.session_state.MEM_RESP = []    # dict(uuid,task_id,usuario_id,usuario_nombre,fecha,hora,trabajo_realizado,localidad,funcionario_responsable,observaciones,estado_validacion,observ_admin,creado_en,editado_en,creado_por,editado_por)
_ensure_memory()

def df_usuarios() -> pd.DataFrame:
    return pd.DataFrame(st.session_state.MEM_USERS)

def df_tareas() -> pd.DataFrame:
    return pd.DataFrame(st.session_state.MEM_TASKS)

def df_respuestas() -> pd.DataFrame:
    return pd.DataFrame(st.session_state.MEM_RESP)

# ---------- Auth admin ----------
def do_login():
    st.subheader("Ingreso (Solo Admin)")
    u = st.text_input("Usuario", placeholder="vperaza")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        dfu = df_usuarios()
        row = dfu[dfu["usuario"].str.lower()==u.strip().lower()]
        if row.empty: st.error("Usuario no encontrado."); return
        row = row.iloc[0]
        if row["rol"]!="admin": st.error("Acceso solo para admin."); return
        if not row["activo"]: st.error("Usuario inactivo."); return
        if hash_password(p)!=row["password_hash"]: st.error("Contraseña incorrecta."); return
        st.session_state.auth = dict(id=row["id"], nombre=row["nombre"], usuario=row["usuario"], rol=row["rol"])
        # marca acceso
        for usr in st.session_state.MEM_USERS:
            if usr["id"]==row["id"]:
                usr["ultimo_acceso"]=iso_now()
        st.rerun()

def logout_btn():
    with st.sidebar:
        st.caption(f"Conectada como **{st.session_state['auth']['nombre']}** (admin)")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("auth", None); st.rerun()

# ---------- Vistas ----------
def portada():
    st.title(APP_TITLE)
    st.info("Pruebas **sin Google Sheets**. Los datos viven en memoria. "
            "Puedes descargar las tareas en JSON para importarlas en la app de **Charly**.")
    st.divider()

def view_admin_usuarios():
    st.subheader("Usuarios (memoria)")
    dfu = df_usuarios()
    st.dataframe(dfu, use_container_width=True, hide_index=True)

    st.markdown("**Acciones rápidas**")
    c1, c2 = st.columns(2)
    with c1:
        uid = st.text_input("ID para alternar activo/inactivo")
        if st.button("Alternar activo", use_container_width=True):
            ok=False
            for usr in st.session_state.MEM_USERS:
                if usr["id"]==uid:
                    usr["activo"]=not bool(usr["activo"]); ok=True
                    st.success(f"Usuario {usr['nombre']}: activo={usr['activo']}")
                    break
            if not ok: st.error("ID no hallado")
    with c2:
        uid2 = st.text_input("ID para resetear a contraseña fija")
        if st.button("Reset a contraseña fija", use_container_width=True):
            ok=False
            for usr in st.session_state.MEM_USERS:
                if usr["id"]==uid2:
                    usrname = usr["usuario"]
                    usr["password_hash"]=hash_password(PASSWORDS_FIJAS[usrname])
                    ok=True; st.success(f"Reseteada a clave fija de {usrname}")
                    break
            if not ok: st.error("ID no hallado")

def view_admin_tareas():
    st.subheader("Delegar Tareas (memoria)")
    dfu = df_usuarios()
    dfu_activos = _usuarios_activos_y_users(dfu)
    opciones_nombres = dfu_activos["nombre"].tolist()
    # default: Charly si existe
    idx = opciones_nombres.index("Charly") if "Charly" in opciones_nombres else 0 if opciones_nombres else 0

    col = st.columns(2)
    with col[0]:
        titulo = st.text_input("Título de la tarea")
        descripcion = st.text_area("Descripción / Instrucciones")
        prioridad = st.selectbox("Prioridad", ["Alta","Media","Baja"], index=1)
    with col[1]:
        persona = st.selectbox("Asignar a", opciones_nombres or ["(sin usuarios)"], index=idx if opciones_nombres else 0)
        fecha_lim = st.date_input("Fecha límite", value=date.today()+timedelta(days=3))

    if st.button("Crear y asignar tarea", type="primary", use_container_width=True, disabled=not (titulo.strip() and opciones_nombres)):
        asig_row = dfu_activos[dfu_activos["nombre"]==persona].iloc[0]
        tid = f"T{int(time.time()*1000)}"
        st.session_state.MEM_TASKS.append(dict(
            task_id=tid, titulo=titulo, descripcion=descripcion, prioridad=prioridad, estado="Nueva",
            asignado_id=str(asig_row["id"]), asignado_nombre=asig_row["nombre"],
            fecha_asignacion=iso_now(), fecha_limite=str(fecha_lim),
            creado_por=st.session_state['auth']['usuario'], observ_admin="", ultima_actualizacion=iso_now()
        ))
        st.success(f"Tarea **{tid}** creada para **{asig_row['nombre']}**.")

    st.markdown("### Listado / Gestión")
    dft = df_tareas()
    if dft.empty:
        st.info("Sin tareas aún.")
    else:
        f1, f2, f3 = st.columns(3)
        with f1: e = st.selectbox("Estado", ["(Todos)","Nueva","En Progreso","Completada","Rechazada"])
        with f2: u = st.selectbox("Asignado", ["(Todos)"] + dft["asignado_nombre"].unique().tolist())
        with f3: solo_no_venc = st.checkbox("Solo no vencidas", value=False)

        data = dft.copy()
        if e!="(Todos)": data = data[data["estado"]==e]
        if u!="(Todos)": data = data[data["asignado_nombre"]==u]
        if solo_no_venc:
            data = data[pd.to_datetime(data["fecha_limite"], errors="coerce")>=pd.Timestamp(date.today())]
        st.dataframe(data, use_container_width=True, hide_index=True)

        st.markdown("#### Cambiar estado / Observación")
        tid = st.text_input("ID de tarea (task_id)")
        c1,c2,c3,c4 = st.columns(4)
        def _set_estado(nuevo):
            for t in st.session_state.MEM_TASKS:
                if t["task_id"]==tid:
                    t["estado"]=nuevo; t["ultima_actualizacion"]=iso_now()
                    st.success("Estado actualizado."); break
            else: st.error("task_id no hallado.")
        with c1:
            if st.button("Nueva", use_container_width=True, disabled=not tid.strip()): _set_estado("Nueva")
        with c2:
            if st.button("En Progreso", use_container_width=True, disabled=not tid.strip()): _set_estado("En Progreso")
        with c3:
            if st.button("Completada", use_container_width=True, disabled=not tid.strip()): _set_estado("Completada")
        with c4:
            if st.button("Rechazada", use_container_width=True, disabled=not tid.strip()): _set_estado("Rechazada")

        obs = st.text_area("Observación administrativa")
        if st.button("Guardar observación", disabled=not tid.strip()):
            for t in st.session_state.MEM_TASKS:
                if t["task_id"]==tid:
                    t["observ_admin"]=obs; t["ultima_actualizacion"]=iso_now()
                    st.success("Observación guardada."); break
            else: st.error("task_id no hallado.")

    st.markdown("---")
    st.markdown("### Exportar / Importar (para compartir con la app de Charly)")
    colx = st.columns(2)
    with colx[0]:
        tasks_json = json.dumps(st.session_state.MEM_TASKS, ensure_ascii=False, indent=2)
        st.download_button("⬇️ Descargar tareas (JSON)", tasks_json, file_name="tareas.json")
    with colx[1]:
        up = st.file_uploader("Cargar tareas (JSON)", type=["json"])
        if up:
            try:
                st.session_state.MEM_TASKS = json.loads(up.read().decode("utf-8"))
                st.success("Tareas importadas.")
            except Exception as e:
                st.error(f"JSON inválido: {e}")

def view_admin_resumen():
    st.subheader("Resumen simple")
    dfr = df_respuestas()
    if dfr.empty:
        st.info("No hay registros aún.")
        return
    agg = dfr.groupby(["usuario_nombre","estado_validacion"]).size().reset_index(name="conteo")
    st.dataframe(agg, use_container_width=True, hide_index=True)

# ---------- Main ----------
def main():
    portada()
    if "auth" not in st.session_state:
        do_login(); return
    logout_btn()

    vista = st.sidebar.radio("Secciones", ["Usuarios","Tareas","Resumen"])
    if vista=="Usuarios":  view_admin_usuarios()
    elif vista=="Tareas":  view_admin_tareas()
    else:                  view_admin_resumen()

if __name__ == "__main__":
    main()







