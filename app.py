import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# --- KONFIGURACJA I POŁĄCZENIE ---
st.set_page_config(page_title="Panel Magazynowy Pro", layout="wide", page_icon="🏢")

@st.cache_resource
def init_connection():
    # Upewnij się, że masz secrets.toml skonfigurowane
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Błąd połączenia z bazą danych: {e}. Sprawdź plik secrets.toml.")
    st.stop()

# --- FUNKCJE POBIERANIA DANYCH ---
def get_products():
    # Pobieramy produkty wraz z nazwą kategorii (join)
    res = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # Wyciągamy nazwę kategorii z zagnieżdżonego słownika
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else 'Brak kategorii')
        # Obliczamy wartość każdej pozycji
        df['wartość_pozycji'] = df['cena'] * df['liczba']
    return df

def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    return pd.DataFrame(res.data)

# --- MENU BOCZNE ---
st.sidebar.title("🏢 Nawigacja")
page = st.sidebar.radio("Wybierz widok:", ["Dashboard & Wykresy", "Dodaj Dane"])
st.sidebar.divider()
st.sidebar.info("System zarządzania magazynem v1.2")

# --- WIDOK 1: DASHBOARD, WYKRESY I TABELE ---
if page == "Dashboard & Wykresy":
    st.title("📊 Podsumowanie Magazynu")
    
    with st.spinner("Ładowanie danych..."):
        products_df = get_products()
        categories_df = get_categories()

    if products_df.empty:
        st.info("Baza danych jest pusta. Przejdź do zakładki 'Dodaj Dane', aby rozpocząć.")
    else:
        # --- SEKCJA SUMOWANIA (METRICS) ---
        total_value = products_df['wartość_pozycji'].sum()
        total_items = products_df['liczba'].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Łączna wartość magazynu", f"{total_value:,.2f} zł".replace(",", " "))
        col2.metric("Suma wszystkich sztuk", f"{int(total_items)}")
        col3.metric("Liczba unikalnych produktów", len(products_df))
        col4.metric("Liczba kategorii", len(categories_df))
        
        st.divider()

        # --- SEKCJA WYKRESÓW (NOWOŚĆ) ---
        st.subheader("📈 Wizualizacja Danych")
        
        chart_col1, chart_col2 = st.columns(2)

        # Wykres 1: Wartość magazynu według kategorii (Pie Chart)
        with chart_col1:
            # Grupujemy dane, aby zsumować wartość dla każdej kategorii
            category_summary = products_df.groupby('kategoria')['wartość_pozycji'].sum().reset_index()
            
            fig_pie = px.pie(
                category_summary, 
                values='wartość_pozycji', 
                names='kategoria', 
                title='Udział Kategorii w Wartości Magazynu',
                hole=0.4, # Donut chart visualization
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

        # Wykres 2: Top 10 najcenniejszych produktów (Bar Chart)
        with chart_col2:
            # Sortujemy malejąco po wartości i bierzemy 10 pierwszych
            top_products = products_df.sort_values(by='wartość_pozycji', ascending=False).head(10)
            
            fig_bar = px.bar(
                top_products, 
                x='wartość_pozycji', 
                y='nazwa', 
                orientation='h', # Poziomy wykres słupkowy
                title='Top 10 Najcenniejszych Pozycji (Ilość × Cena)',
                labels={'wartość_pozycji': 'Łączna Wartość (PLN)', 'nazwa': 'Produkt'},
                color='wartość_pozycji',
                color_continuous_scale=px.colors.sequential.Viridis
            )
            # Odwracamy oś Y, aby produkt nr 1 był na górze
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)

        st.divider()

        # --- TABELE DANYCH ---
        col_a, col_b = st.columns([2, 1])
        
        with col_a:
            st.subheader("📦 Szczegółowa Lista Produktów")
            st.dataframe(
                products_df[['nazwa', 'kategoria', 'liczba', 'cena', 'wartość_pozycji']], 
                use_container_width=True,
                hide_index=True,
                column_config={
                    "cena": st.column_config.NumberColumn(format="%.2f zł"),
                    "wartość_pozycji": st.column_config.NumberColumn(format="%.2f zł", label="Wartość Razem")
                }
            )

        with col_b:
            st.subheader("📁 Kategorie")
            st.dataframe(
                categories_df[['nazwa', 'opis']], 
                use_container_width=True,
                hide_index=True
            )

# --- WIDOK 2: DODAWANIE DANYCH (Bez zmian) ---
elif page == "Dodaj Dane":
    st.title("➕ Zarządzanie Zasobami")
    
    tab_p, tab_k = st.tabs(["Produkt", "Kategoria"])

    with tab_k:
        st.subheader("Nowa Kategoria")
        with st.form("kat_form", clear_on_submit=True):
            n_kat = st.text_input("Nazwa kategorii (wymagane)")
            o_kat = st.text_area("Opis")
            submitted = st.form_submit_button("Zapisz kategorię")
            if submitted:
                if n_kat:
                    try:
                        supabase.table("kategorie").insert({"nazwa": n_kat, "opis": o_kat}).execute()
                        st.success("Dodano kategorię!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd zapisu: {e}")
                else:
                    st.warning("Nazwa kategorii jest wymagana.")

    with tab_p:
        st.subheader("Nowy Produkt")
        categories_df = get_categories()
        if not categories_df.empty:
            # Tworzymy słownik: Nazwa Kategorii -> ID Kategorii
            cat_map = dict(zip(categories_df['nazwa'], categories_df['id']))
            
            with st.form("prod_form", clear_on_submit=True):
                n_prod = st.text_input("Nazwa produktu (wymagane)")
                col_f1, col_f2 = st.columns(2)
                c_prod = col_f1.number_input("Cena (zł)", min_value=0.0, step=0.01, format="%.2f")
                l_prod = col_f2.number_input("Ilość (szt.)", min_value=0, step=1)
                k_prod = st.selectbox("Wybierz kategorię", options=list(cat_map.keys()))
                
                submitted_prod = st.form_submit_button("Dodaj produkt")
                if submitted_prod:
                    if n_prod and k_prod:
                        payload = {
                            "nazwa": n_prod,
                            "cena": c_prod,
                            "liczba": l_prod,
                            "kategoria_id": cat_map[k_prod]
                        }
                        try:
                            supabase.table("Produkty").insert(payload).execute()
                            st.success("Produkt dodany pomyślnie!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Błąd zapisu: {e}")
                    else:
                        st.warning("Nazwa produktu i kategoria są wymagane.")
        else:
            st.warning("⚠️ Najpierw musisz dodać przynajmniej jedną kategorię w zakładce obok!")
