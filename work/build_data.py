# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""把 data/ 裡的 3 個標準 CSV 整理成 docs/data.js，給 BI 網頁直接用 <script> 載入
（純本機雙擊開啟 index.html 時，瀏覽器不允許用 fetch 讀本機檔案，所以不能用 fetch(data.csv)，
改成把資料包成一個 JS 變數，用 <script src="data.js"> 載入就沒有這個限制）。

只保留網頁會用到的欄位，並先依這些欄位加總，讓檔案變小：
- 在學人數：學期、學院、系所、學位別、性別 -> 人數
- 休學人數：學期、學院、系所、學位別、性別、休學原因 -> 學期間休學人數、學期底休學狀態人數
- 系所對照表：只留有舊名稱（aliases）的系所，給網頁做「系所曾用名」查詢/顯示用

為了讓檔案小一點，每筆資料用陣列（不是物件）存，欄位名另外存一次在 *_cols。
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data.js"


def build_enrollment():
    df = pd.read_csv(DATA / "enrollment.csv", encoding="utf-8-sig")
    g = df.groupby(["semester", "college", "dept", "degree", "gender"], as_index=False)["count"].sum()
    g = g.sort_values(["semester", "college", "dept", "degree", "gender"])
    cols = ["semester", "college", "dept", "degree", "gender", "count"]
    rows = g[cols].values.tolist()
    return cols, rows, df


def build_leave():
    df = pd.read_csv(DATA / "leave.csv", encoding="utf-8-sig")
    g = df.groupby(
        ["semester", "college", "dept", "degree", "gender", "reason"], as_index=False
    )[["new_leave", "on_leave_end"]].sum()
    g = g.sort_values(["semester", "college", "dept", "degree", "gender", "reason"])
    cols = ["semester", "college", "dept", "degree", "gender", "reason", "new_leave", "on_leave_end"]
    rows = g[cols].values.tolist()
    return cols, rows


def build_dept_aliases():
    df = pd.read_csv(DATA / "dept_mapping.csv", encoding="utf-8-sig")
    aliases = {}
    for _, row in df.iterrows():
        names = [a.strip() for a in str(row["aliases"]).split(";") if a.strip()]
        if names:
            aliases[row["dept"]] = names
    return aliases


def main():
    enrollment_cols, enrollment_rows, enrollment_df = build_enrollment()
    leave_cols, leave_rows = build_leave()
    dept_aliases = build_dept_aliases()

    # 核對：114-1 在學人數合計應該是 10035 人
    total_1141 = int(enrollment_df.loc[enrollment_df.semester == "114-1", "count"].sum())
    assert total_1141 == 10035, f"114-1 在學人數合計應為 10035，實際為 {total_1141}"
    print(f"✅ 114-1 在學人數合計核對通過：{total_1141} 人")

    payload = {
        "enrollmentCols": enrollment_cols,
        "enrollment": enrollment_rows,
        "leaveCols": leave_cols,
        "leave": leave_rows,
        "deptAliases": dept_aliases,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = "window.BI_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    OUT.write_text(js, encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"寫入 {OUT}")
    print(f"在學人數：{len(enrollment_rows)} 列，休學人數：{len(leave_rows)} 列，系所舊名稱：{len(dept_aliases)} 個系所")
    print(f"檔案大小：{size_kb:.1f} KB")


if __name__ == "__main__":
    main()
