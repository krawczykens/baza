import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# --- KONFIGURACJA ---
st.set_page_config(page_title="Magazyn Pro v5.0", layout="wide", page_icon="📦")

@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Błąd konfiguracji! Sprawdź Secrets.")
        st.stop()

supabase = init_connection()

# --- POBIERANIE DANYCH ---
def get_products():
    res = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else 'Brak')
        df['wartość_razem'] = df['cena'] * df['liczba']
        df['id'] = df['id'].astype(int)
        df['liczba'] = df['liczba'].astype(int)
    return df

def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty: df['id'] = df['id'].astype(int)
    return df

# --- NAWIGACJA ---
st.sidebar.title("🏢 Menu Główne")
page = st.sidebar.radio("Nawigacja:", [
    "📊 Dashboard", 
    "📥 Przyjęcie Towaru", 
    "📤 Wydanie Towaru",
    "➕ Dodaj Nowy Produkt/Kat", 
    "✏️ Edytuj Dane", 
    "🗑️ Usuń Dane", 
    "🛡️ Weryfikacja Zapasów"
])

# --- 1. DASHBOARD ---
if page == "📊 Dashboard":
    st.title("📊 Statystyki")
    df_p = get_products()
    if not df_p.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Wartość", f"{df_p['wartość_razem'].sum():,.2f} zł")
        c2.metric("Sztuki", int(df_p['liczba'].sum()))
        c3.metric("Pozycje", len(df_p))
        st.divider()
        st.plotly_chart(px.pie(df_p, values='wartość_razem', names='kategoria', title="Wartość wg kategorii"), use_container_width=True)
        st.dataframe(df_p[['nazwa', 'kategoria', 'liczba', 'cena', 'wartość_razem']], use_container_width=True, hide_index=True)

# --- 2. PRZYJĘCIE TOWARU (NOWOŚĆ) ---
elif page == "📥 Przyjęcie Towaru":
    st.title("📥 Przyjęcie Produktów (Dostawa)")
    df_p = get_products()
    if not df_p.empty:
        prod_list = {f"{r['nazwa']} (Obecnie: {r['liczba']})": r for _, r in df_p.iterrows()}
        sel_prod = st.selectbox("Wybierz produkt z dostawy", options=list(prod_list.keys()))
        curr = prod_list[sel_prod]
        
        with st.form("inbound_form"):
            add_qty = st.number_input("Ile sztuk przyjąć?", min_value=1, step=1)
            if st.form_submit_button("Potwierdź Przyjęcie"):
                new_total = int(curr['liczba']) + int(add_qty)
                supabase.table("Produkty").update({"liczba": new_total}).eq("id", int(curr['id'])).execute()
                st.success(f"Zwiększono stan produktu {curr['nazwa']} do {new_total} szt.")
                st.rerun()

# --- 3. WYDANIE TOWARU (NOWOŚĆ) ---
elif page == "📤 Wydanie Towaru":
    st.title("📤 Wydanie Produktów (Sprzedaż/Rozchód)")
    df_p = get_products()
    if not df_p.empty:
        prod_list = {f"{r['nazwa']} (Dostępne: {r['liczba']})": r for _, r in df_p.iterrows()}
        sel_prod = st.selectbox("Wybierz produkt do wydania", options=list(prod_list.keys()))
        curr = prod_list[sel_prod]
        
        with st.form("outbound_form"):
            sub_qty = st.number_input("Ile sztuk wydać?", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź Wydanie"):
                if sub_qty > curr['liczba']:
                    st.error(f"Nie masz tyle na stanie! Maksymalnie możesz wydać: {curr['liczba']} szt.")
                else:
                    new_total = int(curr['liczba']) - int(sub_qty)
                    supabase.table("Produkty").update({"liczba": new_total}).eq("id", int(curr['id'])).execute()
                    st.success(f"Wydano {sub_qty} szt. Pozostało: {new_total} szt.")
                    st.rerun()

# --- 4. DODAWANIE ---
elif page == "➕ Dodaj Nowy Produkt/Kat":
    st.title("➕ Nowe Pozycje")
    t1, t2 = st.tabs(["Produkt", "Kategoria"])
    with t2:
        with st.form("a_k"):
            kn = st.text_input("Nazwa kategorii")
            if st.form_submit_button("Dodaj"):
                supabase.table("kategorie").insert({"nazwa": kn}).execute()
                st.rerun()
    with t1:
        df_k = get_categories()
        if not df_k.empty:
            cat_map = dict(zip(df_k['nazwa'], df_k['id']))
            with st.form("a_p"):
                pn = st.text_input("Nazwa")
                pc = st.number_input("Cena", min_value=0.0)
                pl = st.number_input("Ilość", min_value=0)
                pk = st.selectbox("Kategoria", options=list(cat_map.keys()))
                if st.form_submit_button("Zapisz"):
                    supabase.table("Produkty").insert({"nazwa": pn, "cena": pc, "liczba": pl, "kategoria_id": int(cat_map[pk])}).execute()
                    st.rerun()

# --- 5. EDYCJA ---
elif page == "✏️ Edytuj Dane":
    st.title("✏️ Edycja")
    df_p = get_products()
    if not df_p.empty:
        prod_opt = {f"{r['nazwa']} (ID:{r['id']})": r for _, r in df_p.iterrows()}
        sel = st.selectbox("Produkt", options=list(prod_opt.keys()))
        curr = prod_opt[sel]
        with st.form("e_p"):
            en = st.text_input("Nazwa", value=curr['nazwa'])
            ec = st.number_input("Cena", value=float(curr['cena']))
            if st.form_submit_button("Zapisz"):
                supabase.table("Produkty").update({"nazwa": en, "cena": ec}).eq("id", int(curr['id'])).execute()
                st.rerun()

# --- 6. USUWANIE ---
elif page == "🗑️ Usuń Dane":
    st.title("🗑️ Usuwanie")
    df_p = get_products()
    if not df_p.empty:
        p_del = st.selectbox("Wybierz", options=df_p.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
        if st.button("USUŃ", type="primary"):
            id_p = int(p_del.split("ID:")[1])
            supabase.table("Produkty").delete().eq("id", id_p).execute()
            st.rerun()

# --- 7. WERYFIKACJA ---
elif page == "🛡️ Weryfikacja Zapasów":
    st.title("🛡️ Kontrola")
    df_p = get_products()
    safe_level = st.slider("Bezpieczny poziom", 0, 50, 5)
    if not df_p.empty:
        crit = df_p[df_p['liczba'] < safe_level]
        if not crit.empty:
            st.warning(f"Braki: {len(crit)}")
            st.dataframe(crit[['nazwa', 'liczba', 'kategoria']])
        else:
            st.success("Wszystko OK!")
