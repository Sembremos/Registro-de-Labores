# =========================
# RLD – 2025 (Versión local de pruebas) – APP ADMIN (VIVIANA)
# =========================

import json, time
from datetime import datetime, date, timedelta
from typing import List, Dict
import streamlit as st
import pandas as pd

st.set_page_config(page_title="RLD 2025 – Admin (Local)", layout="wide")
APP_TITLE = "REGISTRO DE LABORES DIARIAS – Admin (Local / Pruebas)"

# ----------------- Datos base en memoria (sin Sheets) -----------------
USUARIOS_INICIALES = [
    {"id": "001", "nombre": "Jeremy",  "usuario": "jeremy",  "rol": "user",  "activo": True},
    {"id": "002", "nombre": "Jannia",  "usuario": "jannia",  "rol": "user",  "activo": True},
    {"id": "003", "nombre": "Manfred", "usuario": "manfred", "rol": "user",  "activo": True},
    {"id": "004", "nombre": "Luis",    "usuario": "luis",    "rol": "user",  "activo": True},
    {"id": "005", "nombre": "Adrian",  "usuario": "adrian",  "rol": "user",  "activo": True},
    {"id": "006", "nombre": "Esteban", "usuario": "esteban", "rol": "user",  "activo": True},
    {"id": "007", "nombre": "Pamela",  "usuario": "pamela",  "rol": "user",  "activo": True},
    {"id": "009", "nombre": "Viviana Peraza", "usuario": "vperaza", "rol": "admin", "activo": True},
    {"id": "010", "nombre": "Charly",  "usuario": "charly",  "rol": "user",  "activo": True},
]

PRIORIDADES = ["Alta","Media","Baja"]          # Alta=naranja, Media=rojo, Baja=verde
ESTADOS_TAREA = ["Nueva","En Progreso","Completada","Rechazada"]

def iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _init_state():
    if "usuarios" not in st.session_state:
        st.session_state.usuarios = json.loads(json.dumps(USUARIOS_INICIALES))
    if "tareas" not in st.session_state:
        st.session_state.tareas: List[Dict] = []

_init_state()

# ----------------- UI helpers -----------------
def tag_prioridad_html(p: str) -> str:
    p = (p or "").strip().title()
    color = "#22c55e"  # verde para Baja
    if p == "Alta":
        color = "#f59e0b"  # naranja
    elif p == "Media":
        color = "#ef4444"  # rojo
    return f"<span style='background:{color};color:white;padding:2px 8px;border-radius:999px;font-size:12px'>{p}</span>"

def df_tareas_coloreado(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    df = df.copy()
    df["prioridad_tag"] = df["prioridad"].apply(tag_prioridad_html)
    cols = ["task_id","titulo","prioridad_tag","estado","asignado_id","asignado_nombre","fecha_limite","fecha_asignacion"]
    return df.reindex(columns=[c for c in cols if c in df.columns])

def crear_tareas_multiples(titulo: str, descripcion: str, prioridad: str, asignados: List[Dict], fecha_limite: date, creado_por: str):
    base = int(time.time()*1000)
    nuevas = []
    for u in asignados:
        tid = f"T{base}-{u['id']}"
        nuevas.append({
            "task_id": tid,
            "titulo": titulo.strip(),
            "descripcion": descripcion.strip(),
            "prioridad": prioridad,
            "estado": "Nueva",
            "asignado_id": u["id"],
            "asignado_nombre": u["nombre"],
            "fecha_asignacion": iso_now(),
            "fecha_limite": str(fecha_limite),
            "creado_por": creado_por,
            "observ_admin": "",
            "ultima_actualizacion": iso_now(),
        })
    st.session_state.tareas.extend(nuevas)
    return nuevas

def cambiar_estado_tarea(tid: str, nuevo: str):
    for t in st.session_state.tareas:
        if t["task_id"] == tid:
            t["estado"] = nuevo
            t["ultima_actualizacion"] = iso_now()
            return True
    return False

def guardar_observacion_tarea(tid: str, texto: str):
    for t in st.session_state.tareas:
        if t["task_id"] == tid:
            t["observ_admin"] = texto
            t["ultima_actualizacion"] = iso_now()
            return True
    return False

# ----------------- Vistas -----------------
def portada():
    st.title(APP_TITLE)
    st.info(
        "Versión **local** sin conexión a Google Sheets.\n\n"
        "- **Usuarios**: el administrador solo **activa/inactiva** usuarios.\n"
        "- **Tareas**: delega una tarea a **múltiples usuarios** y visualiza prioridades con **colores**:\n"
        "  - **Naranja** = *Alta* (máxima)\n"
        "  - **Rojo** = *Media* (urge)\n"
        "  - **Verde** = *Baja* (no tanta prioridad)\n"
        "- **Exportar/Importar**: descarga o carga **JSON** para compartir con apps de usuario (ej. Charly)."
    )
    st.divider()

def view_usuarios():
    st.subheader("Usuarios (activar/inactivar)")
    df = pd.DataFrame(st.session_state.usuarios)
    mostrar = df[["id","nombre","usuario","activo"]].sort_values("nombre")
    st.dataframe(mostrar, use_container_width=True, hide_index=True)

    st.markdown("### Cambiar estado")
    sel = st.selectbox("Selecciona usuario", mostrar["nombre"].tolist())
    if st.button("Alternar activo/inactivo", use_container_width=True):
        for u in st.session_state.usuarios:
            if u["nombre"] == sel:
                u["activo"] = not u["activo"]
                st.success(f"Estado actualizado: {u['nombre']} -> {'Activo' if u['activo'] else 'Inactivo'}")
                break

def view_tareas():
    st.subheader("Delegar tareas a múltiples usuarios")

    usuarios_activos = [u for u in st.session_state.usuarios if u["rol"]=="user" and u["activo"]]
    lista_nombres = [u["nombre"] for u in usuarios_activos]

    c1, c2 = st.columns(2)
    with c1:
        titulo = st.text_input("Título de la tarea")
        descripcion = st.text_area("Descripción / Instrucciones")
        prioridad = st.selectbox("Prioridad", PRIORIDADES, index=0)
    with c2:
        asignados_nombres = st.multiselect("Asignar a", lista_nombres, default=["Charly"] if "Charly" in lista_nombres else None)
        fecha_lim = st.date_input("Fecha límite", value=date.today() + timedelta(days=3))

    if st.button("Crear y asignar", type="primary", use_container_width=True, disabled=not titulo.strip() or not asignados_nombres):
        asignados = [u for u in usuarios_activos if u["nombre"] in asignados_nombres]
        nuevas = crear_tareas_multiples(titulo, descripcion, prioridad, asignados, fecha_lim, "vperaza")
        st.success(f"Se crearon {len(nuevas)} tareas.")

    st.markdown("---")
    st.markdown("### Listado / Gestión")
    dft = pd.DataFrame(st.session_state.tareas)
    if not dft.empty:
        styled = df_tareas_coloreado(dft)
        st.write(styled.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No hay tareas registradas.")

    st.markdown("#### Cambiar estado / Observación")
    tid = st.text_input("ID de tarea (task_id)")
    col1, col2, col3, col4 = st.columns(4)
    for label, estado, col in zip(["Nueva","En Progreso","Completada","Rechazada"], ESTADOS_TAREA, [col1,col2,col3,col4]):
        with col:
            if st.button(label, use_container_width=True, disabled=not tid.strip()):
                if cambiar_estado_tarea(tid, estado): st.success("Estado actualizado.")
                else: st.error("No se encontró la tarea.")

    obs = st.text_area("Observación administrativa para la tarea")
    if st.button("Guardar observación", disabled=not tid.strip()):
        if guardar_observacion_tarea(tid, obs): st.success("Observación guardada.")
        else: st.error("No se encontró la tarea.")

def view_export_import():
    st.subheader("Exportar / Importar (para compartir con apps de usuario)")
    tareas_json = json.dumps(st.session_state.tareas, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("⬇️ Descargar tareas (JSON)", data=tareas_json, file_name="tareas_rld.json", mime="application/json")
    st.markdown("#### Cargar tareas (JSON)")
    up = st.file_uploader("Archivo .json", type=["json"])
    modo = st.radio("Modo de carga", ["Agregar", "Reemplazar"], horizontal=True)
    if up is not None:
        try:
            contenido = json.load(up)
            if modo == "Reemplazar":
                st.session_state.tareas = contenido
            else:
                existentes = {t["task_id"] for t in st.session_state.tareas}
                nuevas = [t for t in contenido if t.get("task_id") not in existentes]
                st.session_state.tareas.extend(nuevas)
            st.success(f"Cargadas {len(contenido)} tareas.")
        except Exception as e:
            st.error(f"Archivo inválido: {e}")

# ----------------- Main -----------------
def main():
    portada()
    vista = st.sidebar.radio("Secciones", ["Usuarios", "Tareas", "Exportar/Importar"])
    if vista == "Usuarios":
        view_usuarios()
    elif vista == "Tareas":
        view_tareas()
    else:
        view_export_import()

if __name__ == "__main__":
    main()






