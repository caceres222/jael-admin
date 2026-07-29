import streamlit as st
import pandas as pd
import altair as alt
import json
from datetime import datetime, time
from openai import OpenAI
import math
import io
from streamlit_geolocation import streamlit_geolocation
from supabase import create_client, Client
from streamlit_mic_recorder import mic_recorder

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

# --- REGLAS DE HORARIOS ---
# 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo
HORARIOS = {
    0: [[time(6, 0), time(13, 0)]],
    1: [[time(6, 0), time(13, 0)]],
    2: [[time(6, 0), time(13, 0)], [time(15, 30), time(23, 0)]],
    3: [[time(6, 0), time(13, 0)], [time(15, 30), time(23, 0)]],
    4: [[time(6, 0), time(13, 0)]],
    5: [[time(6, 0), time(15, 0)], [time(17, 0), time(23, 0)]],
    6: [[time(6, 0), time(13, 0)]],
}

def calcular_desglose_horas(t_in, t_out):
    weekday = t_in.weekday()
    bloques = HORARIOS.get(weekday, [])
    
    total_seconds = (t_out - t_in).total_seconds()
    normal_seconds = 0
    llegada_tarde = False
    
    # Calcular cruces con horarios oficiales
    for inicio_str, fin_str in bloques:
        inicio = datetime.combine(t_in.date(), inicio_str)
        fin = datetime.combine(t_in.date(), fin_str)
        
        # Evaluar Retardo (si llega durante el bloque oficial pero después de la hora de inicio)
        if inicio < t_in < fin:
            llegada_tarde = True
            
        # Calcular tiempo traslapado con el turno oficial (Horas normales)
        overlap_start = max(t_in, inicio)
        overlap_end = min(t_out, fin)
        
        if overlap_start < overlap_end:
            normal_seconds += (overlap_end - overlap_start).total_seconds()
            
    horas_normales = normal_seconds / 3600.0
    horas_extras = (total_seconds - normal_seconds) / 3600.0
    
    # Evitar negativos por márgenes de segundo
    horas_extras = max(0, horas_extras)
    
    return round(horas_normales, 2), round(horas_extras, 2), llegada_tarde

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
    st.session_state.chat_history = [{"role": "assistant", "content": "¡Hola! Soy Jael. Puedo registrar gastos y consultar finanzas o asistencia. Presiona el micrófono para hablarme."}]

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
            "description": "Devuelve las asistencias, horas extras y retardos.",
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
            turno_abierto = supabase.table("asistencia").select("*").eq("empleado", emp).is_("salida", "null").execute().data
        except Exception:
            turno_abierto = []
        
        col1, col2 = st.columns(2)
        with col1:
            if not turno_abierto:
                if st.button("🟢 MARCAR ENTRADA", use_container_width=True):
                    try:
                        supabase.table("asistencia").insert({"empleado": emp, "fecha": datetime.now().strftime("%Y-%m-%d"), "entrada": datetime.now().strftime("%H:%M:%S"), "horas": 0.0}).execute()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al marcar entrada: {e}")
            else:
                st.button("🟢 ENTRADA REGISTRADA", disabled=True, use_container_width=True)
                
        with col2:
            if turno_abierto:
                st.write("### 📝 Registrar Actividad y Salida")
                with st.form("salida_form"):
                    actividades = st.text_area("¿Qué actividades realizaste?", placeholder="Ej: Limpieza...")
                    
                    if st.form_submit_button("🔴 GUARDAR Y MARCAR SALIDA"):
                        if not actividades:
                            st.error("Por favor, escribe tus actividades antes de salir.")
                        else:
                            try:
                                id_turno = turno_abierto[0]["id"]
                                h_salida = datetime.now()
                                t_in = datetime.strptime(f"{turno_abierto[0]['fecha']} {turno_abierto[0]['entrada']}", "%Y-%m-%d %H:%M:%S")
                                
                                h_norm, h_ext, hubo_retardo = calcular_desglose_horas(t_in, h_salida)
                                total_h = h_norm + h_ext
                                
                                supabase.table("asistencia").update({
                                    "salida": h_salida.strftime("%H:%M:%S"), 
                                    "horas": round(total_h, 2),
                                    "horas_extras": h_ext,
                                    "retardo": hubo_retardo,
                                    "actividad": actividades
                                }).eq("id", id_turno).execute()
                                st.success("✅ Salida registrada exitosamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al marcar salida: {e}")
            else:
                st.button("🔴 MARCAR SALIDA", disabled=True, use_container_width=True)                            except Exception as e:
                                st.error(f"Error al marcar salida: {e}")
            else:
                st.button("🔴 MARCAR SALIDA", disabled=True, use_container_width=True)        
        st.write("---")
        
        try:
            turno_abierto = supabase.table("asistencia").select("*").eq("empleado", emp).is_("salida", "null").execute().data
        except Exception:
            turno_abierto = []
        
        if not turno_abierto:
            st.write("¿Listo para comenzar a trabajar?")
            if st.button("🟢 MARCAR ENTRADA", use_container_width=True, disabled=not ubicacion_valida):
                try:
                    supabase.table("asistencia").insert({"empleado": emp, "fecha": datetime.now().strftime("%Y-%m-%d"), "entrada": datetime.now().strftime("%H:%M:%S"), "horas": 0.0}).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al marcar entrada: {e}")
        else:
            st.info(f"🟢 Tienes un turno abierto. Entraste a las {turno_abierto[0]['entrada']}.")
            
            st.write("### 📝 Registrar Actividad y Salida")
            with st.form("salida_form"):
                actividades = st.text_area("¿Qué actividades realizaste en este turno?", placeholder="Ej: Preparación de desayunos, limpieza...")
                
                if st.form_submit_button("🔴 GUARDAR Y MARCAR SALIDA", disabled=not ubicacion_valida):
                    if not actividades:
                        st.error("Por favor, escribe tus actividades antes de salir.")
                    else:
                        try:
                            id_turno = turno_abierto[0]["id"]
                            h_salida = datetime.now()
                            t_in = datetime.strptime(f"{turno_abierto[0]['fecha']} {turno_abierto[0]['entrada']}", "%Y-%m-%d %H:%M:%S")
                            
                            # Magia: Calculamos automáticamente las horas normales, extras y el retardo
                            h_norm, h_ext, hubo_retardo = calcular_desglose_horas(t_in, h_salida)
                            total_h = h_norm + h_ext
                            
                            supabase.table("asistencia").update({
                                "salida": h_salida.strftime("%H:%M:%S"), 
                                "horas": round(total_h, 2),
                                "horas_extras": h_ext,
                                "retardo": hubo_retardo,
                                "actividad": actividades
                            }).eq("id", id_turno).execute()
                            st.success("✅ Salida registrada exitosamente. Tus horas extras se calcularon solas.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al marcar salida: {e}")
                
        st.write("### 📅 Mis horas trabajadas")
        try:
            mis_horas = supabase.table("asistencia").select("*").eq("empleado", emp).execute().data
            if mis_horas:
                df_mis_h = pd.DataFrame(mis_horas)
                # Solo mostramos columnas que existen
                columnas_mostrar = [c for c in ["fecha", "entrada", "salida", "horas", "horas_extras", "retardo", "actividad"] if c in df_mis_h.columns]
                st.dataframe(df_mis_h[columnas_mostrar], use_container_width=True)
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
            c4.metric("👷 Horas Totales", f"{tot_h:.1f}")

        elif op == "🤖 Asistente":
            st.title("🎙️ Jael")
            for msg in st.session_state.chat_history:
                if msg["role"] != "system" and msg.get("content"):
                    st.chat_message(msg["role"]).write(msg["content"])

            texto_usuario = st.chat_input("O escribe tu instrucción aquí...")
            mensaje_final = texto_usuario

            audio = mic_recorder(start_prompt="🎙️ Toca para Hablar", stop_prompt="⏹️ Detener Grabación", just_once=True, key="grabador")
            
            if audio and not texto_usuario:
                with st.spinner("Escuchando..."):
                    with open("temp.wav", "wb") as f: 
                        f.write(audio['bytes'])
                    transcription = client.audio.transcriptions.create(model="whisper-1", file=open("temp.wav", "rb"))
                    mensaje_final = transcription.text
                    st.success(f"**Escuché:** {mensaje_final}")

            if mensaje_final:
                st.session_state.chat_history.append({"role": "user", "content": mensaje_final})
                mensajes = [{"role": "system", "content": f"Eres Jael. Hoy es {datetime.now().strftime('%A %Y-%m-%d')}."}] + st.session_state.chat_history
                
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
                                resp_analisis = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "Analiza asistencias, horas extras y retardos: " + json.dumps(horas_db)}] + st.session_state.chat_history).choices[0].message
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
                
                # Pago base total asumiendo 20.0 (puedes ajustarlo si las extras se pagan distinto)
                if "horas" in df.columns:
                    df["pago_estimado"] = df["horas"] * 20.0
                
                st.write("### 📋 Registro de Actividades y Nómina")
                
                # Botón Excel incluyendo las nuevas columnas
                cols_excel = [c for c in ["empleado", "fecha", "entrada", "salida", "horas", "horas_extras", "retardo", "actividad", "pago_estimado"] if c in df.columns]
                
                excel_data = generar_excel(df[cols_excel], "Nomina_Actividades")
                st.download_button(label="📥 Descargar Nómina y Actividades (Excel)", data=excel_data, file_name=f"Nomina_{datetime.now().strftime('%Y-%m-%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
                st.dataframe(df[cols_excel], use_container_width=True)

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
