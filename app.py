import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="System Magazynowy Pro", layout="wide", page_icon="📦")

# --- POŁĄCZENIE Z SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Błąd konfiguracji Secrets! Sprawdź ustawienia na Streamlit Cloud.")
        st.stop()

supabase = init_connection()

# --- FUNKCJE POBIERANIA DANYCH ---
def get_products():
    # Zgodnie z Twoim obrazkiem: tabela 'Produkty' (duża litera)
    res = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # Wyciąganie nazwy kategorii z relacji
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else 'Brak')
        # Obliczanie wartości (cena * liczba)
        df['wartość_razem'] = df['cena'] * df['liczba']
        # Konwersja ID na int, aby uniknąć problemów z typami NumPy
        df['id'] = df['id'].astype(int)
    return df

def get_categories():
    # Zgodnie z Twoim obrazkiem: tabela 'kategorie' (mała litera)
    res = supabase.table("kategorie").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['id'] = df['id'].astype(int)
    return df

# --- MENU BOCZNE ---
st.sidebar.title("🏢 Zarządzanie")
page = st.sidebar.radio("Nawigacja:", ["📊 Dashboard", "➕ Dodaj Nowe", "✏️ Edytuj Dane", "🗑️ Usuń Dane"])

# --- 1. DASHBOARD ---
if page == "📊 Dashboard":
    st.title("📊 Podsumowanie Magazynu")
    df_p = get_products()
    df_k = get_categories()

    if df_p.empty:
        st.info("Baza jest pusta. Dodaj produkty w zakładce 'Dodaj Nowe'.")
    else:
        # Metryki
        total_val = df_p['wartość_razem'].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Wartość magazynu", f"{total_val:,.2f} zł")
        col2.metric("Liczba sztuk", int(df_p['liczba'].sum()))
        col3.metric("Liczba pozycji", len(df_p))

        st.divider()

        # Wykresy
        c_left, c_right = st.columns(2)
        with c_left:
            fig_pie = px.pie(df_p, values='wartość_razem', names='kategoria', title="Podział wartości wg kategorii")
            st.plotly_chart(fig_pie, use_container_width=True)
        with c_right:
            top_df = df_p.sort_values('wartość_razem', ascending=False).head(10)
            fig_bar = px.bar(top_df, x='wartość_razem', y='nazwa', orientation='h', title="Top 10 najdroższych pozycji")
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("📦 Wszystkie Produkty")
        st.dataframe(df_p[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'wartość_razem']], use_container_width=True, hide_index=True)

# --- 2. DODAWANIE ---
elif page == "➕ Dodaj Nowe":
    st.title("➕ Dodawanie danych")
    t1, t2 = st.tabs(["Produkt", "Kategoria"])

    with t2:
        with st.form("form_add_k"):
            kn = st.text_input("Nazwa nowej kategorii")
            ko = st.text_area("Opis kategorii")
            if st.form_submit_button("Dodaj kategorię"):
                if kn:
                    supabase.table("kategorie").insert({"nazwa": kn, "opis": ko}).execute()
                    st.success("Dodano!")
                    st.rerun()

    with t1:
        df_k = get_categories()
        if df_k.empty:
            st.warning("Najpierw musisz dodać kategorię!")
        else:
            cat_map = dict(zip(df_k['nazwa'], df_k['id']))
            with st.form("form_add_p"):
                pn = st.text_input("Nazwa produktu")
                pc = st.number_input("Cena", min_value=0.0, step=0.01)
                pl = st.number_input("Ilość", min_value=0, step=1)
                pk = st.selectbox("Kategoria", options=list(cat_map.keys()))
                if st.form_submit_button("Zapisz produkt"):
                    payload = {
                        "nazwa": pn, 
                        "cena": float(pc), 
                        "liczba": int(pl), 
                        "kategoria_id": int(cat_map[pk])
                    }
                    supabase.table("Produkty").insert(payload).execute()
                    st.success("Produkt dodany!")
                    st.rerun()

# --- 3. EDYCJA (Z POPRAWKĄ BŁĘDU TYPÓW) ---
elif page == "✏️ Edytuj Dane":
    st.title("✏️ Edycja rekordów")
    df_p = get_products()
    df_k = get_categories()

    if not df_p.empty:
        # Wybór produktu (używamy słownika, by łatwo dobrać dane)
        prod_labels = {f"{r['nazwa']} (ID: {r['id']})": r for _, r in df_p.iterrows()}
        selected_prod = st.selectbox("Wybierz produkt", options=list(prod_labels.keys()))
        curr = prod_labels[selected_prod]

        with st.form("form_edit_p"):
            en = st.text_input("Nowa nazwa", value=curr['nazwa'])
            ec = st.number_input("Nowa cena", value=float(curr['cena']), step=0.01)
            el = st.number_input("Nowa ilość", value=int(curr['liczba']), step=1)
            
            # Kategoria
            kat_list = df_k['nazwa'].tolist()
            curr_kat_idx = kat_list.index(curr['kategoria']) if curr['kategoria'] in kat_list else 0
            ek = st.selectbox("Zmień kategorię", options=kat_list, index=curr_kat_idx)
            
            if st.form_submit_button("Zatwierdź zmiany"):
                # KLUCZOWE: Rzutowanie na typy Pythonowe przed wysłaniem JSON
                new_cat_id = int(df_k[df_k['nazwa'] == ek]['id'].iloc[0])
                target_id = int(curr['id'])
                
                upd_payload = {
                    "nazwa": en,
                    "cena": float(ec),
                    "liczba": int(el),
                    "kategoria_id": new_cat_id
                }
                
                try:
                    supabase.table("Produkty").update(upd_payload).eq("id", target_id).execute()
                    st.success("Dane zaktualizowane!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd bazy: {e}")
    else:
        st.info("Brak danych do edycji.")

# --- 4. USUWANIE ---
elif page == "🗑️ Usuń Dane":
    st.title("🗑️ Usuwanie")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Usuń produkt")
        df_p = get_products()
        if not df_p.empty:
            p_del = st.selectbox("Wybierz produkt", options=df_p.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
            id_p_del = int(p_del.split("ID:")[1])
            if st.button("❌ Usuń produkt", type="primary"):
                supabase.table("Produkty").delete().eq("id", id_p_del).execute()
                st.rerun()

    with col_b:
        st.subheader("Usuń kategorię")
        df_k = get_categories()
        if not df_k.empty:
            k_del = st.selectbox("Wybierz kategorię", options=df_k.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
            id_k_del = int(k_del.split("ID:")[1])
            if st.button("🗑️ Usuń kategorię"):
                try:
                    supabase.table("kategorie").delete().eq("id", id_k_del).execute()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii, w której są produkty!")
