import streamlit as st
import pandas as pd
import altair as alt
import json
from datetime import datetime
from openai import OpenAI
import math
from streamlit_geolocation import streamlit_geolocation
from st_supabase_connection import SupabaseConnection

# Configuración inicial 
st.set_page_config(page_title="Jael - Asistente de la Sinagoga", page_icon="🕌", layout="wide", initial_sidebar_state="auto")

# TRUCO CSS
ocultar_menu = """
    <style>
    #MainMenu {visibility: hidden;}
    .stAppDeployButton {display:none;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(ocultar_menu, unsafe_allow_html=True)

# --- CONEXIONES ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# Inicializar la conexión nativa súper estable de Streamlit a Supabase
supabase = st.connection("supabase", type=SupabaseConnection)

# --- GEOLOCALIZACIÓN ---
LAT_SINAGOGA = 25.7617 
LON_SINAGOGA = -80.1918 
RADIO_PERMITIDO_METROS = 200.0 

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371000 
    phi_1 = math.radians(lat1)
    phi_2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- ESTADOS ---
if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if "emp_logged_in" not in st.session_state: st.session_state.emp_logged_in = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "¡Hola! Soy Jael. Puedes hablarme o escribirme."}]

herramientas = [
    {
        "type": "function",
        "function": {
            "name": "registrar_gasto",
            "description": "Registra un nuevo gasto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "enum": ["Desayunos de fin de semana", "Insumos de Limpieza", "Mantenimiento / Cuarto", "Proveedores", "Otros Gastos Extra"]},
                    "descripcion": {"type": "string"},
                    "monto": {"type": "number"}
                },
                "required": ["categoria", "descripcion", "monto"]
            }
        }
    }
]

st.sidebar.title("Acceso")
tipo_acceso = st.sidebar.radio("Selecciona tu perfil:", ["Área de Empleados", "Administración"])

# ==========================================
# ÁREA DE EMPLEADOS
# ==========================================
if tipo_acceso == "Área de Empleados":
    st.title("⏱️ Reloj Checador")
    
    try:
        lista_empleados = supabase.table("empleados").select("*").execute().data
    except Exception:
        lista_empleados = []
    
    if st.session_state.emp_logged_in is None:
        if not lista_empleados:
            st.warning("No hay empleados registrados.")
        else:
            nombres = [e["nombre"] for e in lista_empleados]
            dic_emp = {e["nombre"]: e["pin"] for e in lista_empleados}
            
            emp_sel = st.selectbox("Tu Nombre", nombres)
            pin_input = st.text_input("Tu PIN (4 dígitos)", type="password", max_chars=4)
            if st.button("Ingresar"):
                if dic_emp.get(emp_sel) == pin_input:
                    st.session_state.emp_logged_in = emp_sel
                    st.rerun()
                else:
                    st.error("PIN incorrecto.")
    else:
        emp = st.session_state.emp_logged_in
        st.success(f"Hola, **{emp}**")
        if st.button("Cerrar mi sesión"):
            st.session_state.emp_logged_in = None
            st.rerun()
            
        st.write("---")
        st.write("### 📍 Verificación de Ubicación")
        loc = streamlit_geolocation()
        ubicacion_valida = False
        
        if loc and loc.get("latitude") and loc.get("longitude"):
            lat_emp = loc["latitude"]
            lon_emp = loc["longitude"]
            distancia = calcular_distancia(LAT_SINAGOGA, LON_SINAGOGA, lat_emp, lon_emp)
            
            if distancia <= RADIO_PERMITIDO_METROS:
                st.success(f"✅ Ubicación confirmada")
                ubicacion_valida = True
            else:
                st.error("❌ Estás muy lejos de la sinagoga.")
        
        st.write("---")
        
        try:
            turno_abierto = supabase.table("asistencia").select("*").eq("empleado", emp).is_("salida", "null").execute().data
        except Exception:
            turno_abierto = []
        
        col1, col2 = st.columns(2)
        with col1:
            if not turno_abierto:
                if st.button("🟢 MARCAR ENTRADA", use_container_width=True, disabled=not ubicacion_valida):
                    supabase.table("asistencia").insert({"empleado": emp, "fecha": datetime.now().strftime("%Y-%m-%d"), "entrada": datetime.now().strftime("%H:%M:%S"), "horas": 0.0}).execute()
                    st.rerun()
            else:
                st.button("🟢 ENTRADA REGISTRADA", disabled=True, use_container_width=True)
                
        with col2:
            if turno_abierto:
                if st.button("🔴 MARCAR SALIDA", use_container_width=True, disabled=not ubicacion_valida):
                    id_turno = turno_abierto[0]["id"]
                    h_salida = datetime.now()
                    t_in = datetime.strptime(f"{turno_abierto[0]['fecha']} {turno_abierto[0]['entrada']}", "%Y-%m-%d %H:%M:%S")
                    horas_trabajadas = (h_salida - t_in).total_seconds() / 3600.0
                    supabase.table("asistencia").update({"salida": h_salida.strftime("%H:%M:%S"), "horas": round(horas_trabajadas, 2)}).eq("id", id_turno).execute()
                    st.rerun()
            else:
                st.button("🔴 MARCAR SALIDA", disabled=True, use_container_width=True)
                
        st.write("### 📅 Mis horas trabajadas")
        try:
            mis_horas = supabase.table("asistencia").select("*").eq("empleado", emp).execute().data
            if mis_horas:
                st.dataframe(pd.DataFrame(mis_horas)[["fecha", "entrada", "salida", "horas"]], use_container_width=True)
        except Exception:
            st.info("Aún no tienes registros.")

# ==========================================
# ADMINISTRACIÓN
# ==========================================
elif tipo_acceso == "Administración":
    if not st.session_state.admin_logged_in:
        pwd = st.text_input("Contraseña Admin", type="password")
        if st.button("Entrar") and pwd == "admin123": 
            st.session_state.admin_logged_in = True
            st.rerun()
    else:
        if st.sidebar.button("Cerrar Sesión"):
            st.session_state.admin_logged_in = False
            st.rerun()
            
        op = st.sidebar.radio("Módulo:", ["Dashboard", "🤖 Asistente", "Personal", "Gastos"])

        try:
            datos_gastos = supabase.table("gastos").select("*").execute().data
            datos_horas = supabase.table("asistencia").select("*").execute().data
        except Exception:
            datos_gastos, datos_horas = [], []

        if op == "Dashboard":
            st.title("🕌 Panel de Control")
            tot_g = sum(g["monto"] for g in datos_gastos) if datos_gastos else 0
            tot_h = sum(t["horas"] for t in datos_horas) if datos_horas else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 Gastos Extra", f"${tot_g:,.2f}")
            c2.metric("👥 Nómina", f"${tot_h*20:,.2f}")
            c3.metric("🏢 TOTAL OPERACIÓN", f"${(tot_g + tot_h*20):,.2f}")
            c4.metric("👷 Horas Registradas", f"{tot_h:.1f}")

        elif op == "🤖 Asistente":
            st.title("🎙️ Jael")
            for msg in st.session_state.chat_history:
                if msg["role"] != "system" and msg.get("content"):
                    st.chat_message(msg["role"]).write(msg["content"])

            texto_usuario = st.chat_input("Escribe tu instrucción...")
            if texto_usuario:
                st.session_state.chat_history.append({"role": "user", "content": texto_usuario})
                mensajes = [{"role": "system", "content": "Eres Jael, asistente de la sinagoga."}] + st.session_state.chat_history
                
                resp = client.chat.completions.create(model="gpt-3.5-turbo", messages=mensajes, tools=herramientas, tool_choice="auto").choices[0].message
                if getattr(resp, "tool_calls", None):
                    for tc in resp.tool_calls:
                        if tc.function.name == "registrar_gasto":
                            args = json.loads(tc.function.arguments)
                            supabase.table("gastos").insert({"fecha": datetime.now().strftime("%Y-%m-%d"), "categoria": args["categoria"], "descripcion": args["descripcion"], "monto": args["monto"]}).execute()
                            st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Guardado en nube: ${args['monto']} en {args['categoria']}."})
                else:
                    st.session_state.chat_history.append({"role": "assistant", "content": getattr(resp, "content", "Entendido.")})
                st.rerun()

        elif op == "Personal":
            st.title("👥 Empleados")
            with st.form("f1"):
                c1, c2 = st.columns(2)
                nombre = c1.text_input("Nombre")
                pin = c2.text_input("PIN (4 dígitos)", max_chars=4)
                if st.form_submit_button("Añadir") and nombre and pin:
                    supabase.table("empleados").insert({"nombre": nombre, "pin": pin}).execute()
                    st.success("✅ Añadido a la nube.")
            if datos_horas:
                df = pd.DataFrame(datos_horas)
                df["pago"] = df["horas"] * 20.0
                st.dataframe(df[["empleado", "fecha", "entrada", "salida", "horas", "pago"]], use_container_width=True)

        elif op == "Gastos":
            st.title("📈 Gastos")
            with st.form("f2"):
                c1, c2, c3 = st.columns(3)
                cat = c1.selectbox("Categoría", ["Limpieza", "Proveedores", "Otros"])
                desc = c2.text_input("Descripción")
                monto = c3.number_input("Monto ($)", min_value=0.0)
                if st.form_submit_button("Guardar") and desc and monto > 0:
                    supabase.table("gastos").insert({"fecha": datetime.now().strftime("%Y-%m-%d"), "categoria": cat, "descripcion": desc, "monto": monto}).execute()
                    st.success("✅ Guardado en la nube.")
            if datos_gastos:
                st.dataframe(pd.DataFrame(datos_gastos)[["fecha", "categoria", "descripcion", "monto"]], use_container_width=True)
