import streamlit as st
import pandas as pd
import altair as alt
import json
from datetime import datetime
from openai import OpenAI
import os
import io

# Configuración inicial 
st.set_page_config(page_title="Jael - Asistente de la Sinagoga", page_icon="🕌", layout="wide", initial_sidebar_state="auto")

# TRUCO CSS: Solo ocultamos GitHub, el botón Deploy y el footer. 
ocultar_menu = """
    <style>
    #MainMenu {visibility: hidden;}
    .stAppDeployButton {display:none;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(ocultar_menu, unsafe_allow_html=True)
st.set_option("client.toolbarMode", "viewer")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- BASES DE DATOS EN SESIÓN ---
if "gastos" not in st.session_state: st.session_state.gastos = []
if "empleados" not in st.session_state: st.session_state.empleados = {"Juan Perez": "1234"} # Empleado de prueba
if "asistencia" not in st.session_state: st.session_state.asistencia = []
if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if "emp_logged_in" not in st.session_state: st.session_state.emp_logged_in = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "¡Hola! Soy Jael. Puedes hablarme por micrófono o escribirme. Dime si necesitas registrar un gasto."}]

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
    
    if st.session_state.emp_logged_in is None:
        st.write("Por favor, identifícate para marcar tu entrada o salida.")
        nombres = list(st.session_state.empleados.keys())
        if not nombres:
            st.warning("No hay empleados registrados todavía.")
        else:
            emp_sel = st.selectbox("Tu Nombre", nombres)
            pin_input = st.text_input("Tu PIN (4 dígitos)", type="password", max_chars=4)
            if st.button("Ingresar"):
                if st.session_state.empleados[emp_sel] == pin_input:
                    st.session_state.emp_logged_in = emp_sel
                    st.rerun()
                else:
                    st.error("PIN incorrecto. Intenta de nuevo.")
    else:
        emp = st.session_state.emp_logged_in
        st.success(f"Hola, **{emp}**")
        
        # ERROR CORREGIDO: Se eliminó el parámetro size="small" que causaba el fallo
        if st.button("Cerrar mi sesión"):
            st.session_state.emp_logged_in = None
            st.rerun()
            
        st.write("---")
        turnos_abiertos = [i for i, t in enumerate(st.session_state.asistencia) if t["Empleado"] == emp and t["Salida"] is None]
        
        col1, col2 = st.columns(2)
        with col1:
            if not turnos_abiertos:
                if st.button("🟢 MARCAR ENTRADA", use_container_width=True):
                    st.session_state.asistencia.append({
                        "Empleado": emp,
                        "Fecha": datetime.now().strftime("%Y-%m-%d"),
                        "Entrada": datetime.now().strftime("%H:%M:%S"),
                        "Salida": None,
                        "Horas": 0.0
                    })
                    st.rerun()
            else:
                st.button("🟢 ENTRADA REGISTRADA", disabled=True, use_container_width=True)
                
        with col2:
            if turnos_abiertos:
                if st.button("🔴 MARCAR SALIDA", use_container_width=True):
                    idx = turnos_abiertos[0]
                    hora_salida = datetime.now()
                    str_salida = hora_salida.strftime("%H:%M:%S")
                    str_entrada = st.session_state.asistencia[idx]["Entrada"]
                    fecha = st.session_state.asistencia[idx]["Fecha"]
                    
                    # Calculamos las horas transcurridas
                    fmt = "%Y-%m-%d %H:%M:%S"
                    t_in = datetime.strptime(f"{fecha} {str_entrada}", fmt)
                    horas_trabajadas = (hora_salida - t_in).total_seconds() / 3600.0
                    
                    st.session_state.asistencia[idx]["Salida"] = str_salida
                    st.session_state.asistencia[idx]["Horas"] = round(horas_trabajadas, 2)
                    st.rerun()
            else:
                st.button("🔴 MARCAR SALIDA", disabled=True, use_container_width=True)
                
        st.write("### 📅 Mis horas trabajadas")
        df_emp = pd.DataFrame([t for t in st.session_state.asistencia if t["Empleado"] == emp])
        if not df_emp.empty:
            st.dataframe(df_emp[["Fecha", "Entrada", "Salida", "Horas"]], use_container_width=True)
            st.info(f"**Total acumulado:** {df_emp['Horas'].sum():.2f} horas")
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
            # Contraseña por defecto (puedes cambiarla aquí):
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

        # --- DASHBOARD PRINCIPAL ---
        if opcion_admin == "Dashboard Principal":
            st.title("🕌 Jael - Panel de Control")
            st.write("Resumen financiero y operativo")
            st.write("---")
            total_gastos = sum(g["Monto ($)"] for g in st.session_state.gastos) if st.session_state.gastos else 0
            
            # Cálculo de nómina en base a horas * $20
            tarifa = 20.0
            total_horas_todas = sum(t["Horas"] for t in st.session_state.asistencia)
            total_nomina = total_horas_todas * tarifa
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(label="💰 Gastos Extra", value=f"${total_gastos:,.2f}")
            col2.metric(label="👥 Nómina Acumulada", value=f"${total_nomina:,.2f}")
            col3.metric(label="🏢 TOTAL OPERACIÓN", value=f"${(total_gastos + total_nomina):,.2f}")
            col4.metric(label="👷 Horas Registradas", value=f"{total_horas_todas:.1f}")

        # --- ASISTENTE INTELIGENTE ---
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
                    mensajes_api = [{"role": "system", "content": "Eres Jael, asistente de la sinagoga. Responde siempre de forma profesional."}]
                    mensajes_api.extend([{"role": m["role"], "content": m.get("content", "")} for m in st.session_state.chat_history])
                    response = client.chat.completions.create(model="gpt-3.5-turbo", messages=mensajes_api, tools=herramientas, tool_choice="auto")
                    mensaje_respuesta = response.choices[0].message
                    if getattr(mensaje_respuesta, "tool_calls", None):
                        for tool_call in mensaje_respuesta.tool_calls:
                            if tool_call.function.name == "registrar_gasto":
                                args = json.loads(tool_call.function.arguments)
                                st.session_state.gastos.append({"Fecha": datetime.now().strftime("%Y-%m-%d"), "Categoría": args["categoria"], "Descripción": args["descripcion"], "Monto ($)": args["monto"]})
                                st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Gasto registrado: ${args['monto']} en {args['categoria']}."})
                    else:
                        st.session_state.chat_history.append({"role": "assistant", "content": getattr(mensaje_respuesta, "content", "Entendido.")})
                st.rerun()

        # --- PERSONAL Y PLANILLA ---
        elif opcion_admin == "Personal y Planilla":
            st.title("👥 Control de Empleados")
            
            st.subheader("Crear Nuevo Empleado")
            with st.form("nuevo_emp_form"):
                col1, col2 = st.columns(2)
                with col1: nuevo_nombre = st.text_input("Nombre Completo")
                with col2: nuevo_pin = st.text_input("Crear PIN (4 dígitos)", max_chars=4)
                if st.form_submit_button("Añadir Empleado") and nuevo_nombre and nuevo_pin:
                    st.session_state.empleados[nuevo_nombre] = nuevo_pin
                    st.success(f"✅ {nuevo_nombre} añadido correctamente.")
            
            st.write("---")
            st.subheader("Registro de Horas Global")
            if st.session_state.asistencia:
                df_global = pd.DataFrame(st.session_state.asistencia)
                df_global["Pago ($)"] = df_global["Horas"] * 20.0  # Asumiendo tarifa $20/hr
                st.dataframe(df_global, use_container_width=True)
            else:
                st.info("Nadie ha registrado horas todavía.")

        # --- REPORTES Y SALIDAS ---
        elif opcion_admin == "Salidas y Reportes":
            st.title("📈 Gastos y Salidas")
            with st.form("registro_gasto"):
                col1, col2, col3 = st.columns(3)
                with col1: categoria = st.selectbox("Categoría", ["Desayunos de fin de semana", "Insumos de Limpieza", "Mantenimiento / Cuarto", "Proveedores (Pedidos fijos)", "Otros Gastos Extra"])
                with col2: descripcion = st.text_input("Descripción")
                with col3: monto = st.number_input("Monto ($)", min_value=0.0, step=1.0)
                if st.form_submit_button("Guardar Gasto") and descripcion and monto > 0:
                    st.session_state.gastos.append({"Fecha": datetime.now().strftime("%Y-%m-%d"), "Categoría": categoria, "Descripción": descripcion, "Monto ($)": monto})
                    st.success("✅ Guardado")

            if st.session_state.gastos:
                df_gastos = pd.DataFrame(st.session_state.gastos)
                col1, col2 = st.columns([1, 1])
                with col1: st.dataframe(df_gastos, use_container_width=True)
                with col2: st.altair_chart(alt.Chart(df_gastos.groupby("Categoría")["Monto ($)"].sum().reset_index()).mark_bar().encode(x='Categoría', y='Monto ($)', color=alt.Color('Categoría', legend=None)).properties(height=300), use_container_width=True)
