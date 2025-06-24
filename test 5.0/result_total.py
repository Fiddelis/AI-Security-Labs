import pandas as pd
from pathlib import Path

def main():
    # Lista de pastas de 4 a 10
    folders = list(range(0, 7))
    dfs = []

    for n in folders:
        path = Path(f"./{n}") / "result_table.csv"
        if path.exists():
            df = pd.read_csv(path, sep=";", decimal=",")
            # opcional: marca de qual pasta veio cada linha
            df["source_folder"] = n
            dfs.append(df)
        else:
            print(f"⚠️ Arquivo não encontrado em: {path}")

    if not dfs:
        print("❌ Nenhum CSV lido.")
        return

    # Concatena todos
    df_all = pd.concat(dfs, ignore_index=True, sort=False)

    # Salva num único CSV
    out_path = Path("all_result_tables_brute.csv")
    df_all.to_csv(out_path, index=False, sep=";", decimal=",")
    print(f"✅ Todos combinados em: {out_path}")

if __name__ == "__main__":
    main()