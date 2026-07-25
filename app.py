import streamlit as st
import pandas as pd
import altair as alt
import json
from datetime import datetime
from openai import OpenAI
import os

# Configuración inicial
st.set_page_config(page_title="Jael - Asistente de la Sinagoga", page_icon="🕌", layout="wide")
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🕌 Jael - Asistente de la Sinagoga")
st.write("Administración central para Safra y Jemal")

st.sidebar.title("Menú de Navegación")
opcion = st.sidebar.radio(
    "Selecciona un módulo:",
    ["🤖 Hablar con Jael", "Dashboard Principal", "Control de Personal", "Salidas y Reportes"]
)

# Bases de datos en sesión
if "nomina" not in st.session_state: st.session_state.nomina = []
if "gastos" not in st.session_state: st.session_state.gastos = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "¡Hola! Soy Jael. Puedes hablarme o escribirme. Dime si necesitas registrar un gasto."}]

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

if opcion == "🤖 Hablar con Jael":
    st.header("🎙️ Asistente Inteligente")

    # Mostrar historial de chat
    for msg in st.session_state.chat_history:
        if msg["role"] != "system" and msg.get("content"):
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    # Controles de entrada
    audio_value = st.audio_input("Grabar mensaje de voz", key="audio_recorder")
    texto_usuario = st.chat_input("O escribe tu instrucción...")
    
    mensaje_final = None

    # Procesar solo si hay un texto NUEVO o un audio NUEVO
    if texto_usuario:
        mensaje_final = texto_usuario
    
    # Verificamos que el audio exista y no lo hayamos procesado antes
    elif audio_value is not None and st.session_state.get("last_audio") != audio_value:
        with st.spinner("Escuchando..."):
            with open("temp.wav", "wb") as f: 
                f.write(audio_value.getbuffer())
            transcription = client.audio.transcriptions.create(model="whisper-1", file=open("temp.wav", "rb"))
            mensaje_final = transcription.text
            st.success(f"**Escuché:** {mensaje_final}")
            # Guardamos el audio como "ya procesado"
            st.session_state.last_audio = audio_value

    if mensaje_final:
        st.session_state.chat_history.append({"role": "user", "content": mensaje_final})
        
        with st.spinner("Jael está analizando..."):
            mensajes_api = [{"role": "system", "content": "Eres Jael. Usa la herramienta registrar_gasto si mencionan un gasto."}]
            mensajes_api.extend([{"role": m["role"], "content": m.get("content", "")} for m in st.session_state.chat_history])
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=mensajes_api,
                tools=herramientas,
                tool_choice="auto"
            )
            
            mensaje_respuesta = response.choices[0].message
            
            if getattr(mensaje_respuesta, "tool_calls", None):
                for tool_call in mensaje_respuesta.tool_calls:
                    if tool_call.function.name == "registrar_gasto":
                        argumentos = json.loads(tool_call.function.arguments)
                        st.session_state.gastos.append({
                            "Fecha": datetime.now().strftime("%Y-%m-%d"),
                            "Categoría": argumentos["categoria"],
                            "Descripción": argumentos["descripcion"],
                            "Monto ($)": argumentos["monto"]
                        })
                        st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Gasto registrado: ${argumentos['monto']} en {argumentos['categoria']} ({argumentos['descripcion']})."})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": getattr(mensaje_respuesta, "content", "Entendido.")})
                
        st.rerun()

# --- DEMÁS MÓDULOS ---
elif opcion == "Control de Personal":
    st.header("👥 Control de Personal y Planilla")
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

elif opcion == "Salidas y Reportes":
    st.header("📈 Control de Gastos y Salidas")
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
        with col2: st.altair_chart(alt.Chart(df_gastos.groupby("Categoría")["Monto ($)"].sum().reset_index()).mark_bar(size=30).encode(x=alt.X('Categoría', title=''), y=alt.Y('Monto ($)', title='Total ($)'), color=alt.Color('Categoría', legend=None)).properties(height=300), use_container_width=True)

elif opcion == "Dashboard Principal":
    st.header("📊 Resumen de Actividades")
    st.write("Registra datos en los otros módulos para ver el resumen aquí.")
