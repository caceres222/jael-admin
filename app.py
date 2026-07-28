import streamlit as st
import pandas as pd
import altair as alt
import json
from datetime import datetime
from openai import OpenAI
import math
import io
from streamlit_geolocation import streamlit_geolocation
from supabase import create_client, Client

# Configuración inicial 
st.set_page_config(page_title="Jael - Asistente de la Sinagoga", page_icon="🕌", layout="wide", initial_sidebar_state="auto")

ocultar_menu = """
    <style>
    #MainMenu {visibility: hidden;}
    .stAppDeployButton {display:none;}
    footer {visibility: hidden;}
    .stRadio > div { gap: 20px; }
    .stRadio p { font-size: 20px !important; padding-top: 5px; }
    .stRadio [data-baseweb="radio"] div { height: 24px; width: 24px; }
    .stSelectbox p { font-size: 18px !important; }
    </style>
"""
st.markdown(ocultar_menu, unsafe_allow_html=True)

# --- CONEXIONES ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except KeyError:
        url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
        key = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- FUNCIONES AUXILIARES ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371000 
    phi_1 = math.radians(lat1)
    phi_2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def generar_excel(dataframe, sheet_name="Reporte"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

LAT_SINAGOGA = 25.7617 
LON_SINAGOGA = -80.1918 
RADIO_PERMITIDO_METROS = 200.0 

if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if "emp_logged_in" not in st.session_state: st.session_state.emp_logged_in = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "¡Hola! Soy Jael. Puedo registrar gastos y ahora también puedo consultar finanzas y horas del personal."}]

herramientas = [
    {
        "type": "function",
        "function": {
            "name": "registrar_gasto",
            "description": "Registra un nuevo gasto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "enum": ["Limpieza", "Proveedores", "Otros"]},
                    "descripcion": {"type": "string"},
                    "monto": {"type": "number"}
                },
                "required": ["categoria", "descripcion", "monto"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_gastos",
            "description": "Devuelve los gastos registrados.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_horas",
            "description": "Devuelve las asistencias, horas extras y actividades de los empleados.",
            "parameters": {"type": "object", "properties": {}}
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
        
        # EL GPS AHORA SOLO ADVIERTE, NO BLOQUEA (Para que puedas hacer pruebas desde casa)
        if loc and loc.get("latitude") and loc.get("longitude"):
            lat_emp = loc["latitude"]
            lon_emp = loc["longitude"]
            distancia = calcular_distancia(LAT_SINAGOGA, LON_SINAGOGA, lat_emp, lon_emp)
            if distancia <= RADIO_PERMITIDO_METROS:
                st.success(f"✅ Ubicación confirmada en Sinagoga.")
            else:
                st.warning(f"⚠️ Aviso: Estás a {int(distancia)}m de la sinagoga.")
        
        st.write("---")
        
        try:
            turno_abierto = supabase.table("asistencia").select("*").eq("empleado", emp).is_("salida", "null").execute().data
        except Exception:
            turno_abierto = []
        
        if not turno_abierto:
            st.write("¿Listo para comenzar a trabajar?")
            if st.button("🟢 MARCAR ENTRADA", use_container_width=True):
                try:
                    supabase.table("asistencia").insert({"empleado": emp, "fecha": datetime.now().strftime("%Y-%m-%d"), "entrada": datetime.now().strftime("%H:%M:%S"), "horas": 0.0}).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al marcar entrada: {e}")
        else:
            st.info(f"🟢 Tienes un turno abierto. Entraste a las {turno_abierto[0]['entrada']}.")
            
            st.write("### 📝 Registrar Actividad y Salida")
            with st.form("salida_form"):
                actividades = st.text_area("¿Qué actividades realizaste en este turno?", placeholder="Ej: Limpieza del salón principal, organización de sillas...")
                es_extra = st.checkbox("🔥 Marcar este turno como HORAS EXTRAS")
                
                if st.form_submit_button("🔴 GUARDAR Y MARCAR SALIDA"):
                    if not actividades:
                        st.error("Por favor, escribe tus actividades antes de salir.")
                    else:
                        try:
                            id_turno = turno_abierto[0]["id"]
                            h_salida = datetime.now()
                            t_in = datetime.strptime(f"{turno_abierto[0]['fecha']} {turno_abierto[0]['entrada']}", "%Y-%m-%d %H:%M:%S")
                            horas_trabajadas = (h_salida - t_in).total_seconds() / 3600.0
                            
                            supabase.table("asistencia").update({
                                "salida": h_salida.strftime("%H:%M:%S"), 
                                "horas": round(horas_trabajadas, 2),
                                "actividad": actividades,
                                "si_es_extra": es_extra
                            }).eq("id", id_turno).execute()
                            st.success("✅ Salida registrada exitosamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al marcar salida: {e}")
                
        st.write("### 📅 Mis horas trabajadas")
        try:
            mis_horas = supabase.table("asistencia").select("*").eq("empleado", emp).execute().data
            if mis_horas:
                df_mis_h = pd.DataFrame(mis_horas)
                st.dataframe(df_mis_h[["fecha", "entrada", "salida", "horas", "si_es_extra", "actividad"]], use_container_width=True)
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
                mensajes = [{"role": "system", "content": f"Eres Jael. Hoy es {datetime.now().strftime('%Y-%m-%d')}."}] + st.session_state.chat_history
                
                resp = client.chat.completions.create(model="gpt-3.5-turbo", messages=mensajes, tools=herramientas, tool_choice="auto").choices[0].message
                if getattr(resp, "tool_calls", None):
                    for tc in resp.tool_calls:
                        if tc.function.name == "registrar_gasto":
                            args = json.loads(tc.function.arguments)
                            try:
                                supabase.table("gastos").insert({"fecha": datetime.now().strftime("%Y-%m-%d"), "categoria": args["categoria"], "descripcion": args["descripcion"], "monto": args["monto"]}).execute()
                                st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Gasto registrado: ${args['monto']} en {args['categoria']}."})
                            except Exception as e:
                                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Error: {e}"})
                        elif tc.function.name == "consultar_gastos":
                            try:
                                gastos_db = supabase.table("gastos").select("*").execute().data
                                resp_analisis = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "Analiza: " + json.dumps(gastos_db)}] + st.session_state.chat_history).choices[0].message
                                st.session_state.chat_history.append({"role": "assistant", "content": resp_analisis.content})
                            except Exception:
                                st.session_state.chat_history.append({"role": "assistant", "content": "Error leyendo base de datos."})
                        elif tc.function.name == "consultar_horas":
                            try:
                                horas_db = supabase.table("asistencia").select("*").execute().data
                                resp_analisis = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "Analiza las horas (pago $20/hr, revisa si_es_extra y actividad): " + json.dumps(horas_db)}] + st.session_state.chat_history).choices[0].message
                                st.session_state.chat_history.append({"role": "assistant", "content": resp_analisis.content})
                            except Exception:
                                st.session_state.chat_history.append({"role": "assistant", "content": "Error leyendo base de datos."})
                else:
                    st.session_state.chat_history.append({"role": "assistant", "content": getattr(resp, "content", "Entendido.")})
                st.rerun()

        elif op == "Personal":
            st.title("👥 Empleados y Actividades")
            
            with st.expander("Registrar Nuevo Empleado"):
                with st.form("f1"):
                    c1, c2 = st.columns(2)
                    nombre = c1.text_input("Nombre Completo")
                    pin = c2.text_input("PIN (4 dígitos)", max_chars=4)
                    if st.form_submit_button("Añadir"):
                        try:
                            supabase.table("empleados").insert({"nombre": nombre, "pin": pin}).execute()
                            st.success(f"✅ {nombre} añadido.")
                            st.rerun()
                        except Exception:
                            st.error("Ese nombre ya existe o hay un error.")
                            
            st.write("---")
            if datos_horas:
                df = pd.DataFrame(datos_horas)
                
                # Asumimos que las horas extra se pagan distinto? Por ahora $20 todas. 
                df["pago_estimado"] = df["horas"] * 20.0
                
                st.write("### 📋 Registro de Actividades y Nómina")
                
                # Botón Excel
                cols_excel = ["empleado", "fecha", "entrada", "salida", "horas", "si_es_extra", "actividad", "pago_estimado"]
                if set(cols_excel).issubset(df.columns):
                    excel_data = generar_excel(df[cols_excel], "Nomina_Actividades")
                    st.download_button(label="📥 Descargar Nómina y Actividades (Excel)", data=excel_data, file_name=f"Nomina_{datetime.now().strftime('%Y-%m-%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
                    st.dataframe(df[cols_excel], use_container_width=True)
                else:
                    st.warning("Faltan datos de actividad en registros antiguos. Los nuevos se verán aquí.")

        elif op == "Gastos":
            st.title("📈 Gastos")
            with st.form("f2"):
                c1, c2, c3 = st.columns(3)
                cat = c1.selectbox("Categoría", ["Limpieza", "Proveedores", "Otros"])
                desc = c2.text_input("Descripción")
                monto = c3.number_input("Monto ($)", min_value=0.0)
                if st.form_submit_button("Guardar") and desc and monto > 0:
                    supabase.table("gastos").insert({"fecha": datetime.now().strftime("%Y-%m-%d"), "categoria": cat, "descripcion": desc, "monto": monto}).execute()
                    st.success("✅ Guardado")
                    st.rerun()
            if datos_gastos:
                df_gastos = pd.DataFrame(datos_gastos)
                excel_gastos = generar_excel(df_gastos[["fecha", "categoria", "descripcion", "monto"]], "Gastos")
                st.download_button(label="📥 Descargar Gastos (Excel)", data=excel_gastos, file_name=f"Gastos_{datetime.now().strftime('%Y-%m-%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
                st.dataframe(df_gastos[["fecha", "categoria", "descripcion", "monto"]], use_container_width=True)
