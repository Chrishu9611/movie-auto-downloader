import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import os
import threading
import time
import sys
import io
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cnmkv import CNmkvCrawler
from src.hdzu import HdzuCrawler
from src.deduplicator import Deduplicator
from src.excel_exporter import export_to_excel
from src.crawler import BaseCrawler
import config

# Lazy import Pillow
try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False

# Apple-style color palette
BG_COLOR = "#F5F5F7"
CARD_BG = "#FFFFFF"
PRIMARY = "#007AFF"
TEXT = "#1D1D1F"
TEXT_SECONDARY = "#86868B"
BORDER = "#D2D2D7"
HOVER_BG = "#E8E8ED"
SELECTED_BG = "#007AFF"
SELECTED_TEXT = "#FFFFFF"
DANGER = "#FF3B30"


class CheckboxIcons:
    def __init__(self, master):
        self.master = master
        self._unchecked = None
        self._checked = None
        self._build()

    def _build(self):
        if not HAS_PIL:
            return
        size = 18
        # Unchecked: rounded gray border
        img_u = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw_u = ImageDraw.Draw(img_u)
        if hasattr(draw_u, "rounded_rectangle"):
            draw_u.rounded_rectangle([1, 1, size - 1, size - 1], radius=4, outline="#C7C7CC", width=2)
        else:
            draw_u.rectangle([1, 1, size - 1, size - 1], outline="#C7C7CC", width=2)
        self._unchecked = ImageTk.PhotoImage(img_u, master=self.master)

        # Checked: blue fill with white checkmark
        img_c = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw_c = ImageDraw.Draw(img_c)
        if hasattr(draw_c, "rounded_rectangle"):
            draw_c.rounded_rectangle([0, 0, size - 1, size - 1], radius=4, fill=PRIMARY)
        else:
            draw_c.rectangle([0, 0, size - 1, size - 1], fill=PRIMARY)
        # Checkmark
        draw_c.line([(4, size // 2 + 1), (8, size - 4), (size - 4, 4)], fill="white", width=2)
        self._checked = ImageTk.PhotoImage(img_c, master=self.master)

    @property
    def unchecked(self):
        return self._unchecked

    @property
    def checked(self):
        return self._checked


class MovieTooltip:
    def __init__(self, master):
        self.master = master
        self.tip = None
        self.label_img = None
        self.label_text = None
        self._pending = None
        self._photo = None

    def show(self, movie, x, y):
        self.hide()
        self.tip = tk.Toplevel(self.master)
        self.tip.overrideredirect(True)
        self.tip.configure(
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self.tip.attributes("-topmost", True)

        # Image placeholder
        self.label_img = tk.Label(self.tip, bg=CARD_BG, text="加载中...", fg=TEXT_SECONDARY)
        self.label_img.pack(padx=12, pady=(12, 6))

        # Text
        desc = movie.get("description", "暂无简介")
        self.label_text = tk.Label(
            self.tip, bg=CARD_BG, fg=TEXT, font=("Microsoft YaHei", 10),
            text=desc, wraplength=280, justify="left", anchor="nw"
        )
        self.label_text.pack(padx=12, pady=(0, 12))

        # Position
        self._position(x, y)

        # Async load cover
        cover_url = movie.get("cover_url", "")
        if cover_url and HAS_PIL:
            self._pending = cover_url
            threading.Thread(target=self._load_image, args=(cover_url,), daemon=True).start()

    def _load_image(self, url):
        try:
            # Reuse crawler session for image fetch
            session = BaseCrawler("tmp", "").session
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            # Resize to max 200px width
            w, h = img.size
            if w > 200:
                ratio = 200 / w
                w, h = 200, int(h * ratio)
                img = img.resize((w, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img, master=self.master)
            self.master.after(0, lambda: self._set_image(photo, w, h))
        except Exception:
            self.master.after(0, lambda: self._set_image(None, 0, 0))

    def _set_image(self, photo, w, h):
        if self.tip is None or not self.tip.winfo_exists():
            return
        self._photo = photo
        if photo:
            self.label_img.config(image=photo, text="", width=w, height=h)
        else:
            self.label_img.config(text="无法加载封面", fg=TEXT_SECONDARY)

    def _position(self, x, y):
        if self.tip is None:
            return
        # Offset slightly right and down from cursor
        tip_x = x + 20
        tip_y = y + 20
        # Keep inside screen
        sw = self.master.winfo_screenwidth()
        sh = self.master.winfo_screenheight()
        self.tip.update_idletasks()
        tw = self.tip.winfo_width()
        th = self.tip.winfo_height()
        if tip_x + tw > sw:
            tip_x = x - tw - 10
        if tip_y + th > sh:
            tip_y = y - th - 10
        self.tip.geometry(f"+{tip_x}+{tip_y}")

    def hide(self):
        if self.tip and self.tip.winfo_exists():
            self.tip.destroy()
        self.tip = None
        self._photo = None
        self._pending = None


class MovieDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("电影自动下载器")
        self.root.geometry("1280x800")
        self.root.minsize(1000, 600)
        self.root.configure(bg=BG_COLOR)

        self.dedup = Deduplicator()
        self.movies = []
        self.filtered_movies = []
        self.checked_ids = set()
        self.tooltip = MovieTooltip(self.root)
        self._hover_job = None
        self._last_hover_iid = None

        self.icons = CheckboxIcons(self.root)
        self._create_ui()
        self.load_data()

    def _create_ui(self):
        # Configure ttk style for flat look
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview",
                        background=CARD_BG,
                        foreground=TEXT,
                        fieldbackground=CARD_BG,
                        rowheight=32,
                        borderwidth=0,
                        font=("Microsoft YaHei", 10))
        style.configure("Treeview.Heading",
                        background=CARD_BG,
                        foreground=TEXT_SECONDARY,
                        font=("Microsoft YaHei", 10, "bold"),
                        borderwidth=0,
                        relief="flat")
        style.map("Treeview",
                  background=[("selected", SELECTED_BG)],
                  foreground=[("selected", SELECTED_TEXT)])
        style.layout("Treeview.Heading", [
            ("Treeheading.cell", {"sticky": "nswe"}),
            ("Treeheading.border", {"sticky": "nswe", "children": [
                ("Treeheading.padding", {"sticky": "nswe", "children": [
                    ("Treeheading.image", {"side": "right", "sticky": ""}),
                    ("Treeheading.text", {"sticky": "we"})
                ]})
            ]})
        ])

        # Top toolbar card
        toolbar = tk.Frame(self.root, bg=CARD_BG, padx=16, pady=12)
        toolbar.pack(fill=tk.X, padx=16, pady=(16, 0))

        # Title
        tk.Label(toolbar, text="电影自动下载器", bg=CARD_BG, fg=TEXT,
                 font=("Microsoft YaHei", 16, "bold")).pack(side=tk.LEFT)

        # Buttons
        btn_pad = {"padx": 8, "pady": 6}
        tk.Button(toolbar, text="立即爬取", command=self.on_crawl,
                  bg=PRIMARY, fg="white", activebackground="#0056D3", activeforeground="white",
                  relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                  font=("Microsoft YaHei", 10), **btn_pad).pack(side=tk.LEFT, padx=(24, 8))

        tk.Button(toolbar, text="批量下载", command=self.on_download,
                  bg=PRIMARY, fg="white", activebackground="#0056D3", activeforeground="white",
                  relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                  font=("Microsoft YaHei", 10), **btn_pad).pack(side=tk.LEFT, padx=8)

        tk.Button(toolbar, text="导出Excel", command=self.on_export,
                  bg=CARD_BG, fg=PRIMARY, activebackground=HOVER_BG, activeforeground=PRIMARY,
                  relief="flat", bd=1, highlightthickness=0, cursor="hand2",
                  font=("Microsoft YaHei", 10), highlightbackground=BORDER, **btn_pad).pack(side=tk.LEFT, padx=8)

        # Search
        search_frame = tk.Frame(toolbar, bg=BORDER, padx=1, pady=1)
        search_frame.pack(side=tk.RIGHT, padx=(16, 0))
        search_inner = tk.Frame(search_frame, bg=CARD_BG)
        search_inner.pack()
        tk.Label(search_inner, text="搜索", bg=CARD_BG, fg=TEXT_SECONDARY,
                 font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(8, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.on_search())
        search_entry = tk.Entry(search_inner, textvariable=self.search_var, width=24,
                                relief="flat", bd=0, highlightthickness=0, bg=CARD_BG, fg=TEXT,
                                font=("Microsoft YaHei", 10))
        search_entry.pack(side=tk.LEFT, padx=(0, 8), pady=6)

        # Status label in toolbar
        self.status_label = tk.Label(toolbar, text="就绪", bg=CARD_BG, fg=TEXT_SECONDARY,
                                     font=("Microsoft YaHei", 10))
        self.status_label.pack(side=tk.RIGHT, padx=16)

        # Table card
        table_card = tk.Frame(self.root, bg=CARD_BG, padx=1, pady=1)
        table_card.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Treeview
        columns = ("name", "year", "genre", "size", "source", "link_type")
        self.tree = ttk.Treeview(table_card, columns=columns, show="tree headings",
                                 selectmode="browse")
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=48, anchor="center", minwidth=48)

        self.tree.heading("name", text="电影名")
        self.tree.column("name", width=240, anchor="w")
        self.tree.heading("year", text="年份")
        self.tree.column("year", width=60, anchor="center")
        self.tree.heading("genre", text="分类")
        self.tree.column("genre", width=80, anchor="center")
        self.tree.heading("size", text="文件大小")
        self.tree.column("size", width=90, anchor="center")
        self.tree.heading("source", text="来源")
        self.tree.column("source", width=80, anchor="center")
        self.tree.heading("link_type", text="链接类型")
        self.tree.column("link_type", width=100, anchor="center")

        # Scrollbar
        vsb = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Bind events
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Motion>", self.on_tree_hover)
        self.tree.bind("<Leave>", self.on_tree_leave)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Bottom status
        self.bottom_status = tk.Label(self.root, text="共 0 部电影 | 已勾选 0 部",
                                      bg=BG_COLOR, fg=TEXT_SECONDARY,
                                      font=("Microsoft YaHei", 10), anchor=tk.W, padx=16, pady=8)
        self.bottom_status.pack(side=tk.BOTTOM, fill=tk.X)

    def load_data(self):
        self.movies = self.dedup.get_all()
        self.refresh_table(self.movies)
        self.update_status()

    def refresh_table(self, movies):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.filtered_movies = movies
        self.checked_ids.clear()

        img = self.icons.unchecked if self.icons.unchecked else ""
        for i, movie in enumerate(movies):
            iid = str(i)
            self.tree.insert("", tk.END, iid=iid, image=img, values=(
                movie.get("name", ""),
                movie.get("year", ""),
                movie.get("genre", ""),
                movie.get("size", ""),
                movie.get("source", ""),
                movie.get("link_type", ""),
            ))
        self.update_status()

    def on_search(self):
        keyword = self.search_var.get().strip().lower()
        if not keyword:
            self.refresh_table(self.movies)
            return
        filtered = [m for m in self.movies if keyword in m.get("name", "").lower()
                    or keyword in m.get("year", "").lower()
                    or keyword in m.get("genre", "").lower()]
        self.refresh_table(filtered)

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        iid = self.tree.identify_row(event.y)
        if not iid:
            return

        col = self.tree.identify_column(event.x)
        # Toggle checkbox only when clicking first column or tree region
        if region == "tree" or col == "#0":
            if iid in self.checked_ids:
                self.checked_ids.discard(iid)
                if self.icons.unchecked:
                    self.tree.item(iid, image=self.icons.unchecked)
            else:
                self.checked_ids.add(iid)
                if self.icons.checked:
                    self.tree.item(iid, image=self.icons.checked)
            self.update_status()

    def on_tree_hover(self, event):
        iid = self.tree.identify_row(event.y)
        if iid == self._last_hover_iid:
            return
        self._last_hover_iid = iid

        # Cancel pending tooltip
        if self._hover_job:
            self.root.after_cancel(self._hover_job)
            self._hover_job = None

        # Hide existing tooltip
        self.tooltip.hide()

        if not iid:
            return

        idx = int(iid)
        if 0 <= idx < len(self.filtered_movies):
            movie = self.filtered_movies[idx]
            self._hover_job = self.root.after(500, lambda: self.tooltip.show(movie, event.x_root, event.y_root))

    def on_tree_leave(self, event):
        if self._hover_job:
            self.root.after_cancel(self._hover_job)
            self._hover_job = None
        self.tooltip.hide()
        self._last_hover_iid = None

    def on_tree_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        idx = int(iid)
        if 0 <= idx < len(self.filtered_movies):
            movie = self.filtered_movies[idx]
            self._open_link(movie)

    def on_crawl(self):
        def crawl_task():
            self.set_status("正在爬取...", PRIMARY)
            try:
                all_new = []
                cnmkv = CNmkvCrawler()
                for cat_key in config.SITES["cnmkv"]["categories"]:
                    movies = cnmkv.crawl_category(cat_key, limit=None, dedup=self.dedup)
                    all_new.extend(movies)
                    time.sleep(2)

                hdzu = HdzuCrawler()
                hdzu_movies = hdzu.crawl(limit=None, dedup=self.dedup)
                all_new.extend(hdzu_movies)

                if all_new:
                    self.dedup.deduplicate(all_new)

                self.root.after(0, lambda: self._crawl_done(len(all_new)))
            except Exception as e:
                self.root.after(0, lambda: self.set_status(f"爬取出错: {e}", DANGER))

        threading.Thread(target=crawl_task, daemon=True).start()

    def _crawl_done(self, count):
        self.load_data()
        self.set_status(f"爬取完成，新增 {count} 部电影", "#34C759")
        messagebox.showinfo("完成", f"爬取完成！\n新增 {count} 部电影。")

    def on_download(self):
        if not self.checked_ids:
            messagebox.showwarning("提示", "请先勾选要下载的电影")
            return

        count = 0
        for iid in self.checked_ids:
            idx = int(iid)
            if 0 <= idx < len(self.filtered_movies):
                movie = self.filtered_movies[idx]
                self._open_link(movie)
                count += 1
                time.sleep(1.5)

        self.set_status(f"已打开 {count} 个下载链接", "#34C759")

    def _open_link(self, movie):
        link = movie.get("link", "")
        link_type = movie.get("link_type", "")
        if not link:
            return
        try:
            if link_type == "夸克网盘":
                webbrowser.open(link)
            elif link_type == "磁力链接":
                os.startfile(link)
            else:
                webbrowser.open(link)
        except Exception as e:
            print(f"[Download] Failed to open {link}: {e}")

    def on_export(self):
        try:
            export_to_excel(self.movies)
            self.set_status(f"Excel已导出至 {config.EXCEL_PATH}", "#34C759")
            messagebox.showinfo("完成", f"Excel 已导出至:\n{config.EXCEL_PATH}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")

    def set_status(self, text, color=TEXT_SECONDARY):
        self.status_label.config(text=text, fg=color)
        self.bottom_status.config(text=text)

    def update_status(self):
        total = len(self.filtered_movies)
        checked = len(self.checked_ids)
        self.bottom_status.config(text=f"共 {total} 部电影 | 已勾选 {checked} 部")


def main():
    root = tk.Tk()
    app = MovieDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
