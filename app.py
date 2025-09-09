
import io
from datetime import datetime, date

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from PIL import Image

# ---------------- Config (Streamlit Cloud friendly) ----------------
# Usa SQLite local (arquivo) e guarda FOTOS dentro do banco (BLOB).
DB_URL = "sqlite:///rnc.db"
engine = create_engine(DB_URL, poolclass=NullPool, future=True)

# ---------------- DB ----------------
def init_db():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS inspecoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TIMESTAMP NULL,
            area TEXT,
            titulo TEXT,
            responsavel TEXT,
            descricao TEXT,
            severidade TEXT,
            categoria TEXT,
            acoes TEXT,
            status TEXT DEFAULT 'Aberta',
            encerrada_em TIMESTAMP NULL,
            encerrada_por TEXT,
            encerramento_obs TEXT,
            eficacia TEXT,
            responsavel_acao TEXT,
            reaberta_em TIMESTAMP NULL,
            reaberta_por TEXT,
            reabertura_motivo TEXT
        );
        """)
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inspecao_id INTEGER NOT NULL,
            blob BLOB NOT NULL,
            filename TEXT,
            mimetype TEXT,
            tipo TEXT CHECK(tipo IN ('abertura','encerramento','reabertura')) DEFAULT 'abertura'
        );
        """)
        # Migrações idempotentes
        for ddl in [
            "ALTER TABLE inspecoes ADD COLUMN responsavel_acao TEXT",
            "ALTER TABLE inspecoes ADD COLUMN reaberta_em TIMESTAMP NULL",
            "ALTER TABLE inspecoes ADD COLUMN reaberta_por TEXT",
            "ALTER TABLE inspecoes ADD COLUMN reabertura_motivo TEXT",
            "ALTER TABLE inspecoes ADD COLUMN status TEXT"
        ]:
            try:
                conn.exec_driver_sql(ddl)
            except Exception:
                pass
        try:
            conn.exec_driver_sql("ALTER TABLE fotos ADD COLUMN filename TEXT")
        except Exception:
            pass
        try:
            conn.exec_driver_sql("ALTER TABLE fotos ADD COLUMN mimetype TEXT")
        except Exception:
            pass
        try:
            conn.exec_driver_sql("ALTER TABLE fotos ADD COLUMN blob BLOB")
        except Exception:
            pass
        try:
            conn.exec_driver_sql("ALTER TABLE fotos ADD COLUMN tipo TEXT")
        except Exception:
            pass

def insert_inspecao(rec, images: list):
    with engine.begin() as conn:
        res = conn.execute(text("""
            INSERT INTO inspecoes (data, area, titulo, responsavel, descricao, severidade, categoria, acoes, status, responsavel_acao)
            VALUES (:data, :area, :titulo, :responsavel, :descricao, :severidade, :categoria, :acoes, :status, :responsavel_acao)
        """), rec)
        inspecao_id = res.lastrowid if hasattr(res, "lastrowid") else conn.execute(text("SELECT last_insert_rowid()")).scalar_one()
        for img in images:
            conn.execute(text("""
                INSERT INTO fotos (inspecao_id, blob, filename, mimetype, tipo)
                VALUES (:iid, :blob, :name, :mime, 'abertura')
            """), {"iid": inspecao_id, "blob": img["blob"], "name": img["name"], "mime": img["mime"]})
        return inspecao_id

def add_photos(iid:int, images:list, tipo:str):
    with engine.begin() as conn:
        for img in images:
            conn.execute(text("""
                INSERT INTO fotos (inspecao_id, blob, filename, mimetype, tipo)
                VALUES (:iid, :blob, :name, :mime, :tipo)
            """), {"iid": iid, "blob": img["blob"], "name": img["name"], "mime": img["mime"], "tipo": tipo})

def fetch_df():
    with engine.begin() as conn:
        df = pd.read_sql(text("""
            SELECT id, data, area, titulo, responsavel, severidade, categoria, status,
                   descricao, acoes, encerrada_em, encerrada_por, encerramento_obs, eficacia,
                   responsavel_acao, reaberta_em, reaberta_por, reabertura_motivo
            FROM inspecoes
            ORDER BY id DESC
        """), conn)
    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    return df

def fetch_photos(iid:int, tipo:str):
    with engine.begin() as conn:
        df = pd.read_sql(text("""
            SELECT id, blob, filename, mimetype FROM fotos WHERE inspecao_id=:iid AND tipo=:tipo ORDER BY id
        """), conn, params={"iid": iid, "tipo": tipo})
    return df.to_dict("records") if not df.empty else []

def encerrar_inspecao(iid:int, por:str, obs:str, eficacia:str, images:list):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE inspecoes
               SET status='Encerrada',
                   encerrada_em=:dt,
                   encerrada_por=:por,
                   encerramento_obs=:obs,
                   eficacia=:ef
             WHERE id=:iid
        """), {"dt": datetime.now(), "por": por, "obs": obs, "ef": eficacia, "iid": iid})
    if images:
        add_photos(iid, images, "encerramento")

def reabrir_inspecao(iid:int, por:str, motivo:str, images:list):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE inspecoes
               SET status='Em ação',
                   reaberta_em=:dt,
                   reaberta_por=:por,
                   reabertura_motivo=:motivo
             WHERE id=:iid
        """), {"dt": datetime.now(), "por": por, "motivo": motivo, "iid": iid})
    if images:
        add_photos(iid, images, "reabertura")

# ---------------- UI ----------------
st.set_page_config(page_title="RNC — Streamlit Cloud (Grátis)", page_icon="🧭", layout="wide")
st.sidebar.title("RNC — v2.2 (Cloud)")
st.sidebar.caption("SQLite + fotos no banco (BLOB) • Sem custos")

init_db()

menu = st.sidebar.radio("Navegação", ["Nova RNC", "Consultar/Encerrar/Reabrir", "Exportar"], label_visibility="collapsed")

# Helpers
def files_to_images(uploaded_files):
    out = []
    for up in uploaded_files or []:
        try:
            blob = up.getbuffer().tobytes()
            out.append({"blob": blob, "name": up.name, "mime": up.type or "image/jpeg"})
        except Exception:
            pass
    return out

def show_image_from_blob(blob_bytes, width=360):
    try:
        im = Image.open(io.BytesIO(blob_bytes))
        st.image(im, width=width)
    except Exception:
        st.caption("Não foi possível exibir esta imagem.")

# -------- Nova RNC --------
if menu == "Nova RNC":
    st.header("Nova RNC")
    with st.form("form_rnc"):
        col1, col2, col3 = st.columns(3)
        with col1:
            data_insp = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            severidade = st.selectbox("Severidade", ["Baixa","Média","Alta","Crítica"])
        with col2:
            area = st.text_input("Área/Local", placeholder="Ex.: Correia TR-2011KS-07")
            categoria = st.selectbox("Categoria", ["Segurança","Qualidade","Meio Ambiente","Operação","Manutenção","Outros"])
        with col3:
            responsavel = st.text_input("Responsável pela inspeção", placeholder="Seu nome")
            status = st.text_input("Status inicial", value="Aberta", disabled=True)

        titulo = st.text_input("Título", placeholder="Ex.: Parafusos sem torque identificados...")
        descricao = st.text_area("Descrição", height=140)
        acoes = st.text_area("Ações imediatas", height=80)
        responsavel_acao = st.text_input("Responsável pela ação corretiva", placeholder="Nome do responsável pela ação")
        fotos = st.file_uploader("Fotos da abertura (JPG/PNG)", type=["jpg","jpeg","png"], accept_multiple_files=True)

        submitted = st.form_submit_button("Salvar RNC")
        if submitted:
            imgs = files_to_images(fotos)
            rec = {
                "data": datetime.combine(data_insp, datetime.min.time()),
                "area": area.strip(),
                "titulo": titulo.strip(),
                "responsavel": responsavel.strip(),
                "descricao": descricao.strip(),
                "severidade": severidade,
                "categoria": categoria,
                "acoes": acoes.strip(),
                "status": "Aberta",
                "responsavel_acao": responsavel_acao.strip(),
            }
            iid = insert_inspecao(rec, imgs)
            st.success(f"RNC salva! Código: #{iid} (status: Aberta)")

# -------- Consultar / Encerrar / Reabrir --------
elif menu == "Consultar/Encerrar/Reabrir":
    st.header("Consulta de RNCs")
    df = fetch_df()

    colf1, colf2, colf3, colf4 = st.columns(4)
    with colf1:
        f_status = st.multiselect("Status", ["Aberta","Em análise","Em ação","Bloqueada","Encerrada"])
    with colf2:
        f_sev = st.multiselect("Severidade", ["Baixa","Média","Alta","Crítica"])
    with colf3:
        f_area = st.text_input("Filtrar por Área/Local")
    with colf4:
        f_resp = st.text_input("Filtrar por Responsável")

    if not df.empty:
        if f_status: df = df[df["status"].isin(f_status)]
        if f_sev: df = df[df["severidade"].isin(f_sev)]
        if f_area: df = df[df["area"].str.contains(f_area, case=False, na=False)]
        if f_resp: df = df[df["responsavel"].str.contains(f_resp, case=False, na=False)]

        st.dataframe(df[["id","data","area","titulo","responsavel","responsavel_acao","severidade","categoria","status","encerrada_em","reaberta_em"]],
                     use_container_width=True, hide_index=True)

        st.markdown("---")
        if not df.empty:
            sel_id = st.number_input("Ver RNC (ID)", min_value=int(df["id"].min()), max_value=int(df["id"].max()), value=int(df["id"].iloc[0]), step=1)
            if sel_id in df["id"].values:
                row = df[df["id"] == sel_id].iloc[0].to_dict()
                st.subheader(f"RNC #{int(row['id'])} — {row['titulo']} [{row['status']}]")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Data", str(row["data"]))
                c2.metric("Severidade", row["severidade"])
                c3.metric("Status", row["status"])
                c4.metric("Encerrada em", str(row["encerrada_em"]) if row.get("encerrada_em") else "-")
                c5.metric("Reaberta em", str(row["reaberta_em"]) if row.get("reaberta_em") else "-")
                st.write(f"**Área/Local:** {row['area']}  \n**Responsável (inspeção):** {row['responsavel']}  \n**Responsável (ação corretiva):** {row.get('responsavel_acao') or '-'}  \n**Categoria:** {row['categoria']}")
                st.markdown("**Descrição**")
                st.write(row["descricao"] or "-")
                st.markdown("**Ações imediatas**")
                st.write(row["acoes"] or "-")

                tabs = st.tabs(["📸 Abertura", "✅ Encerramento", "♻️ Reabertura"])
                with tabs[0]:
                    for rec in fetch_photos(int(row["id"]), "abertura"):
                        show_image_from_blob(rec["blob"])
                with tabs[1]:
                    enc = fetch_photos(int(row["id"]), "encerramento")
                    if enc:
                        for rec in enc:
                            show_image_from_blob(rec["blob"])
                    else:
                        st.caption("Sem evidências de encerramento.")
                with tabs[2]:
                    rea = fetch_photos(int(row["id"]), "reabertura")
                    if rea:
                        for rec in rea:
                            show_image_from_blob(rec["blob"])
                    else:
                        st.caption("Sem registros de reabertura.")

                st.markdown("---")
                colA, colB = st.columns(2)
                with colA:
                    st.subheader("Encerrar RNC")
                    can_close = row["status"] != "Encerrada"
                    with st.form(f"encerrar_{sel_id}"):
                        encerr_por = st.text_input("Encerrada por", placeholder="Nome de quem encerra")
                        encerr_obs = st.text_area("Observações de encerramento", placeholder="O que foi feito? Ação definitiva?")
                        eficacia = st.selectbox("Verificação de eficácia", ["A verificar","Eficaz","Não eficaz"])
                        fotos_enc = st.file_uploader("Evidências (fotos)", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"enc_{sel_id}")
                        sub = st.form_submit_button("Encerrar RNC", disabled=not can_close)
                        if sub:
                            imgs = files_to_images(fotos_enc)
                            encerrar_inspecao(int(row["id"]), encerr_por.strip(), encerr_obs.strip(), eficacia, imgs)
                            st.success("RNC encerrada. Recarregue a visualização para ver o novo status.")

                with colB:
                    st.subheader("Reabrir RNC")
                    can_reopen = row["status"] == "Encerrada"
                    with st.form(f"reabrir_{sel_id}"):
                        reab_por = st.text_input("Reaberta por", placeholder="Nome de quem reabre")
                        reab_motivo = st.text_area("Motivo da reabertura", placeholder="Ex.: eficácia não comprovada")
                        fotos_reab = st.file_uploader("Fotos (opcional)", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"reab_{sel_id}")
                        sub2 = st.form_submit_button("Reabrir RNC", disabled=not can_reopen)
                        if sub2:
                            imgs = files_to_images(fotos_reab)
                            reabrir_inspecao(int(row["id"]), reab_por.strip(), reab_motivo.strip(), imgs)
                            st.success("RNC reaberta. Status voltou para 'Em ação'.")

# -------- Exportar --------
elif menu == "Exportar":
    st.header("Exportar dados (CSV)")
    df = fetch_df()
    if df.empty:
        st.info("Sem dados para exportar.")
    else:
       csv_bytes = df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button("Baixar CSV", data=csv_bytes, file_name="rnc_export_v2_2.csv", mime="text/csv")
        st.caption("As fotos não vão no CSV (ficam no banco).")
