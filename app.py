import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro v4.0", layout="wide", page_icon="📦")

# --- POŁĄCZENIE Z SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Błąd konfiguracji! Upewnij się, że w Secrets masz SUPABASE_URL i SUPABASE_KEY.")
        st.stop()

supabase = init_connection()

# --- FUNKCJE POBIERANIA DANYCH ---
def get_products():
    # Pobieramy produkty wraz z nazwą kategorii
    res = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else 'Brak')
        df['wartość_razem'] = df['cena'] * df['liczba']
        # Naprawa typów dla JSON:
        df['id'] = df['id'].astype(int)
        df['liczba'] = df['liczba'].astype(int)
    return df

def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['id'] = df['id'].astype(int)
    return df

# --- SIDEBAR - NAWIGACJA ---
st.sidebar.title("🏢 System Magazynowy")
page = st.sidebar.radio("Nawigacja:", [
    "📊 Dashboard", 
    "➕ Dodaj Nowe", 
    "✏️ Edytuj Dane", 
    "🗑️ Usuń Dane", 
    "🛡️ Weryfikacja Zapasów"
])

# --- 1. DASHBOARD ---
if page == "📊 Dashboard":
    st.title("📊 Statystyki Magazynowe")
    df_p = get_products()
    
    if df_p.empty:
        st.info("Dodaj pierwsze produkty, aby zobaczyć statystyki.")
    else:
        # Metryki
        val = df_p['wartość_razem'].sum()
        szt = df_p['liczba'].sum()
        low_stock = len(df_p[df_p['liczba'] < 5])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Wartość Magazynu", f"{val:,.2f} zł")
        c2.metric("Suma Wszystkich Sztuk", f"{int(szt)}")
        c3.metric("Niskie Stany (<5 szt.)", low_stock, delta_color="inverse")
        
        st.divider()
        
        col_l, col_r = st.columns(2)
        with col_l:
            fig_pie = px.pie(df_p, values='wartość_razem', names='kategoria', title="Udział kategorii w wartości")
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_r:
            st.subheader("📦 Podgląd Tabeli")
            st.dataframe(df_p[['nazwa', 'kategoria', 'liczba', 'cena']], use_container_width=True, hide_index=True)

# --- 2. DODAWANIE ---
elif page == "➕ Dodaj Nowe":
    st.title("➕ Dodaj Zasoby")
    t1, t2 = st.tabs(["Nowy Produkt", "Nowa Kategoria"])
    
    with t2:
        with st.form("add_k"):
            kn = st.text_input("Nazwa kategorii")
            ko = st.text_area("Opis")
            if st.form_submit_button("Zapisz kategorię"):
                if kn:
                    supabase.table("kategorie").insert({"nazwa": kn, "opis": ko}).execute()
                    st.success(f"Dodano kategorię: {kn}")
                    st.rerun()

    with t1:
        df_k = get_categories()
        if df_k.empty:
            st.warning("Najpierw dodaj kategorię w zakładce obok!")
        else:
            cat_map = dict(zip(df_k['nazwa'], df_k['id']))
            with st.form("add_p"):
                pn = st.text_input("Nazwa produktu")
                pc = st.number_input("Cena (zł)", min_value=0.0)
                pl = st.number_input("Ilość (szt)", min_value=0)
                pk = st.selectbox("Kategoria", options=list(cat_map.keys()))
                if st.form_submit_button("Zapisz produkt"):
                    if pn:
                        # Rzutowanie na natywne typy Pythona (int/float)
                        payload = {"nazwa": pn, "cena": float(pc), "liczba": int(pl), "kategoria_id": int(cat_map[pk])}
                        supabase.table("Produkty").insert(payload).execute()
                        st.success("Produkt dodany!")
                        st.rerun()

# --- 3. EDYCJA ---
elif page == "✏️ Edytuj Dane":
    st.title("✏️ Edycja")
    df_p = get_products()
    df_k = get_categories()
    
    if not df_p.empty:
        prod_labels = {f"{r['nazwa']} (ID: {r['id']})": r for _, r in df_p.iterrows()}
        selected_label = st.selectbox("Wybierz produkt", options=list(prod_labels.keys()))
        curr = prod_labels[selected_label]
        
        with st.form("edit_f"):
            en = st.text_input("Nazwa", value=curr['nazwa'])
            ec = st.number_input("Cena", value=float(curr['cena']))
            el = st.number_input("Ilość", value=int(curr['liczba']))
            
            # Kategoria
            kat_list = df_k['nazwa'].tolist()
            curr_idx = kat_list.index(curr['kategoria']) if curr['kategoria'] in kat_list else 0
            ek = st.selectbox("Kategoria", options=kat_list, index=curr_idx)
            
            if st.form_submit_button("Zatwierdź zmiany"):
                new_cat_id = int(df_k[df_k['nazwa'] == ek]['id'].iloc[0])
                payload = {"nazwa": en, "cena": float(ec), "liczba": int(el), "kategoria_id": new_cat_id}
                supabase.table("Produkty").update(payload).eq("id", int(curr['id'])).execute()
                st.success("Zaktualizowano!")
                st.rerun()
    else:
        st.info("Brak danych.")

# --- 4. USUWANIE ---
elif page == "🗑️ Usuń Dane":
    st.title("🗑️ Usuwanie")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Usuń Produkt")
        df_p = get_products()
        if not df_p.empty:
            p_to_del = st.selectbox("Wybierz produkt", options=df_p.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
            if st.button("❌ Usuń produkt", type="primary"):
                id_p = int(p_to_del.split("ID:")[1])
                supabase.table("Produkty").delete().eq("id", id_p).execute()
                st.rerun()

    with col2:
        st.subheader("Usuń Kategorię")
        df_k = get_categories()
        if not df_k.empty:
            k_to_del = st.selectbox("Wybierz kategorię", options=df_k.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
            if st.button("🗑️ Usuń kategorię"):
                id_k = int(k_to_del.split("ID:")[1])
                try:
                    supabase.table("kategorie").delete().eq("id", id_k).execute()
                    st.rerun()
                except:
                    st.error("Kategoria nie jest pusta!")

# --- 5. WERYFIKACJA ZAPASÓW ---
elif page == "🛡️ Weryfikacja Zapasów":
    st.title("🛡️ Kontrola Stanów")
    df_p = get_products()
    
    safe_level = st.slider("Minimalna bezpieczna ilość sztuk:", 0, 50, 10)
    
    if not df_p.empty:
        # Klasyfikacja stanów
        def check_status(row):
            if row['liczba'] == 0: return "🔴 Brak"
            if row['liczba'] < safe_level: return "🟡 Niski"
            return "🟢 OK"
        
        df_p['Status'] = df_p.apply(check_status, axis=1)
        
        critical = df_p[df_p['liczba'] < safe_level].sort_values('liczba')
        
        if not critical.empty:
            st.warning(f"Znaleziono {len(critical)} pozycji wymagających uzupełnienia!")
            st.dataframe(critical[['nazwa', 'liczba', 'kategoria', 'Status']], use_container_width=True, hide_index=True)
            
            fig = px.bar(critical, x='nazwa', y='liczba', color='Status', 
                         title="Produkty poniżej progu bezpieczeństwa",
                         color_discrete_map={"🔴 Brak": "red", "🟡 Niski": "orange"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("Wszystkie stany magazynowe są w normie! ✅")
