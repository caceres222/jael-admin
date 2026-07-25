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
st.write("Administración central para Safra y Jemal")

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
    
    # Tarifa fija definida
    tarifa_hora = 20.00
    st.info(f"💵 Tarifa base por hora configurada: **${tarifa_hora:.2f}**")
    st.write("Corte de nómina: **Cada 15 días**")
    
    # Inicializar la base de datos temporal para la sesión
    if "nomina" not in st.session_state:
        st.session_state.nomina = []
        
    # Formulario para registrar horas
    with st.form("registro_horas"):
        st.subheader("Registrar Horas Trabajadas")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre del Empleado")
        with col2:
            horas = st.number_input("Horas Trabajadas", min_value=0.0, step=0.5)
        
        submit = st.form_submit_button("Registrar en Planilla")
        
        if submit and nombre:
            pago_total = horas * tarifa_hora
            st.session_state.nomina.append({
                "Empleado": nombre,
                "Horas": horas,
                "Tarifa": f"${tarifa_hora:.2f}",
                "Pago Total": f"${pago_total:.2f}"
            })
            st.success(f"✅ Registrado: {nombre} - Pago calculado: ${pago_total:.2f}")
            
    # Mostrar la tabla actualizada
    if st.session_state.nomina:
        st.subheader("📋 Planilla Actual (Quincenal)")
        df_nomina = pd.DataFrame(st.session_state.nomina)
        st.dataframe(df_nomina, use_container_width=True)
        
        if st.button("🔴 Hacer Corte Quincenal (Limpiar Tabla)"):
            st.session_state.nomina = []
            st.rerun()

elif opcion == "Salidas y Reportes":
    st.header("📈 Reportes de Gastos y Salidas")
    st.write("Los reportes en Excel y gráficos se generarán los domingos a las 12:00 AM.")
    datos_gastos = pd.DataFrame({"Categoría": ["Desayunos", "Limpieza"], "Monto ($)": [300, 150]})
    st.bar_chart(datos_gastos.set_index("Categoría"))

elif opcion == "Configuración":
    st.header("⚙️ Configuración del Sistema")
    st.write("Aquí puedes ajustar parámetros de geolocalización, proveedores y otros ajustes.")
