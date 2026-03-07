import streamlit as st
import numpy as np
import numpy_financial as npf
import pandas as pd
import plotly.graph_objects as go

# 1. Page Configuration
st.set_page_config(page_title="Lobito Project Finance & Sensitivities", layout="wide", initial_sidebar_state="expanded")

# 2. Sidebar: Inputs
st.sidebar.header("Macroeconomic Inputs (WACC)")
rf = st.sidebar.slider("US 10-Year Treasury Yield (%)", 0.0, 10.0, 4.30, 0.1) / 100
beta = st.sidebar.slider("Refining Industry Beta", 0.5, 2.0, 1.10, 0.01)
erp = st.sidebar.slider("Equity Risk Premium (%)", 0.0, 10.0, 5.50, 0.1) / 100
crp = st.sidebar.slider("Angola Country Risk Premium (%)", 0.0, 15.0, 7.20, 0.1) / 100

st.sidebar.divider()

st.sidebar.header("Project Stress Tests")
capex_stress = st.sidebar.slider("CAPEX Overrun/Savings (%)", -30, 50, 0, 1) / 100
rev_stress = st.sidebar.slider("Refining Margin Stress (%)", -30, 30, 0, 1) / 100

# 3. Base Project Parameters 
base_capex = 4305.8
base_rev = 11050.0
base_opex = 10260.0

live_capex = base_capex * (1 + capex_stress)
live_rev = base_rev * (1 + rev_stress)

debt_ratio = 0.70
cost_of_debt = 0.05
debt_term = 15
tax_rate = 0.25
tax_holiday = 15

# Calculate Live WACC
cost_of_equity = rf + (beta * erp) + crp
wacc = ((1 - debt_ratio) * cost_of_equity) + (debt_ratio * cost_of_debt)

# 4. Cash Flow Timeline Array Generation (For Tab 1)
years = np.arange(2025, 2057)
n_years = len(years)

capex_schedule = np.zeros(n_years)
capex_schedule[0:3] = [live_capex*0.20, live_capex*0.40, live_capex*0.40]

capacity = np.zeros(n_years)
capacity[3], capacity[4], capacity[5:] = 0.90, 0.95, 1.00 

revenues = capacity * live_rev
opex = capacity * base_opex
ebitda = revenues - opex

depreciation = np.zeros(n_years)
depreciation[3:23] = live_capex / 20

total_debt = live_capex * debt_ratio
debt_service = np.zeros(n_years)
interest = np.zeros(n_years)

if cost_of_debt == 0:
    pmt = total_debt / debt_term
else:
    pmt = total_debt * (cost_of_debt * (1 + cost_of_debt)**debt_term) / ((1 + cost_of_debt)**debt_term - 1)

balance = total_debt
for i in range(n_years):
    if 3 <= i < (3 + debt_term):
        interest[i] = balance * cost_of_debt
        debt_service[i] = pmt
        balance -= (pmt - interest[i])

ebt = ebitda - depreciation - interest
taxes = np.zeros(n_years)
for i in range(n_years):
    if i >= 3 and (i - 2) > tax_holiday and ebt[i] > 0:
        taxes[i] = ebt[i] * tax_rate

cfads = ebitda - taxes
fcff = ebitda - capex_schedule - taxes

dscr_array = np.zeros(n_years)
for i in range(n_years):
    if debt_service[i] > 0:
        dscr_array[i] = cfads[i] / debt_service[i]
min_dscr = np.min(dscr_array[dscr_array > 0]) if np.any(dscr_array > 0) else 0

project_npv = npf.npv(wacc, fcff)
project_irr = npf.irr(fcff)

# ---------------------------------------------------------
# HELPER ENGINE: Dynamic NPV & Breakeven Calculators
# ---------------------------------------------------------
def get_dynamic_npv(test_capex, test_rev):
    test_capex_sched = np.zeros(n_years)
    test_capex_sched[0:3] = [test_capex*0.20, test_capex*0.40, test_capex*0.40]
    
    test_ebitda = (capacity * test_rev) - (capacity * base_opex)
    test_depr = np.zeros(n_years)
    test_depr[3:23] = test_capex / 20
    
    test_total_debt = test_capex * debt_ratio
    test_interest = np.zeros(n_years)
    if cost_of_debt > 0:
        test_pmt = test_total_debt * (cost_of_debt * (1 + cost_of_debt)**debt_term) / ((1 + cost_of_debt)**debt_term - 1)
    else:
        test_pmt = test_total_debt / debt_term
        
    test_bal = test_total_debt
    for i in range(n_years):
        if 3 <= i < (3 + debt_term):
            test_interest[i] = test_bal * cost_of_debt
            test_bal -= (test_pmt - test_interest[i])
            
    test_ebt = test_ebitda - test_depr - test_interest
    test_taxes = np.zeros(n_years)
    for i in range(n_years):
        if i >= 3 and (i - 2) > tax_holiday and test_ebt[i] > 0:
            test_taxes[i] = test_ebt[i] * tax_rate
            
    test_fcff = test_ebitda - test_capex_sched - test_taxes
    return npf.npv(wacc, test_fcff)

# Bisection algorithms to automatically find the TRUE $0 NPV crossing
def find_capex_breakeven(test_rev, target_npv=0):
    low, high = 100.0, 20000.0
    for _ in range(40):
        mid = (low + high) / 2
        if get_dynamic_npv(mid, test_rev) > target_npv:
            low = mid
        else:
            high = mid
    return mid

def find_rev_breakeven(test_capex, target_npv=0):
    low, high = 100.0, 30000.0
    for _ in range(40):
        mid = (low + high) / 2
        if get_dynamic_npv(test_capex, mid) > target_npv:
            high = mid
        else:
            low = mid
    return mid

# 5. Dashboard Setup & Tabs
st.title("Lobito Refinery: Master Dashboard")
tab1, tab2 = st.tabs(["📊 Project Finance Dashboard", "📈 Board Sensitivity Analysis"])

# ==========================================
# TAB 1: MAIN INTERACTIVE DASHBOARD
# ==========================================
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calculated WACC", f"{wacc*100:.2f}%")
    
    if np.isnan(project_irr) or project_irr < 0:
        col2.metric("Project IRR (Unlevered)", "N/M")
    else:
        col2.metric("Project IRR (Unlevered)", f"{project_irr*100:.2f}%")
    
    col3.metric("Project NPV (MM USD)", f"${project_npv:,.0f}")
    
    if min_dscr >= 1.25:
        col4.metric("Minimum DSCR", f"{min_dscr:.2f}x", "Bankable", delta_color="normal")
    else:
        col4.metric("Minimum DSCR", f"{min_dscr:.2f}x", "High Risk / Breach", delta_color="inverse")
    
    st.divider()
    
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("CFADS vs. Debt Obligations")
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=years[3:18], y=cfads[3:18], name='CFADS', marker_color='#2CA02C'))
        fig1.add_trace(go.Scatter(x=years[3:18], y=debt_service[3:18], name='Debt Service Requirement', mode='lines', line=dict(color='#FF0000', width=3)))
        fig1.update_layout(xaxis_title="Operating Year", yaxis_title="Cash Flow (MM USD)", barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor='white')
        fig1.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        st.plotly_chart(fig1, use_container_width=True)
    
    with col_chart2:
        st.subheader("Amortization: Principal vs. Interest")
        chart_principal = debt_service[3:18] - interest[3:18]
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=years[3:18], y=interest[3:18], name='Interest', marker_color='#FF7F0E'))
        fig2.add_trace(go.Bar(x=years[3:18], y=chart_principal, name='Principal', marker_color='#1F77B4'))
        fig2.update_layout(xaxis_title="Operating Year", yaxis_title="Debt Payment (MM USD)", barmode='stack', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor='white')
        fig2.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        st.plotly_chart(fig2, use_container_width=True)

# ==========================================
# TAB 2: DYNAMIC BOARD SENSITIVITY ANALYSIS
# ==========================================
with tab2:
    st.markdown("<h2 style='text-align: center;'>BOARD SENSITIVITY ANALYSIS</h2>", unsafe_allow_html=True)
    st.write("") 
    st.write("") 
    
    # Calculate EXACT Breakeven points
    c_break = find_capex_breakeven(live_rev)
    r_break = find_rev_breakeven(live_capex)
    
    # 1. Generate 5 Dynamic CAPEX Data points crossing precisely through the zero mark
    c_diff = c_break - live_capex
    capex_steps = [live_capex + c_diff * (i / 3) for i in range(5)]
    capex_npvs = [get_dynamic_npv(c, live_rev) for c in capex_steps]
    df_capex = pd.DataFrame({"CAPEX": capex_steps, "NPV": capex_npvs})
    
    # 2. Generate 5 Dynamic Revenue Data points crossing precisely through the zero mark
    r_diff = r_break - live_rev
    rev_steps = [live_rev + r_diff * (i / 3) for i in range(5)]
    rev_npvs = [get_dynamic_npv(live_capex, r) for r in rev_steps]
    df_rev = pd.DataFrame({"Revenues": rev_steps, "NPV": rev_npvs})
    
    col_sens1, col_sens2 = st.columns(2)
    
    with col_sens1:
        # Format Data Table
        st.dataframe(df_capex.style.format({"CAPEX": "{:,.0f}", "NPV": "{:,.0f}"}), hide_index=True, use_container_width=True)
        st.write("")
        
        # Excel-Style Dynamic Chart
        fig_capex = go.Figure()
        fig_capex.add_trace(go.Scatter(x=df_capex["CAPEX"], y=df_capex["NPV"], mode='lines+markers', name='NPV', marker=dict(symbol='diamond', size=10, color='#4472C4'), line=dict(color='#4472C4', width=3)))
        
        # Widening the X-axis by 15% so the zero crossing is highly visible
        x_min, x_max = min(capex_steps), max(capex_steps)
        x_pad = (x_max - x_min) * 0.15
        
        fig_capex.update_layout(title=dict(text="<b>CAPEX Sensitivity</b>", font=dict(size=24, color="black"), x=0.5), xaxis_title=dict(text="<b>CAPEX</b>", font=dict(color="black", size=14)), yaxis_title=dict(text="<b>NPV</b>", font=dict(color="black", size=14)), plot_bgcolor='white', margin=dict(l=40, r=40, t=60, b=40), xaxis=dict(range=[x_min - x_pad, x_max + x_pad], showgrid=False, linecolor='gray', ticks='outside'), yaxis=dict(showgrid=True, gridcolor='lightgray', linecolor='gray', ticks='outside'))
        fig_capex.add_hline(y=0, line_width=1, line_color="black") # Breakeven Line
        fig_capex.update_xaxes(mirror=True, showline=True, linecolor='gray')
        fig_capex.update_yaxes(mirror=True, showline=True, linecolor='gray')
        st.plotly_chart(fig_capex, use_container_width=True)
    
    with col_sens2:
        # Format Data Table
        st.dataframe(df_rev.style.format({"Revenues": "{:,.0f}", "NPV": "{:,.0f}"}), hide_index=True, use_container_width=True)
        st.write("") 
        
        # Excel-Style Dynamic Chart
        fig_rev = go.Figure()
        fig_rev.add_trace(go.Scatter(x=df_rev["Revenues"], y=df_rev["NPV"], mode='lines+markers', name='NPV', marker=dict(symbol='diamond', size=10, color='#4472C4'), line=dict(color='#4472C4', width=3)))
        
        # Widening the X-axis by 15% so the zero crossing is highly visible
        rx_min, rx_max = min(rev_steps), max(rev_steps)
        rx_pad = (rx_max - rx_min) * 0.15
        
        fig_rev.update_layout(title=dict(text="<b>Revenues Sensitivities</b>", font=dict(size=24, color="black"), x=0.5), xaxis_title=dict(text="<b>Revenues</b>", font=dict(color="black", size=14)), yaxis_title=dict(text="<b>NPV</b>", font=dict(color="black", size=14)), plot_bgcolor='white', margin=dict(l=40, r=40, t=60, b=40), xaxis=dict(range=[rx_min - rx_pad, rx_max + rx_pad], showgrid=False, linecolor='gray', ticks='outside'), yaxis=dict(showgrid=True, gridcolor='lightgray', linecolor='gray', ticks='outside'))
        fig_rev.add_hline(y=0, line_width=1, line_color="black") # Breakeven Line
        fig_rev.update_xaxes(mirror=True, showline=True, linecolor='gray')
        fig_rev.update_yaxes(mirror=True, showline=True, linecolor='gray')
        st.plotly_chart(fig_rev, use_container_width=True)
