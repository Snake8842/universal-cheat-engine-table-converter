import tkinter as tk
from tkinter import filedialog, messagebox
import re
import os

class ToolTip:
    """Creates a floating description text window when hovering over a UI element."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        # Position the tooltip slightly below and to the right of the mouse cursor
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify='left', wraplength=460,
                         background="#2d2d30", foreground="#e1e1e1",
                         relief='solid', borderwidth=1,
                         font=("Arial", "9", "normal"), padx=8, pady=5)
        label.pack()

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


# ---------------------------------------------------------------------------
#  CORE CONVERSION LOGIC (pure functions, no GUI -- easy to test/reuse)
# ---------------------------------------------------------------------------

def parse_address_token(raw):
    """Split an address string into (module_or_None, hex_string).

        'ePSXe.exe+AF3A7C'   -> ('ePSXe.exe', 'AF3A7C')   # module-relative
        'NO$PSX.EXE+1A2B3C'  -> ('NO$PSX.EXE', '1A2B3C')  # module-relative
        '03B2BB5C'           -> (None, '03B2BB5C')        # absolute
        'AF3A7C'             -> (None, 'AF3A7C')           # bare offset

    The hex is taken from AFTER the last '+', then stripped of any non-hex
    characters. The module (everything before the last '+') is returned as-is.
    """
    raw = (raw or "").strip()
    if "+" in raw:
        module, _, rest = raw.rpartition("+")
        return (module.strip() or None), re.sub(r'[^0-9a-fA-F]', '', rest)
    return None, re.sub(r'[^0-9a-fA-F]', '', raw)


def build_mapping(examples):
    """examples: list of (raw_old, raw_new) strings.

    Returns a dict describing the conversion, or raises ValueError if no
    usable row was supplied. The OUTPUT FORMAT is taken from the *new* address:
    if the new example carries a module (e.g. NO$PSX.EXE+...), output stays
    module-relative with that module; otherwise output is absolute hex.
    """
    rows = []          # (idx, parsed-info or None, message)
    shifts = []
    out_modules = []

    for idx, (raw_old, raw_new) in enumerate(examples):
        if not raw_old.strip() or not raw_new.strip():
            continue
        old_mod, old_hex = parse_address_token(raw_old)
        new_mod, new_hex = parse_address_token(raw_new)
        if not old_hex or not new_hex:
            rows.append((idx, None, "unparseable hex"))
            continue
        try:
            shift = int(new_hex, 16) - int(old_hex, 16)
        except ValueError:
            rows.append((idx, None, "hex parse failed"))
            continue
        shifts.append(shift)
        out_modules.append(new_mod)
        rows.append((idx, (old_mod, old_hex, new_mod, new_hex, shift), "ok"))

    if not shifts:
        raise ValueError("No valid address pair rows were supplied.")

    return {
        "shift": shifts[0],
        "out_module": out_modules[0],   # None  =>  emit absolute addresses
        "shifts": shifts,
        "out_modules": out_modules,
        "rows": rows,
        "first_old_raw": next(o for o, n in examples if o.strip() and n.strip()),
    }


def collect_table_offsets(file_content):
    """Return the numeric values of every <Address> in the table (skipping
    pointer expressions). Used only to sanity-check the user's OLD example."""
    vals = []
    for inner in re.findall(r"<Address>([^<]+)</Address>", file_content):
        if "[" in inner or "]" in inner:
            continue
        _, hexs = parse_address_token(inner)
        if hexs:
            try:
                vals.append(int(hexs, 16))
            except ValueError:
                pass
    return vals


def table_uses_modules(file_content):
    return any("+" in inner for inner in re.findall(r"<Address>([^<]+)</Address>", file_content))


def detect_frame_mismatch(file_content, first_old_raw):
    """Catch the classic mistake: the table stores module-relative offsets
    (e.g. ePSXe.exe+AF3A7C) but the user pasted a full ABSOLUTE old address
    (e.g. 01663A7C). That silently drops the module base and shifts the whole
    table by the base amount. Returns True if a mismatch is suspected."""
    old_mod, old_hex = parse_address_token(first_old_raw)
    if old_mod is not None:
        return False                      # they included a module -> fine
    if not table_uses_modules(file_content):
        return False                      # table is absolute too -> fine
    vals = collect_table_offsets(file_content)
    if not vals or not old_hex:
        return False
    try:
        ov = int(old_hex, 16)
    except ValueError:
        return False
    lo, hi = min(vals), max(vals)
    # If the old value sits far outside the band of the table's own offsets,
    # it is almost certainly an absolute address paired with a relative table.
    return ov < lo - 0x100000 or ov > hi + 0x100000


def apply_offset_conversion(file_content, shift, out_module):
    """Shift every <Address> in the table by `shift` and re-emit it.

    out_module is None  -> write absolute 8-digit hex
    out_module is a str -> write  <module>+<hex>

    Pointer expressions (containing [ or ]) and non-hex values are left
    untouched. Returns (modified_text, adjusted_count, skipped_count).
    """
    count = 0
    skipped = 0

    def repl(match):
        nonlocal count, skipped
        inner = match.group(1).strip()
        if "[" in inner or "]" in inner:          # pointer chain -> leave alone
            skipped += 1
            return match.group(0)
        _, hexs = parse_address_token(inner)
        if not hexs:
            skipped += 1
            return match.group(0)
        try:
            new_val = int(hexs, 16) + shift
        except ValueError:
            skipped += 1
            return match.group(0)
        if new_val < 0:
            skipped += 1
            return match.group(0)
        count += 1
        if out_module is None:
            return f"<Address>{new_val:08X}</Address>"
        return f"<Address>{out_module}+{new_val:X}</Address>"

    modified = re.sub(r"<Address>([^<]+)</Address>", repl, file_content)
    return modified, count, skipped


# ---------------------------------------------------------------------------
#  GUI
# ---------------------------------------------------------------------------

class CTConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Cheat Engine Table Converter")
        self.root.geometry("680x720")
        self.root.configure(bg="#1e1e1e")

        self.root.resizable(True, True)
        self.root.minsize(680, 600)

        self.file_path = ""

        # Style Definitions (Custom Dark Mode)
        self.bg_dark = "#1e1e1e"
        self.bg_card = "#252526"
        self.bg_input = "#3c3c3c"
        self.fg_light = "#d4d4d4"
        self.fg_white = "#ffffff"
        self.accent_blue = "#0e639c"
        self.accent_hover = "#1177bb"
        self.accent_green = "#16825d"

        self.create_widgets()

    def create_widgets(self):
        # --- TITLE & DESCRIPTION PANEL ---
        title_frame = tk.Frame(self.root, bg=self.bg_card, padx=15, pady=15, relief="groove", bd=1)
        title_frame.pack(fill="x", padx=15, pady=15)

        header_row = tk.Frame(title_frame, bg=self.bg_card)
        header_row.pack(fill="x")

        title_lbl = tk.Label(header_row, text="✨ Universal Cheat Engine Table Converter",
                             font=("Arial", "14", "bold"), bg=self.bg_card, fg=self.fg_white)
        title_lbl.pack(side="left", anchor="w")

        donate_btn = tk.Button(header_row, text="❤️ Support ️❤", font=("Arial", "9", "bold"),
                               bg="#7b2d42", fg=self.fg_white, activebackground="#9b3d52",
                               activeforeground=self.fg_white, relief="flat", padx=10, pady=2,
                               command=self.show_donate)
        donate_btn.pack(side="right", anchor="n")
        ToolTip(donate_btn, "Support the developer — view donation options.")

        # The full guide lives in this panel's hover tooltip; the visible blurb is kept short so the
        # Execution Output Log below has room on shorter screens (this was the cause of the thin log).
        full_desc = (
            "What this program does:\n"
            "Game data lives at a fixed spot in an emulator's RAM. When the emulator updates -- or when "
            "you switch to a DIFFERENT emulator (ePSXe -> No$PSX, PCSX-Redux, etc.) -- that whole block "
            "shifts by a constant amount. This tool finds that shift from a single known address and "
            "applies it to EVERY address in your .CT file.\n\n"
            "How to use it:\n"
            "1. Select your original .CT file.\n"
            "2. Find the SAME value (e.g. 'Money') in both emulators.\n"
            "3. OLD address: paste it exactly as the source table shows it (for ePSXe that is "
            "'ePSXe.exe+AF3A7C').  NEW address: paste it in the format you want OUT -- a bare absolute "
            "like '03B2BB5C' for No$PSX, or 'MODULE+offset' to keep it module-relative.\n\n"
            "The OUTPUT format follows your NEW address, so the same tool converts across emulators."
        )
        desc_text = (
            "Shifts every address in a Cheat Engine .CT by one constant offset -- for emulator updates "
            "or cross-emulator ports (ePSXe -> No$PSX, PCSX-Redux, DuckStation...).\n"
            "1) Pick your .CT file.    2) Find the SAME value (e.g. Money) in both emulators.\n"
            "3) OLD = paste it as the source table shows it (e.g. ePSXe.exe+AF3A7C).    "
            "NEW = paste it how you want it OUT (absolute 03B2BB5C, or MODULE+offset).\n"
            "Output format follows your NEW address.    (Hover this panel for the full guide.)"
        )
        desc_lbl = tk.Label(title_frame, text=desc_text, font=("Arial", "9"), bg=self.bg_card,
                            fg=self.fg_light, justify="left", wraplength=620)
        desc_lbl.pack(anchor="w", pady=(5, 0))
        ToolTip(title_frame, full_desc)

        # --- FILE SELECTION SECTION ---
        file_frame = tk.LabelFrame(self.root, text=" 1. Select Cheat Table File ", font=("Arial", "10", "bold"),
                                   bg=self.bg_dark, fg=self.fg_white, padx=10, pady=10)
        file_frame.pack(fill="x", padx=15, pady=5)

        self.file_label = tk.Label(file_frame, text="No file selected...", font=("Arial", "9", "italic"),
                                   bg=self.bg_dark, fg="#aaaaaa", anchor="w", width=50)
        self.file_label.pack(side="left", padx=(5, 10), fill="x", expand=True)

        browse_btn = tk.Button(file_frame, text="Browse .CT File", font=("Arial", "9", "bold"),
                               bg=self.accent_blue, fg=self.fg_white, activebackground=self.accent_hover,
                               activeforeground=self.fg_white, relief="flat", padx=15, command=self.browse_file)
        browse_btn.pack(side="right")
        ToolTip(browse_btn, "Open a file browser to load your old Cheat Engine template table (.CT).")
        ToolTip(self.file_label, "Displays the current path of the cheat table target queued for upgrading.")

        # --- ADDRESS MAPPING SECTION ---
        map_frame = tk.LabelFrame(self.root, text=" 2. Input Address Mapping Examples ", font=("Arial", "10", "bold"),
                                  bg=self.bg_dark, fg=self.fg_white, padx=15, pady=15)
        map_frame.pack(fill="x", padx=15, pady=10)

        tip_lbl = tk.Label(map_frame,
                           text="💡 OLD = source format (e.g. ePSXe.exe+AF3A7C).  NEW = output format "
                                "(absolute 03B2BB5C, or MODULE+offset).",
                           font=("Arial", "8", "italic"), bg=self.bg_dark, fg="#10a37f",
                           justify="left", wraplength=620)
        tip_lbl.pack(anchor="w", pady=(0, 10))

        # Table Header Labels
        header_frame = tk.Frame(map_frame, bg=self.bg_dark)
        header_frame.pack(fill="x", pady=(0, 5))
        tk.Label(header_frame, text="Original/Old Address", font=("Arial", "9", "bold"), bg=self.bg_dark, fg=self.fg_light, width=30, anchor="w").pack(side="left")
        tk.Label(header_frame, text="New/Current Address", font=("Arial", "9", "bold"), bg=self.bg_dark, fg=self.fg_light, width=30, anchor="w").pack(side="left")

        # Generate 3 Row Inputs
        self.rows = []
        for i in range(3):
            row_fr = tk.Frame(map_frame, bg=self.bg_dark, pady=4)
            row_fr.pack(fill="x")

            lbl = tk.Label(row_fr, text=f"{i+1}.", font=("Arial", "9", "bold"), bg=self.bg_dark, fg=self.fg_light, width=3)
            lbl.pack(side="left")

            old_ent = tk.Entry(row_fr, bg=self.bg_input, fg=self.fg_white, insertbackground=self.fg_white, relief="flat", font=("Consolas", "10"), width=26)
            old_ent.pack(side="left", padx=5)

            arrow_lbl = tk.Label(row_fr, text="➔", bg=self.bg_dark, fg=self.accent_blue, width=4)
            arrow_lbl.pack(side="left")

            new_ent = tk.Entry(row_fr, bg=self.bg_input, fg=self.fg_white, insertbackground=self.fg_white, relief="flat", font=("Consolas", "10"), width=26)
            new_ent.pack(side="left", padx=5)

            self.rows.append((old_ent, new_ent))

            ToolTip(old_ent, f"Example #{i+1}: the address in the OLD/source table, in that table's own format "
                             f"(e.g. ePSXe.exe+AF3A7C).")
            ToolTip(new_ent, f"Example #{i+1}: the matching address in the NEW emulator, written in the format you "
                             f"want the output to use (absolute hex, or MODULE+offset).")

        # --- EXECUTION SECTION ---
        exec_frame = tk.Frame(self.root, bg=self.bg_dark, pady=15)
        exec_frame.pack(fill="x", padx=15)

        self.convert_btn = tk.Button(exec_frame, text="⚡ Convert Cheat Table", font=("Arial", "12", "bold"),
                                     bg=self.accent_green, fg=self.fg_white, activebackground="#1e9c75",
                                     activeforeground=self.fg_white, relief="flat", pady=8, command=self.process_conversion)
        self.convert_btn.pack(fill="x")
        ToolTip(self.convert_btn, "Analyzes input pairs, verifies math consistency, and recalculates every address in your file.")

        # --- STATUS LOG WINDOW ---
        log_frame = tk.LabelFrame(self.root, text=" Execution Output Log ", font=("Arial", "9", "bold"),
                                  bg=self.bg_dark, fg=self.fg_light, padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        self.log_box = tk.Text(log_frame, bg="#111111", fg="#80e5ff", font=("Consolas", "9"), relief="flat", state="disabled", height=12)
        self.log_box.pack(fill="both", expand=True)
        ToolTip(self.log_box, "Real-time engine terminal displaying diagnostic details, structural math offsets, and execution outputs.")

    def show_donate(self):
        popup = tk.Toplevel(self.root)
        popup.title("Support the Developer")
        popup.configure(bg=self.bg_card)
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        # Center the popup over the main window
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 240
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 140
        popup.geometry(f"480x280+{x}+{y}")

        outer = tk.Frame(popup, bg=self.bg_card, padx=25, pady=20)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="If you'd like to support, feel free to donate any amount:",
                 font=("Arial", "10"), bg=self.bg_card, fg=self.fg_light,
                 justify="left").pack(anchor="w", pady=(0, 15))

        # Crypto
        tk.Label(outer, text="💰  Crypto (MetaMask Wallet):",
                 font=("Arial", "10", "bold"), bg=self.bg_card, fg=self.fg_white).pack(anchor="w")
        crypto_entry = tk.Entry(outer, font=("Consolas", "10"), bg=self.bg_input, fg="#80e5ff",
                                relief="flat", readonlybackground=self.bg_input)
        crypto_entry.insert(0, "0x60296899c228372F81876B4275E6f4665f3098a5")
        crypto_entry.config(state="readonly")
        crypto_entry.pack(fill="x", pady=(4, 12))

        # PayPal
        tk.Label(outer, text="💳  PayPal:",
                 font=("Arial", "10", "bold"), bg=self.bg_card, fg=self.fg_white).pack(anchor="w")
        paypal_entry = tk.Entry(outer, font=("Consolas", "10"), bg=self.bg_input, fg="#80e5ff",
                                relief="flat", readonlybackground=self.bg_input)
        paypal_entry.insert(0, "DiegoM.Hepp@Gmail.com")
        paypal_entry.config(state="readonly")
        paypal_entry.pack(fill="x", pady=(4, 15))

        tk.Label(outer, text="️❤  Thank you for considering. ❤️",
                 font=("Arial", "10", "italic"), bg=self.bg_card, fg="#f0c070").pack(pady=(0, 15))

        tk.Button(outer, text="Close", font=("Arial", "9", "bold"),
                  bg=self.bg_input, fg=self.fg_white, activebackground="#555555",
                  activeforeground=self.fg_white, relief="flat", padx=20, pady=5,
                  command=popup.destroy).pack()

    def log(self, text):
        """Helper to append status logs to our dark console component safely."""
        self.log_box.config(state="normal")
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state="disabled")

    def clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.config(state="disabled")

    def browse_file(self):
        selected = filedialog.askopenfilename(filetypes=[("Cheat Engine Tables", "*.CT"), ("All Files", "*.*")])
        if selected:
            self.file_path = selected
            self.file_label.config(text=os.path.basename(selected), fg=self.fg_white, font=("Arial", "9", "bold"))
            self.clear_log()
            self.log(f"[INIT] Loaded target master file: {os.path.basename(selected)}")

    def process_conversion(self):
        self.clear_log()
        if not self.file_path:
            messagebox.showerror("Error", "Please select a valid source '.CT' file first!")
            return

        # 1. Build the mapping from the example rows
        examples = [(o.get(), n.get()) for (o, n) in self.rows]
        try:
            mapping = build_mapping(examples)
        except ValueError:
            messagebox.showerror("Missing Data", "You must fill out at least one valid address pair row!")
            return

        for idx, info, msg in mapping["rows"]:
            if info is None:
                self.log(f"[WARN] Row {idx+1}: {msg}. Skipping...")
            else:
                old_mod, old_hex, new_mod, new_hex, shift = info
                src = f"{old_mod}+{old_hex}" if old_mod else old_hex
                tgt = f"{new_mod}+{new_hex}" if new_mod else new_hex
                self.log(f"[PARSED] Row {idx+1}: {src}  ->  {tgt}   (shift {shift:+X})")

        # 2. Consistency checks across the example rows
        if len(set(mapping["shifts"])) > 1:
            self.log("[WARN] Example rows produced DIFFERENT shifts:")
            for s in mapping["shifts"]:
                self.log(f"          {s:+X}")
            self.log("        -> Either the memory is not one uniform block, an example is mistyped,")
            self.log("           or old/new got swapped. Using the FIRST row's shift.")
            messagebox.showwarning(
                "Shift mismatch",
                "Your example pairs gave different offsets.\n\nUsing the first pair. If the result is "
                "wrong, check that every pair points to the SAME value and that old/new are not reversed.")
        if len(set(mapping["out_modules"])) > 1:
            self.log("[WARN] NEW-address formats differ between rows; using the first row's format.")

        shift = mapping["shift"]
        out_module = mapping["out_module"]
        out_desc = "ABSOLUTE (8-digit hex)" if out_module is None else f"{out_module}+OFFSET"

        # 3. Read the file
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
        except Exception as e:
            messagebox.showerror("File Error", f"Failed reading the target file:\n{str(e)}")
            return

        # 4. Sanity guard for the classic "absolute OLD vs relative table" mistake
        if detect_frame_mismatch(file_content, mapping["first_old_raw"]):
            self.log("[WARN] Your OLD address looks ABSOLUTE, but this table stores module-relative")
            self.log("       offsets (e.g. ePSXe.exe+AF3A7C). That drops the module base and shifts")
            self.log("       the whole table by the wrong amount.")
            proceed = messagebox.askyesno(
                "Possible format mismatch",
                "Your OLD address looks like a full absolute address, but the table stores "
                "module-relative offsets (e.g. ePSXe.exe+AF3A7C).\n\n"
                "Paste the OLD address WITH its module prefix, exactly as Cheat Engine's address "
                "column shows it.\n\nConvert anyway?")
            if not proceed:
                self.log("[ABORT] Conversion cancelled. Re-enter the OLD address with its module prefix.")
                return

        self.log("-" * 60)
        self.log(f"[CONFIG] Shift applied : {shift:+X} Hex")
        self.log(f"[CONFIG] Output format : {out_desc}")

        # 5. Convert
        modified_content, count, skipped = apply_offset_conversion(file_content, shift, out_module)

        if count == 0:
            self.log("[WARN] No <Address> tags were modified. Is this a valid Cheat Engine table?")

        # 6. Save (never overwrites the source)
        dir_name, file_name = os.path.split(self.file_path)
        new_file_name = f"UPDATED_{file_name}"
        output_path = os.path.join(dir_name, new_file_name)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)

            self.log("-" * 60)
            self.log("[SUCCESS] Conversion complete!")
            self.log(f"[OUTPUT] Addresses adjusted : {count}")
            if skipped:
                self.log(f"[OUTPUT] Skipped (pointers / non-hex) : {skipped}")
            self.log(f"[SAVED] Generated file location:\n {output_path}")
            messagebox.showinfo("Success", f"Cheat Table updated successfully!\nAdjusted {count} addresses.\nSaved as: {new_file_name}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed exporting the new file asset:\n{str(e)}")


if __name__ == "__main__":
    app_root = tk.Tk()
    app = CTConverterApp(app_root)
    app_root.mainloop()
