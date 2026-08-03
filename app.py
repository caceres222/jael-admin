# ==========================================
# ÁREA DE EMPLEADOS
# ==========================================
if tipo_acceso == "Área de Empleados":
    st.title("⏱️ Reloj Checador")
    
    try:
        lista_empleados = supabase.table("empleados").select("*").execute().data
        config_db = supabase.table("configuracion").select("*").eq("id", 1).execute().data
        config = config_db[0] if config_db else {"horario_texto": "", "actividades_texto": ""}
    except Exception:
        lista_empleados, config = [], {"horario_texto": "", "actividades_texto": ""}
    
    if st.session_state.emp_logged_in is None:
        if not lista_empleados:
            st.warning("No hay empleados registrados.")
        else:
            emp_sel = st.selectbox("Tu Nombre", [e["nombre"] for e in lista_empleados])
            pin_input = st.text_input("Tu PIN (4 dígitos)", type="password", max_chars=4)
            if st.button("Ingresar"):
                if {e["nombre"]: e["pin"] for e in lista_empleados}.get(emp_sel) == pin_input:
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
            
        st.write("---")
        st.write("### 📌 Instrucciones de la Manager")
        c_info1, c_info2 = st.columns(2)
        c_info1.info(f"**⏰ Horario Autorizado:**\n\n{config.get('horario_texto', 'No definido')}")
        c_info2.info(f"**📋 Actividades a realizar:**\n\n{config.get('actividades_texto', 'No definidas')}")
            
        st.write("---")
        st.write("### 📍 Verificación de Ubicación")
        loc = streamlit_geolocation()
        ubicacion_valida = False
        
        if loc and loc.get("latitude") and loc.get("longitude"):
            distancia = calcular_distancia(LAT_SINAGOGA, LON_SINAGOGA, loc["latitude"], loc["longitude"])
            if distancia <= RADIO_PERMITIDO_METROS:
                st.success(f"✅ Ubicación confirmada en Sinagoga.")
                ubicacion_valida = True
            else:
                st.error(f"❌ Estás a {int(distancia)}m. El reloj está bloqueado.")
        
        try:
            turno_abierto = supabase.table("asistencia").select("*").eq("empleado", emp).is_("salida", "null").execute().data
        except Exception:
            turno_abierto = []
        
        # PUNTO 6: IDENTIFICACIÓN POR CÁMARA OBLIGATORIA
        st.write("---")
        st.write("### 📸 Verificación Facial")
        st.write("Debes tomarte una foto en este momento para habilitar el reloj.")
        foto_facial = st.camera_input("Toma una foto de tu rostro")
        
        # El sistema verifica que el empleado esté en la sinagoga Y se haya tomado la foto
        puede_marcar = ubicacion_valida and (foto_facial is not None)

        col1, col2 = st.columns(2)
        with col1:
            if not turno_abierto:
                if st.button("🟢 MARCAR ENTRADA", use_container_width=True, disabled=not puede_marcar):
                    supabase.table("asistencia").insert({"empleado": emp, "fecha": datetime.now().strftime("%Y-%m-%d"), "entrada": datetime.now().strftime("%H:%M:%S"), "horas": 0.0}).execute()
                    st.rerun()
            else:
                st.button("🟢 ENTRADA REGISTRADA", disabled=True, use_container_width=True)
                
        with col2:
            if turno_abierto:
                with st.form("salida_form"):
                    actividades = st.text_area("Confirma tus actividades realizadas:")
                    if st.form_submit_button("🔴 GUARDAR Y MARCAR SALIDA", disabled=not puede_marcar):
                        if actividades:
                            id_t = turno_abierto[0]["id"]
                            h_salida = datetime.now()
                            t_in = datetime.strptime(f"{turno_abierto[0]['fecha']} {turno_abierto[0]['entrada']}", "%Y-%m-%d %H:%M:%S")
                            h_norm, h_ext, hubo_retardo = calcular_desglose_horas(t_in, h_salida)
                            supabase.table("asistencia").update({"salida": h_salida.strftime("%H:%M:%S"), "horas": round(h_norm+h_ext, 2), "horas_extras": h_ext, "retardo": hubo_retardo, "actividad": actividades}).eq("id", id_t).execute()
                            st.rerun()
                        else:
                            st.error("Escribe tus actividades.")
            else:
                st.button("🔴 MARCAR SALIDA", disabled=True, use_container_width=True)
