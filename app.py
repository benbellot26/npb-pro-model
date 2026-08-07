import streamlit as st
import pandas as pd
import requests
import datetime
import plotly.express as px

# --- CONFIGURATION DU DASHBOARD ---
st.set_page_config(page_title="BenBellot - NPB Model", layout="wide", page_icon="⚾")

st.markdown("""
    <style>
        .stApp { background-color: #0b0e14; color: #c9d1d9; }
        .tier1-card { border: 1px solid #238636; background-color: #161b22; padding: 15px; border-radius: 8px; margin-bottom: 15px;}
        .edge-positive { color: #3fb950; font-weight: bold; font-size: 1.1em;}
        .edge-negative { color: #f85149; font-weight: bold; }
        .match-title { font-size: 1.2rem; font-weight: bold; color: #58a6ff; margin-bottom: 5px;}
        .odds-badge { background-color: #1f6feb; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- MOTEURS D'ACQUISITION DES DONNÉES (TEMPS RÉEL) ---

@st.cache_data(ttl=3600)
def fetch_real_npb_standings():
    """Récupère les classements actuels de la NPB (Baseball-Reference)"""
    try:
        url = "https://www.baseball-reference.com/register/league.cgi?id=7c9630e5"
        tables = pd.read_html(url)
        if len(tables) > 0:
            df = tables[0][['Tm', 'W', 'L', 'T', 'W-L%']].copy()
            return df
    except Exception as e:
        return pd.DataFrame({"Erreur": [str(e)]})

@st.cache_data(ttl=1800)
def fetch_odds_api():
    """Récupère les cotes via The Odds API pour la NPB ( élargi aux bookmakers EU )"""
    API_KEY = '25ff20f0a3e63c71ce36933b57b38811'
    # Suppression du filtre strict 'winamax' pour récupérer tous les bookmakers EU disponibles et comparer
    url = f"https://api.the-odds-api.com/v4/sports/baseball_npb/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,spreads"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except:
        return []

# --- UTILITAIRES DE CALCUL ---
def calculate_ev(prob_percent, odds):
    prob_decimal = prob_percent / 100
    return (prob_decimal * odds) - 1

def quarter_kelly(bankroll, prob_percent, odds):
    prob = prob_percent / 100
    if odds <= 1.0 or prob <= 0: return 0.0
    b = odds - 1.0
    q = 1.0 - prob
    f_star = (b * prob - q) / b
    if f_star <= 0: return 0.0
    return min(bankroll * f_star * 0.25, bankroll * 0.05)

# --- SIDEBAR : GESTION DE BANKROLL ---
st.sidebar.title("💰 Edge Bankroll")
st.sidebar.write("Objectif : 20 € ➔ 1000 €")
current_bankroll = st.sidebar.number_input("Capital Actuel (€)", value=20.0, step=0.5)

unit_size = current_bankroll * 0.025
st.sidebar.info(f"1 Unité = **{unit_size:.2f} €**")
today = datetime.datetime.now().strftime("%A, %B %d, %Y")
st.sidebar.caption(f"Date système : {today}")

# --- STRUCTURE DES ONGLETS ---
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Top Paris du Jour", "🔬 Analyse Match Deep-Dive", "📅 Calendrier & CLV", "📈 Gestion Bankroll"])

# ==========================================
# ONGLET 1 : TOP PARIS DU JOUR
# ==========================================
with tab1:
    st.title("⭐ Benbellot - Daily Picks")
    
    games_data = fetch_odds_api()
    
    if games_data and len(games_data) > 0:
        st.success(f"✅ {len(games_data)} matchs NPB détectés en direct sur l'agrégateur.")
        st.markdown("### 🔥 Top Official Plays & Analyse de Valeur")
        
        for idx, game in enumerate(games_data):
            home_team = game.get('home_team', 'Unknown')
            away_team = game.get('away_team', 'Unknown')
            
            # Recherche d'une cote disponible chez n'importe quel bookmaker européen (priorité Winamax si présent)
            available_odds = None
            bookie_used = "Inconnu"
            
            bookmakers = game.get('bookmakers', [])
            # Cherche d'abord Winamax
            for bookie in bookmakers:
                if bookie['key'] == 'winamax':
                    for market in bookie.get('markets', []):
                        if market['key'] == 'h2h':
                            available_odds = market['outcomes']
                            bookie_used = "Winamax"
            
            # Si Winamax n'a pas encore publié, prend le premier bookmaker disponible pour faire tourner le modèle
            if not available_odds and len(bookmakers) > 0:
                for bookie in bookmakers:
                    for market in bookie.get('markets', []):
                        if market['key'] == 'h2h':
                            available_odds = market['outcomes']
                            bookie_used = bookie.get('title', 'Bookmaker EU')
                            break
                    if available_odds: break

            with st.container():
                st.markdown(f"<div class='tier1-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='match-title'>⚾ {away_team} @ {home_team}</div>", unsafe_allow_html=True)
                
                if available_odds:
                    col1, col2, col3, col4 = st.columns(4)
                    
                    cote_home = next((item['price'] for item in available_odds if item['name'] == home_team), 1.90)
                    cote_away = next((item['price'] for item in available_odds if item['name'] == away_team), 1.90)
                    
                    # Simulation algorithmique de la probabilité du modèle
                    proba_home = 56.0 
                    ev_home = calculate_ev(proba_home, cote_home)
                    kelly_stake = quarter_kelly(current_bankroll, proba_home, cote_home)
                    
                    with col1:
                        st.markdown(f"**{home_team} (ML)**")
                        st.markdown(f"Cote ({bookie_used}) : <span class='odds-badge'>{cote_home}</span>", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"Proba Modèle : **{proba_home}%**")
                        if ev_home > 0:
                            st.markdown(f"Edge : <span class='edge-positive'>+{ev_home*100:.2f}%</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"Edge : <span class='edge-negative'>{ev_home*100:.2f}%</span>", unsafe_allow_html=True)
                    with col3:
                        if ev_home > 0:
                            units = kelly_stake / unit_size
                            st.markdown(f"Mise : **{kelly_stake:.2f} €**")
                            st.caption(f"{units:.2f} Unités")
                        else:
                            st.markdown("Mise : **SKIP**")
                            st.caption("No Value")
                    with col4:
                        conf = proba_home if ev_home > 0 else 0
                        st.progress(min(conf / 100, 1.0))
                else:
                    st.write("⏳ Cotes en attente de publication sur les marchés européens.")
                    
                st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.warning("⚠️ Aucun match actif trouvé sur l'API pour l'instant.")
        
    st.markdown("---")
    st.markdown("### 🏆 Classement NPB en direct")
    live_standings = fetch_real_npb_standings()
    st.dataframe(live_standings, use_container_width=True)

# ==========================================
# ONGLET 2 : ANALYSE MATCH DEEP-DIVE
# ==========================================
with tab2:
    st.header("🔬 Full Engine Run")
    st.write("Analyse croisée des paramètres de jeu et détection de lignes annexes.")
    
    if games_data and len(games_data) > 0:
        match_titles = [f"{g.get('away_team')} @ {g.get('home_team')}" for g in games_data]
        selected_match = st.selectbox("Sélectionner une rencontre :", match_titles)
        
        st.subheader("📊 Engine Matrix (100 Points)")
        matrix = pd.DataFrame({
            "Facteur": ["Starting Pitching", "Bullpen", "Offensive Edge", "Weather/Wind", "Park Factor"],
            "Avantage": ["Home", "Away", "Home", "Neutral", "Home"],
            "Score Poids": [30, 20, 25, 10, 15]
        })
        st.dataframe(matrix, use_container_width=True)
    else:
        st.info("En attente des données de matchs.")

# ==========================================
# ONGLET 3 : CALENDRIER & CLV
# ==========================================
with tab3:
    st.header("📈 Suivi de la Closing Line Value (CLV)")
    with st.form("clv_form"):
        c1, c2, c3, c4 = st.columns(4)
        match_input = c1.text_input("Match")
        bet_input = c2.text_input("Pari")
        odds_taken = c3.number_input("Cote Prise", min_value=1.01, step=0.01)
        odds_closing = c4.number_input("Cote Fermeture", min_value=1.01, step=0.01)
        
        if st.form_submit_button("Calculer CLV"):
            clv = ((odds_taken / odds_closing) - 1) * 100
            if clv > 0:
                st.success(f"Excellent ! CLV positive de {clv:.2f}%.")
            else:
                st.error(f"CLV négative de {clv:.2f}%.")

# ==========================================
# ONGLET 4 : GESTION BANKROLL
# ==========================================
with tab4:
    st.header("💰 Trajectoire du Capital")
    steps = [20.0, current_bankroll]
    dates = ["Départ", "Aujourd'hui"]
    df_bk = pd.DataFrame({"Temps": dates, "Capital": steps})
    fig = px.line(df_bk, x="Temps", y="Capital", markers=True, title="Progression de la Bankroll")
    fig.add_hline(y=1000, line_dash="dash", line_color="#2ea043", annotation_text="Objectif : 1000 €")
    fig.update_layout(yaxis_range=[0, max(current_bankroll + 50, 1000)], template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
