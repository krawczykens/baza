import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro v5.0", layout="wide", page_icon="📦")

# --- POŁĄCZENIE Z SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Błąd konfiguracji! Sprawdź Secrets w Streamlit Cloud.")
        st.stop()

supabase = init_connection()

# --- FUNKCJE POBIERANIA DANYCH ---
def get_products():
    res = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else 'Brak')
        df['wartość_razem'] = df['cena'] * df['liczba']
        # Konwersja typów dla stabilności JSON
        df['id'] = df['id'].astype(int)
        df['liczba'] = df['liczba'].astype(int)
        df['cena'] = df['cena'].astype(float)
    return df

def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['id'] = df['id'].astype(int)
    return df

# --- MENU BOCZNE ---
st.sidebar.title("🏢 System Zarządzania")
page = st.sidebar.radio("Nawigacja:", [
    "📊 Dashboard", 
    "📥 Przyjęcie Towaru", 
    "📤 Wydanie Towaru",
    "➕ Zarządzanie Bazą", 
    "✏️ Edytuj Dane", 
    "🗑️ Usuń Dane", 
    "🛡️ Weryfikacja Zapasów"
])

# --- 1. DASHBOARD ---
if page == "📊 Dashboard":
    st.title("📊 Analityka Magazynowa")
    df_p = get_products()
    
    if df_p.empty:
        st.info("Magazyn jest pusty. Dodaj produkty, aby zobaczyć statystyki.")
    else:
        # Metryki
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Wartość Magazynu", f"{df_p['wartość_razem'].sum():,.2f} zł")
        c2.metric("Suma Sztuk", f"{int(df_p['liczba'].sum())}")
        c3.metric("Liczba Pozycji", len(df_p))
        c4.metric("Średnia Cena", f"{df_p['cena'].mean():,.2f} zł")

        st.divider()

        # Wykresy - Rząd 1
        col1, col2 = st.columns(2)
        with col1:
            fig1 = px.pie(df_p, values='wartość_razem', names='kategoria', title="Udział Kategorii w Wartości", hole=0.4)
            st.plotly_chart(fig1, use_container_width=True)
        with col2:
            cat_val = df_p.groupby('kategoria')['wartość_razem'].sum().reset_index()
            fig2 = px.bar(cat_val, x='kategoria', y='wartość_razem', title="Suma Wartości wg Kategorii", color='kategoria')
            st.plotly_chart(fig2, use_container_width=True)

        # Wykresy - Rząd 2
        col3, col4 = st.columns(2)
        with col3:
            top_qty = df_p.sort_values('liczba', ascending=False).head(10)
            fig3 = px.bar(top_qty, x='liczba', y='nazwa', orientation='h', title="Top 10 Najliczniejszych Produktów", color='liczba')
            st.plotly_chart(fig3, use_container_width=True)
        with col4:
            fig4 = px.histogram(df_p, x="cena", title="Rozkład Cen Produktów", color_discrete_sequence=['indianred'])
            st.plotly_chart(fig4, use_container_width=True)

        st.subheader("📋 Aktualny Stan Tabelaryczny")
        st.dataframe(df_p[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'wartość_razem']], use_container_width=True, hide_index=True)

# --- 2. PRZYJĘCIE TOWARU ---
elif page == "📥 Przyjęcie Towaru":
    st.title("📥 Przyjęcie Produktów")
    df_p = get_products()
    if not df_p.empty:
        options = {f"{r['nazwa']} (Stan: {r['liczba']})": r for _, r in df_p.iterrows()}
        selected = st.selectbox("Wybierz produkt", options=list(options.keys()))
        curr = options[selected]
        
        with st.form("in_form"):
            qty = st.number_input("Ilość do dodania", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź Przyjęcie"):
                new_qty = int(curr['liczba']) + int(qty)
                supabase.table("Produkty").update({"liczba": new_qty}).eq("id", int(curr['id'])).execute()
                st.success(f"Zaktualizowano! Nowy stan {curr['nazwa']}: {new_qty} szt.")
                st.rerun()

# --- 3. WYDANIE TOWARU ---
elif page == "📤 Wydanie Towaru":
    st.title("📤 Wydanie Produktów")
    df_p = get_products()
    if not df_p.empty:
        options = {f"{r['nazwa']} (Dostępne: {r['liczba']})": r for _, r in df_p.iterrows()}
        selected = st.selectbox("Wybierz produkt", options=list(options.keys()))
        curr = options[selected]
        
        with st.form("out_form"):
            qty = st.number_input("Ilość do wydania", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź Wydanie"):
                if qty > curr['liczba']:
                    st.error(f"Błąd! Brakuje {qty - curr['liczba']} sztuk na magazynie.")
                else:
                    new_qty = int(curr['liczba']) - int(qty)
                    supabase.table("Produkty").update({"liczba": new_qty}).eq("id", int(curr['id'])).execute()
                    st.success(f"Wydano towar. Pozostało: {new_qty} szt.")
                    st.rerun()

# --- 4. ZARZĄDZANIE BAZĄ (DODAWANIE) ---
elif page == "➕ Zarządzanie Bazą":
    st.title("➕ Dodawanie do bazy")
    tab_p, tab_k = st.tabs(["Nowy Produkt", "Nowa Kategoria"])
    
    with tab_k:
        with st.form("add_k"):
            n_k = st.text_input("Nazwa kategorii")
            if st.form_submit_button("Dodaj Kategorię"):
                if n_k:
                    supabase.table("kategorie").insert({"nazwa": n_k}).execute()
                    st.success("Dodano kategorię!")
                    st.rerun()

    with tab_p:
        df_k = get_categories()
        if not df_k.empty:
            cat_map = dict(zip(df_k['nazwa'], df_k['id']))
            with st.form("add_p"):
                n_p = st.text_input("Nazwa produktu")
                c_p = st.number_input("Cena", min_value=0.0, step=0.01)
                l_p = st.number_input("Początkowa ilość", min_value=0, step=1)
                k_p = st.selectbox("Kategoria", options=list(cat_map.keys()))
                if st.form_submit_button("Zapisz Produkt"):
                    payload = {"nazwa": n_p, "cena": float(c_p), "liczba": int(l_p), "kategoria_id": int(cat_map[k_p])}
                    supabase.table("Produkty").insert(payload).execute()
                    st.success("Produkt dodany!")
                    st.rerun()

# --- 5. EDYCJA ---
elif page == "✏️ Edytuj Dane":
    st.title("✏️ Edycja Danych")
    df_p = get_products()
    df_k = get_categories()
    if not df_p.empty:
        options = {f"{r['nazwa']} (ID:{r['id']})": r for _, r in df_p.iterrows()}
        selected = st.selectbox("Produkt do edycji", options=list(options.keys()))
        curr = options[selected]
        
        with st.form("edit_form"):
            e_n = st.text_input("Nazwa", value=curr['nazwa'])
            e_c = st.number_input("Cena", value=float(curr['cena']))
            k_list = df_k['nazwa'].tolist()
            e_k = st.selectbox("Kategoria", options=k_list, index=k_list.index(curr['kategoria']))
            if st.form_submit_button("Zapisz zmiany"):
                k_id = int(df_k[df_k['nazwa'] == e_k]['id'].iloc[0])
                upd = {"nazwa": e_n, "cena": float(e_c), "kategoria_id": k_id}
                supabase.table("Produkty").update(upd).eq("id", int(curr['id'])).execute()
                st.success("Zaktualizowano dane!")
                st.rerun()

# --- 6. USUWANIE ---
elif page == "🗑️ Usuń Dane":
    st.title("🗑️ Usuwanie z bazy")
    col_p, col_k = st.columns(2)
    with col_p:
        st.subheader("Usuń Produkt")
        df_p = get_products()
        if not df_p.empty:
            p_del = st.selectbox("Wybierz produkt", options=df_p.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
            if st.button("USUŃ PRODUKT", type="primary"):
                id_to_del = int(p_del.split("ID:")[1])
                supabase.table("Produkty").delete().eq("id", id_to_del).execute()
                st.rerun()
    with col_k:
        st.subheader("Usuń Kategorię")
        df_k = get_categories()
        if not df_k.empty:
            k_del = st.selectbox("Wybierz kategorię", options=df_k.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
            if st.button("USUŃ KATEGORIĘ"):
                id_k_del = int(k_del.split("ID:")[1])
                try:
                    supabase.table("kategorie").delete().eq("id", id_k_del).execute()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii z produktami!")

# --- 7. WERYFIKACJA ---
elif page == "🛡️ Weryfikacja Zapasów":
    st.title("🛡️ Kontrola Stanów")
    df_p = get_products()
    limit = st.slider("Próg ostrzegawczy (ilość sztuk):", 0, 50, 5)
    if not df_p.empty:
        low_stock = df_p[df_p['liczba'] < limit].sort_values('liczba')
        if not low_stock.empty:
            st.warning(f"Uwaga! {len(low_stock)} produktów wymaga uzupełnienia.")
            st.dataframe(low_stock[['nazwa', 'liczba', 'kategoria']], use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(low_stock, x='nazwa', y='liczba', title="Brakujące produkty", color_discrete_sequence=['orange']))
        else:
            st.success("Wszystkie stany są na bezpiecznym poziomie!")
