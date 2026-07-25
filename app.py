import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from openai import OpenAI
import os

# Configuración inicial de la página
st.set_page_config(page_title="Jael - Asistente de la Sinagoga", page_icon="🕌", layout="wide")

# Conectar OpenAI con la llave secreta
# Streamlit busca en sus 'secrets' automáticamente
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Título y saludo
st.title("🕌 Jael - Asistente de la Sinagoga")
st.write("Administración central para Safra y Jemal")

# Menú lateral para navegación
st.sidebar.title("Menú de Navegación")
opcion = st.sidebar.radio(
    "Selecciona un módulo:",
    ["🤖 Hablar con Jael", "Dashboard Principal", "Control de Personal", "Salidas y Reportes"]
)

# Base de datos global en sesión para que Jael pueda leerla
if "nomina" not in st.session_state:
    st.session_state.nomina = []
if "gastos" not in st.session_state:
    st.session_state.gastos = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "¡Hola! Soy Jael. Puedes hablarme por micrófono o escribirme. ¿En qué te ayudo hoy?"}]

if opcion == "🤖 Hablar con Jael":
    st.header("🎙️ Asistente Inteligente")
    st.write("Háblame en español o inglés. Puedo registrar gastos o analizar la nómina.")

    # Mostrar historial del chat
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Grabar voz
    audio_value = st.audio_input("Grabar mensaje de voz para Jael")
    
    # Escribir texto
    texto_usuario = st.chat_input("O escribe tu instrucción aquí...")

    mensaje_final = None

    if texto_usuario:
        mensaje_final = texto_usuario

    elif audio_value:
        # Si grabó audio, convertirlo a texto usando Whisper
        with st.spinner("Escuchando..."):
            # Guardar temporalmente el audio para que OpenAI lo lea
            with open("temp_audio.wav", "wb") as f:
                f.write(audio_value.getbuffer())
            
            audio_file = open("temp_audio.wav", "rb")
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            mensaje_final = transcription.text
            st.success(f"**Escuché:** {mensaje_final}")

    # Procesar el mensaje (sea de texto o voz)
    if mensaje_final:
        # Guardar mensaje del usuario
        st.session_state.chat_history.append({"role": "user", "content": mensaje_final})
        
        # Enviar a OpenAI
        with st.spinner("Jael está pensando..."):
            contexto = f"Eres Jael, asistente de las sinagogas Safra y Jemal. Responde en el mismo idioma que el usuario. Total de gastos registrados: {len(st.session_state.gastos)}. Empleados en nómina: {len(st.session_state.nomina)}."
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": contexto},
                    {"role": "user", "content": mensaje_final}
                ]
            )
            respuesta_jael = response.choices[0].message.content
            
        # Guardar y mostrar respuesta de Jael
        st.session_state.chat_history.append({"role": "assistant", "content": respuesta_jael})
        st.rerun()

elif opcion == "Control de Personal":
    st.header("👥 Control de Personal y Planilla")
    tarifa_hora = 20.00
    st.info(f"💵 Tarifa base por hora configurada: **${tarifa_hora:.2f}**")
    
    with st.form("registro_horas"):
        col1, col2 = st.columns(2)
        with col1: nombre = st.text_input("Nombre del Empleado")
        with col2: horas = st.number_input("Horas Trabajadas", min_value=0.0, step=0.5)
        if st.form_submit_button("Registrar en Planilla") and nombre:
            pago_total = horas * tarifa_hora
            st.session_state.nomina.append({"Empleado": nombre, "Horas": horas, "Tarifa": f"${tarifa_hora:.2f}", "Pago Total": f"${pago_total:.2f}"})
            st.success("✅ Guardado")
            
    if st.session_state.nomina:
        st.dataframe(pd.DataFrame(st.session_state.nomina), use_container_width=True)

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
        with col2:
            chart = alt.Chart(df_gastos.groupby("Categoría")["Monto ($)"].sum().reset_index()).mark_bar(size=30).encode(x=alt.X('Categoría', title=''), y=alt.Y('Monto ($)', title='Total ($)'), color=alt.Color('Categoría', legend=None)).properties(height=300)
            st.altair_chart(chart, use_container_width=True)

elif opcion == "Dashboard Principal":
    st.header("📊 Resumen de Actividades")
    st.write("Registra datos en los otros módulos para ver el resumen aquí.")
