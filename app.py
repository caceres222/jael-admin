import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os
from datetime import datetime
import pandas as pd
from streamlit_geolocation import streamlit_geolocation
from io import BytesIO
import base64
import json

# ==========================================
# CONFIGURACIÓN BÁSICA
# ==========================================
load_dotenv()
cliente = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
st.set_page_config(page_title="Jael Admin", layout="wide")

EMPLEADO_ACTUAL = "Gustavo"
TARIFA_POR_HORA = 20.00  

# ==========================================
# INICIALIZACIÓN DE BASES DE DATOS SIMULADAS
# ==========================================
if "sinagoga_actual" not in st.session_state:
    st.session_state.sinagoga_actual = "Safra"

if "registros_personal" not in st.session_state:
    st.session_state.registros_personal = [
        ["David", "Vigilancia", "Entrada Regular", "2026-07-22 08:00:00", "25.76,-80.19", ""],
        ["David", "Vigilancia", "Salida Regular", "2026-07-22 12:00:00", "25.76,-80.19", ""],
        ["Sara", "Limpieza", "Entrada Regular", "2026-07-22 09:00:00", "25.76,-80.19", ""]
    ]

if "mensajes" not in st.session_state:
    st.session_state.mensajes = [
        {"role": "assistant", "content": f"¡Hola {EMPLEADO_ACTUAL}! Soy Jael. Conozco todos los datos de nómina y gastos de tus sedes. ¿En qué te ayudo hoy?"}
    ]

if "gastos_registrados" not in st.session_state:
    st.session_state.gastos_registrados = [
        ["Gusto Alimentos", 450.00, "Alimentos/Desayunos", "2026-07-16", "Aprobado"],
        ["Ferretería Eléctrica", 120.00, "Mantenimiento", "2026-07-20", "Pendiente"]
    ]

if "factura_auto" not in st.session_state:
    st.session_state.factura_auto = {
        "proveedor": "",
        "monto": 0.00,
        "categoria": "Otros",
        "fecha": datetime.now().date()
    }

# ==========================================
# FUNCIONES MATEMÁTICAS Y DE EXCEL
# ==========================================
def calcular_nomina_general(registros):
    resumen = {}
    for r in registros:
        emp = r[0]
        accion = r[2]
        hora = datetime.strptime(r[3], "%Y-%m-%d %H:%M:%S")
        if emp not in resumen:
            resumen[emp] = {"ultima_entrada": None, "horas_totales": 0.0}
        if "Entrada" in accion:
            resumen[emp]["ultima_entrada"] = hora
        elif "Salida" in accion and resumen[emp]["ultima_entrada"] is not None:
            horas_fragmento = (hora - resumen[emp]["ultima_entrada"]).total_seconds() / 3600
            resumen[emp]["horas_totales"] += horas_fragmento
            resumen[emp]["ultima_entrada"] = None 

    datos_tabla = []
    for emp, data in resumen.items():
        hrs = round(data["horas_totales"], 2)
        pago = round(hrs * TARIFA_POR_HORA, 2)
        datos_tabla.append({"Empleado": emp, "Horas Totales": hrs, "Costo Nómina ($)": pago})
    return pd.DataFrame(datos_tabla)

def generar_excel_personal(df_registros, df_resumen):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_registros.to_excel(writer, sheet_name='Detalle de Fichajes', index=False)
        df_resumen.to_excel(writer, sheet_name='Resumen Quincenal', index=False)
    return output.getvalue()

def generar_excel_gastos(df_gastos, tipo_reporte):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_gastos.to_excel(writer, sheet_name=tipo_reporte, index=False)
    return output.getvalue()

def limpiar_formulario_factura():
    st.session_state.factura_auto = {"proveedor": "", "monto": 0.00, "categoria": "Otros", "fecha": datetime.now().date()}

# ==========================================
# MENÚ LATERAL
# ==========================================
with st.sidebar:
    st.title("⚙️ Panel de Control")
    opcion = st.selectbox("Selecciona un módulo:", 
                          ["⏱️ Control de Personal",
                           "💬 Asistente Virtual", 
                           "📊 Control de Gastos"])
    st.divider()
    st.write("Usuario Activo:")
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=70)
    st.write(f"**Nombre:** {EMPLEADO_ACTUAL}")
    
    st.session_state.sinagoga_actual = st.selectbox("📍 Sede Activa:", ["Safra", "Jemal"], index=["Safra", "Jemal"].index(st.session_state.sinagoga_actual))

# ==========================================
# MÓDULO 1: CONTROL DE PERSONAL (ACTIVO)
# ==========================================
if opcion == "⏱️ Control de Personal":
    st.title(f"⏱️ Registro de Asistencia ({st.session_state.sinagoga_actual})")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("1. Tu Ubicación")
        ubicacion = streamlit_geolocation()
        gps_valido = False
        lat, lon = None, None
        if ubicacion is not None and isinstance(ubicacion, dict) and ubicacion.get("latitude"):
            lat, lon = ubicacion['latitude'], ubicacion['longitude']
            st.success(f"📍 GPS Real activado: Lat {lat:.4f}")
            gps_valido = True
        
        if not gps_valido:
            st.warning("Ubicación pendiente...")
            if st.button("🚨 Simular GPS (Prueba)"):
                st.session_state.gps_simulado = True
        if st.session_state.get("gps_simulado"):
            lat, lon = 25.7617, -80.1918 
            st.success("📍 GPS Simulado activado")
            gps_valido = True

    with col2:
        st.subheader("2. Fichaje y Actividad")
        if gps_valido:
            tipo_registro = st.radio("¿Qué deseas marcar?", ["Entrada Regular", "Salida Regular", "Entrada Horas Extras", "Salida Horas Extras"])
            rol_actividad = st.text_input("Rol diario de actividad laboral:") if "Entrada Regular" in tipo_registro else ""
            notas_extras = st.text_area("Justificación:") if "Extras" in tipo_registro else ""
            
            if st.button("✅ Registrar Ahora", type="primary", width="stretch"):
                if "Entrada Regular" in tipo_registro and not rol_actividad.strip():
                    st.error("⚠️ Especifica tu rol.")
                elif "Extras" in tipo_registro and not notas_extras.strip():
                    st.error("⚠️ Llena la justificación.")
                else:
                    hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    coord_str = f"{lat:.4f}, {lon:.4f}"
                    st.session_state.registros_personal.append([EMPLEADO_ACTUAL, rol_actividad or "Horas Extras", tipo_registro, hora_actual, coord_str, notas_extras])
                    st.success("¡Registrado exitosamente!")
                    st.rerun()
        else:
            st.button("✅ Registrar Ahora", disabled=True, width="stretch")

    st.divider()
    st.header("📊 Resumen Quincenal de Nómina")
    if len(st.session_state.registros_personal) > 0:
        df_registros = pd.DataFrame(st.session_state.registros_personal, columns=["Empleado", "Actividad", "Acción", "Fecha/Hora", "Ubicación", "Notas"])
        df_resumen = calcular_nomina_general(st.session_state.registros_personal)
        
        dash1, dash2 = st.columns([2, 1])
        with dash1:
            st.bar_chart(data=df_resumen.set_index("Empleado")["Costo Nómina ($)"], use_container_width=True)
        with dash2:
            st.metric("Total Horas", f"{round(df_resumen['Horas Totales'].sum(), 2)} hrs")
            st.metric("Total Nómina", f"${round(df_resumen['Costo Nómina ($)'].sum(), 2)}")
        
        st.dataframe(df_resumen, width="stretch")
        st.download_button(label="📥 Download Bi-weekly Payroll", data=generar_excel_personal(df_registros, df_resumen), file_name="Payroll_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

# ==========================================
# MÓDULO 2: ASISTENTE VIRTUAL (ACTIVO)
# ==========================================
elif opcion == "💬 Asistente Virtual":
    st.title(f"🕍 Jael - Asistente Administrativa ({st.session_state.sinagoga_actual})")
    
    for mensaje in st.session_state.mensajes:
        with st.chat_message(mensaje["role"]):
            st.markdown(mensaje["content"])
            
    if pregunta := st.chat_input("Escribe tu pregunta a Jael..."):
        with st.chat_message("user"):
            st.markdown(pregunta)
        st.session_state.mensajes.append({"role": "user", "content": pregunta})
        
        df_personal = calcular_nomina_general(st.session_state.registros_personal)
        df_gastos = pd.DataFrame(st.session_state.gastos_registrados, columns=["Proveedor", "Total ($)", "Categoría", "Fecha", "Aprobación"])
        contexto_personal = df_personal.to_csv(index=False) if not df_personal.empty else "No hay horas registradas."
        contexto_gastos = df_gastos.to_csv(index=False) if not df_gastos.empty else "No hay gastos."
        
        prompt_sistema = f"""
        Eres Jael, la asistente de las sinagogas Safra y Jemal. El administrador ve la sede: {st.session_state.sinagoga_actual}.
        Responde sus preguntas con los siguientes datos en tiempo real:
        NÓMINA: {contexto_personal}
        GASTOS: {contexto_gastos}
        Suma totales si te lo piden y responde en español conversacional.
        """
        
        with st.chat_message("assistant"):
            with st.spinner("Jael está revisando las bases de datos..."):
                respuesta = cliente.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": pregunta}]
                ).choices[0].message.content
                st.markdown(respuesta)
                
        st.session_state.mensajes.append({"role": "assistant", "content": respuesta})

# ==========================================
# MÓDULO 3: CONTROL DE GASTOS (ACTIVO)
# ==========================================
elif opcion == "📊 Control de Gastos":
    st.title(f"📊 Control de Gastos e IA ({st.session_state.sinagoga_actual})")
    tab1, tab2 = st.tabs(["📷 Escáner con IA", "📈 Reportes y Excel"])

    with tab1:
        col_scan, col_datos = st.columns([1.5, 1])
        with col_scan:
            st.subheader("1. Captura la Factura")
            metodo = st.radio("Método:", ["📸 Usar Cámara", "📁 Subir Archivo"])
            foto_factura = st.camera_input("Enfoca el recibo:") if metodo == "📸 Usar Cámara" else st.file_uploader("Sube recibo:", type=["jpg", "jpeg", "png"])

            if foto_factura:
                st.success("✅ ¡Factura capturada!")
                if st.button("🧠 Pedir a Jael que lea el recibo", type="primary"):
                    with st.spinner("Jael está analizando..."):
                        try:
                            base64_image = base64.b64encode(foto_factura.getvalue()).decode('utf-8')
                            prompt = """Extrae en formato JSON exacto: {"proveedor": "Nombre", "monto": 0.00, "categoria": "Alimentos/Desayunos o Limpieza o Mantenimiento o Eventos o Otros"}"""
                            respuesta_ia = cliente.chat.completions.create(
                                model="gpt-4o",
                                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}]
                            )
                            datos_extraidos = json.loads(respuesta_ia.choices[0].message.content.replace("```json", "").replace("```", "").strip())
                            st.session_state.factura_auto["proveedor"] = datos_extraidos.get("proveedor", "")
                            st.session_state.factura_auto["monto"] = float(datos_extraidos.get("monto", 0.0))
                            st.session_state.factura_auto["categoria"] = datos_extraidos.get("categoria", "Otros")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al leer imagen: {e}")

        with col_datos:
            st.subheader("2. Datos Extraídos")
            proveedor_nombre = st.text_input("Proveedor:", value=st.session_state.factura_auto["proveedor"])
            opciones_cat = ["Alimentos/Desayunos", "Limpieza", "Mantenimiento", "Eventos", "Otros"]
            cat_actual = st.session_state.factura_auto["categoria"]
            categoria = st.selectbox("Categoría:", opciones_cat, index=opciones_cat.index(cat_actual) if cat_actual in opciones_cat else 4)
            monto_total = st.number_input("Monto ($):", min_value=0.00, step=1.00, value=st.session_state.factura_auto["monto"])
            fecha_entrega = st.date_input("Fecha:", value=st.session_state.factura_auto["fecha"])
            
            if st.button("📤 Guardar Factura", type="primary", width="stretch"):
                if proveedor_nombre and monto_total > 0:
                    st.session_state.gastos_registrados.append([proveedor_nombre, monto_total, categoria, fecha_entrega.strftime("%Y-%m-%d"), "Pendiente"])
                    limpiar_formulario_factura()
                    st.success("¡Gasto guardado!")
                    st.rerun()
                else:
                    st.error("Falta proveedor o monto.")

    with tab2:
        st.header("📈 Centro de Reportes Financieros")
        df_gastos = pd.DataFrame(st.session_state.gastos_registrados, columns=["Proveedor", "Total ($)", "Categoría", "Fecha", "Aprobación"])
        if not df_gastos.empty:
            rep_semanal, rep_mensual = st.tabs(["1️⃣ Reporte Semanal", "2️⃣ Reporte Mensual Acumulado"])
            with rep_semanal:
                st.bar_chart(df_gastos.groupby("Categoría")["Total ($)"].sum(), width="stretch")
                st.dataframe(df_gastos, width="stretch")
                st.download_button("📥 Download Weekly Expenses (Excel)", generar_excel_gastos(df_gastos, "Weekly"), "Weekly_Expenses.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
            with rep_mensual:
                df_gastos["Fecha"] = pd.to_datetime(df_gastos["Fecha"])
                col_g1, col_g2 = st.columns(2)
                with col_g1: st.line_chart(df_gastos.groupby("Fecha")["Total ($)"].sum(), width="stretch")
                with col_g2: st.bar_chart(df_gastos.groupby("Proveedor")["Total ($)"].sum(), width="stretch")
                st.dataframe(df_gastos, width="stretch")
                st.download_button("📥 Download Monthly Expenses (Excel)", generar_excel_gastos(df_gastos, "Monthly"), "Monthly_Expenses.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        else:
            st.info("No hay gastos registrados.")