# =========================
# RLD – 2025 (Versión local de pruebas) – APP ADMIN (VIVIANA)
# =========================

import json, time, hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict
import uuid

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
    {"id": "008", "nombre": "Carlos",  "usuario": "carlos",  "rol": "user",  "activo": True},
    {"id": "009", "nombre": "Viviana Peraza", "usuario": "vperaza", "rol": "admin", "activo": True},
    {"id": "010", "nombre": "Charly",  "usuario": "charly",  "rol": "user",  "activo": True},
]

PASSWORDS_FIJAS = { # solo como referencia en pruebas (no lo usamos en esta app local)
    "jeremy":"jeremy2025","jannia":"jannia2025","manfred":"manfred2025","luis":"luis2025",
    "adrian":"adrian2025","esteban":"esteban2025","pamela":"pamela2025","carlos":"carlos2025",
    "charly":"charly2025","vperaza":"viviana2025"
}

PRIORIDADES = ["Alta","Media","Baja"]          # Alta=naranja, Media=rojo, Baja=verde
ESTADOS_TAREA = ["Nueva","En Progreso","Completada","Rechazada"]

def iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _init_state():
    if "usuarios" not in st.session_state:
        # copia profunda para no alterar la constante
        st.session_state.usuarios = json.loads(json.dumps(USUARIOS_INICIALES))
    if "tareas" not in st.session_state:
        st.session_state.tareas: List[Dict] = []
    if "respuestas" not in st.session_state:
        st.session_state.respuestas: List[Dict] = []  # reservado para futuras pruebas

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
    # Mostrar columnas ordenadas y limpias
    cols = ["task_id","titulo","prioridad_tag","estado","asignado_id","asignado_nombre","fecha_limite","fecha_asignacion"]
    return df.reindex(columns=[c for c in cols if c in df.columns])

def crear_tareas_multiples(titulo: str, descripcion: str, prioridad: str, asignados: List[Dict], fecha_limite: date, creado_por: str):
    base = int(time.time()*1000)
    nuevas = []
    for i, u in enumerate(asignados, start=1):
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
        "- **Tareas**: delega una tarea a **múltiples usuarios** y visualiza por prioridad con **etiquetas de color**:\n"
        "  - **Naranja** = *Alta* (prioridad máxima)  \n"
        "  - **Rojo** = *Media* (urge)  \n"
        "  - **Verde** = *Baja* (no tan prioritaria)\n"
        "- **Exportar/Importar**: descarga o carga **JSON** para compartir con la app de Charly u otras."
    )
    st.divider()

def view_usuarios():
    st.subheader("Usuarios (activar/inactivar)")
    df = pd.DataFrame(st.session_state.usuarios)
    # Solo mostrar columnas mínimas
    mostrar = df[["id","nombre","usuario","activo"]].sort_values("nombre")
    st.dataframe(mostrar, use_container_width=True, hide_index=True)

    st.markdown("### Cambiar estado")
    col1, col2 = st.columns([2,1])
    with col1:
        nombres = mostrar["nombre"].tolist()
        sel = st.selectbox("Selecciona usuario", nombres)
    with col2:
        if st.button("Alternar activo/inactivo", use_container_width=True):
            for u in st.session_state.usuarios:
                if u["nombre"] == sel:
                    u["activo"] = not u["activo"]
                    st.success(f"Estado actualizado: {u['nombre']} -> {'Activo' if u['activo'] else 'Inactivo'}")
                    break

    st.caption("Nota: en las apps de usuario, si el usuario está **inactivo**, se debe impedir el acceso y mostrar un mensaje.")

def view_tareas():
    st.subheader("Delegar tareas a múltiples usuarios")

    # Usuarios activos tipo 'user'
    usuarios_activos = [u for u in st.session_state.usuarios if u["rol"]=="user" and u["activo"]]
    lista_nombres = [u["nombre"] for u in usuarios_activos]

    c1, c2 = st.columns(2)
    with c1:
        titulo = st.text_input("Título de la tarea")
        descripcion = st.text_area("Descripción / Instrucciones")
        prioridad = st.selectbox("Prioridad", PRIORIDADES, index=0)  # Alta por defecto (naranja)
    with c2:
        asignados_nombres = st.multiselect("Asignar a (múltiples)", lista_nombres, default=["Charly"] if "Charly" in lista_nombres else None)
        fecha_lim = st.date_input("Fecha límite", value=date.today() + timedelta(days=3))

    if st.button("Crear y asignar", type="primary", use_container_width=True, disabled=not titulo.strip() or not asignados_nombres):
        asignados = [u for u in usuarios_activos if u["nombre"] in asignados_nombres]
        nuevas = crear_tareas_multiples(titulo, descripcion, prioridad, asignados, fecha_lim, "vperaza")
        st.success(f"Se crearon {len(nuevas)} tareas (una por asignado).")

    st.markdown("---")
    st.markdown("### Listado / Gestión")

    dft = pd.DataFrame(st.session_state.tareas)
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        f_estado = st.selectbox("Estado", ["(Todos)"] + ESTADOS_TAREA)
    with f2:
        f_prioridad = st.selectbox("Prioridad", ["(Todas)"] + PRIORIDADES)
    with f3:
        f_usuario = st.selectbox("Asignado", ["(Todos)"] + sorted(list(dft["asignado_nombre"].unique())) if not dft.empty else ["(Todos)"])
    with f4:
        solo_vigentes = st.checkbox("Solo no vencidas", value=False)

    data = dft.copy()
    if not data.empty:
        if f_estado != "(Todos)":
            data = data[data["estado"] == f_estado]
        if f_prioridad != "(Todas)":
            data = data[data["prioridad"] == f_prioridad]
        if f_usuario != "(Todos)":
            data = data[data["asignado_nombre"] == f_usuario]
        if solo_vigentes:
            data = data[pd.to_datetime(data["fecha_limite"], errors="coerce") >= pd.Timestamp(date.today())]

    # Render con prioridad coloreada
    if not data.empty:
        styled = df_tareas_coloreado(data)
        # mostrar prioridad_tag como HTML
        st.write(styled.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No hay tareas para mostrar.")

    st.markdown("#### Cambiar estado / Observación")
    tid = st.text_input("ID de tarea (task_id)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Nueva", use_container_width=True, disabled=not tid.strip()):
            if cambiar_estado_tarea(tid, "Nueva"): st.success("Estado actualizado.")
            else: st.error("No se encontró la tarea.")
    with c2:
        if st.button("En Progreso", use_container_width=True, disabled=not tid.strip()):
            if cambiar_estado_tarea(tid, "En Progreso"): st.success("Estado actualizado.")
            else: st.error("No se encontró la tarea.")
    with c3:
        if st.button("Completada", use_container_width=True, disabled=not tid.strip()):
            if cambiar_estado_tarea(tid, "Completada"): st.success("Estado actualizado.")
            else: st.error("No se encontró la tarea.")
    with c4:
        if st.button("Rechazada", use_container_width=True, disabled=not tid.strip()):
            if cambiar_estado_tarea(tid, "Rechazada"): st.success("Estado actualizado.")
            else: st.error("No se encontró la tarea.")

    obs = st.text_area("Observación administrativa para la tarea")
    if st.button("Guardar observación", disabled=not tid.strip()):
        if guardar_observacion_tarea(tid, obs): st.success("Observación guardada.")
        else: st.error("No se encontró la tarea.")

def view_export_import():
    st.subheader("Exportar / Importar (para compartir con la app de Charly)")

    # ---- Exportar
    tareas_json = json.dumps(st.session_state.tareas, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("⬇️ Descargar tareas (JSON)", data=tareas_json, file_name="tareas_rld.json", mime="application/json")

    # ---- Importar
    st.markdown("#### Cargar tareas (JSON)")
    up = st.file_uploader("Drag & drop o selecciona un archivo .json", type=["json"])
    modo = st.radio("Modo de carga", ["Agregar a las existentes", "Reemplazar todas"], horizontal=True)
    if up is not None:
        try:
            contenido = json.load(up)
            if not isinstance(contenido, list):
                st.error("El JSON debe ser una lista de tareas.")
            else:
                if modo == "Reemplazar todas":
                    st.session_state.tareas = contenido
                else:
                    # evita duplicados por task_id
                    existentes = {t["task_id"] for t in st.session_state.tareas}
                    nuevas = [t for t in contenido if t.get("task_id") not in existentes]
                    st.session_state.tareas.extend(nuevas)
                st.success(f"Tareas cargadas ({len(contenido)}).")
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








