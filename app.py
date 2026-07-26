import streamlit as st
import pandas as pd
import altair as alt
import json
from datetime import datetime
from openai import OpenAI
import math
from streamlit_geolocation import streamlit_geolocation
from supabase import create_client, Client

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

# --- CONFIGURACIÓN DE CONEXIONES ---
# Conexión a OpenAI
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Conexión a Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- CONFIGURACIÓN DE GEOLOCALIZACIÓN ---
# Coordenadas de la Sinagoga (Cámbialas por las tuyas)
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

# --- INICIALIZAR ESTADOS ---
if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if "emp_logged_in" not in st.session_state: st.session_state.emp_logged_in = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "¡Hola! Soy Jael. Puedes hablarme o escribirme. Dime si necesitas registrar un gasto."}]

# Herramienta para Jael
herramientas = [
    {
        "type": "function",
        "function": {
            "name": "registrar_gasto",
            "description": "Registra un nuevo gasto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "enum": ["Desayunos de fin de semana", "Insumos de Limpieza", "Mantenimiento / Cuarto", "Proveedores (Pedidos fijos)", "Otros Gastos Extra"]},
                    "descripcion": {"type": "string"},
                    "monto": {"type": "number"}
                },
                "required": ["categoria", "descripcion", "monto"]
            }
        }
    }
]

# --- NAVEGACIÓN PRINCIPAL ---
st.sidebar.title("Acceso")
tipo_acceso = st.sidebar.radio("Selecciona tu perfil:", ["Área de Empleados", "Administración"])

# ==========================================
# VISTA: ÁREA DE EMPLEADOS
# ==========================================
if tipo_acceso == "Área de Empleados":
    st.title("⏱️ Reloj Checador")
    
    # Descargar empleados de la base de datos
    respuesta_emp = supabase.table("empleados").select("*").execute()
    lista_empleados = respuesta_emp.data
    
    if st.session_state.emp_logged_in is None:
        st.write("Por favor, identifícate para marcar tu entrada o salida.")
        
        if not lista_empleados:
            st.warning("No hay empleados registrados. Pídele al administrador que te registre.")
        else:
            # Crear diccionario de Nombre -> PIN
            nombres = [e["nombre"] for e in lista_empleados]
            dic_emp = {e["nombre"]: e["pin"] for e in lista_empleados}
            
            emp_sel = st.selectbox("Tu Nombre", nombres)
            pin_input = st.text_input("Tu PIN (4 dígitos)", type="password", max_chars=4)
            if st.button("Ingresar"):
                if dic_emp.get(emp_sel) == pin_input:
                    st.session_state.emp_logged_in = emp_sel
                    st.rerun()
                else:
                    st.error("PIN incorrecto. Intenta de nuevo.")
    else:
        emp = st.session_state.emp_logged_in
        st.success(f"Hola, **{emp}**")
        
        if st.button("Cerrar mi sesión"):
            st.session_state.emp_logged_in = None
            st.rerun()
            
        st.write("---")
        
        # Geolocalización
        st.write("### 📍 Verificación de Ubicación")
        loc = streamlit_geolocation()
        ubicacion_valida = False
        
        if loc and loc.get("latitude") and loc.get("longitude"):
            lat_emp = loc["latitude"]
            lon_emp = loc["longitude"]
            distancia = calcular_distancia(LAT_SINAGOGA, LON_SINAGOGA, lat_emp, lon_emp)
            
            if distancia <= RADIO_PERMITIDO_METROS:
                st.success(f"✅ Ubicación confirmada (Estás a {int(distancia)}m)")
                ubicacion_valida = True
            else:
                st.error(f"❌ Estás muy lejos de la sinagoga (Estás a {int(distancia)}m). Debes estar a menos de {int(RADIO_PERMITIDO_METROS)}m.")
        
        st.write("---")
        
        # Revisar si hay un turno abierto de este empleado en la base de datos
        respuesta_turnos = supabase.table("asistencia").select("*").eq("empleado", emp).is_("salida", "null").execute()
        turno_abierto = respuesta_turnos.data
        
        col1, col2 = st.columns(2)
        with col1:
            if not turno_abierto:
                if st.button("🟢 MARCAR ENTRADA", use_container_width=True, disabled=not ubicacion_valida):
                    nuevo_registro = {
                        "empleado": emp,
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "entrada": datetime.now().strftime("%H:%M:%S"),
                        "horas": 0.0
                    }
                    supabase.table("asistencia").insert(nuevo_registro).execute()
                    st.rerun()
            else:
                st.button("🟢 ENTRADA REGISTRADA", disabled=True, use_container_width=True)
                
        with col2:
            if turno_abierto:
                if st.button("🔴 MARCAR SALIDA", use_container_width=True, disabled=not ubicacion_valida):
                    id_turno = turno_abierto[0]["id"]
                    hora_salida = datetime.now()
                    str_salida = hora_salida.strftime("%H:%M:%S")
                    str_entrada = turno_abierto[0]["entrada"]
                    fecha = turno_abierto[0]["fecha"]
                    
                    fmt = "%Y-%m-%d %H:%M:%S"
                    t_in = datetime.strptime(f"{fecha} {str_entrada}", fmt)
                    horas_trabajadas = (hora_salida - t_in).total_seconds() / 3600.0
                    
                    # Actualizar en Supabase
                    supabase.table("asistencia").update({"salida": str_salida, "horas": round(horas_trabajadas, 2)}).eq("id", id_turno).execute()
                    st.rerun()
            else:
                st.button("🔴 MARCAR SALIDA", disabled=True, use_container_width=True)
                
        st.write("### 📅 Mis horas trabajadas")
        respuesta_horas = supabase.table("asistencia").select("*").eq("empleado", emp).execute()
        if respuesta_horas.data:
            df_emp = pd.DataFrame(respuesta_horas.data)
            st.dataframe(df_emp[["fecha", "entrada", "salida", "horas"]], use_container_width=True)
            st.info(f"**Total acumulado:** {df_emp['horas'].sum():.2f} horas")
        else:
            st.info("Aún no tienes registros de horas.")

# ==========================================
# VISTA: ADMINISTRACIÓN
# ==========================================
elif tipo_acceso == "Administración":
    if not st.session_state.admin_logged_in:
        st.title("🔐 Acceso Administrativo")
        pwd = st.text_input("Contraseña de Administrador", type="password")
        if st.button("Entrar"):
            if pwd == "admin123": 
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    else:
        st.sidebar.markdown("---")
        if st.sidebar.button("Cerrar Sesión Admin"):
            st.session_state.admin_logged_in = False
            st.rerun()
            
        opcion_admin = st.sidebar.radio("Módulo:", ["Dashboard Principal", "🤖 Asistente Inteligente", "Personal y Planilla", "Salidas y Reportes"])

        # Descargar datos globales para el admin
        res_gastos = supabase.table("gastos").select("*").execute()
        res_horas = supabase.table("asistencia").select("*").execute()
        datos_gastos = res_gastos.data
        datos_horas = res_horas.data

        if opcion_admin == "Dashboard Principal":
            st.title("🕌 Jael - Panel de Control")
            total_gastos = sum(g["monto"] for g in datos_gastos) if datos_gastos else 0
            total_horas_todas = sum(t["horas"] for t in datos_horas) if datos_horas else 0
            total_nomina = total_horas_todas * 20.0 # Tarifa de $20
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(label="💰 Gastos Extra", value=f"${total_gastos:,.2f}")
            col2.metric(label="👥 Nómina Acumulada", value=f"${total_nomina:,.2f}")
            col3.metric(label="🏢 TOTAL OPERACIÓN", value=f"${(total_gastos + total_nomina):,.2f}")
            col4.metric(label="👷 Horas Registradas", value=f"{total_horas_todas:.1f}")

        elif opcion_admin == "🤖 Asistente Inteligente":
            st.title("🎙️ Asistente Inteligente")
            for msg in st.session_state.chat_history:
                if msg["role"] != "system" and msg.get("content"):
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])

            audio_value = st.audio_input("Grabar mensaje de voz", key="audio_recorder")
            texto_usuario = st.chat_input("O escribe tu instrucción...")
            mensaje_final = texto_usuario

            if not mensaje_final and audio_value is not None and st.session_state.get("last_audio") != audio_value:
                with st.spinner("Escuchando..."):
                    with open("temp.wav", "wb") as f: f.write(audio_value.getbuffer())
                    transcription = client.audio.transcriptions.create(model="whisper-1", file=open("temp.wav", "rb"))
                    mensaje_final = transcription.text
                    st.success(f"**Escuché:** {mensaje_final}")
                    st.session_state.last_audio = audio_value

            if mensaje_final:
                st.session_state.chat_history.append({"role": "user", "content": mensaje_final})
                with st.spinner("Jael está analizando..."):
                    mensajes_api = [{"role": "system", "content": "Eres Jael, asistente de la sinagoga."}]
                    mensajes_api.extend([{"role": m["role"], "content": m.get("content", "")} for m in st.session_state.chat_history])
                    response = client.chat.completions.create(model="gpt-3.5-turbo", messages=mensajes_api, tools=herramientas, tool_choice="auto")
                    mensaje_respuesta = response.choices[0].message
                    if getattr(mensaje_respuesta, "tool_calls", None):
                        for tool_call in mensaje_respuesta.tool_calls:
                            if tool_call.function.name == "registrar_gasto":
                                args = json.loads(tool_call.function.arguments)
                                # Guardar gasto en Supabase
                                supabase.table("gastos").insert({
                                    "fecha": datetime.now().strftime("%Y-%m-%d"), 
                                    "categoria": args["categoria"], 
                                    "descripcion": args["descripcion"], 
                                    "monto": args["monto"]
                                }).execute()
                                st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Gasto registrado en la base de datos permanente: ${args['monto']} en {args['categoria']}."})
                    else:
                        st.session_state.chat_history.append({"role": "assistant", "content": getattr(mensaje_respuesta, "content", "Entendido.")})
                st.rerun()

        elif opcion_admin == "Personal y Planilla":
            st.title("👥 Control de Empleados")
            with st.form("nuevo_emp_form"):
                col1, col2 = st.columns(2)
                with col1: nuevo_nombre = st.text_input("Nombre Completo")
                with col2: nuevo_pin = st.text_input("Crear PIN (4 dígitos)", max_chars=4)
                if st.form_submit_button("Añadir Empleado") and nuevo_nombre and nuevo_pin:
                    # Guardar empleado en Supabase
                    supabase.table("empleados").insert({"nombre": nuevo_nombre, "pin": nuevo_pin}).execute()
                    st.success(f"✅ {nuevo_nombre} añadido a la base de datos.")
            
            st.write("---")
            if datos_horas:
                df_global = pd.DataFrame(datos_horas)
                df_global["pago ($)"] = df_global["horas"] * 20.0
                st.dataframe(df_global[["empleado", "fecha", "entrada", "salida", "horas", "pago ($)"]], use_container_width=True)
            else:
                st.info("Nadie ha registrado horas todavía.")

        elif opcion_admin == "Salidas y Reportes":
            st.title("📈 Gastos y Salidas")
            with st.form("registro_gasto"):
                col1, col2, col3 = st.columns(3)
                with col1: categoria = st.selectbox("Categoría", ["Desayunos de fin de semana", "Insumos de Limpieza", "Mantenimiento / Cuarto", "Proveedores (Pedidos fijos)", "Otros Gastos Extra"])
                with col2: descripcion = st.text_input("Descripción")
                with col3: monto = st.number_input("Monto ($)", min_value=0.0, step=1.0)
                if st.form_submit_button("Guardar Gasto") and descripcion and monto > 0:
                    supabase.table("gastos").insert({
                        "fecha": datetime.now().strftime("%Y-%m-%d"), 
                        "categoria": categoria, 
                        "descripcion": descripcion, 
                        "monto": monto
                    }).execute()
                    st.success("✅ Guardado en la nube.")

            if datos_gastos:
                df_gastos = pd.DataFrame(datos_gastos)
                col1, col2 = st.columns([1, 1])
                with col1: st.dataframe(df_gastos[["fecha", "categoria", "descripcion", "monto"]], use_container_width=True)
                with col2: st.altair_chart(alt.Chart(df_gastos.groupby("categoria")["monto"].sum().reset_index()).mark_bar().encode(x='categoria', y='monto', color=alt.Color('categoria', legend=None)).properties(height=300), use_container_width=True)
