"""
Manjubinha Investidor - Configuracoes do site WordPress
Adiciona pagina de ranking ao menu de navegacao (block navigation) e CSS de espacamento no rodape.
Roda toda execucao (idempotente): verifica antes de adicionar.
"""

import os, json, requests, base64

WP_URL = "https://manjubinhainvestidor.com.br"
WP_USER = os.environ["WP_USER"]
WP_PASS = os.environ["WP_APP_PASS"]

WP_API = WP_URL + "/wp-json/wp/v2"
_cred = base64.b64encode((WP_USER + ":" + WP_PASS).encode()).decode()
WP_HEADERS = {
    "Authorization": "Basic " + _cred,
    "Content-Type": "application/json",
}

RANKING_SLUG = "ranking-de-ativos"
RANKING_URL  = WP_URL + "/" + RANKING_SLUG + "/"
RANKING_TITLE = "Ranking"

FOOTER_CSS = """
/* Manjubinha: espaco antes do rodape */
.entry-content,
.wp-block-post-content,
article.post,
article.page,
.site-main > article {
    margin-bottom: 60px !important;
}
"""

RANKING_NAV_BLOCK = (
    "<!-- wp:navigation-link"
    ' {"label":"Ranking","type":"page","url":"' + WP_URL + "/" + RANKING_SLUG + '/",'
    '"kind":"post-type","isTopLevelLink":true} /-->'
)


def setup_block_navigation():
    print("\n=== Block Navigation ===")
    r = requests.get(WP_API + "/navigation", headers=WP_HEADERS,
                     params={"per_page": 20, "context": "edit"})
    if r.status_code != 200:
        print("  navigation endpoint: " + str(r.status_code) + " " + r.text[:200])
        return

    navs = r.json()
    if not isinstance(navs, list):
        print("  navigation: unexpected response: " + str(navs)[:200])
        return

    for nav in navs:
        nid = nav["id"]
        ntitle = nav.get("title", {}).get("rendered", "?") or nav.get("title", "?")
        raw = nav.get("content", {}).get("raw", "") or ""
        print("  Nav " + str(nid) + ": " + str(ntitle) + " (" + str(len(raw)) + " chars)")

        if not raw:
            print("    -> sem conteudo raw, pulando")
            continue

        if RANKING_SLUG in raw or "Ranking" in raw:
            print("    -> Ranking ja existe nessa nav, pulando")
            continue

        new_raw = raw.strip() + "\n" + RANKING_NAV_BLOCK
        r2 = requests.post(WP_API + "/navigation/" + str(nid), headers=WP_HEADERS,
                           json={"content": new_raw})
        if r2.status_code in (200, 201):
            print("    -> Ranking adicionado!")
        else:
            print("    -> Erro: " + str(r2.status_code) + " " + r2.text[:200])


def setup_css():
    print("\n=== Additional CSS (rodape) ===")
    r = requests.get(WP_URL + "/wp-json/wp/v2/settings", headers=WP_HEADERS)
    if r.status_code != 200:
        print("  settings endpoint: " + str(r.status_code))
        return

    settings = r.json()
    current_css = settings.get("custom_css", "") or ""
    marker = "/* Manjubinha: espaco antes do rodape */"

    if marker in current_css:
        print("  CSS de rodape ja aplicado.")
        return

    new_css = current_css + "\n" + FOOTER_CSS
    r2 = requests.post(WP_URL + "/wp-json/wp/v2/settings", headers=WP_HEADERS,
                       json={"custom_css": new_css})
    if r2.status_code in (200, 201):
        print("  CSS de rodape adicionado com sucesso!")
    else:
        print("  Erro ao salvar CSS: " + str(r2.status_code) + " " + r2.text[:300])


if __name__ == "__main__":
    print("Manjubinha - Setup do site")
    setup_block_navigation()
    setup_css()
    print("\nConcluido!")
