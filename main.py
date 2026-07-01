import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import json, os, base64, io, subprocess, sys, tempfile
from PIL import Image, ImageTk, ImageGrab

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DATA_FILE = os.path.join(os.path.expanduser("~"), ".pinner_data.json")

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"lists": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def copy_image_to_clipboard(pil_image):
    """Copy PIL image to Windows clipboard so Win+V catches it."""
    try:
        if sys.platform == "win32":
            import win32clipboard
            from io import BytesIO
            output = BytesIO()
            pil_image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]  # strip BMP file header
            output.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            return True
        else:
            # Mac / Linux fallback — save temp file
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            pil_image.save(tmp.name)
            tmp.close()
            if sys.platform == "darwin":
                subprocess.run(["osascript", "-e",
                    f'set the clipboard to (read (POSIX file "{tmp.name}") as TIFF picture)'])
            return True
    except ImportError:
        return False
    except Exception:
        return False

class PinnerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("الرصة | The Pinner")
        self.geometry("1100x700")
        self.minsize(800, 550)
        self.data = load_data()
        self.current_list = None
        self._build_ui()
        self._refresh_lists()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── SIDEBAR ──────────────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0,
                                    fg_color=("#1a1a2e","#0f0f1a"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1)
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="📌 الرصة",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="#4da6ff").grid(row=0, column=0, padx=16, pady=(20,4), sticky="w")
        ctk.CTkLabel(self.sidebar, text="The Pinner",
                     font=ctk.CTkFont(size=11),
                     text_color="#666688").grid(row=1, column=0, padx=16, pady=(0,12), sticky="w")

        self.list_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", label_text="")
        self.list_frame.grid(row=2, column=0, padx=8, pady=4, sticky="nsew")

        btn_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_row.grid(row=3, column=0, padx=8, pady=(10,4), sticky="ew")
        btn_row.grid_columnconfigure((0,1), weight=1)
        ctk.CTkButton(btn_row, text="+ قائمة", height=32,
                      command=self._new_list).grid(row=0, column=0, padx=2, sticky="ew")
        ctk.CTkButton(btn_row, text="🗑", width=36, height=32,
                      fg_color="#3a1a1a", hover_color="#5a2a2a",
                      command=self._delete_list).grid(row=0, column=1, padx=2, sticky="ew")

        ctk.CTkButton(self.sidebar, text="📥 استيراد", height=30,
                      fg_color="#1a3a1a", hover_color="#2a5a2a",
                      command=self._import).grid(row=4, column=0, padx=10, pady=(4,2), sticky="ew")
        ctk.CTkButton(self.sidebar, text="📤 تصدير", height=30,
                      fg_color="#1a1a3a", hover_color="#2a2a5a",
                      command=self._export).grid(row=5, column=0, padx=10, pady=(2,14), sticky="ew")

        # ── CONTENT ──────────────────────────────────────────────────────────
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=("#121220","#0a0a14"))
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self.content, height=56, fg_color=("#1a1a2e","#111126"), corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        top.grid_propagate(False)

        self.list_title = ctk.CTkLabel(top, text="اختر قائمة أو أنشئ واحدة",
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       text_color="#ccccee")
        self.list_title.grid(row=0, column=0, padx=20, pady=14, sticky="w")

        add_row = ctk.CTkFrame(top, fg_color="transparent")
        add_row.grid(row=0, column=1, padx=12, pady=8)

        # Only TEXT and IMAGE buttons
        ctk.CTkButton(add_row, text="+ نص", width=80, height=32,
                      font=ctk.CTkFont(size=13),
                      command=self._add_text).grid(row=0, column=0, padx=4)
        ctk.CTkButton(add_row, text="+ صورة", width=80, height=32,
                      font=ctk.CTkFont(size=13),
                      fg_color="#2a1a4a", hover_color="#3a2a6a",
                      command=self._add_image).grid(row=0, column=1, padx=4)

        self.items_frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        self.items_frame.grid(row=1, column=0, sticky="nsew")
        self.items_frame.grid_columnconfigure(0, weight=1)

    # ── Lists ─────────────────────────────────────────────────────────────────
    def _refresh_lists(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        for name in self.data["lists"]:
            self._make_list_btn(name)

    def _make_list_btn(self, name):
        ctk.CTkButton(self.list_frame, text=f"📋  {name}", anchor="w", height=34,
                      font=ctk.CTkFont(size=13), fg_color="transparent",
                      hover_color=("#2a2a4a","#2a2a4a"), text_color="#aaaacc",
                      command=lambda n=name: self._open_list(n)).pack(fill="x", pady=2)

    def _new_list(self):
        d = ctk.CTkInputDialog(text="اسم القائمة الجديدة:", title="قائمة جديدة")
        name = d.get_input()
        if name and name.strip():
            name = name.strip()
            if name not in self.data["lists"]:
                self.data["lists"][name] = []
                save_data(self.data)
                self._make_list_btn(name)
            self._open_list(name)

    def _delete_list(self):
        if not self.current_list:
            return
        if messagebox.askyesno("حذف", f'هتحذف قائمة "{self.current_list}"؟'):
            del self.data["lists"][self.current_list]
            save_data(self.data)
            self.current_list = None
            self.list_title.configure(text="اختر قائمة أو أنشئ واحدة")
            self._refresh_lists()
            self._render_items()

    def _open_list(self, name):
        self.current_list = name
        self.list_title.configure(text=f"📋  {name}")
        self._render_items()

    # ── Render ────────────────────────────────────────────────────────────────
    def _render_items(self):
        for w in self.items_frame.winfo_children():
            w.destroy()
        if not self.current_list:
            return
        items = self.data["lists"].get(self.current_list, [])
        if not items:
            ctk.CTkLabel(self.items_frame,
                         text="📌\n\nالقائمة فاضية\nاضغط + نص أو + صورة لتضيف",
                         font=ctk.CTkFont(size=14), text_color="#444466",
                         justify="center").pack(expand=True, pady=80)
            return
        for i, item in enumerate(items):
            self._make_card(i, item)

    def _make_card(self, idx, item):
        card = ctk.CTkFrame(self.items_frame, corner_radius=10,
                            fg_color=("#1e1e32","#16162a"),
                            border_width=1, border_color="#2a2a44")
        card.pack(fill="x", padx=16, pady=6)
        card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8,4))
        hdr.grid_columnconfigure(0, weight=1)

        t = item.get("type","text")
        colors = {"text":"#4da6ff","image":"#ff88dd"}
        labels = {"text":"نص","image":"صورة"}
        ctk.CTkLabel(hdr, text=f"  {labels.get(t,t)}",
                     font=ctk.CTkFont(size=10), text_color=colors.get(t,"#aaa"),
                     fg_color=("#2a2a3a","#1a1a2a"), corner_radius=4).grid(row=0,column=0,sticky="w")

        acts = ctk.CTkFrame(hdr, fg_color="transparent")
        acts.grid(row=0, column=1, sticky="e")

        if t == "image":
            ctk.CTkButton(acts, text="📋 نسخ", width=70, height=26,
                          font=ctk.CTkFont(size=11),
                          fg_color="#1a3a1a", hover_color="#2a5a2a",
                          command=lambda i=idx: self._copy_image(i)).pack(side="left", padx=2)
            ctk.CTkButton(acts, text="💾 حفظ", width=70, height=26,
                          font=ctk.CTkFont(size=11),
                          fg_color="#1a1a3a", hover_color="#2a2a5a",
                          command=lambda i=idx: self._save_image(i)).pack(side="left", padx=2)
        else:
            ctk.CTkButton(acts, text="📋 نسخ", width=70, height=26,
                          font=ctk.CTkFont(size=11),
                          fg_color="#1a3a1a", hover_color="#2a5a2a",
                          command=lambda i=idx: self._copy_text(i)).pack(side="left", padx=2)
            ctk.CTkButton(acts, text="✏️ تعديل", width=70, height=26,
                          font=ctk.CTkFont(size=11),
                          fg_color="#2a2a1a", hover_color="#4a4a2a",
                          command=lambda i=idx: self._edit_item(i)).pack(side="left", padx=2)

        ctk.CTkButton(acts, text="🗑", width=32, height=26,
                      fg_color="#3a1a1a", hover_color="#5a2a2a",
                      command=lambda i=idx: self._delete_item(i)).pack(side="left", padx=2)

        if t == "image":
            try:
                img_data = base64.b64decode(item["content"])
                img = Image.open(io.BytesIO(img_data))
                img.thumbnail((420, 280))
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(card, image=photo, bg="#16162a")
                lbl.image = photo
                lbl.grid(row=1, column=0, padx=10, pady=(0,10), sticky="w")
            except Exception:
                ctk.CTkLabel(card, text="[خطأ في الصورة]",
                             text_color="#ff6666").grid(row=1,column=0,padx=10,pady=6)
        else:
            preview = item.get("label") or item["content"][:160]
            if len(item["content"]) > 160 and not item.get("label"):
                preview += "..."
            ctk.CTkLabel(card, text=preview,
                         font=ctk.CTkFont(size=13),
                         text_color="#ccccee",
                         justify="left", wraplength=720, anchor="w").grid(
                             row=1, column=0, padx=12, pady=(0,10), sticky="w")

    # ── Add ───────────────────────────────────────────────────────────────────
    def _require_list(self):
        if not self.current_list:
            messagebox.showwarning("تنبيه", "اختر أو أنشئ قائمة أول!")
            return False
        return True

    def _add_text(self):
        if self._require_list():
            self._text_editor({"type":"text","content":"","label":""})

    def _add_image(self):
        if not self._require_list():
            return
        path = filedialog.askopenfilename(
            filetypes=[("صور","*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if not path:
            return
        with open(path,"rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        self.data["lists"][self.current_list].append(
            {"type":"image","content":b64,"label":os.path.basename(path)})
        save_data(self.data)
        self._render_items()

    # ── Text editor with full paste support ───────────────────────────────────
    def _text_editor(self, item, idx=None):
        win = ctk.CTkToplevel(self)
        win.title("تعديل نص" if idx is not None else "نص جديد")
        win.geometry("640x520")
        win.grab_set()
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(win, text="وصف مختصر (اختياري):",
                     font=ctk.CTkFont(size=12)).grid(row=0,column=0,padx=16,pady=(16,4),sticky="w")
        label_entry = ctk.CTkEntry(win, placeholder_text="مثال: رسالة ترحيب، بروبت AI...")
        label_entry.grid(row=1,column=0,padx=16,pady=(0,8),sticky="ew")
        if item.get("label"):
            label_entry.insert(0, item["label"])

        # Native tk.Text — supports ALL paste methods including Win+V
        wrap = tk.Frame(win, bg="#1a1a2e", bd=1, relief="flat")
        wrap.grid(row=2,column=0,padx=16,pady=(0,8),sticky="nsew")
        wrap.grid_rowconfigure(0,weight=1)
        wrap.grid_columnconfigure(0,weight=1)

        txt = tk.Text(wrap,
                      font=("Segoe UI", 13),
                      bg="#12121e", fg="#e0e0ff",
                      insertbackground="#4da6ff",
                      relief="flat", padx=12, pady=10,
                      wrap="word", undo=True,
                      selectbackground="#3a3a7a",
                      selectforeground="#ffffff")
        txt.grid(row=0,column=0,sticky="nsew")
        sb = tk.Scrollbar(wrap, command=txt.yview)
        sb.grid(row=0,column=1,sticky="ns")
        txt.configure(yscrollcommand=sb.set)

        if item.get("content"):
            txt.insert("1.0", item["content"])

        # Force focus so Ctrl+V / Win+V work immediately on open
        win.after(50, lambda: txt.focus_force())

        # Explicit paste bindings as safety net
        def do_paste(event=None):
            try:
                clip = win.clipboard_get()
                txt.delete("sel.first", "sel.last") if txt.tag_ranges("sel") else None
                txt.insert(tk.INSERT, clip)
                txt.see(tk.INSERT)
            except Exception:
                pass
            return "break"

        txt.bind("<Control-v>", do_paste)
        txt.bind("<Control-V>", do_paste)
        txt.bind("<Shift-Insert>", do_paste)  # Win+V pastes as Shift+Insert sometimes

        # Bottom bar
        bar = tk.Frame(win, bg="#0a0a14")
        bar.grid(row=3,column=0,padx=16,pady=(0,8),sticky="ew")

        ctk.CTkButton(bar, text="📋 لصق", width=100, height=30,
                      fg_color="#1a3a1a", hover_color="#2a5a2a",
                      command=do_paste).pack(side="left", padx=(0,6))
        ctk.CTkButton(bar, text="🗑 مسح", width=100, height=30,
                      fg_color="#3a1a1a", hover_color="#5a2a2a",
                      command=lambda: txt.delete("1.0", tk.END)).pack(side="left")

        def _save():
            content = txt.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning("تنبيه","المحتوى فاضي!", parent=win)
                return
            new_item = {"type":"text","content":content,"label":label_entry.get().strip()}
            lst = self.data["lists"][self.current_list]
            if idx is not None:
                lst[idx] = new_item
            else:
                lst.append(new_item)
            save_data(self.data)
            self._render_items()
            win.destroy()

        ctk.CTkButton(win, text="💾 حفظ", height=40,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=_save).grid(row=4,column=0,padx=16,pady=(0,16),sticky="ew")

    # ── Actions ───────────────────────────────────────────────────────────────
    def _copy_text(self, idx):
        content = self.data["lists"][self.current_list][idx]["content"]
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()
        self._toast("✅ النص اتنسخ!")

    def _copy_image(self, idx):
        item = self.data["lists"][self.current_list][idx]
        try:
            img_data = base64.b64decode(item["content"])
            img = Image.open(io.BytesIO(img_data))
            ok = copy_image_to_clipboard(img)
            if ok:
                self._toast("✅ الصورة اتنسخت!")
            else:
                # fallback: install pywin32 prompt
                messagebox.showinfo("تثبيت مطلوب",
                    "عشان تنسخ صور للكليبورد، شغّل الأمر ده في CMD:\n\npip install pywin32\n\nوبعدين أعد تشغيل البرنامج.")
        except Exception as e:
            messagebox.showerror("خطأ", str(e))

    def _save_image(self, idx):
        item = self.data["lists"][self.current_list][idx]
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG","*.png"),("JPEG","*.jpg")],
            initialfile=item.get("label","image.png"))
        if not path:
            return
        with open(path,"wb") as f:
            f.write(base64.b64decode(item["content"]))
        self._toast("💾 الصورة اتحفظت!")

    def _edit_item(self, idx):
        item = self.data["lists"][self.current_list][idx]
        self._text_editor(dict(item), idx=idx)

    def _delete_item(self, idx):
        if messagebox.askyesno("حذف","هتحذف العنصر ده؟"):
            self.data["lists"][self.current_list].pop(idx)
            save_data(self.data)
            self._render_items()

    def _toast(self, msg):
        t = ctk.CTkLabel(self, text=f"  {msg}  ",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         fg_color="#1a4a1a", corner_radius=8,
                         text_color="#44ff88")
        t.place(relx=0.5, rely=0.95, anchor="center")
        self.after(2000, t.destroy)

    # ── Import / Export ───────────────────────────────────────────────────────
    def _export(self):
        if not self.current_list:
            messagebox.showwarning("تنبيه","اختر قائمة أول!")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pinner",
            filetypes=[("Pinner","*.pinner"),("JSON","*.json")],
            initialfile=f"{self.current_list}.pinner")
        if not path:
            return
        with open(path,"w",encoding="utf-8") as f:
            json.dump({"list_name":self.current_list,
                       "items":self.data["lists"][self.current_list]},
                      f, ensure_ascii=False, indent=2)
        self._toast("📤 اتصدر!")

    def _import(self):
        path = filedialog.askopenfilename(
            filetypes=[("Pinner","*.pinner"),("JSON","*.json")])
        if not path:
            return
        try:
            with open(path,"r",encoding="utf-8") as f:
                imp = json.load(f)
            name = imp.get("list_name", os.path.basename(path).replace(".pinner",""))
            items = imp.get("items",[])
            if name in self.data["lists"]:
                if not messagebox.askyesno("استيراد",f'القائمة "{name}" موجودة. هتستبدلها؟'):
                    return
            self.data["lists"][name] = items
            save_data(self.data)
            self._refresh_lists()
            self._open_list(name)
            self._toast("📥 اتستورد!")
        except Exception as e:
            messagebox.showerror("خطأ",f"مش قدر يستورد:\n{e}")


if __name__ == "__main__":
    app = PinnerApp()
    app.mainloop()
