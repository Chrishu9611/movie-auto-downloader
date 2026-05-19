import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import os
import threading
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cnmkv import CNmkvCrawler
from src.hdzu import HdzuCrawler
from src.deduplicator import Deduplicator
from src.excel_exporter import export_to_excel
import config


class MovieDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("电影自动下载器")
        self.root.geometry("1200x700")
        self.root.minsize(900, 500)

        self.dedup = Deduplicator()
        self.movies = []
        self.checked_ids = set()
        self.all_movies = []

        self._create_ui()
        self.load_data()

    def _create_ui(self):
        # Top control frame
        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        tk.Button(top_frame, text="立即爬取", command=self.on_crawl, width=12, bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="批量下载", command=self.on_download, width=12, bg="#2196F3", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="导出Excel", command=self.on_export, width=12).pack(side=tk.LEFT, padx=5)

        tk.Label(top_frame, text="搜索:").pack(side=tk.LEFT, padx=(30, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.on_search())
        tk.Entry(top_frame, textvariable=self.search_var, width=30).pack(side=tk.LEFT)

        self.status_label = tk.Label(top_frame, text="就绪", fg="gray")
        self.status_label.pack(side=tk.RIGHT)

        # Treeview
        columns = ("name", "year", "genre", "size", "source", "link_type")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("#0", text="选择")
        self.tree.column("#0", width=50, anchor="center")

        self.tree.heading("name", text="电影名")
        self.tree.column("name", width=200)
        self.tree.heading("year", text="年份")
        self.tree.column("year", width=60, anchor="center")
        self.tree.heading("genre", text="分类")
        self.tree.column("genre", width=80, anchor="center")
        self.tree.heading("size", text="文件大小")
        self.tree.column("size", width=80, anchor="center")
        self.tree.heading("source", text="来源")
        self.tree.column("source", width=80, anchor="center")
        self.tree.heading("link_type", text="链接类型")
        self.tree.column("link_type", width=90, anchor="center")

        # Scrollbar
        vsb = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Bind click
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Bottom status
        self.bottom_status = tk.Label(self.root, text="共 0 部电影 | 已勾选 0 部", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.bottom_status.pack(side=tk.BOTTOM, fill=tk.X)

    def load_data(self):
        self.all_movies = self.dedup.get_all()
        self.refresh_table(self.all_movies)
        self.update_status()

    def refresh_table(self, movies):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.movies = movies
        self.checked_ids.clear()

        for i, movie in enumerate(movies):
            iid = str(i)
            self.tree.insert("", tk.END, iid=iid, text="☐", values=(
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
            self.refresh_table(self.all_movies)
            return

        filtered = [m for m in self.all_movies if keyword in m.get("name", "").lower()
                    or keyword in m.get("year", "").lower()
                    or keyword in m.get("genre", "").lower()]
        self.refresh_table(filtered)

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell" and region != "tree":
            return

        iid = self.tree.identify_row(event.y)
        if not iid:
            return

        col = self.tree.identify_column(event.x)
        # Toggle checkbox if clicked on first column
        if col == "#0" or region == "tree":
            if iid in self.checked_ids:
                self.checked_ids.discard(iid)
                self.tree.item(iid, text="☐")
            else:
                self.checked_ids.add(iid)
                self.tree.item(iid, text="☑")
            self.update_status()

    def on_tree_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        idx = int(iid)
        if 0 <= idx < len(self.movies):
            movie = self.movies[idx]
            self._open_link(movie)

    def on_crawl(self):
        def crawl_task():
            self.set_status("正在爬取...", "blue")
            try:
                all_new = []
                # Crawl cnmkv categories incrementally
                cnmkv = CNmkvCrawler()
                for cat_key in config.SITES["cnmkv"]["categories"]:
                    movies = cnmkv.crawl_category(cat_key, limit=None, dedup=self.dedup)
                    all_new.extend(movies)
                    time.sleep(2)

                # Crawl hdzu incrementally
                hdzu = HdzuCrawler()
                hdzu_movies = hdzu.crawl(limit=None, dedup=self.dedup)
                all_new.extend(hdzu_movies)

                # Deduplicate and insert
                if all_new:
                    self.dedup.deduplicate(all_new)

                self.root.after(0, lambda: self._crawl_done(len(all_new)))
            except Exception as e:
                self.root.after(0, lambda: self.set_status(f"爬取出错: {e}", "red"))

        threading.Thread(target=crawl_task, daemon=True).start()

    def _crawl_done(self, count):
        self.load_data()
        self.set_status(f"爬取完成，新增 {count} 部电影", "green")
        messagebox.showinfo("完成", f"爬取完成！\n新增 {count} 部电影。")

    def on_download(self):
        if not self.checked_ids:
            messagebox.showwarning("提示", "请先勾选要下载的电影")
            return

        count = 0
        for iid in self.checked_ids:
            idx = int(iid)
            if 0 <= idx < len(self.movies):
                movie = self.movies[idx]
                self._open_link(movie)
                count += 1
                time.sleep(1.5)

        self.set_status(f"已打开 {count} 个下载链接", "green")

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
            export_to_excel(self.all_movies)
            self.set_status(f"Excel已导出至 {config.EXCEL_PATH}", "green")
            messagebox.showinfo("完成", f"Excel 已导出至:\n{config.EXCEL_PATH}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")

    def set_status(self, text, color="black"):
        self.status_label.config(text=text, fg=color)
        self.bottom_status.config(text=text)

    def update_status(self):
        total = len(self.movies)
        checked = len(self.checked_ids)
        self.bottom_status.config(text=f"共 {total} 部电影 | 已勾选 {checked} 部")


def main():
    root = tk.Tk()
    app = MovieDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
