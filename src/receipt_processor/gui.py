"""Desktop GUI for ReceiptProcessor."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

from receipt_processor.interface_options import OutputType, resolve_output_file
from receipt_processor.pipeline import run_pipeline

TKINTER_MISSING_HELP = """\
Tkinter is not available in this Python environment, so the desktop GUI cannot start.

You can still run the app from CLI:
  receipts_processor <receipts_folder>

To enable GUI support, install/use a Python build that includes Tk (tkinter),
then reinstall this package in your environment.
"""


def _load_tk_modules() -> tuple[Any, Any, Any, Any]:
    """Import tkinter modules lazily so CLI use is unaffected."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(TKINTER_MISSING_HELP) from exc
    return tk, ttk, filedialog, messagebox


class ReceiptProcessorGUI:
    """Tkinter-based desktop GUI for running the receipt pipeline."""

    def __init__(self, root: Any) -> None:
        tk, ttk, filedialog, messagebox = _load_tk_modules()
        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox

        self.root = root
        self.root.title("ReceiptProcessor")
        self.root.geometry("860x560")

        self.input_dir_var = tk.StringVar(value="data/inbox")
        self.model_file_var = tk.StringVar(value="models/model.csv")
        self.example_file_var = tk.StringVar(value="models/example.csv")
        self.output_file_var = tk.StringVar(value="")
        self.output_type_var = tk.StringVar(value=OutputType.csv.value)
        self.log_dir_var = tk.StringVar(value="logs")
        self.risk_controls_var = tk.StringVar(value="")

        self.advanced_open = False
        self.run_button: Any
        self.advanced_button: Any
        self.advanced_frame: Any
        self.status_text: Any

        self._build_ui()

    def _build_ui(self) -> None:
        ttk = self.ttk
        tk = self.tk

        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="ReceiptProcessor GUI",
            font=("TkDefaultFont", 14, "bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w")

        ttk.Label(
            container,
            text="Select your receipts folder, then run extraction.",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 12))

        ttk.Label(container, text="Receipts Folder").grid(row=2, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.input_dir_var, width=82).grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=(0, 8)
        )
        ttk.Button(container, text="Browse", command=self._pick_input_dir).grid(
            row=3, column=3, sticky="ew"
        )

        action_frame = ttk.Frame(container)
        action_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(12, 8))

        self.run_button = ttk.Button(action_frame, text="Run", command=self._run_pipeline)
        self.run_button.pack(side="left")

        self.advanced_button = ttk.Button(
            action_frame,
            text="Show Advanced \u25be",
            command=self._toggle_advanced,
        )
        self.advanced_button.pack(side="left", padx=(10, 0))

        self.advanced_frame = ttk.LabelFrame(container, text="Advanced Options", padding=12)
        self._build_advanced(self.advanced_frame)

        ttk.Label(container, text="Status").grid(row=6, column=0, sticky="w", pady=(12, 6))
        self.status_text = tk.Text(container, height=14, wrap="word")
        self.status_text.grid(row=7, column=0, columnspan=4, sticky="nsew")
        self.status_text.configure(state="disabled")

        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.columnconfigure(2, weight=1)
        container.columnconfigure(3, weight=0)
        container.rowconfigure(7, weight=1)

        self._log_status("Ready. Select a receipts folder and click Run.")

    def _build_advanced(self, frame: Any) -> None:
        ttk = self.ttk
        row = 0

        ttk.Label(frame, text="Model File").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.model_file_var, width=62).grid(
            row=row, column=1, sticky="ew", padx=(8, 8)
        )
        ttk.Button(frame, text="Browse", command=self._pick_model_file).grid(
            row=row, column=2, sticky="ew"
        )
        row += 1

        ttk.Label(frame, text="Example File").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.example_file_var, width=62).grid(
            row=row, column=1, sticky="ew", padx=(8, 8), pady=(8, 0)
        )
        ttk.Button(frame, text="Browse", command=self._pick_example_file).grid(
            row=row, column=2, sticky="ew", pady=(8, 0)
        )
        row += 1

        ttk.Label(frame, text="Output Type").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            frame,
            textvariable=self.output_type_var,
            values=[OutputType.csv.value, OutputType.xlsx.value],
            state="readonly",
            width=20,
        ).grid(row=row, column=1, sticky="w", padx=(8, 8), pady=(8, 0))
        row += 1

        ttk.Label(frame, text="Output File").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.output_file_var, width=62).grid(
            row=row, column=1, sticky="ew", padx=(8, 8), pady=(8, 0)
        )
        ttk.Button(frame, text="Browse", command=self._pick_output_file).grid(
            row=row, column=2, sticky="ew", pady=(8, 0)
        )
        row += 1

        ttk.Label(frame, text="Log Directory").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.log_dir_var, width=62).grid(
            row=row, column=1, sticky="ew", padx=(8, 8), pady=(8, 0)
        )
        ttk.Button(frame, text="Browse", command=self._pick_log_dir).grid(
            row=row, column=2, sticky="ew", pady=(8, 0)
        )
        row += 1

        ttk.Label(frame, text="Risk Controls File").grid(
            row=row, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(frame, textvariable=self.risk_controls_var, width=62).grid(
            row=row, column=1, sticky="ew", padx=(8, 8), pady=(8, 0)
        )
        ttk.Button(frame, text="Browse", command=self._pick_risk_controls_file).grid(
            row=row, column=2, sticky="ew", pady=(8, 0)
        )

        frame.columnconfigure(1, weight=1)

    def _toggle_advanced(self) -> None:
        self.advanced_open = not self.advanced_open
        if self.advanced_open:
            self.advanced_button.configure(text="Hide Advanced \u25b4")
            self.advanced_frame.grid(row=5, column=0, columnspan=4, sticky="ew")
        else:
            self.advanced_button.configure(text="Show Advanced \u25be")
            self.advanced_frame.grid_forget()

    def _pick_input_dir(self) -> None:
        selected = self.filedialog.askdirectory(title="Select receipts folder")
        if selected:
            self.input_dir_var.set(selected)

    def _pick_model_file(self) -> None:
        selected = self.filedialog.askopenfilename(
            title="Select model file",
            filetypes=[("CSV/XLSX", "*.csv *.xlsx"), ("All files", "*.*")],
        )
        if selected:
            self.model_file_var.set(selected)

    def _pick_example_file(self) -> None:
        selected = self.filedialog.askopenfilename(
            title="Select example file",
            filetypes=[("CSV/XLSX", "*.csv *.xlsx"), ("All files", "*.*")],
        )
        if selected:
            self.example_file_var.set(selected)

    def _pick_output_file(self) -> None:
        output_type = self._current_output_type()
        selected = self.filedialog.asksaveasfilename(
            title="Select output file",
            defaultextension=f".{output_type.value}",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"), ("All files", "*.*")],
        )
        if selected:
            self.output_file_var.set(selected)

    def _pick_log_dir(self) -> None:
        selected = self.filedialog.askdirectory(title="Select log directory")
        if selected:
            self.log_dir_var.set(selected)

    def _pick_risk_controls_file(self) -> None:
        selected = self.filedialog.askopenfilename(
            title="Select risk controls file",
            filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if selected:
            self.risk_controls_var.set(selected)

    def _current_output_type(self) -> OutputType:
        raw = self.output_type_var.get().strip().lower()
        if raw == OutputType.xlsx.value:
            return OutputType.xlsx
        return OutputType.csv

    def _log_status(self, message: str) -> None:
        self.status_text.configure(state="normal")
        self.status_text.insert("end", f"{message}\n")
        self.status_text.see("end")
        self.status_text.configure(state="disabled")

    def _run_pipeline(self) -> None:
        input_dir = Path(self.input_dir_var.get().strip())
        if not input_dir.exists() or not input_dir.is_dir():
            self.messagebox.showerror("Invalid Input", "Please select a valid receipts folder.")
            return

        model_file = Path(self.model_file_var.get().strip())
        example_file = Path(self.example_file_var.get().strip())
        if not model_file.exists():
            self.messagebox.showerror("Missing File", "Model file not found.")
            return
        if not example_file.exists():
            self.messagebox.showerror("Missing File", "Example file not found.")
            return

        output_file_text = self.output_file_var.get().strip()
        output_file = Path(output_file_text) if output_file_text else None
        resolved_output = resolve_output_file(
            input_dir=input_dir,
            output_file=output_file,
            output_type=self._current_output_type(),
        )

        log_dir_text = self.log_dir_var.get().strip()
        log_dir = Path(log_dir_text) if log_dir_text else None
        risk_controls_text = self.risk_controls_var.get().strip()
        risk_controls = Path(risk_controls_text) if risk_controls_text else None

        self.run_button.configure(state="disabled")
        self._log_status(f"Running extraction for: {input_dir}")

        thread = threading.Thread(
            target=self._run_pipeline_thread,
            args=(input_dir, model_file, example_file, resolved_output, log_dir, risk_controls),
            daemon=True,
        )
        thread.start()

    def _run_pipeline_thread(
        self,
        input_dir: Path,
        model_file: Path,
        example_file: Path,
        output_file: Path,
        log_dir: Path | None,
        risk_controls_file: Path | None,
    ) -> None:
        try:
            run_pipeline(
                input_dir=input_dir,
                model_file=model_file,
                example_file=example_file,
                output_file=output_file,
                log_dir=log_dir,
                risk_controls_file=risk_controls_file,
            )
            self.root.after(0, self._on_run_success, output_file)
        except Exception as exc:  # pragma: no cover - GUI error handling
            self.root.after(0, self._on_run_error, str(exc))

    def _on_run_success(self, output_file: Path) -> None:
        self._log_status(f"Completed successfully: {output_file}")
        self.run_button.configure(state="normal")

    def _on_run_error(self, error: str) -> None:
        self._log_status(f"Failed: {error}")
        self.messagebox.showerror("Run Failed", error)
        self.run_button.configure(state="normal")


def main() -> None:
    """Launch the desktop GUI."""
    tk, _, _, _ = _load_tk_modules()
    root = tk.Tk()
    ReceiptProcessorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

