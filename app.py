import streamlit as st
import pandas as pd
import altair as alt
import json
from datetime import datetime
from openai import OpenAI
import os
import io

# Configuración inicial
st.set_page_config(page_title="Jael - Asistente de la Sinagoga", page_icon="🕌", layout="wide")
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.sidebar.title("Menú de Navegación")
opcion = st.sidebar.radio(
    "Selecciona un módulo:",
    ["Dashboard Principal", "🤖 Asistente Inteligente", "Control de Personal", "Salidas y Reportes"]
)

# Bases de datos en sesión
if "nomina" not in st.session_state: st.session_state.nomina = []
if "gastos" not in st.session_state: st.session_state.gastos = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "¡Hola! Soy Jael. Puedes hablarme por micrófono o escribirme. Dime si necesitas registrar un gasto."}]

# Herramienta para registrar gastos
herramientas = [
    {
        "type": "function",
        "function": {
            "name": "registrar_gasto",
            "description": "Registra un nuevo gasto o compra en la base de datos de la sinagoga.",
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

# --- DASHBOARD PRINCIPAL ---
if opcion == "Dashboard Principal":
    st.title("🕌 Jael - Panel de Control")
    st.write("Resumen financiero y operativo de Safra y Jemal")
    st.write("---")
    
    # Calcular totales
    total_gastos = sum(g["Monto ($)"] for g in st.session_state.gastos) if st.session_state.gastos else 0
    total_nomina = sum(float(n["Pago Total"].replace("$", "")) for n in st.session_state.nomina) if st.session_state.nomina else 0
    total_empleados = len(st.session_state.nomina)
    total_operacion = total_gastos + total_nomina
    
    # Mostrar tarjetas con números grandes
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="💰 Gastos de la Semana", value=f"${total_gastos:,.2f}")
    col2.metric(label="👥 Pago de Nómina", value=f"${total_nomina:,.2f}")
    col3.metric(label="🏢 TOTAL OPERACIÓN", value=f"${total_operacion:,.2f}")
    col4.metric(label="👷 Empleados Activos", value=f"{total_empleados}")
    
    st.write("---")
    
    # Mostrar resumen rápido en dos columnas
    col_g, col_n = st.columns(2)
    with col_g:
        st.subheader("Últimos Gastos Registrados")
        if st.session_state.gastos:
            st.dataframe(pd.DataFrame(st.session_state.gastos).tail(5), use_container_width=True)
        else:
            st.info("No hay gastos registrados aún.")
            
    with col_n:
        st.subheader("Estado de la Planilla")
        if st.session_state.nomina:
            st.dataframe(pd.DataFrame(st.session_state.nomina), use_container_width=True)
        else:
            st.info("No hay horas registradas aún.")

# --- ASISTENTE INTELIGENTE ---
elif opcion == "🤖 Asistente Inteligente":
    st.title("🎙️ Asistente Inteligente")
    for msg in st.session_state.chat_history:
        if msg["role"] != "system" and msg.get("content"):
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    audio_value = st.audio_input("Grabar mensaje de voz", key="audio_recorder")
    texto_usuario = st.chat_input("O escribe tu instrucción...")
    mensaje_final = None

    if texto_usuario:
        mensaje_final = texto_usuario
    elif audio_value is not None and st.session_state.get("last_audio") != audio_value:
        with st.spinner("Escuchando..."):
            with open("temp.wav", "wb") as f: f.write(audio_value.getbuffer())
            transcription = client.audio.transcriptions.create(model="whisper-1", file=open("temp.wav", "rb"))
            mensaje_final = transcription.text
            st.success(f"**Escuché:** {mensaje_final}")
            st.session_state.last_audio = audio_value

    if mensaje_final:
        st.session_state.chat_history.append({"role": "user", "content": mensaje_final})
        with st.spinner("Jael está analizando..."):
            mensajes_api = [{"role": "system", "content": "Eres Jael, la asistente administrativa oficial de las sinagogas Safra y Jemal. Eres amable, profesional y directa. Conoces las tarifas de pago ($20/hora) y las categorías de gastos (Desayunos, Limpieza, Mantenimiento). Tu trabajo principal es ayudar al administrador. Usa la herramienta registrar_gasto SOLO si el usuario te pide registrar una compra. Responde siempre en el mismo idioma en el que te hablen."}]
            mensajes_api.extend([{"role": m["role"], "content": m.get("content", "")} for m in st.session_state.chat_history])
            response = client.chat.completions.create(model="gpt-3.5-turbo", messages=mensajes_api, tools=herramientas, tool_choice="auto")
            mensaje_respuesta = response.choices[0].message
            if getattr(mensaje_respuesta, "tool_calls", None):
                for tool_call in mensaje_respuesta.tool_calls:
                    if tool_call.function.name == "registrar_gasto":
                        argumentos = json.loads(tool_call.function.arguments)
                        st.session_state.gastos.append({"Fecha": datetime.now().strftime("%Y-%m-%d"), "Categoría": argumentos["categoria"], "Descripción": argumentos["descripcion"], "Monto ($)": argumentos["monto"]})
                        st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Gasto registrado: ${argumentos['monto']} en {argumentos['categoria']}."})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": getattr(mensaje_respuesta, "content", "Entendido.")})
        st.rerun()

# --- NÓMINA ---
elif opcion == "Control de Personal":
    st.title("👥 Control de Personal y Planilla")
    tarifa_hora = 20.00
    st.info(f"💵 Tarifa base: **${tarifa_hora:.2f}**")
    with st.form("registro_horas"):
        col1, col2 = st.columns(2)
        with col1: nombre = st.text_input("Nombre del Empleado")
        with col2: horas = st.number_input("Horas Trabajadas", min_value=0.0, step=0.5)
        if st.form_submit_button("Registrar") and nombre:
            st.session_state.nomina.append({"Empleado": nombre, "Horas": horas, "Tarifa": f"${tarifa_hora:.2f}", "Pago Total": f"${horas*tarifa_hora:.2f}"})
            st.success("✅ Guardado")
    if st.session_state.nomina: st.dataframe(pd.DataFrame(st.session_state.nomina), use_container_width=True)

# --- REPORTES ---
elif opcion == "Salidas y Reportes":
    st.title("📈 Control de Gastos y Salidas")
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
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_gastos.to_excel(writer, sheet_name='Gastos', index=False)
        st.download_button(label="📥 Descargar Reporte en Excel", data=buffer.getvalue(), file_name=f"Reporte_{datetime.now().strftime('%Y-%m-%d')}.xlsx", mime="application/vnd.ms-excel", type="primary")
        col1, col2 = st.columns([1, 1])
        with col1: st.dataframe(df_gastos, use_container_width=True)
        with col2: st.altair_chart(alt.Chart(df_gastos.groupby("Categoría")["Monto ($)"].sum().reset_index()).mark_bar(size=30).encode(x=alt.X('Categoría', title=''), y=alt.Y('Monto ($)', title='Total ($)'), color=alt.Color('Categoría', legend=None)).properties(height=300), use_container_width=True)
