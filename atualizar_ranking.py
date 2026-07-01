# -*- coding: utf-8 -*-
"""
Atualiza o ranking.json do Manjubinha com dados reais de mercado.

Metodologia (sem notas subjetivas):
  CORTES DE ENTRADA
    FIIs : liquidez >= R$500k/dia | listado ha 5+ anos | DY 12m > 0 | P/VP entre 0,70 e 1,20
    Acoes: liquidez >= R$10M/dia  | listada ha 8+ anos | DY 12m > 0 | retorno total 5a > 0 | tag along >= 80%
  ORDENACAO
    Posicao em cada pilar (1 = melhor). Score = 2x pos_liquidez + pos_perenidade + pos_renda + pos_valorizacao.
    Menor score fica na frente. Empate: maior liquidez.
  PILARES (metricas)
    Liquidez    = volume medio diario (Fundamentus)
    Perenidade  = anos desde a listagem na B3 (Yahoo firstTradeDate)
    Renda       = Dividend Yield 12m (Fundamentus)
    Valorizacao = retorno TOTAL 24m (preco ajustado por proventos, Yahoo) -
                  usa retorno total para nao punir FIIs que distribuem 95% do lucro.

Fontes: fundamentus.com.br (liquidez, DY, P/VP), Yahoo Finance (historico ajustado,
data de listagem), investidor10.com.br (tag along das acoes).
"""

import json
import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# ---------------- Cortes de entrada ----------------
CORTE_FII_LIQUIDEZ = 500_000        # R$/dia
CORTE_FII_ANOS = 5
CORTE_FII_PVP_MIN = 0.70
CORTE_FII_PVP_MAX = 1.20
CORTE_ACAO_LIQUIDEZ = 10_000_000    # R$/dia
CORTE_ACAO_ANOS = 8
CORTE_ACAO_TAG_ALONG = 80           # %
PESO_LIQUIDEZ = 2                   # liquidez vale em dobro na soma de posicoes


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
    """Converte '1.234,56' ou '12,3%' em float."""
    txt = txt.strip().replace(".", "").replace("%", "").replace(",", ".")
    try:
        return float(txt)
    except Exception:
        return None


# ---------------- Fundamentus ----------------

def fundamentus_fiis():
    """Retorna {ticker: {dy, pvp, liquidez}} de todos os FIIs."""
    url = "https://www.fundamentus.com.br/fii_resultado.php"
    html = requests.get(url, headers=UA, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
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
        t = tds[0].upper()
        dados[t] = {
            "dy": _num(tds[idx.get("Dividend Yield", 4)]),
            "pvp": _num(tds[idx.get("P/VP", 5)]),
            "liquidez": _num(tds[idx.get("Liquidez", 7)]),
        }
    return dados


def fundamentus_acoes():
    """Retorna {ticker: {dy, pvp, liquidez}} de todas as acoes."""
    url = "https://www.fundamentus.com.br/resultado.php"
    html = requests.get(url, headers=UA, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
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
        t = tds[0].upper()
        dados[t] = {
            "dy": _num(tds[idx.get("Div.Yield", 5)]),
            "pvp": _num(tds[idx.get("P/VP", 3)]),
            "liquidez": _num(tds[idx.get("Liq.2meses", 16)]),
        }
    return dados


# ---------------- Yahoo Finance ----------------

def yahoo_historico(ticker):
    """Retorna (anos_listado, retorno_total_24m_pct, retorno_total_5a_pct)."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s.SA"
           "?range=10y&interval=1mo&events=div%%7Csplit" % ticker)
    try:
        r = requests.get(url, headers=UA, timeout=30)
        res = r.json()["chart"]["result"][0]
        meta = res["meta"]
        anos = None
        if meta.get("firstTradeDate"):
            first = datetime.utcfromtimestamp(meta["firstTradeDate"])
            anos = (datetime.utcnow() - first).days / 365.25
        adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or res["indicators"]["quote"][0].get("close")
        ts = res["timestamp"]
        pares = [(t, p) for t, p in zip(ts, adj) if p]
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


# ---------------- Investidor10 (tag along) ----------------

def tag_along_acao(ticker):
    """Extrai o tag along (%) da pagina do Investidor10. None se nao achou."""
    url = "https://investidor10.com.br/acoes/%s/" % ticker.lower()
    try:
        html = requests.get(url, headers=UA, timeout=30).text
        m = re.search(r"TAG\s*ALONG.{0,400}?([\d]{1,3})\s*%", html, re.IGNORECASE | re.DOTALL)
        if m:
            return int(m.group(1))
    except Exception as e:
        print("  [i10] falha em %s: %s" % (ticker, e))
    return None


# ---------------- Nucleo do ranking ----------------

def montar_lista(itens, tipo):
    """Coleta dados, aplica cortes e retorna (aprovados, reprovados)."""
    fund = fundamentus_fiis() if tipo == "fii" else fundamentus_acoes()
    aprovados, reprovados = [], []
    for item in itens:
        t = item["ticker"].upper()
        print("Coletando %s..." % t)
        f = fund.get(t, {})
        anos, ret24, ret60 = yahoo_historico(t)
        time.sleep(0.6)

        m = {
            "liquidez_diaria": f.get("liquidez"),
            "dy_12m": f.get("dy"),
            "p_vp": f.get("pvp"),
            "anos_listado": round(anos, 1) if anos else None,
            "retorno_total_24m": ret24,
        }
        motivos = []
        if tipo == "fii":
            if m["liquidez_diaria"] is None or m["liquidez_diaria"] < CORTE_FII_LIQUIDEZ:
                motivos.append("liquidez abaixo de R$500 mil/dia")
            if m["anos_listado"] is None or m["anos_listado"] < CORTE_FII_ANOS:
                motivos.append("menos de 5 anos de listagem")
            if not m["dy_12m"] or m["dy_12m"] <= 0:
                motivos.append("sem distribuicao nos ultimos 12m")
            if m["p_vp"] is None or not (CORTE_FII_PVP_MIN <= m["p_vp"] <= CORTE_FII_PVP_MAX):
                motivos.append("P/VP fora da faixa 0,70-1,20")
        else:
            m["retorno_total_5a"] = ret60
            m["tag_along"] = tag_along_acao(t)
            time.sleep(0.6)
            if m["liquidez_diaria"] is None or m["liquidez_diaria"] < CORTE_ACAO_LIQUIDEZ:
                motivos.append("liquidez abaixo de R$10 mi/dia")
            if m["anos_listado"] is None or m["anos_listado"] < CORTE_ACAO_ANOS:
                motivos.append("menos de 8 anos de listagem")
            if not m["dy_12m"] or m["dy_12m"] <= 0:
                motivos.append("sem dividendos nos ultimos 12m")
            if ret60 is None or ret60 <= 0:
                motivos.append("retorno total negativo em 5 anos")
            if m["tag_along"] is not None and m["tag_along"] < CORTE_ACAO_TAG_ALONG:
                motivos.append("tag along abaixo de 80%")
            if m["tag_along"] is None:
                m["tag_along_pendente"] = True  # nao exclui, sinaliza p/ conferencia

        novo = dict(item)
        for k in ("perene", "renda", "valorizacao", "liquidez", "nota", "motivo_exclusao", "posicoes", "score", "destaque"):
            novo.pop(k, None)
        novo["metricas"] = m
        if motivos:
            novo["motivo_exclusao"] = "; ".join(motivos)
            reprovados.append(novo)
        else:
            aprovados.append(novo)
    return aprovados, reprovados


def ordenar(aprovados):
    """Soma de posicoes por pilar; liquidez vale em dobro. Marca destaques."""
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
    fiis, fiis_fora = montar_lista(ranking.get("fiis", []) + ranking.get("reprovados", {}).get("fiis", []), "fii")
    acoes, acoes_fora = montar_lista(ranking.get("acoes", []) + ranking.get("reprovados", {}).get("acoes", []), "acao")

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
    print("FIIs aprovados: %d | reprovados: %d" % (len(fiis), len(fiis_fora)))
    for r in fiis_fora:
        print("  - %s: %s" % (r["ticker"], r["motivo_exclusao"]))
    print("Acoes aprovadas: %d | reprovadas: %d" % (len(acoes), len(acoes_fora)))
    for r in acoes_fora:
        print("  - %s: %s" % (r["ticker"], r["motivo_exclusao"]))
    pend = [a["ticker"] for a in acoes if a["metricas"].get("tag_along_pendente")]
    if pend:
        print("Tag along pendente de conferencia manual: %s" % ", ".join(pend))


if __name__ == "__main__":
    main()
