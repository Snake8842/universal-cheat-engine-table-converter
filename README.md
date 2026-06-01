# Universal Cheat Engine Table Converter

A small, dependency-free desktop tool that **re-points an entire Cheat Engine table (`.CT`) to a new memory layout in one click** — whether the layout changed because your emulator updated, or because you switched to a *completely different* emulator (e.g. **ePSXe → No$PSX → PCSX-Redux → DuckStation**).

You give it one address you already know the answer to (say, *Money*) in the old build and the new build. It works out the constant amount everything shifted by, applies that to **every** address in the table, and writes a brand-new `.CT` you can load straight away — without ever touching your original file.

> [!NOTE]
> It is built around PlayStation (PSX) emulators because that's the most common case, but nothing in it is PSX-specific. It works on **any** Cheat Engine table whose cheats live in a single block of emulated RAM.

<!-- Add a screenshot of the running app here for your repo: -->
<!-- ![Screenshot of the app](docs/screenshot.png) -->

---

## ⚡ Installation & Running

No `pip install` needed — the only requirement is Python itself (Tkinter is bundled with it on Windows and macOS).

### Windows

1. Download and install Python from **[python.org/downloads](https://www.python.org/downloads/)**
   - On the installer screen, check **"Add Python to PATH"** before clicking Install
2. Download this repository (green **Code** button → **Download ZIP**) and extract it
3. Open **Command Prompt**, navigate to the folder and run:

```cmd
python Universal_Cheat_Engine_Table_Converter.py
```

> Alternatively, just **double-click** the `.py` file if Python is associated with `.py` on your system.

### Linux

Python is usually pre-installed, but Tkinter needs to be added separately. Open a terminal and run the command for your distro:

```bash
# Debian / Ubuntu / Mint
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

Then run the script:

```bash
python3 Universal_Cheat_Engine_Table_Converter.py
```

### macOS

Tkinter is included with the official Python installer from [python.org](https://www.python.org/downloads/). Then run:

```bash
python3 Universal_Cheat_Engine_Table_Converter.py
```

---

## Table of Contents

- [Installation & Running](#installation--running)
- [Why this exists (the problem)](#why-this-exists-the-problem)
- [How it works (the idea)](#how-it-works-the-idea)
- [Features](#features)
- [Quick start (60 seconds)](#quick-start-60-seconds)
- [The two address formats you must understand](#the-two-address-formats-you-must-understand)
- [The Golden Rule](#the-golden-rule)
- [Full step-by-step tutorial](#full-step-by-step-tutorial)
- [Finding your example addresses in Cheat Engine](#finding-your-example-addresses-in-cheat-engine)
- [Worked examples](#worked-examples)
- [Working across different emulators](#working-across-different-emulators)
- [Handling the output](#handling-the-output)
- [Built-in safeguards](#built-in-safeguards)
- [Validating the result](#validating-the-result)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Limitations](#limitations)
- [How it works under the hood](#how-it-works-under-the-hood)
- [Contributing](#contributing)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## Why this exists (the problem)

A Cheat Engine table stores the **memory addresses** where a game keeps its values — money, health, stamina, item counts, and so on. Those addresses are not inside the game; they're inside the **emulator's process memory** on your PC.

Here's the catch: the emulator loads the game's RAM (for the PSX, that's its 2 MB of main RAM) as one big block somewhere in its own address space. The **position of that block moves**:

- when the emulator releases a **new version**, and
- when you load the game in a **different emulator** entirely.

When the block moves, every address in your table is wrong — but they're all wrong by *the exact same amount*, because the game's internal layout never changed. Only the starting point of the block did.

Manually fixing a 300-entry table by hand is miserable. This tool does it in one step.

---

## How it works (the idea)

Think of it like a street that got renumbered. If every house number went up by the same amount, you only need to check **one** house to know the rule for the whole street.

1. The game's RAM block sits at some **base address** in the old emulator, and a **different base address** in the new one.
2. Every value's position *within* that block is identical between the two — same game, same data.
3. Therefore, for **every** address:

   ```
   new_address  =  old_address  +  SHIFT
   ```

   …where `SHIFT` is a single constant: the difference between the two base addresses.

4. You hand the tool one known pair (e.g. *Money*). It computes:

   ```
   SHIFT  =  new_money_address  -  old_money_address
   ```

   …and applies that `SHIFT` to every `<Address>` in the file.

That's the whole trick. One known value unlocks the entire table.

> [!TIP]
> Because it's just *"old value + a constant"*, the conversion works in **any direction** and between **any** two emulators — not only the example pairs shown in this document.

---

## Features

- ✅ **One-click conversion** of an entire `.CT` table to a new memory layout.
- ✅ **Cross-emulator and cross-version** — ePSXe, No$PSX, PCSX-Redux, DuckStation, or any other Cheat Engine target.
- ✅ **Bidirectional** — convert in either direction (A → B *or* B → A).
- ✅ **Output format follows your input** — produce absolute addresses *or* module-relative addresses, automatically.
- ✅ **Up to 3 example pairs** with an automatic consistency check.
- ✅ **Safety guard** that catches the most common mistake (mismatched address formats).
- ✅ **Never overwrites your original** — always writes a separate `UPDATED_…` file.
- ✅ **Live log panel** showing exactly what it computed and did.
- ✅ **Zero external dependencies** — pure Python standard library (Tkinter).

---

## Quick start (60 seconds)

1. Launch the app.
2. **Browse .CT File** → pick the table you want to convert.
3. In **row 1**, type the same value's address from the *old* build (**Old**) and the *new* build (**New**).
4. Click **⚡ Convert Cheat Table**.
5. Open the generated `UPDATED_<yourfile>.CT` in Cheat Engine, attached to the new emulator.

Example, ePSXe → No$PSX:

| Field | Value |
|------|-------|
| **Old** | `ePSXe.exe+AF3A7C` |
| **New** | `03B2BB5C` |

That's it — every address in the table is shifted to match No$PSX.

---

## The two address formats you must understand

This is the single most important concept in the whole tool. Cheat Engine writes addresses in **two** styles, and you'll see both depending on the emulator:

### 1. Absolute address

A full runtime address, e.g. `03B2BB5C`. It's the literal location in the process's memory **right now**.

- Looks like: `03B2BB5C`, `1A2B3C4D`
- Common in: **No$PSX**, and many other targets.

### 2. Module-relative address

An offset measured **from where a module (an `.exe` or `.dll`) was loaded**, written as `Module+offset`, e.g. `ePSXe.exe+AF3A7C`.

- Looks like: `ePSXe.exe+AF3A7C`, `pcsx-redux.main+1234AB`
- Common in: **ePSXe**, and any setup where Cheat Engine anchors the address to a module.
- The part after the `+` is just an **offset number** (`AF3A7C`), *not* a full address.

> [!IMPORTANT]
> The tool always works with the **number after the `+`** when an address is module-relative. So when you type your *Old* example, it must be in the **same style the table itself uses**. If the table says `ePSXe.exe+AF3A7C`, give the tool `ePSXe.exe+AF3A7C` (or just `AF3A7C`) — **not** the absolute `01663A7C`. Mixing styles is the #1 cause of "everything came out off by a constant amount." (There's a guard for exactly this — see [Built-in safeguards](#built-in-safeguards).)

---

## The Golden Rule

Two short sentences that make everything work:

> **Old address** = paste it exactly how the **source table** writes it.
> **New address** = paste it exactly how you want the **output** to look (i.e. how the **target emulator** shows it).

The tool reads the number from your **New** address to decide the output style:

| Your **New** entry looks like… | Output addresses will be… |
|--------------------------------|----------------------------|
| `03B2BB5C` (no `+`)            | **Absolute** 8-digit hex (`03B2BB5C`) |
| `NO$PSX.EXE+1A2B3C`            | **Module-relative** (`NO$PSX.EXE+1A2B3C`) |
| `pcsx-redux.main+1234AB`       | **Module-relative** (`pcsx-redux.main+1234AB`) |

So you control the output format simply by how you type the example. Want absolute output? Type an absolute New address. Want to keep it tied to a module? Type `Module+offset`.

---

## Full step-by-step tutorial

The window has four numbered areas, top to bottom.

### Step 1 — Select Cheat Table File

Click **Browse .CT File** and choose your source table. The log panel confirms it loaded. Your original is never modified.

### Step 2 — Input Address Mapping Examples

There are three rows, each with an **Original/Old Address** box and a **New/Current Address** box. You only need to fill in **one** row, but filling in two or three lets the tool cross-check itself.

- **Old** = the address as it appears in the **source** table / old emulator.
- **New** = the address of the **same value** in the **target** emulator, written in your desired output format.

> [!TIP]
> Pick values that are easy to pin down exactly — *Money*, an item count, a timer. If you use two or three different values and they all produce the same shift, you can be confident the conversion is correct.

### Step 3 — Convert

Click **⚡ Convert Cheat Table**. The **Execution Output Log** shows:

- the shift it calculated (e.g. `Shift applied : +30380E0 Hex`),
- the output format it chose (absolute vs module-relative),
- how many addresses it adjusted,
- how many it skipped (pointers / non-hex), and
- where it saved the result.

### Step 4 — Collect your new file

A new file named **`UPDATED_<original-name>.CT`** is written **next to your source file**. That's your converted table.

---

## Finding your example addresses in Cheat Engine

To get the Old → New pair you feed the tool:

1. **Old build:** open the game in the old emulator, attach Cheat Engine, scan for a known value (e.g. your current money). Once you've narrowed it to a single address, note it **exactly as Cheat Engine displays it** — that's your *Old* format.
2. **New build:** load the **same game / same save** in the new emulator, attach Cheat Engine, and find that **same value** again. Note that address — that's your *New* format.
3. (Optional but recommended) repeat for a second and third value to fill rows 2-3 as a sanity check.

> [!NOTE]
> Use the same save state or same in-game moment in both emulators so the value is genuinely identical. A value that differs between the two runs will give you a wrong shift.

---

## Worked examples

### Example A — ePSXe → No$PSX (module-relative source, absolute output)

| Field | Value |
|------|-------|
| **Old** | `ePSXe.exe+AF3A7C` |
| **New** | `03B2BB5C` |

The tool computes:

```
old number  = AF3A7C      = 11,483,772
new number  = 03B2BB5C    = 62,045,020
SHIFT       = 62,045,020 - 11,483,772 = 50,561,248 = +30380E0
```

Every entry then moves by `+30380E0` and is written as an absolute address:

```
ePSXe.exe+AF3A7C   →   03B2BB5C     (Money)
ePSXe.exe+AF7A1A   →   03B2FAFA     (some other cheat — same shift)
ePSXe.exe+AF3A34   →   03B2BB14     (and so on, for the whole table)
```

### Example B — ePSXe → ePSXe (a version update, kept module-relative)

| Field | Value |
|------|-------|
| **Old** | `ePSXe.exe+AF3A7C` |
| **New** | `ePSXe.exe+B12A7C` |

Both sides are module-relative, so the output **stays** `ePSXe.exe+…`, just shifted. This is the classic "the emulator updated and all my cheats broke" fix.

### Example C — No$PSX → ePSXe (the reverse direction)

| Field | Value |
|------|-------|
| **Old** | `03B2BB5C` |
| **New** | `ePSXe.exe+AF3A7C` |

The shift is simply negative this time. Output is module-relative `ePSXe.exe+…`. The tool doesn't care which way you're going.

### Example D — ePSXe → PCSX-Redux / DuckStation (module-relative target)

| Field | Value |
|------|-------|
| **Old** | `ePSXe.exe+AF3A7C` |
| **New** | `pcsx-redux.main+1AF3A7C` *(use whatever Cheat Engine actually shows)* |

Because the **New** example carries a module, the output keeps that module for every entry: `pcsx-redux.main+…`.

---

## Working across different emulators

This is where the tool shines, so it's worth being explicit.

**The source can be any emulator, and the target can be any emulator.** Nothing is hard-coded to ePSXe — that's just a common starting point. The only thing that matters is the [Golden Rule](#the-golden-rule): match your **Old** to the source's format and your **New** to the target's format.

A rough reference for common PSX emulators (always verify against what Cheat Engine shows on **your** machine, because module names and absolute values vary by build, version, and OS):

| Emulator | Typical address style in Cheat Engine |
|----------|----------------------------------------|
| **ePSXe** | Module-relative — `ePSXe.exe+OFFSET` |
| **No$PSX** | Absolute — `03B2BB5C` |
| **PCSX-Redux** | Often module-relative — `Module+OFFSET` |
| **DuckStation** | Often module-relative — `Module+OFFSET` |

Practical workflow for a cross-emulator port:

1. Decide your direction (which table you have = **source**; where you want it = **target**).
2. Find one shared value (Money) in both.
3. **Old** = how the source emulator shows it. **New** = how the target emulator shows it.
4. Convert, then load the `UPDATED_` file in Cheat Engine attached to the target emulator.

> [!CAUTION]
> The single-shift trick is valid only when **all** the table's cheats live in the **same contiguous block of emulated RAM** (true for normal RAM cheats). It is not designed for tables that mix multiple modules, nor does it transform pointer chains (those are skipped on purpose — see below).

---

## Handling the output

- **Where it goes:** a new file `UPDATED_<original>.CT` in the **same folder** as your source. Your original is left untouched, so you can always re-run with different examples.
- **Load it** in Cheat Engine while it's attached to the **target** emulator/process.
- **Choose your output style deliberately:**
  - **Absolute** output (type an absolute **New** address) is simplest and is what some emulators (e.g. No$PSX) naturally show. Note that absolute addresses can shift if the target process is reloaded.
  - **Module-relative** output (type a `Module+offset` **New** address) is generally **more durable across restarts**, because Cheat Engine re-resolves the module base each time. If the target emulator's Cheat Engine shows addresses as `Module+offset`, prefer using that form for your **New** example.
- **Re-running is cheap.** If something's off, just change the example pair and convert again — you'll get a fresh `UPDATED_` file each time.

---

## Built-in safeguards

- **Never overwrites your source.** Output is always a separate `UPDATED_` copy.
- **Format-mismatch guard.** If the table is module-relative but your **Old** example looks like a full absolute address sitting far outside the table's own offset range, the tool warns you and asks before proceeding — this is the exact situation that silently shifts everything by the module base.
- **Consistency check.** If you fill in two or three example rows and they disagree on the shift, the tool warns you (and uses the first row), so a typo or a swapped Old/New doesn't slip through.
- **Pointer chains are skipped.** Any address containing `[` or `]` (a pointer expression) is left exactly as-is, since those resolve at runtime and don't shift like static addresses.
- **Non-hex / invalid entries are skipped** rather than corrupted.
- **Everything is logged** in the Execution Output Log so you can see precisely what happened.

---

## Validating the result

A 30-second check that saves headaches:

1. Open the `UPDATED_` table in Cheat Engine on the target emulator.
2. Confirm the value you mapped (e.g. Money) reads correctly.
3. **Check at least one *other* cheat** (a different value, ideally far from Money in the table). If it's also correct, the uniform shift held and the whole table is good.

If the mapped value is right but others are wrong, your cheats may not all live in one contiguous block — re-check that the table is a normal single-RAM-block table.

---

## Troubleshooting & FAQ

**Everything came out off by a constant amount.**
Your **Old** example was almost certainly in the wrong format — e.g. you pasted an absolute address (`01663A7C`) while the table is module-relative (`ePSXe.exe+AF3A7C`). Re-enter **Old** exactly as the source table shows it (with the `ePSXe.exe+` prefix, or just the offset after the `+`). The guard usually catches this and prompts you.

**`ModuleNotFoundError: No module named 'tkinter'` (Linux).**
Install Tkinter for your distro — see [Installation & Running](#installation--running).

**"No `<Address>` tags were modified."**
The selected file probably isn't a Cheat Engine table (or contains no addresses). Make sure you picked a real `.CT`.

**"Skipped (pointers / non-hex)" count is non-zero.**
That's expected and safe — pointer chains and any non-hex address are intentionally left untouched.

**My addresses work, then break after I restart the emulator.**
Use **module-relative** output if the target supports it (type a `Module+offset` **New** address). Absolute addresses can move between runs.

**My table mixes several modules / is full of pointers.**
That's outside what a single uniform shift can handle in one pass — see [Limitations](#limitations).

**Can I go from No$PSX back to ePSXe (or any other direction)?**
Yes. It's fully bidirectional — see [Example C](#example-c--nopsx--epsxe-the-reverse-direction).

---

## Limitations

- Applies **one** constant shift and **one** output format per run. Tables whose cheats span multiple independent modules aren't handled in a single pass.
- Does **not** read live process memory — you supply the example mapping yourself.
- **Pointer chains** are deliberately not transformed (they're skipped).
- Only the `<Address>` fields of the `.CT` are touched; all other table data is preserved as-is.
- The uniform-shift assumption holds for cheats located in one contiguous RAM block. Always [validate](#validating-the-result) a second cheat after converting.

---

## How it works under the hood

For the curious and for contributors, the logic is split into small, testable, GUI-free functions:

- `parse_address_token(raw)` — splits an address into `(module, hex)`, taking the number after the last `+`.
- `build_mapping(examples)` — turns the example rows into a single `SHIFT` plus the output format (module or absolute), derived from the **New** address.
- `detect_frame_mismatch(...)` — the absolute-vs-relative safety guard.
- `apply_offset_conversion(...)` — walks every `<Address>` via regex, applies `SHIFT`, re-emits in the chosen format, and skips pointers / non-hex / negative results.

The GUI is a thin Tkinter layer (`CTConverterApp`) on top of those functions, which makes the core easy to unit-test or reuse from other scripts.

---

## Contributing

Contributions are welcome! A few ideas:

- Support for additional address/table formats.
- Optional module-relative ⇆ absolute auto-detection across more emulators.
- A command-line mode for batch conversion.
- Tests around the core conversion functions.

Please open an issue to discuss larger changes before submitting a pull request.

---

## License

Released under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

## Disclaimer

This tool edits **your own** Cheat Engine tables for use in **single-player** emulation. Please use it responsibly and respect the terms of service of any game or platform — don't use cheats in online or competitive contexts.

It is **not affiliated with** Cheat Engine or with any emulator (ePSXe, No$PSX, PCSX-Redux, DuckStation, etc.). All product names, logos, and trademarks belong to their respective owners and are used here for identification only.

Always keep backups of your tables. The software is provided "as is," without warranty of any kind.
