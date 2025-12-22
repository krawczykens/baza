import streamlit as st
from supabase import create_client, Client

# --- KONFIGURACJA POŁĄCZENIA ---
# W wersji produkcyjnej (GitHub/Streamlit Cloud) użyj st.secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_categories():
    """Pobiera listę kategorii do selectboxa"""
    response = supabase.table("kategorie").select("id, nazwa").execute()
    return response.data

# --- INTERFEJS UŻYTKOWNIKA ---
st.set_page_config(page_title="Zarządzanie Produktami", layout="centered")
st.title("📦 System Zarządzania Magazynem")

tab1, tab2 = st.tabs(["Dodaj Produkt", "Dodaj Kategorię"])

# --- TAB: DODAWANIE KATEGORII ---
with tab2:
    st.header("Nowa Kategoria")
    with st.form("category_form", clear_on_submit=True):
        kat_nazwa = st.text_input("Nazwa kategorii*")
        kat_opis = st.text_area("Opis")
        
        submit_kat = st.form_submit_button("Zapisz kategorię")
        
        if submit_kat:
            if kat_nazwa:
                data = {"nazwa": kat_nazwa, "opis": kat_opis}
                try:
                    supabase.table("kategorie").insert(data).execute()
                    st.success(f"Dodano kategorię: {kat_nazwa}")
                except Exception as e:
                    st.error(f"Błąd: {e}")
            else:
                st.warning("Nazwa kategorii jest wymagana!")

# --- TAB: DODAWANIE PRODUKTU ---
with tab1:
    st.header("Nowy Produkt")
    
    # Pobieramy aktualne kategorie
    categories = get_categories()
    cat_options = {cat['nazwa']: cat['id'] for cat in categories}
    
    with st.form("product_form", clear_on_submit=True):
        prod_nazwa = st.text_input("Nazwa produktu*")
        prod_liczba = st.number_input("Liczba (szt.)", min_value=0, step=1)
        prod_cena = st.number_input("Cena", min_value=0.0, format="%.2f")
        prod_kat_name = st.selectbox("Kategoria", options=list(cat_options.keys()))
        
        submit_prod = st.form_submit_button("Dodaj produkt do bazy")
        
        if submit_prod:
            if prod_nazwa and prod_kat_name:
                payload = {
                    "nazwa": prod_nazwa,
                    "liczba": prod_liczba,
                    "cena": prod_cena,
                    "kategoria_id": cat_options[prod_kat_name]
                }
                try:
                    supabase.table("Produkty").insert(payload).execute()
                    st.success(f"Produkt '{prod_nazwa}' został dodany!")
                except Exception as e:
                    st.error(f"Wystąpił błąd: {e}")
            else:
                st.warning("Wypełnij wymagane pola (nazwa i kategoria)!")

# --- PODGLĄD DANYCH ---
if st.checkbox("Pokaż listę produktów"):
    res = supabase.table("Produkty").select("nazwa, liczba, cena, kategorie(nazwa)").execute()
    if res.data:
        st.table(res.data)
