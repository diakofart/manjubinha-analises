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

FOOTER_CSS = (
    "/* Manjubinha: espaco antes do rodape */\n"
    "main#wp--skip-link--target,\n"
    ".wp-site-blocks > main,\n"
    "main.wp-block-group {\n"
    "    padding-bottom: 60px !important;\n"
    "}\n"
)

RANKING_NAV_BLOCK = (
    "<!-- wp:navigation-link"
    ' {"label":"Ranking","type":"page","url":"' + WP_URL + "/" + RANKING_SLUG + '/",'
    '"kind":"post-type","isTopLevelLink":true} /-->'
)
MARKER = "/* Manjubinha: espaco antes do rodape */"


def setup_block_navigation():
    print("\n=== Block Navigation ===")
    r = requests.get(WP_API + "/navigation", headers=WP_HEADERS,
                     params={"per_page": 20, "context": "edit"})
    if r.status_code != 200:
        print("  navigation endpoint: " + str(r.status_code) + " " + r.text[:200])
        return

    navs = r.json()
    if not isinstance(navs, list):
        print("  navigation: unexpected: " + str(navs)[:100])
        return

    for nav in navs:
        nid = nav["id"]
        ntitle = (nav.get("title") or {}).get("rendered", "?")
        raw = (nav.get("content") or {}).get("raw", "") or ""
        print("  Nav " + str(nid) + ": " + str(ntitle) + " (" + str(len(raw)) + " chars)")
        if not raw:
            print("    -> sem raw")
            continue
        if RANKING_SLUG in raw or "Ranking" in raw:
            print("    -> ja tem Ranking")
            continue
        r2 = requests.post(WP_API + "/navigation/" + str(nid), headers=WP_HEADERS,
                           json={"content": raw.strip() + "\n" + RANKING_NAV_BLOCK})
        if r2.status_code in (200, 201):
            print("    -> adicionado!")
        else:
            print("    -> erro " + str(r2.status_code) + " " + r2.text[:150])


def setup_css():
    print("\n=== CSS via Global Styles ===")
    r = requests.get(WP_API + "/global-styles", headers=WP_HEADERS,
                     params={"per_page": 5, "context": "edit"})
    if r.status_code == 200:
        gs_list = r.json()
        for gs in (gs_list if isinstance(gs_list, list) else []):
            gs_id = gs.get("id")
            if not gs_id:
                continue
            current_css = (gs.get("styles") or {}).get("css", "") or ""
            print("  GS id=" + str(gs_id) + " css_len=" + str(len(current_css)))
            if MARKER in current_css:
                print("  CSS ja aplicado.")
                return
            new_css = current_css + "\n" + FOOTER_CSS
            r2 = requests.post(WP_API + "/global-styles/" + str(gs_id), headers=WP_HEADERS,
                               json={"styles": {"css": new_css}})
            if r2.status_code in (200, 201):
                print("  CSS adicionado via global-styles!")
                return
            else:
                print("  erro gs " + str(r2.status_code) + " " + r2.text[:150])
    else:
        print("  global-styles: " + str(r.status_code) + " " + r.text[:100])

    print("  Fallback: settings...")
    r3 = requests.get(WP_URL + "/wp-json/wp/v2/settings", headers=WP_HEADERS)
    if r3.status_code == 200:
        current = r3.json().get("custom_css", "") or ""
        if MARKER in current:
            print("  CSS ja em settings.")
            return
        r4 = requests.post(WP_URL + "/wp-json/wp/v2/settings", headers=WP_HEADERS,
                           json={"custom_css": current + "\n" + FOOTER_CSS})
        if r4.status_code in (200, 201):
            print("  CSS adicionado via settings!")
        else:
            print("  settings erro " + str(r4.status_code))
    else:
        print("  settings: " + str(r3.status_code))


if __name__ == "__main__":
    print("Manjubinha - Setup do site")
    setup_block_navigation()
    setup_css()
    print("\nConcluido!")
