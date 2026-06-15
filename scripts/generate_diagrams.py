"""Generate architecture diagrams for the enterprise RAG project."""

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

matplotlib.rcParams['font.sans-serif'] = ['Noto Sans SC', 'Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "images")
os.makedirs(OUTPUT_DIR, exist_ok=True)

COLORS = {
    "user": "#E3F2FD",
    "gateway": "#FFF3E0",
    "frontend": "#F3E5F5",
    "backend": "#E8F5E9",
    "worker": "#FFFDE7",
    "storage": "#E0F7FA",
    "monitor": "#FCE4EC",
    "arrow": "#546E7A",
    "text": "#263238",
    "border": "#37474F",
}


def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Generated {path}")


def draw_box(ax, x, y, w, h, text, color, fontsize=9, bold=False, border_color=None):
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        facecolor=color,
        edgecolor=border_color or COLORS["border"],
        linewidth=1.2,
    )
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=COLORS["text"],
        weight=weight,
        wrap=True,
    )
    return box


def draw_arrow(ax, x1, y1, x2, y2, label=None, color=None):
    color = color or COLORS["arrow"]
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="->", color=color, lw=1.5),
    )
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my + 0.15, label, ha="center", va="bottom", fontsize=7, color=color)


def draw_larrow(ax, points, label=None, color=None, label_offset=(0, 0.15)):
    """Draw a polyline arrow through a list of (x, y) points."""
    color = color or COLORS["arrow"]
    ax.plot([p[0] for p in points], [p[1] for p in points], color=color, lw=1.5)
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="->", color=color, lw=1.5),
    )
    if label:
        mx = sum(p[0] for p in points) / len(points)
        my = sum(p[1] for p in points) / len(points)
        ax.text(
            mx + label_offset[0],
            my + label_offset[1],
            label,
            ha="center",
            va="bottom",
            fontsize=7,
            color=color,
        )


def draw_group(ax, x, y, w, h, label, items, color, item_color, n_cols=2):
    rect = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.2",
        facecolor="white",
        edgecolor=color,
        linewidth=2,
        linestyle="--",
    )
    ax.add_patch(rect)
    ax.text(
        x,
        y + h / 2 - 0.25,
        label,
        ha="center",
        va="center",
        fontsize=10,
        weight="bold",
        color=COLORS["text"],
    )
    # Draw items
    n = len(items)
    rows = (n + n_cols - 1) // n_cols
    item_w = (w - 0.6) / n_cols
    item_h = (h - 0.7) / rows
    start_y = y + h / 2 - 0.55 - item_h / 2
    for i, item in enumerate(items):
        row = i // n_cols
        col = i % n_cols
        ix = x - w / 2 + 0.3 + item_w / 2 + col * item_w
        iy = start_y - row * item_h
        draw_box(ax, ix, iy, item_w - 0.1, item_h - 0.1, item, item_color, fontsize=8)


def gen_system_architecture():
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Enterprise Private RAG System Architecture", fontsize=16, weight="bold", pad=20)

    # Users
    draw_box(ax, 1.5, 9, 2, 0.8, "Web Users", COLORS["user"], bold=True)
    # Kong
    draw_box(ax, 4.5, 9, 2.2, 0.8, "Kong Gateway\n(rate-limiting)", COLORS["gateway"], bold=True)
    # Frontend
    draw_box(ax, 8, 9, 2.2, 0.8, "React Frontend\n(Ant Design)", COLORS["frontend"], bold=True)

    draw_arrow(ax, 2.5, 9, 3.4, 9)
    draw_arrow(ax, 5.6, 9, 6.9, 9)

    # Backend group
    backend_items = [
        "Auth Service",
        "Ingestion Pipeline",
        "Retrieval Engine",
        "Generation Service",
        "Permission Service",
        "Keyword Service",
        "Model Config",
        "Audit Log",
    ]
    draw_group(ax, 7, 6.8, 8, 2.2, "FastAPI Backend", backend_items, COLORS["backend"], "#C8E6C9", n_cols=4)

    # Workers group
    worker_items = ["ingest-worker", "embed-worker", "permission-sync-worker"]
    draw_group(ax, 3.5, 4.3, 4.5, 1.8, "Celery Workers", worker_items, COLORS["worker"], "#FFF59D", n_cols=1)

    # Storage group
    storage_items = ["PostgreSQL", "Redis", "RabbitMQ", "Milvus", "MinIO"]
    draw_group(ax, 9.5, 4.3, 5.5, 1.8, "Storage Layer", storage_items, COLORS["storage"], "#B2EBF2", n_cols=2)

    # Monitoring
    monitor_items = ["Prometheus", "Grafana"]
    draw_group(ax, 7, 1.8, 4, 1.4, "Monitoring", monitor_items, COLORS["monitor"], "#F8BBD0", n_cols=2)

    # Arrows
    # Frontend -> Backend (API calls)
    draw_arrow(ax, 8, 8.6, 7, 7.9, "API calls")

    # Kong -> Workers (enqueue tasks, avoid crossing Backend)
    draw_larrow(ax, [(4.5, 8.6), (4.5, 7.4), (3.5, 7.4), (3.5, 5.2)], label_offset=(0.5, 0.1))
    ax.text(4.0, 7.6, "enqueue", ha="center", va="bottom", fontsize=7, color=COLORS["arrow"])

    # Backend -> Storage
    draw_larrow(ax, [(7, 5.7), (7, 5.4), (9.5, 5.4), (9.5, 5.2)], label_offset=(0, 0.12))
    ax.text(8.2, 5.55, "read/write", ha="center", va="bottom", fontsize=7, color=COLORS["arrow"])

    # Workers -> Storage
    draw_larrow(ax, [(3.5, 3.4), (3.5, 3.1), (9.5, 3.1), (9.5, 3.4)], label_offset=(0, 0.12))
    ax.text(6.5, 2.95, "persist", ha="center", va="bottom", fontsize=7, color=COLORS["arrow"])

    # Backend -> Monitoring
    draw_larrow(ax, [(5.1, 5.7), (5.1, 2.5), (7, 2.5), (7, 2.3)], label_offset=(0, 0))
    ax.text(5.4, 4.1, "metrics", ha="center", va="bottom", fontsize=7, color=COLORS["arrow"])

    save(fig, "system_architecture.png")


def gen_rag_flow():
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("RAG Retrieval & Generation Flow", fontsize=16, weight="bold", pad=20)

    nodes = [
        (1.5, 3, "User\nQuery"),
        (3.5, 3, "Permission\nFilter"),
        (5.5, 3, "Keyword\nCheck"),
        (7.5, 4.2, "Vector\nRetrieval\n(Milvus)"),
        (7.5, 1.8, "Keyword\nFallback"),
        (9.8, 3, "Re-rank\n& Fusion"),
        (12, 3, "Context\nCompression"),
    ]
    for x, y, text in nodes:
        draw_box(ax, x, y, 1.5, 1.0, text, COLORS["backend"], fontsize=9, bold=True)

    draw_arrow(ax, 2.25, 3, 2.75, 3)
    draw_arrow(ax, 4.25, 3, 4.75, 3)
    draw_arrow(ax, 6.25, 3, 6.75, 3.8, "allowed")
    draw_arrow(ax, 6.25, 3, 6.75, 2.2, "blocked/\nkeyword")
    draw_arrow(ax, 8.25, 3.8, 9.05, 3.2)
    draw_arrow(ax, 8.25, 2.2, 9.05, 2.8)
    draw_arrow(ax, 10.55, 3, 11.25, 3)

    # Final answer box
    draw_box(ax, 12, 1.0, 1.5, 0.7, "LLM Answer\n(minimax-m3)", COLORS["frontend"], fontsize=8, bold=True)
    draw_arrow(ax, 12, 2.5, 12, 1.35)

    save(fig, "rag_retrieval_flow.png")


def gen_blue_green():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("Blue-Green Deployment Flow", fontsize=16, weight="bold", pad=20)

    steps = [
        (2, 5.8, "1. Detect\nInactive Color"),
        (4.5, 5.8, "2. Deploy New\nVersion"),
        (7, 5.8, "3. Health\nCheck"),
        (9.5, 5.8, "4. Switch\nTraffic"),
        (9.5, 3.5, "5. Stop Old\nVersion"),
    ]
    for x, y, text in steps:
        draw_box(ax, x, y, 1.6, 0.9, text, COLORS["frontend"], fontsize=9, bold=True)

    for i in range(len(steps) - 1):
        x1, y1, _ = steps[i]
        x2, y2, _ = steps[i + 1]
        draw_arrow(ax, x1 + 0.8, y1, x2 - 0.8, y2)

    # Blue / Green illustration
    draw_box(ax, 3, 2.2, 2.2, 1.0, "[BLUE] v1.0\nACTIVE", "#BBDEFB", fontsize=9, bold=True)
    draw_box(ax, 7, 2.2, 2.2, 1.0, "[GREEN] v1.1\nIDLE", "#C8E6C9", fontsize=9, bold=True)
    draw_arrow(ax, 5.3, 2.7, 6.7, 2.7, "deploy")
    ax.text(6, 1.3, "After switch: Green becomes ACTIVE, Blue stops", ha="center", fontsize=10, style="italic", color=COLORS["text"])

    save(fig, "blue_green_deployment.png")


def gen_permission_levels():
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("Five-Level Permission Model", fontsize=16, weight="bold", pad=20)

    levels = [
        ("L1 Public", "Everyone", "#C8E6C9"),
        ("L2 Internal", "All Employees", "#DCEDC8"),
        ("L3 Confidential", "Dept / Project", "#FFF9C4"),
        ("L4 Secret", "Senior / Core", "#FFE0B2"),
        ("L5 Top Secret", "Board Only", "#FFCDD2"),
    ]

    y = 6.0
    for label, desc, color in levels:
        draw_box(ax, 5, y, 3.5, 0.7, f"{label}\n{desc}", color, fontsize=10, bold=True)
        y -= 1.0

    # User vs Document matching
    draw_box(ax, 1.8, 3.5, 1.6, 1.0, "User\nClearance\nLevel", COLORS["user"], fontsize=9, bold=True)
    draw_box(ax, 8.2, 3.5, 1.6, 1.0, "Document\nSecurity\nLevel", COLORS["storage"], fontsize=9, bold=True)
    ax.annotate("", xy=(7.3, 3.8), xytext=(2.7, 3.8),
                arrowprops=dict(arrowstyle="<->", color=COLORS["arrow"], lw=2))
    ax.text(5, 6.7, "Access granted when User Level ≥ Document Level", ha="center", fontsize=10, weight="bold", color=COLORS["text"])

    save(fig, "permission_levels.png")


def gen_context_compression():
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("Permission-Aware Context Compression", fontsize=16, weight="bold", pad=20)

    steps = [
        (1.5, 2.5, "Raw\nContext"),
        (3.5, 2.5, "Chunk\nSplitting"),
        (5.5, 2.5, "Tag\nPermission\nInline"),
        (7.5, 2.5, "Group by\nLevel"),
        (9.5, 2.5, "Compress\nOutput"),
        (11.2, 2.5, "LLM"),
    ]
    colors = [COLORS["storage"], COLORS["backend"], COLORS["worker"], COLORS["frontend"], COLORS["gateway"], COLORS["user"]]
    for (x, y, text), color in zip(steps, colors):
        draw_box(ax, x, y, 1.3, 1.0, text, color, fontsize=9, bold=True)

    for i in range(len(steps) - 1):
        x1, y1, _ = steps[i]
        x2, y2, _ = steps[i + 1]
        draw_arrow(ax, x1 + 0.65, y1, x2 - 0.65, y2)

    ax.text(6, 1.0, "[L3] This chunk contains confidential sales data... → compressed with level tag",
            ha="center", fontsize=9, style="italic", color=COLORS["text"])

    save(fig, "context_compression.png")


def gen_ui_login():
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("Login Page Mockup", fontsize=14, weight="bold", pad=15)

    # Browser window
    ax.add_patch(FancyBboxPatch((0.5, 0.5), 6, 4, boxstyle="round,pad=0.02,rounding_size=0.1",
                                facecolor="#FAFAFA", edgecolor=COLORS["border"], linewidth=2))
    # Header bar
    ax.add_patch(FancyBboxPatch((0.5, 4.2), 6, 0.3, boxstyle="round,pad=0.02,rounding_size=0.05",
                                facecolor="#ECEFF1", edgecolor=COLORS["border"], linewidth=1))
    ax.text(3.5, 4.35, "Enterprise RAG", ha="center", va="center", fontsize=10, weight="bold", color=COLORS["text"])
    # Login card
    ax.add_patch(FancyBboxPatch((2, 2), 3, 1.8, boxstyle="round,pad=0.02,rounding_size=0.1",
                                facecolor="white", edgecolor=COLORS["border"], linewidth=1.5))
    ax.text(3.5, 3.5, "User Login", ha="center", va="center", fontsize=11, weight="bold", color=COLORS["text"])
    ax.add_patch(FancyBboxPatch((2.3, 2.9), 2.4, 0.35, facecolor="white", edgecolor="#B0BEC5", linewidth=1))
    ax.text(2.5, 3.08, "Username", ha="left", va="center", fontsize=8, color="#78909C")
    ax.add_patch(FancyBboxPatch((2.3, 2.35), 2.4, 0.35, facecolor="white", edgecolor="#B0BEC5", linewidth=1))
    ax.text(2.5, 2.52, "Password", ha="left", va="center", fontsize=8, color="#78909C")
    ax.add_patch(FancyBboxPatch((2.3, 1.75), 2.4, 0.35, boxstyle="round,pad=0.02,rounding_size=0.05",
                                facecolor="#1976D2", edgecolor=COLORS["border"], linewidth=1))
    ax.text(3.5, 1.92, "Sign In", ha="center", va="center", fontsize=9, weight="bold", color="white")

    save(fig, "ui_login.png")


def gen_ui_search():
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("Knowledge Search Console Mockup", fontsize=14, weight="bold", pad=15)

    # Window
    ax.add_patch(FancyBboxPatch((0.3, 0.3), 7.4, 4.4, boxstyle="round,pad=0.02,rounding_size=0.1",
                                facecolor="#FAFAFA", edgecolor=COLORS["border"], linewidth=2))
    # Sidebar
    ax.add_patch(FancyBboxPatch((0.3, 0.3), 1.5, 4.4, boxstyle="round,pad=0.02,rounding_size=0.05",
                                facecolor="#263238", edgecolor=COLORS["border"], linewidth=1))
    for i, label in enumerate(["Search", "Upload", "KB", "Admin"]):
        ax.text(1.05, 4.0 - i * 0.4, label, ha="center", va="center", fontsize=8, color="white")
    # Top search bar
    ax.add_patch(FancyBboxPatch((2.2, 4.0), 5.0, 0.4, boxstyle="round,pad=0.02,rounding_size=0.1",
                                facecolor="white", edgecolor="#B0BEC5", linewidth=1))
    ax.text(2.4, 4.2, "Search knowledge base...", ha="left", va="center", fontsize=8, color="#78909C")
    ax.add_patch(FancyBboxPatch((6.8, 4.0), 0.7, 0.4, boxstyle="round,pad=0.02,rounding_size=0.05",
                                facecolor="#1976D2", edgecolor=COLORS["border"], linewidth=1))
    ax.text(7.15, 4.2, "Go", ha="center", va="center", fontsize=8, weight="bold", color="white")
    # Result cards
    y = 3.3
    for i in range(3):
        ax.add_patch(FancyBboxPatch((2.2, y - i * 0.9), 5.3, 0.7, boxstyle="round,pad=0.02,rounding_size=0.05",
                                    facecolor="white", edgecolor="#CFD8DC", linewidth=1))
        ax.text(2.4, y + 0.35 - i * 0.9, f"Result {i+1}: Project RFC v{i+1}.0", ha="left", va="center",
                fontsize=9, weight="bold", color=COLORS["text"])
        ax.text(2.4, y + 0.05 - i * 0.9, "Relevant excerpt with highlighted answer...", ha="left", va="center",
                fontsize=7, color="#546E7A")
        ax.text(7.1, y + 0.35 - i * 0.9, "L2", ha="center", va="center", fontsize=7,
                color="white", bbox=dict(boxstyle="round,pad=0.2", facecolor="#43A047", edgecolor="none"))

    save(fig, "ui_search.png")


def gen_ui_model_config():
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("Model Configuration Page Mockup", fontsize=14, weight="bold", pad=15)

    # Window
    ax.add_patch(FancyBboxPatch((0.3, 0.3), 6.4, 4.4, boxstyle="round,pad=0.02,rounding_size=0.1",
                                facecolor="#FAFAFA", edgecolor=COLORS["border"], linewidth=2))
    ax.text(3.5, 4.5, "System Settings > Model Config", ha="center", va="center", fontsize=10, weight="bold", color=COLORS["text"])

    fields = [
        ("Embedding URL", "http://embedding-api:8080/embed"),
        ("Re-rank URL", "http://rerank-api:8080/rerank"),
        ("LLM URL", "http://llm-api:8080/v1/chat"),
        ("Top-K", "5"),
    ]
    y = 3.8
    for label, value in fields:
        ax.text(1.0, y, label, ha="left", va="center", fontsize=9, weight="bold", color=COLORS["text"])
        ax.add_patch(FancyBboxPatch((1.0, y - 0.35), 4.5, 0.35, boxstyle="round,pad=0.02,rounding_size=0.05",
                                    facecolor="white", edgecolor="#B0BEC5", linewidth=1))
        ax.text(1.15, y - 0.18, value, ha="left", va="center", fontsize=8, color="#37474F")
        y -= 0.75

    # Save button
    ax.add_patch(FancyBboxPatch((1.0, 1.0), 1.5, 0.4, boxstyle="round,pad=0.02,rounding_size=0.05",
                                facecolor="#1976D2", edgecolor=COLORS["border"], linewidth=1))
    ax.text(1.75, 1.2, "Save", ha="center", va="center", fontsize=9, weight="bold", color="white")

    save(fig, "ui_model_config.png")


if __name__ == "__main__":
    gen_system_architecture()
    gen_rag_flow()
    gen_blue_green()
    gen_permission_levels()
    gen_context_compression()
    gen_ui_login()
    gen_ui_search()
    gen_ui_model_config()
    print("All diagrams generated successfully.")
