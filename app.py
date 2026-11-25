import streamlit as st
from google import genai
from google.genai import types
import plotly.graph_objects as go
import pandas as pd
import json
import re

st.set_page_config(page_title="Saga Falabella - Análisis Predictivo", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .main-header {background: linear-gradient(90deg, #98c93c 0%, #5a8f29 100%); padding: 1.2rem; border-radius: 10px; color: white; margin-bottom: 1.5rem;}
    .stMetric {background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #98c93c;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h2>📊 Saga Falabella S.A. | Simulador Predictivo E-Commerce</h2><p>Soporte Estratégico para Reducción de Devoluciones Evitables</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configuración")
    api_key = st.secrets.get("GEMINI_API_KEY", "") or st.text_input("Ingresa tu Google API Key:", type="password")
    st.divider()
    st.subheader("📌 Reglas del Modelo")
    st.caption("**Obligatorios (4):** Categoría, Pedidos/mes, Tasa devolución (%), Adopción (%).")
    st.caption("**Opcionales (2):** Costo/devolución (S/), Inversión (S/).")
    if st.button("🗑️ Limpiar Conversación"):
        st.session_state.messages = []
        st.rerun()

SYSTEM_PROMPT = """
Eres un Analista Predictivo Estratégico para la gerencia de Saga Falabella S.A. Evalúas escenarios operativos y financieros del e-commerce para sugerir qué alternativa conviene más para reducir devoluciones evitables.

PASO 1: VERIFICAR DATOS MÍNIMOS
Busca en el mensaje del usuario estos 4 DATOS OBLIGATORIOS:
1. Categoría (Vestuario/Calzado, Electrodomésticos o Tecnología)
2. Volumen mensual de pedidos
3. Tasa actual de devoluciones (%)
4. Nivel estimado de adopción (%)

-> SI EL USUARIO HACE UNA CONSULTA DE CÁLCULO FINANCIERO (Ahorro y ROI con % de reducción, sin pedir diagnóstico de adopción):
Usa estas fórmulas exactas:
- Devoluciones actuales = Volumen * (% Tasa / 100)
- Devoluciones evitadas = Devoluciones actuales * (% Reducción / 100)
- Ahorro mensual = Devoluciones evitadas * Costo por devolución
- ROI primer mes (%) = ((Ahorro mensual - Inversión) / Inversión) * 100
- Meses recuperación = Inversión / Ahorro mensual
Responde claro y cierra con una recomendación estratégica breve.

-> SI FALTA ALGUNO DE LOS 4 DATOS OBLIGATORIOS (y no es consulta directa de ROI):
NO diagnostiques ni inventes datos. Confirma en una oración corta lo que ya tienes y pide únicamente el dato obligatorio que falte. (Costo por devolución e Inversión son OPCIONALES; nunca los exijas).

-> SI TIENES LOS 4 DATOS OBLIGATORIOS:
Clasifica según estos rangos exactos:
- Volumen pedidos: Positivo (> 10,000) | Estándar (6,000 a 10,000) | Negativo (< 6,000)
- Tasa devoluciones: Positivo (0% a 5%) | Estándar (> 5% a 10%) | Negativo (> 10%)
- Nivel adopción: Positivo (>= 60%) | Estándar (30% a 59%) | Negativo (< 30%)
- Costo devolución (si existe): Positivo (<= 25) | Estándar (> 25 a 40) | Negativo (> 40)
- Inversión (si existe): Positivo (<= 15,000) | Estándar (> 15,000 a 30,000) | Negativo (> 30,000)

Escenario Global:
- Positivo/Optimista: Mayoría en Positivo y adopción >= 60%.
- Negativo/Pesimista: Mayoría en Negativo, o adopción < 30% con devoluciones > 10%.
- Estándar/Esperado: Casos intermedios o mixtos.

FORMATO DE RESPUESTA:
1. **Evaluación de Parámetros:** Lista cada dato ingresado con su clasificación (Positivo/Estándar/Negativo). Si no se dio costo ni inversión, pon "No proporcionado (análisis operativo)".
2. **Diagnóstico Predictivo:** Indica el escenario resultante y justifica por qué.
3. **Comparativa de Alternativas:**
   - Alt. 1: Asistente interactivo pre-compra en web/app.
   - Alt. 2: Mejora estática de fichas y guías visuales.
   - Alt. 3: Incentivos post-compra (cupones y envíos gratuitos).
4. **Recomendación Estratégica:** Explica la causa real del cliente (ej. compra "por corazonada" sin ver tallas reales en Vestuario, dudas de compatibilidad en Tecnología, o dimensiones en Electrodomésticos) y sugiere qué alternativa podría optar Saga Falabella.

ADEMÁS, SIEMPRE QUE DES UN DIAGNÓSTICO O CÁLCULO FINANCIERO, incluye al final de tu respuesta un bloque JSON exacto entre etiquetas [JSON_START] y [JSON_END] con esta estructura para graficar (usa 0 si no se dio costo o inversión):
[JSON_START]
{
  "escenario": "Positivo / Optimista",
  "pedidos": 12000,
  "tasa_devolucion": 4,
  "adopcion": 70,
  "costo_devolucion": 20,
  "inversion": 14000,
  "ahorro_mensual_estimado": 4800
}
[JSON_END]
"""

def render_dashboard(data):
    st.divider()
    st.subheader(f"📈 Panel Visual del Diagnóstico: {data.get('escenario', 'Evaluación')}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pedidos / Mes", f"{data.get('pedidos', 0):,}")
    c2.metric("Tasa Devolución", f"{data.get('tasa_devolucion', 0)}%")
    c3.metric("Adopción Estimada", f"{data.get('adopcion', 0)}%")
    ahorro = data.get('ahorro_mensual_estimado', 0)
    c4.metric("Ahorro Mensual Est.", f"S/ {ahorro:,.0f}" if ahorro > 0 else "Modo Operativo")

    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        fig1 = go.Figure(data=[
            go.Bar(name='Escenario Actual', x=['Tasa Devolución (%)', 'Adopción (%)'], 
                   y=[data.get('tasa_devolucion', 0), data.get('adopcion', 0)],
                   marker_color=['#e74c3c' if data.get('tasa_devolucion', 0) > 10 else '#2ecc71', '#3498db']),
            go.Bar(name='Meta Saga Falabella', x=['Tasa Devolución (%)', 'Adopción (%)'], 
                   y=[5, 60], marker_color=['#95a5a6', '#95a5a6'])
        ])
        fig1.update_layout(title="Comparativa vs. Meta Óptima (%)", barmode='group', height=320)
        st.plotly_chart(fig1, use_container_width=True)

    with col_g2:
        inv = data.get('inversion', 0)
        if inv > 0 and ahorro > 0:
            meses = [f"Mes {i}" for i in range(1, 7)]
            flujo = [(ahorro * i) - inv for i in range(1, 7)]
            colores = ['#e74c3c' if v < 0 else '#2ecc71' for v in flujo]
            fig2 = go.Figure(data=[go.Bar(x=meses, y=flujo, marker_color=colores)])
            fig2.update_layout(title="Flujo Neto Acumulado / Recuperación (S/)", height=320)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            fig2 = go.Figure(go.Indicator(
                mode="gauge+number",
                value=data.get('adopcion', 0),
                title={'text': "Índice de Viabilidad por Adopción (%)"},
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#5a8f29"},
                       'steps': [{'range': [0, 30], 'color': "#fadbd8"},
                                 {'range': [30, 60], 'color': "#fcf3cf"},
                                 {'range': [60, 100], 'color': "#d4efdf"}]}
            ))
            fig2.update_layout(height=320)
            st.plotly_chart(fig2, use_container_width=True)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "¡Hola! Soy el Asistente Predictivo de **Saga Falabella S.A.** 📊\n\nIndícame la **categoría** (Vestuario/Calzado, Electrodomésticos o Tecnología) y los datos operativos o financieros que tengas para generar el diagnóstico y los gráficos."}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        clean_text = re.sub(r'\[JSON_START\].*?\[JSON_END\]', '', msg["content"], flags=re.DOTALL)
        st.markdown(clean_text)
        match = re.search(r'\[JSON_START\]\s*(.*?)\s*\[JSON_END\]', msg["content"], flags=re.DOTALL)
        if match:
            try:
                render_dashboard(json.loads(match.group(1)))
            except:
                pass

if prompt := st.chat_input("Ej: Evalúa Vestuario con 12,000 pedidos, 4% devolución, 70% adopción, costo S/ 20 e inversión S/ 14,000"):
    if not api_key:
        st.warning("⚠️ Ingresa tu Google API Key en el menú lateral izquierdo (flecha > arriba a la izquierda en celular).")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando escenarios y generando gráficos..."):
            client = genai.Client(api_key=api_key)
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=history_text,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.2)
            )
            full_reply = response.text
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
            clean_reply = re.sub(r'\[JSON_START\].*?\[JSON_END\]', '', full_reply, flags=re.DOTALL)
            st.markdown(clean_reply)
            match = re.search(r'\[JSON_START\]\s*(.*?)\s*\[JSON_END\]', full_reply, flags=re.DOTALL)
            if match:
                try:
                    render_dashboard(json.loads(match.group(1)))
                except:
                    pass
 
