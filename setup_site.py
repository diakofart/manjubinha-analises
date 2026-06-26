"""
Manjubinha Investidor - Configuracoes do site WordPress
Adiciona pagina de ranking ao menu de navegacao e CSS de espacamento no rodape.
Roda uma vez (idempotente): verifica antes de adicionar.
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


def get_page_id(slug):
    r = requests.get(WP_API + "/pages", headers=WP_HEADERS,
                     params={"slug": slug, "_fields": "id,link"})
    pages = r.json()
    if isinstance(pages, list) and pages:
        return pages[0]["id"]
    return None


def get_menus():
    r = requests.get(WP_API + "/menus", headers=WP_HEADERS,
                     params={"per_page": 100, "_fields": "id,name,slug"})
    if r.status_code == 200:
        return r.json()
    print("  menus: " + str(r.status_code) + " " + r.text[:200])
    return []


def get_menu_items(menu_id):
    r = requests.get(WP_API + "/menu-items", headers=WP_HEADERS,
                     params={"menus": menu_id, "per_page": 100})
    if r.status_code == 200:
        return r.json()
    return []


def add_menu_item(menu_id, page_id, title, order):
    payload = {
        "title":   title,
        "url":     RANKING_URL,
        "type":    "post_type",
        "type_label": "Pagina",
        "object":  "page",
        "object_id": page_id,
        "status":  "publish",
        "menus":   menu_id,
        "menu_order": order,
    }
    r = requests.post(WP_API + "/menu-items", headers=WP_HEADERS, json=payload)
    return r.status_code in (200, 201), r


def setup_menu():
    print("\n=== Menu de Navegacao ===")
    page_id = get_page_id(RANKING_SLUG)
    if not page_id:
        print("  ERRO: pagina " + RANKING_SLUG + " nao encontrada!")
        return

    print("  Pagina ID: " + str(page_id))
    menus = get_menus()
    if not menus:
        print("  Nenhum menu encontrado.")
        return

    for menu in menus:
        mid = menu["id"]
        mname = menu.get("name", "") + " (slug:" + menu.get("slug", "") + ")"
        print("  Menu: " + mname + " id=" + str(mid))

        items = get_menu_items(mid)
        already = any(
            it.get("object_id") == page_id or
            it.get("url", "").rstrip("/") == RANKING_URL.rstrip("/")
            for it in items
        )
        if already:
            print("    -> Ranking ja esta no menu!")
            continue

        order = len(items) + 1
        ok, resp = add_menu_item(mid, page_id, RANKING_TITLE, order)
        if ok:
            print("    -> Ranking adicionado (item id=" + str(resp.json().get("id")) + ")")
        else:
            print("    -> Erro ao adicionar: " + str(resp.status_code) + " " + resp.text[:200])


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
    setup_menu()
    setup_css()
    print("\nConcluido!")
