"""Publication-ready charts for the NBA salary/performance analysis."""

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

OUTPUT_DIR = Path(__file__).parent / "output"

sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["font.size"] = 10


def plot_salary_vs_performance(df, out_dir: Path = OUTPUT_DIR):
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(
        data=df, x="SALARY", y="EFF", size="PTS", sizes=(30, 220),
        alpha=0.7, color=sns.color_palette("deep")[0], ax=ax, legend="brief",
    )
    ax.set_xlabel("Salary ($)")
    ax.set_ylabel("Efficiency (EFF, per game)")
    ax.set_title("Salary vs. On-Court Performance")
    ax.xaxis.set_major_formatter(lambda x, _: f"${x/1e6:.0f}M")
    ax.legend(title="PTS/game", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    path = out_dir / "salary_vs_performance.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_correlation_heatmap(corr_df, out_dir: Path = OUTPUT_DIR):
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(
        corr_df, annot=True, fmt=".2f", cmap="coolwarm", center=0,
        square=True, linewidths=0.5, ax=ax, cbar_kws={"shrink": 0.8},
    )
    ax.set_title("Correlation Matrix: Salary & Performance Metrics")
    fig.tight_layout()
    path = out_dir / "correlation_heatmap.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_top_value_players(value_df, out_dir: Path = OUTPUT_DIR):
    fig, ax = plt.subplots(figsize=(9, 7))
    data = value_df.sort_values("VALUE_INDEX")
    bars = ax.barh(data["PLAYER"], data["VALUE_INDEX"], color=sns.color_palette("deep")[2])
    ax.set_xlabel("Value Index (EFF per $1M salary)")
    ax.set_title("Most Undervalued Players")
    ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=8)
    fig.tight_layout()
    path = out_dir / "top_value_players.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_team_breakdown(team_df, out_dir: Path = OUTPUT_DIR):
    """Average salary and Value Index per team (real TEAM field, since the source
    game log has no position data to break down by)."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 9))

    by_salary = team_df.sort_values("avg_salary", ascending=False)
    axes[0].bar(by_salary.index, by_salary["avg_salary"] / 1e6, color=sns.color_palette("deep")[0])
    axes[0].set_ylabel("Avg. Salary ($M)")
    axes[0].set_title("Average Salary by Team")
    axes[0].tick_params(axis="x", rotation=90, labelsize=8)

    by_value = team_df.sort_values("avg_value_index", ascending=False)
    axes[1].bar(by_value.index, by_value["avg_value_index"], color=sns.color_palette("deep")[3])
    axes[1].set_ylabel("Avg. Value Index")
    axes[1].set_title("Average Value Index by Team")
    axes[1].tick_params(axis="x", rotation=90, labelsize=8)

    fig.suptitle("Team-Level Salary & Value Disparities")
    fig.tight_layout()
    path = out_dir / "team_breakdown.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def generate_all_charts(df, corr_df, value_df, team_df, out_dir: Path = OUTPUT_DIR):
    out_dir.mkdir(exist_ok=True)
    paths = [
        plot_salary_vs_performance(df, out_dir),
        plot_correlation_heatmap(corr_df, out_dir),
        plot_top_value_players(value_df, out_dir),
        plot_team_breakdown(team_df, out_dir),
    ]
    return paths
