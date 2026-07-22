"""Baixa os datasets abertos do TCE-PB (SAGRES) para o município de Teixeira/PB.

Fonte: https://dados-abertos.tce.pb.gov.br/ — download direto, sem autenticação,
em https://download.tce.pb.gov.br/dados-abertos/dados-por-municipio/{municipio}/{dataset}/{dataset}-{ano}.zip

Anos passados são imutáveis: na primeira execução baixa o histórico completo de
cada dataset; nas execuções seguintes baixa só o ano corrente e faz upsert no
parquet existente.
"""

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

MUNICIPIO = "215"  # Teixeira/PB
DATASETS = {
    "despesas": 2003,
    "receitas": 2003,
    "licitacoes": 2015,
}
BASE_URL = "https://download.tce.pb.gov.br/dados-abertos/dados-por-municipio/{municipio}/{dataset}/{dataset}-{ano}.zip"

DADOS_DIR = Path(__file__).resolve().parent.parent / "dados"
TIMEOUT = 60


def baixar_ano(dataset: str, ano: int) -> pd.DataFrame | None:
    url = BASE_URL.format(municipio=MUNICIPIO, dataset=dataset, ano=ano)
    resp = requests.get(url, timeout=TIMEOUT)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        nome_csv = zf.namelist()[0]
        with zf.open(nome_csv) as f:
            df = pd.read_csv(f, sep=";", encoding="utf-8-sig", dtype=str, low_memory=False)
    # Tag explícita do ano do arquivo baixado: o schema de "despesas" não traz uma
    # coluna de ano própria (só "data_empenho"), então usamos isso — e não uma
    # coluna de dados — para saber quais linhas substituir num upsert.
    df["_ano_arquivo"] = ano
    return df


def atualizar_dataset(dataset: str, ano_inicio: int, ano_atual: int) -> int:
    caminho = DADOS_DIR / f"{dataset}_raw.parquet"

    if caminho.exists():
        historico = pd.read_parquet(caminho)
        historico = historico[historico["_ano_arquivo"] != ano_atual]
        anos_a_baixar = [ano_atual]
    else:
        historico = None
        anos_a_baixar = list(range(ano_inicio, ano_atual + 1))

    partes = []
    for ano in anos_a_baixar:
        df_ano = baixar_ano(dataset, ano)
        if df_ano is not None:
            partes.append(df_ano)

    if not partes and historico is None:
        raise RuntimeError(f"Nenhum dado encontrado para o dataset '{dataset}'")

    novo = pd.concat(partes, ignore_index=True) if partes else None
    if historico is not None and novo is not None:
        final = pd.concat([historico, novo], ignore_index=True)
    elif novo is not None:
        final = novo
    else:
        final = historico

    DADOS_DIR.mkdir(exist_ok=True)
    final.to_parquet(caminho, index=False)
    return len(final)


def main() -> None:
    ano_atual = datetime.now().year
    contagens = {}
    for dataset, ano_inicio in DATASETS.items():
        contagens[dataset] = atualizar_dataset(dataset, ano_inicio, ano_atual)
        print(f"{dataset}: {contagens[dataset]:,} linhas".replace(",", "."))

    metadata = {
        "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": contagens,
    }
    DADOS_DIR.mkdir(exist_ok=True)
    (DADOS_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"metadata.json atualizado: {metadata['last_updated']}")


if __name__ == "__main__":
    main()
