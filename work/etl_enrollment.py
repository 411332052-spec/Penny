# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "xlrd"]
# ///
"""把 114-1 在學人數統計表 (.xls) 轉成整齊的 CSV。

輸入：東華大學統計資料/在學人數統計表/114-1在學生人數統計表1141020--網路公告-10035人.xls
輸出：work/enrollment_114-1.csv

報表結構（第一個工作表）：
- 第 0~2 列是標題/欄名
- 第 3 列是全校總計（跳過）
- 「XX班 合計N」列是學制小計列，用來標記接下來的資料屬於哪個學制（博士班/碩士班/碩專班/學士班），本身不是資料
- 學院、系所欄並非真正的 Excel 合併儲存格（檔案裡沒有 merged cell），只是同一系所/學院時後面幾列留空，
  要往下補值（forward fill）。「系所個數」欄看起來像是可以用來判斷新系所邊界，但實測它在後半部分組
  （例如「社會工作組」）也會跳號，並不可靠，所以不採用，只用系所文字本身來補值
- 原始檔有一處資料錯置：「物理學系」的系所名稱打在它第二個分組（應用物理博士班國際組）那一列，
  它第一個分組（應用物理博士班一般組）那一列系所欄是空的，往下補值會誤算到前一個系所
  （材料科學與工程學系），這一列用分組文字獨立比對後單獨校正
- 同一系所、同一學制下可能有多個「分組」細項列，分組本身不需要保留，但數字要加總
- 「總計」欄位底下的女、男兩欄（第 5、6 欄）就是該列的實際人數
- 「備註：」開始是頁尾說明文字，要停止解析
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "東華大學統計資料" / "在學人數統計表" / "114-1在學生人數統計表1141020--網路公告-10035人.xls"
OUT = ROOT / "work" / "enrollment_114-1.csv"

PROGRAM_MAP = {"博士班": "博士班", "碩士班": "碩士班", "碩專班": "碩士在職專班", "學士班": "學士班"}
TOTAL_RE = re.compile(r"^(博士班|碩士班|碩專班|學士班)\s*合計")
strip_paren = lambda s: re.sub(r"[（(].*?[）)]", "", str(s)).strip()


def main():
    df = pd.read_excel(SRC, sheet_name=0, header=None)

    # 第一遍：篩出資料列，記錄學制、學院（forward fill）、系所原文（可能是 nan）、系所個數欄、男女人數
    rows = []
    current_program = None
    current_college = None
    started = False  # 在遇到第一個「XX班 合計」列之前，都是標題/總計列，跳過

    for row in df.itertuples(index=False, name=None):
        col0 = row[0]
        col0_str = "" if pd.isna(col0) else str(col0).strip()

        if col0_str.startswith("備註"):
            break
        m = TOTAL_RE.match(col0_str)
        if m:
            current_program = PROGRAM_MAP[m.group(1)]
            started = True
            continue
        if not started:
            continue

        if not pd.isna(row[1]):
            current_college = strip_paren(row[1])

        rows.append(
            {
                "college": current_college,
                "program": current_program,
                "dept_col": None if pd.isna(row[2]) else str(row[2]).strip(),
                "detail": None if pd.isna(row[3]) else str(row[3]).strip(),  # 分組文字，只用來比對特例
                "female": 0 if pd.isna(row[5]) else int(row[5]),
                "male": 0 if pd.isna(row[6]) else int(row[6]),
            }
        )

    # 第二遍：系所文字往下補值
    current_dept = None
    for r in rows:
        if r["dept_col"]:
            current_dept = r["dept_col"]
        r["dept"] = current_dept

    # 特例校正：見上方說明，這一列系所欄是空的，實際屬於物理學系而不是前一個系所
    for r in rows:
        if r["detail"] == "應用物理博士班一般組(106起)":
            r["dept"] = "物理學系"

    counts: dict[tuple[str, str, str], dict[str, int]] = {}
    for r in rows:
        key = (r["college"], r["dept"], r["program"])
        slot = counts.setdefault(key, {"女": 0, "男": 0})
        slot["女"] += r["female"]
        slot["男"] += r["male"]

    records = []
    for (college, dept_raw, program_raw), genders in counts.items():
        for gender in ("女", "男"):
            records.append(
                {
                    "college": college,
                    "dept_raw": dept_raw,
                    "program_raw": program_raw,
                    "gender": gender,
                    "count": genders[gender],
                }
            )

    out_df = pd.DataFrame(records, columns=["college", "dept_raw", "program_raw", "gender", "count"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"寫入 {OUT}，共 {len(out_df)} 列")


if __name__ == "__main__":
    main()
