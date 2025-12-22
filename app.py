import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- KONFIGURACJA I POŁĄCZENIE ---
st.set_page_config(page_title="Panel Magazynowy Pro", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- FUNKCJE POBIERANIA DANYCH ---
def get_products():
    # Pobieramy produkty wraz z nazwą kategorii (join)
    res = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # Wyciągamy nazwę kategorii z zagnieżdżonego słownika
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else 'Brak')
        df['wartość_razem'] = df['cena'] * df['liczba']
    return df

def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    return pd.DataFrame(res.data)

# --- MENU BOCZNE ---
st.sidebar.title("🏢 Nawigacja")
page = st.sidebar.radio("Wybierz widok:", ["Dashboard & Tabele", "Dodaj Dane"])

# --- WIDOK 1: DASHBOARD I TABELE ---
if page == "Dashboard & Tabele":
    st.title("📊 Podsumowanie Magazynu")
    
    products_df = get_products()
    categories_df = get_categories()

    # --- SEKCJA SUMOWANIA (METRICS) ---
    if not products_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Suma produktów (szt.)", int(products_df['liczba'].sum()))
        with col2:
            st.metric("Łączna wartość", f"{products_df['wartość_razem'].sum():,.2f} zł")
        with col3:
            st.metric("Liczba pozycji", len(products_df))
        with col4:
            st.metric("Liczba kategorii", len(categories_df))
        
        st.divider()

        # --- TABELE ---
        col_a, col_b = st.columns([2, 1])
        
        with col_a:
            st.subheader("📦 Lista Produktów")
            # Wyświetlamy tylko wybrane kolumny dla przejrzystości
            st.dataframe(
                products_df[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'wartość_razem']], 
                use_container_width=True,
                hide_index=True
            )

        with col_b:
            st.subheader("📁 Kategorie")
            st.dataframe(
                categories_df[['id', 'nazwa', 'opis']], 
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("Baza danych jest pusta. Dodaj pierwsze produkty w menu bocznym.")

# --- WIDOK 2: DODAWANIE DANYCH ---
elif page == "Dodaj Dane":
    st.title("➕ Zarządzanie Zasobami")
    
    tab_p, tab_k = st.tabs(["Produkt", "Kategoria"])

    with tab_k:
        st.subheader("Nowa Kategoria")
        with st.form("kat_form"):
            n_kat = st.text_input("Nazwa kategorii")
            o_kat = st.text_area("Opis")
            if st.form_submit_button("Zapisz kategorię"):
                if n_kat:
                    supabase.table("kategorie").insert({"nazwa": n_kat, "opis": o_kat}).execute()
                    st.success("Dodano kategorię!")
                    st.rerun()

    with tab_p:
        st.subheader("Nowy Produkt")
        cats = get_categories()
        if not cats.empty:
            cat_map = dict(zip(cats['nazwa'], cats['id']))
            with st.form("prod_form"):
                n_prod = st.text_input("Nazwa produktu")
                c_prod = st.number_input("Cena (zł)", min_value=0.0, step=0.01)
                l_prod = st.number_input("Ilość (szt.)", min_value=0, step=1)
                k_prod = st.selectbox("Wybierz kategorię", options=list(cat_map.keys()))
                
                if st.form_submit_button("Dodaj produkt"):
                    payload = {
                        "nazwa": n_prod,
                        "cena": c_prod,
                        "liczba": l_prod,
                        "kategoria_id": cat_map[k_prod]
                    }
                    supabase.table("Produkty").insert(payload).execute()
                    st.success("Produkt dodany!")
                    st.rerun()
        else:
            st.warning("Najpierw musisz dodać przynajmniej jedną kategorię!")
