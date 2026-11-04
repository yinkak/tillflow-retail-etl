"""Plot monthly product revenue from the gold mart -> docs/img/monthly-revenue.png."""

import matplotlib.pyplot as plt
import pandas as pd

from tillflow_retail_etl.config import get_settings
from tillflow_retail_etl.load import connect

OUTPUT = "docs/img/monthly-revenue.png"


def main() -> None:
    with connect(get_settings()) as conn:
        rows = conn.execute(
            "SELECT month, revenue, is_partial_month FROM marts.monthly_revenue ORDER BY month"
        ).fetchall()
    df = pd.DataFrame(rows, columns=["month", "revenue", "is_partial_month"])
    df["revenue"] = df["revenue"].astype(float) / 1_000_000

    colors = ["#b0b0b0" if partial else "#2b6cb0" for partial in df["is_partial_month"]]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(df["month"], df["revenue"], width=20, color=colors)
    ax.set_ylabel("Revenue ($M)")
    ax.set_title("Monthly product revenue, Dec 2009 – Dec 2011 (grey = partial month)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUT, dpi=150)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
