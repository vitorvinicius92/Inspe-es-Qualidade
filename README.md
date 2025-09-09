
# RNC App v2.2 — Streamlit Cloud (Grátis)
**Sem pagar nada**: usa **SQLite** local e guarda **fotos dentro do banco** (BLOB).

## Como publicar no Streamlit Cloud
1. Envie estes arquivos para um repositório no GitHub.
2. Acesse https://streamlit.io/cloud e clique em **Deploy an app**.
3. Conecte ao seu repositório e selecione **app.py** como arquivo principal.
4. Aguarde a URL pública ser gerada (ex.: `https://seuapp.streamlit.app`).

## Recursos
- Abertura de RNC (status inicial **Aberta**).
- Encerramento com observações, eficácia e **fotos de encerramento**.
- **Reabertura** com motivo e fotos (status volta para **Em ação**).
- Filtros de consulta + exportação **CSV**.
- **Fotos salvas no banco** (sem precisar de disco pago).

> Observação: Em ambientes gratuitos, o armazenamento pode ser reiniciado em atualizações/redeploy. Para produção, considere banco gerenciado (Postgres) e storage externo (S3/GCS).
