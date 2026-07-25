import streamlit as st
import pandas as pd
from datetime import datetime

# Configuración inicial de la página
st.set_page_config(
    page_title="Jael - Asistente de la Sinagoga",
    page_icon="🕌",
    layout="wide"
)

# Título y saludo
st.title("🕌 Jael - Asistente de la Sinagoga")
st.write("¡Hola, mundo! Esta es la nueva página web de Jael.")

# Menú lateral para navegación
st.sidebar.title("Menú de Navegación")
opcion = st.sidebar.radio(
    "Selecciona un módulo:",
    ["Dashboard Principal", "Control de Personal", "Salidas y Reportes", "Configuración"]
)

if opcion == "Dashboard Principal":
    st.header("📊 Resumen de Actividades")
    st.write("Aquí irán los indicadores principales y las actividades pendientes.")

elif opcion == "Control de Personal":
    st.header("👥 Control de Personal y Planilla")
    st.write("Tarifa base por hora configurada: $20.00")
    
    # Ejemplo de tabla de personal
    datos_personal = pd.DataFrame({
        "Nombre": ["Empleado 1", "Empleado 2"],
        "Horas Trabajadas": [40, 35],
        "Pago Total ($)": [800, 700]
    })
    st.dataframe(datos_personal)

elif opcion == "Salidas y Reportes":
    st.header("📈 Reportes de Gastos y Salidas")
    st.write("Los reportes en Excel y gráficos se generarán los domingos a las 12:00 AM.")
    
    # Ejemplo de gráfico de gastos
    datos_gastos = pd.DataFrame({
        "Categoría": ["Desayunos", "Limpieza", "Mantenimiento"],
        "Monto ($)": [300, 150, 400]
    })
    st.bar_chart(datos_gastos.set_index("Categoría"))

elif opcion == "Configuración":
    st.header("⚙️ Configuración del Sistema")
    st.write("Aquí puedes ajustar parámetros de geolocalización, proveedores y otros ajustes.")
