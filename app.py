import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro v3.0", layout="wide", page_icon="📦")

# --- POŁĄCZENIE Z SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Błąd konfiguracji Secrets! Upewnij się, że dodałeś SUPABASE_URL i SUPABASE_KEY.")
        st.stop()

supabase = init_connection()

# --- FUNKCJE POMOCNICZE (POBIERANIE DANYCH) ---
def get_products():
    # Pobieranie produktów z joinem do tabeli kategorie
    res = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # Mapowanie zagnieżdżonej nazwy kategorii
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else 'Brak')
        df['wartość_razem'] = df['cena'] * df['liczba']
    return df

def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    return pd.DataFrame(res.data)

# --- SIDEBAR (NAWIGACJA) ---
st.sidebar.title("🏢 Menu Magazynu")
page = st.sidebar.radio("Nawigacja:", ["📊 Dashboard", "➕ Dodaj Nowe", "✏️ Edytuj Dane", "🗑️ Usuń Dane"])

# --- 1. DASHBOARD (WYKRESY I STATYSTYKI) ---
if page == "📊 Dashboard":
    st.title("📊 Statystyki i Podsumowanie")
    
    df_p = get_products()
    df_k = get_categories()

    if df_p.empty:
        st.info("Baza produktów jest pusta. Dodaj dane, aby zobaczyć wykresy.")
    else:
        # Metryki na górze
        c1, c2, c3, c4 = st.columns(4)
        total_val = df_p['wartość_razem'].sum()
        c1.metric("Wartość magazynu", f"{total_val:,.2f} zł")
        c2.metric("Suma sztuk", int(df_p['liczba'].sum()))
        c3.metric("Liczba produktów", len(df_p))
        c4.metric("Liczba kategorii", len(df_k))

        st.divider()

        # Wykresy
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # Kołowy: Wartość wg kategorii
            cat_sum = df_p.groupby('kategoria')['wartość_razem'].sum().reset_index()
            fig_pie = px.pie(cat_sum, values='wartość_razem', names='kategoria', title="Podział wartości wg kategorii", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_chart2:
            # Słupkowy: Top 5 najdroższych stanów (cena * ilość)
            top_5 = df_p.sort_values('wartość_razem', ascending=False).head(5)
            fig_bar = px.bar(top_5, x='wartość_razem', y='nazwa', orientation='h', title="Top 5 najcenniejszych pozycji", color='nazwa')
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("📦 Pełna lista produktów")
        st.dataframe(df_p[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'wartość_razem']], use_container_width=True, hide_index=True)

# --- 2. DODAWANIE DANYCH ---
elif page == "➕ Dodaj Nowe":
    st.title("➕ Dodaj do bazy")
    tab1, tab2 = st.tabs(["Produkt", "Kategoria"])

    with tab2:
        st.subheader("Nowa Kategoria")
        with st.form("form_add_kat", clear_on_submit=True):
            kat_n = st.text_input("Nazwa kategorii")
            kat_o = st.text_area("Opis")
            if st.form_submit_button("Zapisz kategorię"):
                if kat_n:
                    supabase.table("kategorie").insert({"nazwa": kat_n, "opis": kat_o}).execute()
                    st.success("Dodano kategorię!")
                    st.rerun()

    with tab1:
        st.subheader("Nowy Produkt")
        df_k = get_categories()
        if df_k.empty:
            st.warning("Najpierw dodaj kategorię!")
        else:
            cat_map = dict(zip(df_k['nazwa'], df_k['id']))
            with st.form("form_add_prod", clear_on_submit=True):
                p_n = st.text_input("Nazwa produktu")
                p_c = st.number_input("Cena (zł)", min_value=0.0)
                p_l = st.number_input("Liczba (szt)", min_value=0)
                p_k = st.selectbox("Kategoria", options=list(cat_map.keys()))
                if st.form_submit_button("Dodaj produkt"):
                    payload = {"nazwa": p_n, "cena": p_c, "liczba": p_l, "kategoria_id": cat_map[p_k]}
                    supabase.table("Produkty").insert(payload).execute()
                    st.success("Produkt dodany!")
                    st.rerun()

# --- 3. EDYCJA DANYCH ---
elif page == "✏️ Edytuj Dane":
    st.title("✏️ Edytuj istniejące rekordy")
    df_p = get_products()
    df_k = get_categories()

    if not df_p.empty:
        prod_options = {f"{r['nazwa']} (ID: {r['id']})": r for _, r in df_p.iterrows()}
        selected_label = st.selectbox("Wybierz produkt do edycji", options=list(prod_options.keys()))
        curr = prod_options[selected_label]

        with st.form("form_edit"):
            e_n = st.text_input("Nazwa", value=curr['nazwa'])
            e_c = st.number_input("Cena", value=float(curr['cena']))
            e_l = st.number_input("Ilość", value=int(curr['liczba']))
            e_k = st.selectbox("Kategoria", options=df_k['nazwa'].tolist(), index=df_k['nazwa'].tolist().index(curr['kategoria']))
            
            if st.form_submit_button("Zatwierdź zmiany"):
                new_cat_id = df_k[df_k['nazwa'] == e_k]['id'].values[0]
                upd = {"nazwa": e_n, "cena": e_c, "liczba": e_l, "kategoria_id": new_cat_id}
                supabase.table("Produkty").update(upd).eq("id", curr['id']).execute()
                st.success("Zaktualizowano!")
                st.rerun()
    else:
        st.info("Brak danych do edycji.")

# --- 4. USUWANIE DANYCH ---
elif page == "🗑️ Usuń Dane":
    st.title("🗑️ Usuwanie")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Usuń produkt")
        df_p = get_products()
        if not df_p.empty:
            p_to_del = st.selectbox("Produkt", options=df_p.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
            id_to_del = int(p_to_del.split("ID:")[1])
            if st.button("❌ Usuń produkt", type="primary"):
                supabase.table("Produkty").delete().eq("id", id_to_del).execute()
                st.rerun()

    with col2:
        st.subheader("Usuń kategorię")
        df_k = get_categories()
        if not df_k.empty:
            k_to_del = st.selectbox("Kategoria", options=df_k.apply(lambda x: f"{x['nazwa']} | ID:{x['id']}", axis=1))
            id_k_to_del = int(k_to_del.split("ID:")[1])
            if st.button("🗑️ Usuń kategorię"):
                try:
                    supabase.table("kategorie").delete().eq("id", id_k_to_del).execute()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii, która ma przypisane produkty!")
