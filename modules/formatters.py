import pandas as pd

def parse_valor_percentual(val) -> float:
    if pd.isna(val) or str(val).strip() == "":
        return 0.0
    if isinstance(val, str):
        s = val.strip().replace("%", "").replace(",", ".")
        if s == "":
            return 0.0
        try:
            num = float(s)
        except ValueError:
            return 0.0
        return (num / 100.0) if num > 1 else num
    try:
        f = float(val)
    except:
        return 0.0
    return (f / 100.0) if f > 1 else f

def formatar_percentual_para_planilha(val) -> str:
    if pd.isna(val):
        return ""
    try:
        if isinstance(val, str):
            s = val.replace(",", ".").strip()
            num = float(s) if s != "" else 0.0
        else:
            num = float(val)
    except:
        return str(val)
    if num > 100:
        num = num / 10
    if num.is_integer():
        return str(int(num))
    return f"{num:.1f}".replace(".", ",")

def formatar_para_exibir(val) -> str:
    if pd.isna(val):
        return ""
    if isinstance(val, str):
        s = val.strip()
        if "," in s:
            return s
        if "." in s:
            return s.replace(".", ",")
        if s.isdigit():
            num = float(s)
        else:
            return s
    else:
        num = float(val)
    if num > 100:
        num = num / 10
    if num.is_integer():
        return str(int(num))
    return f"{num:.1f}".replace(".", ",")
