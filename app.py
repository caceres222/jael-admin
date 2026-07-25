import streamlit as st
import pandas as pd
import altair as alt  # <-- Añadimos esta librería para mejores gráficos
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
    tarifa_hora = 20.00
    st.info(f"💵 Tarifa base por hora configurada: **${tarifa_hora:.2f}**")
    
    if "nomina" not in st.session_state:
        st.session_state.nomina = []
        
    with st.form("registro_horas"):
        st.subheader("Registrar Horas Trabajadas")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre del Empleado")
        with col2:
            horas = st.number_input("Horas Trabajadas", min_value=0.0, step=0.5)
        
        if st.form_submit_button("Registrar en Planilla") and nombre:
            pago_total = horas * tarifa_hora
            st.session_state.nomina.append({"Empleado": nombre, "Horas": horas, "Tarifa": f"${tarifa_hora:.2f}", "Pago Total": f"${pago_total:.2f}"})
            st.success(f"✅ Registrado: {nombre} - Pago: ${pago_total:.2f}")
            
    if st.session_state.nomina:
        st.subheader("📋 Planilla Actual")
        st.dataframe(pd.DataFrame(st.session_state.nomina), use_container_width=True)
        if st.button("🔴 Hacer Corte Quincenal (Limpiar Tabla)"):
            st.session_state.nomina = []
            st.rerun()

elif opcion == "Salidas y Reportes":
    st.header("📈 Control de Gastos y Salidas")
    
    if "gastos" not in st.session_state:
        st.session_state.gastos = []
        
    with st.form("registro_gasto"):
        st.subheader("Registrar Nueva Compra o Gasto")
        col1, col2, col3 = st.columns(3)
        with col1:
            categoria = st.selectbox("Categoría", ["Desayunos de fin de semana", "Insumos de Limpieza", "Mantenimiento / Cuarto", "Proveedores (Pedidos fijos)", "Otros Gastos Extra"])
        with col2:
            descripcion = st.text_input("Descripción breve (ej. Frutas, Cloro, etc.)")
        with col3:
            monto = st.number_input("Monto Pagado ($)", min_value=0.0, step=1.0)
            
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        
        if st.form_submit_button("Guardar Gasto") and descripcion and monto > 0:
            st.session_state.gastos.append({
                "Fecha": fecha_actual,
                "Categoría": categoria,
                "Descripción": descripcion,
                "Monto ($)": monto
            })
            st.success(f"✅ Gasto guardado: {descripcion} por ${monto:.2f}")

    if st.session_state.gastos:
        df_gastos = pd.DataFrame(st.session_state.gastos)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📋 Historial de Gastos")
            st.dataframe(df_gastos, use_container_width=True)
            
        with col2:
            st.subheader("📊 Gastos por Categoría")
            gastos_agrupados = df_gastos.groupby("Categoría")["Monto ($)"].sum().reset_index()
            
            # NUEVO GRÁFICO CON BARRAS DELGADAS (30px)
            chart = alt.Chart(gastos_agrupados).mark_bar(size=30).encode(
                x=alt.X('Categoría', title=''),
                y=alt.Y('Monto ($)', title='Total Gastado ($)'),
                color=alt.Color('Categoría', legend=None)
            ).properties(height=300)
            
            st.altair_chart(chart, use_container_width=True)
            
            # Mostrar total gastado
            total = df_gastos["Monto ($)"].sum()
            st.info(f"💰 **Total Acumulado:** ${total:.2f}")

elif opcion == "Configuración":
    st.header("⚙️ Configuración del Sistema")
    st.write("Aquí puedes ajustar parámetros de geolocalización, proveedores y otros ajustes.")
