import streamlit as st
import pandas as pd
from datetime import datetime, time
from openai import OpenAI
import math
import io
import json
import base64
import uuid
from streamlit_geolocation import streamlit_geolocation
from supabase import create_client

# Configuración de la página
st.set_page_config(page_title="Jael - Asistente", page_icon="🕌", layout="wide", initial_sidebar_state="auto")

# Ocultar menú por defecto de Streamlit
ocultar_menu = """
    <style>
    #MainMenu {visibility: hidden;}
    .stAppDeployButton {display:none;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(ocultar_menu, unsafe_allow_html=True)

# --- CONEXIONES ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except KeyError:
        return create_client(st.secrets["connections"]["supabase"]["SUPABASE_URL"], st.secrets["connections"]["supabase"]["SUPABASE_KEY"])

supabase = init_connection()

# --- FUNCIONES AUXILIARES ---
def traducir_mensaje(texto, al_ingles=True):
    idioma = "inglés" if al_ingles else "español"
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Eres un traductor. Traduce al {idioma}. Responde SOLO con la traducción."},
                {"role": "user", "content": texto}
            ]
        )
        return resp.choices[0].message.content.strip()
    except: 
        return texto

def generar_excel(dataframe, sheet_name="Reporte"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# Reglas de Horarios
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
    
    if bloques and t_in > datetime.combine(t_in.date(), bloques[0][0]): 
        llegada_tarde = True
        
    for inicio_str, fin_str in bloques:
        overlap_start = max(t_in, datetime.combine(t_in.date(), inicio_str))
        overlap_end = min(t_out, datetime.combine(t_in.date(), fin_str))
        if overlap_start < overlap_end: 
            normal_seconds += (overlap_end - overlap_start).total_seconds()
            
    horas_normales = normal_seconds / 3600.0
    horas_extras = max(0, (total_seconds - normal_seconds) / 3600.0)
    return round(horas_normales, 2), round(horas_extras, 2), llegada_tarde

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371000 
    phi_1, phi_2 = math.radians(lat1), math.radians(lat2)
    a = math.sin(math.radians(lat2 - lat1)/2.0)**2 + math.cos(phi_1)*math.cos(phi_2)*math.sin(math.radians(lon2 - lon1)/2.0)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# ESTADOS GLOBALES
if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if "board_logged_in" not in st.session_state: st.session_state.board_logged_in = False
if "emp_logged_in" not in st.session_state: st.session_state.emp_logged_in = None
if "tarifa_normal" not in st.session_state: st.session_state.tarifa_normal = 20.0
if "tarifa_extra" not in st.session_state: st.session_state.tarifa_extra = 30.0

if "f_cat" not in st.session_state: st.session_state.f_cat = "Otros"
if "f_desc" not in st.session_state: st.session_state.f_desc = ""
if "f_monto" not in st.session_state: st.session_state.f_monto = 0.0
if "f_url" not in st.session_state: st.session_state.f_url = ""

LAT_SINAGOGA, LON_SINAGOGA, RADIO_PERMITIDO_METROS = 25.7617, -80.1918, 200.0 

st.sidebar.title("Acceso / Access")
tipo_acceso = st.sidebar.radio("Selecciona tu perfil:", ["Área de Empleados", "Administración", "Board / Accountant"])

# ==========================================
# 1. ÁREA DE EMPLEADOS
# ==========================================
if tipo_acceso == "Área de Empleados":
    st.title("⏱️ Reloj Checador")
    try:
        lista_empleados = supabase.table("empleados").select("*").execute().data
        config = supabase.table("configuracion").select("*").eq("id", 1).execute().data[0]
    except:
        lista_empleados, config = [], {"horario_texto": "", "actividades_texto": ""}
    
    if st.session_state.emp_logged_in is None:
        emp_sel = st.selectbox("Tu Nombre", [e["nombre"] for e in lista_empleados] if lista_empleados else ["No hay empleados"])
        pin_input = st.text_input("Tu PIN (4 dígitos)", type="password", max_chars=4)
        
        if st.button("Ingresar"):
            if lista_empleados and {e["nombre"]: e["pin"] for e in lista_empleados}.get(emp_sel) == pin_input:
                st.session_state.emp_logged_in = emp_sel
                st.rerun()
            else: 
                st.error("PIN incorrecto.")
    else:
        emp = st.session_state.emp_logged_in
        st.success(f"Hola, **{emp}**")
        if st.button("Cerrar mi sesión"): 
            st.session_state.emp_logged_in = None
            st.rerun()
            
        c_info1, c_info2 = st.columns(2)
        c_info1.info(f"**⏰ Horario Autorizado:**\n\n{config.get('horario_texto', '')}")
        c_info2.info(f"**📋 Actividades:**\n\n{config.get('actividades_texto', '')}")
            
        loc = streamlit_geolocation()
        ubicacion_valida = False
        if loc and loc.get("latitude"):
            dist = calcular_distancia(LAT_SINAGOGA, LON_SINAGOGA, loc["latitude"], loc["longitude"])
            if dist <= RADIO_PERMITIDO_METROS: 
                st.success("✅ Ubicación confirmada en Sinagoga.")
                ubicacion_valida = True
            else: 
                st.error(f"❌ Estás a {int(dist)}m. Reloj bloqueado.")
        
        try: 
            turno_abierto = supabase.table("asistencia").select("*").eq("empleado", emp).is_("salida", "null").execute().data
        except: 
            turno_abierto = []
        
        foto_facial = st.camera_input("📸 Foto obligatoria para marcar asistencia")
        puede_marcar = ubicacion_valida and (foto_facial is not None)

        col1, col2 = st.columns(2)
        with col1:
            if not turno_abierto:
                if st.button("🟢 MARCAR ENTRADA", use_container_width=True, disabled=not puede_marcar):
                    supabase.table("asistencia").insert({
                        "empleado": emp, 
                        "fecha": datetime.now().strftime("%Y-%m-%d"), 
                        "entrada": datetime.now().strftime("%H:%M:%S"), 
                        "horas": 0.0
                    }).execute()
                    st.rerun()
            else:
                st.button("🟢 ENTRADA REGISTRADA", disabled=True, use_container_width=True)
                
        with col2:
            if turno_abierto:
                with st.form("salida_form"):
                    actividades = st.text_area("Actividades realizadas en tu turno:")
                    if st.form_submit_button("🔴 MARCAR SALIDA", disabled=not puede_marcar):
                        if actividades:
                            h_salida = datetime.now()
                            t_in = datetime.strptime(f"{turno_abierto[0]['fecha']} {turno_abierto[0]['entrada']}", "%Y-%m-%d %H:%M:%S")
                            h_norm, h_ext, hubo_retardo = calcular_desglose_horas(t_in, h_salida)
                            supabase.table("asistencia").update({
                                "salida": h_salida.strftime("%H:%M:%S"), 
                                "horas": round(h_norm+h_ext, 2), 
                                "horas_extras": h_ext, 
                                "retardo": hubo_retardo, 
                                "actividad": actividades
                            }).eq("id", turno_abierto[0]["id"]).execute()
                            st.rerun()
            else:
                st.button("🔴 MARCAR SALIDA", disabled=True, use_container_width=True)

# ==========================================
# 2. ÁREA DE ADMINISTRACIÓN (MANAGER)
# ==========================================
elif tipo_acceso == "Administración":
    if not st.session_state.admin_logged_in:
        st.title("🔒 Acceso a Administración")
        pwd_admin = st.text_input("Contraseña", type="password")
        if st.button("Entrar a Administración"):
            if pwd_admin == "admin123": 
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    else:
        st.sidebar.write("---")
        if st.sidebar.button("🔒 Cerrar Sesión Admin"): 
            st.session_state.admin_logged_in = False
            st.rerun()
            
        op = st.sidebar.radio("Módulo:", ["Dashboard", "Personal", "Gastos", "💬 Chat Contador"])

        try:
            datos_gastos = supabase.table("gastos").select("*").order("id", desc=True).execute().data
            datos_horas = supabase.table("asistencia").select("*").execute().data
        except: 
            datos_gastos, datos_horas = [], []

        if op == "Dashboard":
            st.title("🕌 Panel de Control")
            tot_g = sum(g["monto"] for g in datos_gastos)
            pago_nomina = sum((max(0, t.get("horas",0) - t.get("horas_extras",0)) * st.session_state.tarifa_normal) + (t.get("horas_extras",0) * st.session_state.tarifa_extra) for t in datos_horas) if datos_horas else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Gastos Extras", f"${tot_g:,.2f}")
            c2.metric("👥 Nómina Estimada", f"${pago_nomina:,.2f}")
            c3.metric("🏢 TOTAL OPERACIÓN", f"${(tot_g + pago_nomina):,.2f}")

        elif op == "Personal":
            st.title("👥 Personal y Horarios")
            
            with st.expander("⚙️ Tarifas de Pago Automático"):
                c1, c2 = st.columns(2)
                st.session_state.tarifa_normal = c1.number_input("Hora Normal ($)", value=st.session_state.tarifa_normal)
                st.session_state.tarifa_extra = c2.number_input("Hora Extra ($)", value=st.session_state.tarifa_extra)
            
            with st.expander("📝 Definir Horario y Actividades"):
                try: 
                    conf = supabase.table("configuracion").select("*").eq("id", 1).execute().data[0]
                except: 
                    conf = {}
                with st.form("form_reglas"):
                    n_horario = st.text_area("Horario Autorizado", value=conf.get("horario_texto", ""))
                    n_activ = st.text_area("Actividades Asignadas", value=conf.get("actividades_texto", ""))
                    if st.form_submit_button("Guardar Configuración"):
                        supabase.table("configuracion").update({"horario_texto": n_horario, "actividades_texto": n_activ}).eq("id", 1).execute()
                        st.success("Guardado. Los empleados lo verán en su pantalla.")
                        st.rerun()
                        
            st.write("---")
            if datos_horas:
                st.write("### Historial de Turnos")
                for t in datos_horas:
                    cA, cB, cC = st.columns([2, 4, 1])
                    cA.write(f"**{t['empleado']}**")
                    cB.write(f"{t['fecha']} | {t['entrada']} a {t['salida']} ({t.get('horas', 0)} hrs)")
                    if cC.button("🗑️ Borrar", key=f"del_t_{t['id']}"):
                        supabase.table("asistencia").delete().eq("id", t["id"]).execute()
                        st.rerun()

                st.write("---")
                st.write("### 📊 Tabla de Datos y Excel (Nómina)")
                df_horas = pd.DataFrame(datos_horas)
                cols_mostrar = [c for c in ["empleado", "fecha", "entrada", "salida", "horas", "horas_extras", "actividad"] if c in df_horas.columns]
                st.dataframe(df_horas[cols_mostrar], use_container_width=True)
                
                excel_data = generar_excel(df_horas[cols_mostrar], "Nomina")
                st.download_button("📥 Descargar Excel de Nómina", data=excel_data, file_name="Nomina_Sinagoga.xlsx", type="primary")

        elif op == "Gastos":
            st.title("📈 Gastos y Facturas")
            
            st.write("### 📸 Lector Automático de Facturas")
            foto_factura = st.file_uploader("Sube o toma una foto del recibo con la cámara de tu celular", type=['jpg', 'jpeg', 'png'], key="camara")
            
            if foto_factura:
                with st.spinner("🧠 Analizando factura y guardando imagen..."):
                    bytes_data = foto_factura.getvalue()
                    img_base64 = base64.b64encode(bytes_data).decode('utf-8')
                    url_publica = ""
                    
                    try:
                        buckets_existentes = [b.name for b in supabase.storage.list_buckets()]
                        if "facturas" not in buckets_existentes:
                            supabase.storage.create_bucket("facturas", options={"public": True})
                            
                        nombre_archivo = f"recibo_{uuid.uuid4().hex}.jpg"
                        supabase.storage.from_("facturas").upload(
                            path=nombre_archivo,
                            file=bytes_data,
                            file_options={"content-type": "image/jpeg"}
                        )
                        url_publica = supabase.storage.from_("facturas").get_public_url(nombre_archivo)
                    except Exception as e:
                        st.warning(f"⚠️ Nota: {e}. Se procederá solo con la lectura de texto.")
                        
                    try:
                        resp = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "Devuelve un JSON con: 'monto' (solo número float), 'descripcion' (proveedor o concepto de gasto), 'categoria' (Limpieza, Proveedores, u Otros)."},
                                {"role": "user", "content": [{"type": "text", "text": "Extrae los datos."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}]}
                            ],
                            response_format={"type": "json_object"}
                        )
                        datos = json.loads(resp.choices[0].message.content)
                        
                        st.session_state.f_cat = datos.get("categoria", "Otros")
                        st.session_state.f_desc = datos.get("descripcion", "")
                        st.session_state.f_monto = float(datos.get("monto", 0.0))
                        st.session_state.f_url = url_publica
                        st.success("✅ ¡Factura leída con éxito!")
                    except Exception as e:
                        st.error(f"❌ Error al procesar con IA: {e}")

            st.write("---")
            with st.form("f2"):
                cat_index = ["Limpieza", "Proveedores", "Otros"].index(st.session_state.f_cat) if st.session_state.f_cat in ["Limpieza", "Proveedores", "Otros"] else 2
                cat = st.selectbox("Categoría", ["Limpieza", "Proveedores", "Otros"], index=cat_index)
                desc = st.text_input("Descripción", value=st.session_state.f_desc)
                monto = st.number_input("Monto ($)", min_value=0.0, value=st.session_state.f_monto)
                
                if st.form_submit_button("Guardar Gasto"):
                    supabase.table("gastos").insert({
                        "fecha": datetime.now().strftime("%Y-%m-%d"), 
                        "categoria": cat, 
                        "descripcion": desc, 
                        "monto": monto, 
                        "foto_url": st.session_state.f_url
                    }).execute()
                    
                    st.session_state.f_desc = ""
                    st.session_state.f_monto = 0.0
                    st.session_state.f_url = ""
                    st.success("Guardado correctamente.")
                    st.rerun()

            st.write("---")
            st.write("### 📋 Historial de Gastos")
            if datos_gastos:
                for g in datos_gastos:
                    cA, cB, cC, cD = st.columns([1, 2, 2, 1])
                    if g.get("foto_url"):
                        cA.image(g["foto_url"], use_container_width=True)
                    else:
                        cA.write("📄 Sin foto")
                    
                    cB.write(f"**{g['categoria']}**\n${g['monto']}")
                    cC.write(f"{g['descripcion']}\n*{g['fecha']}*")
                    if cD.button("🗑️ Borrar", key=f"del_g_{g['id']}"):
                        supabase.table("gastos").delete().eq("id", g["id"]).execute()
                        st.rerun()
                
                st.write("---")
                st.write("### 📊 Tabla de Datos y Excel (Gastos)")
                df_gastos = pd.DataFrame(datos_gastos)
                cols_g = [c for c in ["fecha", "categoria", "descripcion", "monto"] if c in df_gastos.columns]
                st.dataframe(df_gastos[cols_g], use_container_width=True)
                
                excel_gastos = generar_excel(df_gastos[cols_g], "Gastos")
                st.download_button("📥 Descargar Excel de Gastos", data=excel_gastos, file_name="Gastos_Sinagoga.xlsx", type="primary")

        elif op == "💬 Chat Contador":
            st.title("💬 Chat con Contabilidad")
            st.info("Escribe en español. La IA lo traducirá automáticamente al inglés para la Junta/Contador.")
            try: 
                mensajes = supabase.table("comunicacion").select("*").order("id", desc=False).execute().data
            except: 
                mensajes = []
            
            for m in mensajes:
                if m['remitente'] == "Manager":
                    st.chat_message("user").write(f"**Tú:** {m['texto_es']}")
                else:
                    st.chat_message("assistant").write(f"**Contador:** {m['texto_es']}\n*(Original: {m['texto_en']})*")
                    
            nuevo_msg = st.chat_input("Escribe tu mensaje en español...")
            if nuevo_msg:
                trad = traducir_mensaje(nuevo_msg, al_ingles=True)
                supabase.table("comunicacion").insert({"remitente": "Manager", "texto_es": nuevo_msg, "texto_en": trad}).execute()
                st.rerun()

# ==========================================
# 3. ÁREA DE JUNTA / CONTADOR (INGLÉS)
# ==========================================
elif tipo_acceso == "Board / Accountant":
    if not st.session_state.board_logged_in:
        st.title("🔒 Board Login")
        pwd_b = st.text_input("Password", type="password")
        if st.button("Login to Board Dashboard"):
            if pwd_b == "board123": 
                st.session_state.board_logged_in = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    else:
        st.sidebar.write("---")
        if st.sidebar.button("🔒 Logout Board"): 
            st.session_state.board_logged_in = False
            st.rerun()
            
        op_board = st.sidebar.radio("Menu:", ["Financial Dashboard", "💬 Manager Chat"])
        
        if op_board == "Financial Dashboard":
            st.title("📊 Financial Dashboard")
            try:
                dg = supabase.table("gastos").select("*").execute().data
                dh = supabase.table("asistencia").select("*").execute().data
            except: 
                dg, dh = [], []

            tot_g = sum(g["monto"] for g in dg)
            pago_nomina = sum((max(0, t.get("horas",0) - t.get("horas_extras",0)) * st.session_state.tarifa_normal) + (t.get("horas_extras",0) * st.session_state.tarifa_extra) for t in dh) if dh else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Total Expenses", f"${tot_g:,.2f}")
            c2.metric("👥 Estimated Payroll", f"${pago_nomina:,.2f}")
            c3.metric("🏢 TOTAL OPEX", f"${(tot_g + pago_nomina):,.2f}")
            
            if dg:
                st.write("---")
                st.write("### Expense Breakdown")
                df_dg = pd.DataFrame(dg)
                cols_b = [c for c in ["fecha", "categoria", "descripcion", "monto"] if c in df_dg.columns]
                st.dataframe(df_dg[cols_b].rename(columns={"fecha":"Date", "categoria":"Category", "descripcion":"Description", "monto":"Amount ($)"}), use_container_width=True)
            
        elif op_board == "💬 Manager Chat":
            st.title("💬 Messages with Manager")
            st.info("Type in English. The AI will translate your message to Spanish for the Manager.")
            try: 
                mensajes = supabase.table("comunicacion").select("*").order("id", desc=False).execute().data
            except: 
                mensajes = []
            
            for m in mensajes:
                if m['remitente'] == "Contador":
                    st.chat_message("user").write(f"**You:** {m['texto_en']}")
                else:
                    st.chat_message("assistant").write(f"**Manager:** {m['texto_en']}\n*(Original: {m['texto_es']})*")
                    
            nuevo_msg = st.chat_input("Type your message in English...")
            if nuevo_msg:
                trad = traducir_mensaje(nuevo_msg, al_ingles=False)
                supabase.table("comunicacion").insert({"remitente": "Contador", "texto_es": trad, "texto_en": nuevo_msg}).execute()
                st.rerun()
