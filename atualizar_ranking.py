# -*- coding: utf-8 -*-
"""
Atualiza o ranking.json do Manjubinha com dados reais de mercado. v2

Metodologia (sem notas subjetivas):
  CORTES DE ENTRADA
    FIIs : liquidez >= R$500k/dia | listado ha 5+ anos | DY 12m > 0 | P/VP entre 0,70 e 1,20
    Acoes: liquidez >= R$10M/dia  | listada ha 8+ anos | DY 12m > 0 | retorno total 5a > 0 | tag along >= 80%
  ORDENACAO
    Posicao em cada pilar (1 = melhor). Score = 2x pos_liquidez + pos_perenidade + pos_renda + pos_valorizacao.
    Menor score fica na frente. Empate: maior liquidez.
  DADO INDISPONIVEL nao reprova: o ativo fica fora da lista desta rodada com motivo
    'dados indisponiveis', claramente separado de reprovacao real.

Fontes: fundamentus.com.br (liquidez, DY, P/VP), Yahoo Finance (historico ajustado,
data de listagem), statusinvest.com.br (tag along das acoes).
"""

import json
import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}

CORTE_FII_LIQUIDEZ = 500_000
CORTE_FII_ANOS = 5
CORTE_FII_PVP_MIN = 0.70
CORTE_FII_PVP_MAX = 1.20
CORTE_ACAO_LIQUIDEZ = 10_000_000
CORTE_ACAO_ANOS = 8
CORTE_ACAO_TAG_ALONG = 80
PESO_LIQUIDEZ = 2

# Preencher manualmente se a coleta automatica nao encontrar (ticker: %)
TAG_ALONG_MANUAL = {
    # Novo Mercado (regulamento B3 exige 100% para ON)
    "VALE3": 100, "BBAS3": 100, "WEGE3": 100, "PRIO3": 100, "SBSP3": 100,
    "RDOR3": 100, "B3SA3": 100, "SUZB3": 100, "CPFE3": 100, "TOTS3": 100,
    "EMBR3": 100, "RENT3": 100, "CSAN3": 100, "HAPV3": 100, "IRBR3": 100,
    "EGIE3": 100,
    # Nivel 2 (regulamento B3 exige 100% para ON e PN)
    "TAEE11": 100, "ALUP11": 100, "ENGI11": 100, "KLBN11": 100,
    "BPAC11": 100, "POMO4": 100,
    # Minimo legal ON (Lei 6.404) / estatuto documentado
    "ABEV3": 80, "VIVT3": 80, "ITUB4": 80, "BBDC4": 80,
    "RAIL3": 100,  # Novo Mercado
    "ITSA4": 80,   # estatuto documentado
    "PETR4": 100,  # Nivel 2, estatuto garante 100% as PN
    "CPLE3": 100,  # Novo Mercado (pos-migracao Copel)
}


def carregar(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def salvar(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _num(txt):
    txt = txt.strip().replace(".", "").replace("%", "").replace(",", ".")
    try:
        return float(txt)
    except Exception:
        return None


def _get(url, tentativas=3):
    """GET com retry e backoff."""
    for i in range(tentativas):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 200:
                return r
            print("  [http %s] %s" % (r.status_code, url))
        except Exception as e:
            print("  [http err] %s: %s" % (url, e))
        time.sleep(2 * (i + 1))
    return None


def _tabela_fundamentus(url, col_dy, col_pvp, col_liq):
    r = _get(url)
    if not r:
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    dados = {}
    tabela = soup.find("table")
    if not tabela:
        return dados
    headers = [th.get_text(strip=True) for th in tabela.find_all("th")]
    idx = {h: i for i, h in enumerate(headers)}
    for tr in tabela.find_all("tr")[1:]:
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not tds:
            continue
        dados[tds[0].upper()] = {
            "dy": _num(tds[idx.get(col_dy[0], col_dy[1])]),
            "pvp": _num(tds[idx.get(col_pvp[0], col_pvp[1])]),
            "liquidez": _num(tds[idx.get(col_liq[0], col_liq[1])]),
        }
    return dados


def fundamentus_fiis():
    return _tabela_fundamentus("https://www.fundamentus.com.br/fii_resultado.php",
                               ("Dividend Yield", 4), ("P/VP", 5), ("Liquidez", 7))


def fundamentus_acoes():
    return _tabela_fundamentus("https://www.fundamentus.com.br/resultado.php",
                               ("Div.Yield", 5), ("P/VP", 3), ("Liq.2meses", 16))


def yahoo_historico(ticker):
    """(anos_listado, retorno_total_24m, retorno_total_5a). Usa range=max + retry."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s.SA"
           "?range=max&interval=1mo&events=div%%7Csplit" % ticker)
    r = _get(url)
    if not r:
        return None, None, None
    try:
        res = r.json()["chart"]["result"][0]
        meta = res["meta"]
        ts = res.get("timestamp") or []
        adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or res["indicators"]["quote"][0].get("close") or []
        pares = [(t, p) for t, p in zip(ts, adj) if p]
        primeiro = meta.get("firstTradeDate") or (pares[0][0] if pares else None)
        anos = None
        if primeiro:
            anos = (datetime.utcnow() - datetime.utcfromtimestamp(primeiro)).days / 365.25
        if not pares:
            return anos, None, None
        agora = pares[-1][1]

        def retorno(meses):
            alvo = datetime.utcnow() - timedelta(days=30 * meses)
            base = None
            for t, p in pares:
                if datetime.utcfromtimestamp(t) >= alvo:
                    base = p
                    break
            if base is None or base == 0:
                return None
            return round((agora / base - 1) * 100, 1)

        return anos, retorno(24), retorno(60)
    except Exception as e:
        print("  [yahoo] falha em %s: %s" % (ticker, e))
        return None, None, None


def tag_along_acao(ticker):
    """Tag along (%) via StatusInvest, com validacao de sanidade (0-100)."""
    if ticker.upper() in TAG_ALONG_MANUAL:
        return TAG_ALONG_MANUAL[ticker.upper()]
    r = _get("https://statusinvest.com.br/acoes/%s" % ticker.lower())
    if not r:
        return None
    html = r.text
    i = html.upper().find("TAG ALONG")
    if i < 0:
        return None
    janela = html[i:i + 800]
    # valores em elementos tipo >100,00%<
    for m in re.finditer(r">\s*(\d{1,3})(?:[.,]\d{1,2})?\s*%", janela):
        v = int(m.group(1))
        if 0 <= v <= 100:
            return v
    return None


def montar_lista(itens, tipo):
    fund = fundamentus_fiis() if tipo == "fii" else fundamentus_acoes()
    aprovados, reprovados = [], []
    for item in itens:
        t = item["ticker"].upper()
        print("Coletando %s..." % t)
        f = fund.get(t, {})
        anos, ret24, ret60 = yahoo_historico(t)
        time.sleep(1.0)

        m = {
            "liquidez_diaria": f.get("liquidez"),
            "dy_12m": f.get("dy"),
            "p_vp": f.get("pvp"),
            "anos_listado": round(anos, 1) if anos else None,
            "retorno_total_24m": ret24,
        }
        motivos, faltando = [], []

        def corte(valor, cond_reprova, msg, nome_dado):
            if valor is None:
                faltando.append(nome_dado)
            elif cond_reprova(valor):
                motivos.append(msg)

        if tipo == "fii":
            corte(m["liquidez_diaria"], lambda v: v < CORTE_FII_LIQUIDEZ, "liquidez abaixo de R$500 mil/dia", "liquidez")
            corte(m["anos_listado"], lambda v: v < CORTE_FII_ANOS, "menos de 5 anos de listagem", "idade")
            corte(m["dy_12m"], lambda v: v <= 0, "sem distribuicao nos ultimos 12m", "DY")
            corte(m["p_vp"], lambda v: not (CORTE_FII_PVP_MIN <= v <= CORTE_FII_PVP_MAX), "P/VP fora da faixa 0,70-1,20", "P/VP")
        else:
            m["retorno_total_5a"] = ret60
            m["tag_along"] = tag_along_acao(t)
            time.sleep(1.0)
            corte(m["liquidez_diaria"], lambda v: v < CORTE_ACAO_LIQUIDEZ, "liquidez abaixo de R$10 mi/dia", "liquidez")
            corte(m["anos_listado"], lambda v: v < CORTE_ACAO_ANOS, "menos de 8 anos de listagem", "idade")
            corte(m["dy_12m"], lambda v: v <= 0, "sem dividendos nos ultimos 12m", "DY")
            corte(m["retorno_total_5a"], lambda v: v <= 0, "retorno total negativo em 5 anos", "retorno 5a")
            corte(m["tag_along"], lambda v: v < CORTE_ACAO_TAG_ALONG, "tag along abaixo de 80%", "tag along")

        novo = dict(item)
        for k in ("perene", "renda", "valorizacao", "liquidez", "nota", "motivo_exclusao", "posicoes", "score", "destaque", "metricas"):
            novo.pop(k, None)
        novo["metricas"] = m
        if motivos:
            novo["motivo_exclusao"] = "; ".join(motivos)
            reprovados.append(novo)
        elif faltando:
            novo["motivo_exclusao"] = "dados indisponiveis nesta coleta (nao e reprovacao): " + ", ".join(faltando)
            reprovados.append(novo)
        else:
            aprovados.append(novo)
    return aprovados, reprovados


def ordenar(aprovados):
    if not aprovados:
        return aprovados
    pilares = {
        "liquidez": lambda a: a["metricas"]["liquidez_diaria"] or 0,
        "perenidade": lambda a: a["metricas"]["anos_listado"] or 0,
        "renda": lambda a: a["metricas"]["dy_12m"] or 0,
        "valorizacao": lambda a: a["metricas"]["retorno_total_24m"] if a["metricas"]["retorno_total_24m"] is not None else -999,
    }
    rotulos = {
        "liquidez": "Maior liquidez da lista",
        "perenidade": "Mais antigo da lista",
        "renda": "Maior renda da lista",
        "valorizacao": "Maior valorizacao da lista",
    }
    for nome, chave in pilares.items():
        ordem = sorted(aprovados, key=chave, reverse=True)
        for pos, a in enumerate(ordem, 1):
            a.setdefault("posicoes", {})[nome] = pos
    for a in aprovados:
        p = a["posicoes"]
        a["score"] = PESO_LIQUIDEZ * p["liquidez"] + p["perenidade"] + p["renda"] + p["valorizacao"]
        destaques = [rotulos[k] for k, v in a["posicoes"].items() if v == 1]
        if destaques:
            a["destaque"] = destaques[0]
    aprovados.sort(key=lambda a: (a["score"], a["posicoes"]["liquidez"]))
    return aprovados


def main():
    ranking = carregar("ranking.json", {})
    fiis_all = ranking.get("fiis", []) + ranking.get("reprovados", {}).get("fiis", [])
    acoes_all = ranking.get("acoes", []) + ranking.get("reprovados", {}).get("acoes", [])
    fiis, fiis_fora = montar_lista(fiis_all, "fii")
    acoes, acoes_fora = montar_lista(acoes_all, "acao")

    novo = {
        "ultima_atualizacao": datetime.today().strftime("%Y-%m-%d"),
        "proxima_atualizacao": ranking.get("proxima_atualizacao", ""),
        "metodologia": {
            "ordenacao": "Soma das posicoes nos 4 pilares (liquidez com peso 2). Menor soma = melhor colocado.",
            "pilares": "Liquidez (vol. medio diario), Perenidade (anos de B3), Renda (DY 12m), Valorizacao (retorno total 24m, ajustado por proventos).",
            "cortes_fiis": "Liquidez >= R$500 mil/dia; 5+ anos de listagem; DY 12m > 0; P/VP entre 0,70 e 1,20.",
            "cortes_acoes": "Liquidez >= R$10 mi/dia; 8+ anos de listagem; DY 12m > 0; retorno total positivo em 5 anos; tag along >= 80%.",
        },
        "fiis": ordenar(fiis),
        "acoes": ordenar(acoes),
        "reprovados": {"fiis": fiis_fora, "acoes": acoes_fora},
    }
    salvar("ranking.json", novo)

    print("\n===== RESUMO =====")
    print("FIIs aprovados: %d | fora: %d" % (len(fiis), len(fiis_fora)))
    for r in fiis_fora:
        print("  - %s: %s" % (r["ticker"], r["motivo_exclusao"]))
    print("Acoes aprovadas: %d | fora: %d" % (len(acoes), len(acoes_fora)))
    for r in acoes_fora:
        print("  - %s: %s" % (r["ticker"], r["motivo_exclusao"]))


if __name__ == "__main__":
    main()
