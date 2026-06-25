from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional

from .color_pick_service import run_color_pick
from .config_schema import BuildingClassConfig
from .i18n import t


class BuildingTypesTab(ttk.Frame):
    """Searchable building-type list with add / inspect / update / delete."""

    _COLUMNS = (
        "class_id", "label_zh", "label_en", "color_zh", "color_hex",
        "calibrated", "examples_zh", "footprints",
    )

    def __init__(
        self,
        parent: tk.Widget,
        get_camera_settings: Callable[[], tuple[int, int, int, int]],
        **kwargs,
    ) -> None:
        super().__init__(parent, padding=12, **kwargs)
        self._get_camera_settings = get_camera_settings
        self._all_classes: List[BuildingClassConfig] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(toolbar, text=t("lbl_search")).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=28)
        search_entry.pack(side=tk.LEFT, padx=(4, 8))
        search_entry.bind("<KeyRelease>", lambda _e: self._apply_filter())
        ttk.Button(toolbar, text=t("btn_search"), command=self._apply_filter).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(toolbar, text=t("btn_clear_search"), command=self._clear_search).pack(side=tk.LEFT)

        list_frame = ttk.LabelFrame(self, text=t("sect_building_list"), padding=6)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        col_heads = {
            "class_id": t("col_class_id"),
            "label_zh": t("lbl_label_zh"),
            "label_en": t("lbl_label_en"),
            "color_zh": t("lbl_color_name_zh"),
            "color_hex": t("col_color_hex"),
            "calibrated": t("col_calibrated"),
            "examples_zh": t("lbl_examples_zh"),
            "footprints": t("col_footprints"),
        }
        col_widths = {
            "class_id": 55, "label_zh": 90, "label_en": 100, "color_zh": 70,
            "color_hex": 75, "calibrated": 70, "examples_zh": 120, "footprints": 90,
        }

        self.tree = ttk.Treeview(list_frame, columns=self._COLUMNS, show="headings", height=16)
        for col in self._COLUMNS:
            self.tree.heading(col, text=col_heads[col])
            self.tree.column(col, width=col_widths[col], anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_selected)
        self.tree.bind("<Double-1>", lambda _e: self._inspect_selected())

        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        list_btns = ttk.Frame(list_frame)
        list_btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(list_btns, text=t("btn_add"), command=self._add).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(list_btns, text=t("btn_delete"), command=self._delete).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(list_btns, text=t("btn_inspect"), command=self._inspect_selected).pack(side=tk.LEFT, padx=(0, 4))
        self.count_var = tk.StringVar(value=t("building_count_fmt", n=0))
        ttk.Label(list_btns, textvariable=self.count_var).pack(side=tk.RIGHT)

        detail = ttk.LabelFrame(self, text=t("lbl_edit"), padding=8)
        detail.grid(row=1, column=1, sticky="nsew")
        for i in range(6):
            detail.columnconfigure(i, weight=1)

        self.class_id_var = tk.StringVar()
        self.class_label_zh_var = tk.StringVar()
        self.class_label_en_var = tk.StringVar()
        self.class_color_zh_var = tk.StringVar()
        self.class_color_en_var = tk.StringVar()
        self.class_color_hex_var = tk.StringVar()
        self.class_calibrated_lab_var = tk.StringVar()
        self.class_examples_zh_var = tk.StringVar()
        self.class_examples_en_var = tk.StringVar()
        self.class_fixed_var = tk.BooleanVar(value=False)
        self.class_footprints_var = tk.StringVar()

        self._add_field(detail, t("lbl_class_id"), self.class_id_var, 0, 0)
        self._add_field(detail, t("lbl_label_zh"), self.class_label_zh_var, 1, 0)
        self._add_field(detail, t("lbl_label_en"), self.class_label_en_var, 2, 0)
        self._add_field(detail, t("lbl_color_name_zh"), self.class_color_zh_var, 3, 0)
        self._add_field(detail, t("lbl_color_name_en"), self.class_color_en_var, 4, 0)
        self._add_field(detail, t("lbl_color_hex"), self.class_color_hex_var, 5, 0)
        self._add_field(detail, t("lbl_calib_lab"), self.class_calibrated_lab_var, 6, 0)
        self._add_field(detail, t("lbl_examples_zh"), self.class_examples_zh_var, 7, 0)
        self._add_field(detail, t("lbl_examples_en"), self.class_examples_en_var, 8, 0)
        self._add_field(detail, t("lbl_footprints"), self.class_footprints_var, 9, 0)
        ttk.Checkbutton(detail, text=t("chk_fixed"), variable=self.class_fixed_var).grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(6, 0),
        )

        detail_btns = ttk.Frame(detail)
        detail_btns.grid(row=11, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        ttk.Button(detail_btns, text=t("btn_save_type"), command=self._save).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(detail_btns, text=t("btn_color_pick"), command=self._color_pick).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(detail_btns, text=t("btn_new_blank"), command=self._clear_form).pack(side=tk.LEFT)

        ttk.Label(self, text=t("building_tab_hint"), wraplength=900, foreground="#555").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0),
        )

    def _add_field(self, parent: ttk.LabelFrame, label: str, variable: tk.StringVar, row: int, col: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=col + 1, sticky="ew", pady=3, padx=(0, 8))

    def _calibrated_label(self, cls: BuildingClassConfig) -> str:
        if cls.calibrated_lab and len(cls.calibrated_lab) == 3:
            return t("yes")
        return t("no")

    def _row_values(self, cls: BuildingClassConfig) -> tuple:
        return (
            cls.class_id,
            cls.label,
            cls.label_en,
            cls.color_name,
            cls.color_hex,
            self._calibrated_label(cls),
            cls.building_examples,
            ",".join(cls.allowed_footprints),
        )

    def _class_from_form(self) -> Optional[BuildingClassConfig]:
        if not self._validate_form():
            return None
        lab_raw = self.class_calibrated_lab_var.get().strip()
        calibrated_lab = [float(v) for v in lab_raw.split(",") if v.strip()] if lab_raw else []
        return BuildingClassConfig(
            class_id=int(self.class_id_var.get()),
            label=self.class_label_zh_var.get().strip(),
            label_en=self.class_label_en_var.get().strip(),
            color_name=self.class_color_zh_var.get().strip(),
            color_name_en=self.class_color_en_var.get().strip(),
            color_hex=self.class_color_hex_var.get().strip(),
            building_examples=self.class_examples_zh_var.get().strip(),
            building_examples_en=self.class_examples_en_var.get().strip(),
            is_fixed_default=self.class_fixed_var.get(),
            allowed_footprints=[s.strip() for s in self.class_footprints_var.get().split(",") if s.strip()] or ["1x1"],
            calibrated_lab=calibrated_lab,
        )

    def _validate_form(self) -> bool:
        if not self.class_id_var.get().strip():
            messagebox.showerror(t("dlg_input_error"), t("dlg_class_id_empty"))
            return False
        if not self.class_label_zh_var.get().strip():
            messagebox.showerror(t("dlg_input_error"), t("dlg_label_empty"))
            return False
        if not self.class_label_en_var.get().strip():
            messagebox.showerror(t("dlg_input_error"), t("dlg_label_en_empty"))
            return False
        if not self.class_color_zh_var.get().strip() or not self.class_color_en_var.get().strip():
            messagebox.showerror(t("dlg_input_error"), t("dlg_color_en_empty"))
            return False
        if not self.class_color_hex_var.get().startswith("#"):
            messagebox.showerror(t("dlg_input_error"), t("dlg_hex_prefix"))
            return False
        try:
            int(self.class_id_var.get())
        except ValueError:
            messagebox.showerror(t("dlg_input_error"), t("dlg_class_id_int"))
            return False
        return True

    def _next_class_id(self) -> int:
        if not self._all_classes:
            return 1
        return max(c.class_id for c in self._all_classes) + 1

    def _apply_filter(self) -> None:
        query = self.search_var.get().strip().lower()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        shown = 0
        for cls in self._all_classes:
            haystack = " ".join([
                str(cls.class_id), cls.label, cls.label_en,
                cls.color_name, cls.color_name_en, cls.color_hex,
                cls.building_examples, cls.building_examples_en,
                ",".join(cls.allowed_footprints),
            ]).lower()
            if query and query not in haystack:
                continue
            self.tree.insert("", tk.END, iid=f"class-{cls.class_id}", values=self._row_values(cls))
            shown += 1
        self.count_var.set(t("building_count_fmt", n=shown, total=len(self._all_classes)))

    def _clear_search(self) -> None:
        self.search_var.set("")
        self._apply_filter()

    def load_classes(self, classes: List[BuildingClassConfig]) -> None:
        self._all_classes = list(classes)
        self._apply_filter()

    def collect_classes(self) -> List[BuildingClassConfig]:
        return list(self._all_classes)

    def _on_selected(self, _event: object) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        cls = self._find_class(int(self.tree.item(sel[0], "values")[0]))
        if cls:
            self._fill_form(cls)

    def _find_class(self, class_id: int) -> Optional[BuildingClassConfig]:
        for cls in self._all_classes:
            if cls.class_id == class_id:
                return cls
        return None

    def _fill_form(self, cls: BuildingClassConfig) -> None:
        self.class_id_var.set(str(cls.class_id))
        self.class_label_zh_var.set(cls.label)
        self.class_label_en_var.set(cls.label_en)
        self.class_color_zh_var.set(cls.color_name)
        self.class_color_en_var.set(cls.color_name_en)
        self.class_color_hex_var.set(cls.color_hex)
        lab_str = ",".join(f"{v:.1f}" for v in cls.calibrated_lab) if cls.calibrated_lab else ""
        self.class_calibrated_lab_var.set(lab_str)
        self.class_examples_zh_var.set(cls.building_examples)
        self.class_examples_en_var.set(cls.building_examples_en)
        self.class_fixed_var.set(cls.is_fixed_default)
        self.class_footprints_var.set(",".join(cls.allowed_footprints))

    def _clear_form(self) -> None:
        self.class_id_var.set(str(self._next_class_id()))
        self.class_label_zh_var.set("")
        self.class_label_en_var.set("")
        self.class_color_zh_var.set("")
        self.class_color_en_var.set("")
        self.class_color_hex_var.set("#000000")
        self.class_calibrated_lab_var.set("")
        self.class_examples_zh_var.set("")
        self.class_examples_en_var.set("")
        self.class_fixed_var.set(False)
        self.class_footprints_var.set("1x1")

    def _add(self) -> None:
        self._clear_form()
        self.tree.selection_remove(self.tree.selection())

    def _save(self) -> None:
        cls = self._class_from_form()
        if cls is None:
            return
        existing = self._find_class(cls.class_id)
        if existing is None:
            self._all_classes.append(cls)
        else:
            idx = self._all_classes.index(existing)
            self._all_classes[idx] = cls
        self._apply_filter()
        self.tree.selection_set(f"class-{cls.class_id}")
        messagebox.showinfo(t("btn_save_type"), t("building_saved_fmt", name=cls.label))

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(t("dlg_no_select"), t("dlg_select_del"))
            return
        class_id = int(self.tree.item(sel[0], "values")[0])
        cls = self._find_class(class_id)
        if cls is None:
            return
        if not messagebox.askyesno(t("btn_delete"), t("building_delete_confirm", name=cls.label)):
            return
        self._all_classes = [c for c in self._all_classes if c.class_id != class_id]
        self._apply_filter()
        self._clear_form()

    def _inspect_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(t("dlg_no_select"), t("dlg_select_row"))
            return
        cls = self._find_class(int(self.tree.item(sel[0], "values")[0]))
        if cls is None:
            return
        lab = ",".join(f"{v:.1f}" for v in cls.calibrated_lab) if cls.calibrated_lab else t("not_calibrated")
        messagebox.showinfo(
            t("btn_inspect"),
            t(
                "building_inspect_fmt",
                cid=cls.class_id,
                zh=cls.label,
                en=cls.label_en,
                color_zh=cls.color_name,
                color_en=cls.color_name_en,
                hex=cls.color_hex,
                lab=lab,
                ex_zh=cls.building_examples or "-",
                ex_en=cls.building_examples_en or "-",
                footprints=",".join(cls.allowed_footprints),
                fixed=t("yes") if cls.is_fixed_default else t("no"),
            ),
        )

    def _color_pick(self) -> None:
        try:
            idx, w, h, fps = self._get_camera_settings()
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num"))
            return
        label = self.class_label_zh_var.get().strip() or self.class_label_en_var.get().strip() or "?"
        messagebox.showinfo(t("dlg_color_hint_title"), t("dlg_color_hint", label=label))
        result = run_color_pick(idx, w, h, fps, class_label=label)
        if result is None:
            messagebox.showwarning(t("dlg_color_result"), t("dlg_color_fail"))
            return
        lab_str = ",".join(f"{v:.1f}" for v in result.lab_values)
        self.class_calibrated_lab_var.set(lab_str)
        self.class_color_hex_var.set(result.hex_color)
        messagebox.showinfo(t("dlg_color_result"), t("dlg_color_ok", lab=lab_str, hex=result.hex_color))
