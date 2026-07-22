"""Limpeza e engenharia de atributos dos datasets brutos baixados por fetch.py.

Schema já vem bem mais limpo que o CSV do Projeto 2 (sem corrupção por quebra de
linha, sem colunas duplicadas) — aqui só tratamos tipos (datas, números em
formato BR) e derivamos algumas colunas usadas nos gráficos.
"""

from pathlib import Path

import numpy as np
import pandas as pd

DADOS_DIR = Path(__file__).resolve().parent.parent / "dados"


def to_num(serie: pd.Series) -> pd.Series:
    """'1.234,56' -> 1234.56 (mesma função usada em analise.ipynb)."""
    return pd.to_numeric(
        serie.astype(str).str.strip().replace({"": np.nan, "nan": np.nan})
        .str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )


# O formato de data_empenho mudou ao longo dos anos na fonte (TCE-PB trocou de
# exportador do sistema contábil mais de uma vez): 2003-2019 vem em datetime ISO
# com frações de segundo, 2020-2025 em data ISO simples, 2026 em dd/mm/yyyy.
DATA_EMPENHO_FORMATOS = ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d", "%d/%m/%Y"]


def parse_data_multi_formato(serie: pd.Series, formatos: list[str]) -> pd.Series:
    resultado = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")
    pendente = serie.notna()
    for fmt in formatos:
        if not pendente.any():
            break
        parsed = pd.to_datetime(serie[pendente], format=fmt, errors="coerce")
        resultado.loc[parsed.dropna().index] = parsed.dropna()
        pendente = resultado.isna() & serie.notna()
    return resultado


def transformar_despesas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["data_empenho"] = parse_data_multi_formato(df["data_empenho"], DATA_EMPENHO_FORMATOS)
    df["ano"] = df["data_empenho"].dt.year
    df["mes_num"] = df["data_empenho"].dt.month
    for c in ["valor_empenhado", "valor_liquidado", "valor_pago"]:
        df[c] = to_num(df[c])
    df["execucao_pct"] = np.where(
        df["valor_empenhado"] > 0, df["valor_pago"] / df["valor_empenhado"] * 100, np.nan
    )
    df["sem_licitacao"] = df["modalidade_licitacao"].fillna("").str.contains(
        "sem licita", case=False
    )
    return df


def transformar_receitas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
    df["mes_num"] = df["mes_ano"].astype(str).str.slice(0, 2).astype("Int64")
    df["valor"] = to_num(df["valor"])
    return df


def transformar_licitacoes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["data_homologacao"] = pd.to_datetime(df["data_homologacao"], format="%d/%m/%Y", errors="coerce")
    df["ano_licitacao"] = pd.to_numeric(df["ano_licitacao"], errors="coerce").astype("Int64")
    df["valor_ofertado"] = to_num(df["valor_ofertado"])
    return df


TRANSFORMS = {
    "despesas": transformar_despesas,
    "receitas": transformar_receitas,
    "licitacoes": transformar_licitacoes,
}


def main() -> None:
    for dataset, fn in TRANSFORMS.items():
        bruto = pd.read_parquet(DADOS_DIR / f"{dataset}_raw.parquet")
        limpo = fn(bruto)
        limpo.to_parquet(DADOS_DIR / f"{dataset}.parquet", index=False)
        print(f"{dataset}: {len(limpo):,} linhas processadas".replace(",", "."))


if __name__ == "__main__":
    main()
