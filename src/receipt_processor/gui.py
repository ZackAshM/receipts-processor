"""Desktop GUI for ReceiptProcessor."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

from receipt_processor.interface_options import OutputType, resolve_output_file
from receipt_processor.pipeline import run_pipeline
from receipt_processor.review.models import (
    ReviewDecision,
    ReviewField,
    ReviewRequest,
    RunCancelledError,
)

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

    def _handle_pipeline_warning(self, event: dict[str, object]) -> None:
        self.root.after(0, self._on_pipeline_warning, dict(event))

    def _on_pipeline_warning(self, event: dict[str, object]) -> None:
        if event.get("warning_type") != "non_blocking_contradictions":
            return
        source_file = str(event.get("source_file", "unknown"))
        details = event.get("details")
        detail_count = len(details) if isinstance(details, list) else 0
        if detail_count > 0:
            self._log_status(
                f"Warning ({source_file}): {detail_count} non-blocking contradiction(s) logged."
            )
        else:
            self._log_status(f"Warning ({source_file}): non-blocking contradictions logged.")

    def _create_gui_review_handler(self):
        def handler(request: ReviewRequest) -> ReviewDecision:
            result: dict[str, object] = {}
            ready = threading.Event()

            def show_dialog() -> None:
                try:
                    result["decision"] = self._show_review_dialog(request)
                except Exception as exc:  # pragma: no cover - GUI-specific fallback
                    result["error"] = exc
                finally:
                    ready.set()

            self.root.after(0, show_dialog)
            ready.wait()
            if "error" in result:
                raise RuntimeError(f"Review dialog failed: {result['error']}")
            decision = result.get("decision")
            if not isinstance(decision, ReviewDecision):
                raise RuntimeError("Review dialog returned invalid decision.")
            return decision

        return handler

    def _show_review_dialog(self, request: ReviewRequest) -> ReviewDecision:
        self._log_status(
            f"Review required for {request.receipt_filename}: {request.title}"
        )
        resolved_fields: dict[str, str] = {}
        for field in request.fields:
            field_result = self._show_field_dialog(request, field)
            if isinstance(field_result, ReviewDecision):
                return field_result
            resolved_fields[field.name] = field_result
        return ReviewDecision(action="resolved", resolved_fields=resolved_fields)

    def _show_field_dialog(
        self,
        request: ReviewRequest,
        field: ReviewField,
    ) -> str | ReviewDecision:
        tk = self.tk
        ttk = self.ttk
        dialog = tk.Toplevel(self.root)
        dialog.title(f"User Review - {field.display_name}")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        container = ttk.Frame(dialog, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text=request.title,
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            container,
            text=f"Receipt: {request.receipt_filename}",
        ).grid(row=1, column=0, sticky="w", pady=(2, 6))
        ttk.Label(
            container,
            text=request.message,
            wraplength=520,
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(0, 8))
        ttk.Label(
            container,
            text=f"Resolve field: {field.display_name}",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=3, column=0, sticky="w", pady=(0, 6))

        choice_var = tk.StringVar(value="manual" if not field.options else "")
        manual_var = tk.StringVar(value="")

        options_frame = ttk.Frame(container)
        options_frame.grid(row=4, column=0, sticky="ew")
        for idx, option in enumerate(field.options):
            source = option.source or "unknown"
            label = option.label or option.value
            value = f"option:{idx}"
            ttk.Radiobutton(
                options_frame,
                text=f"(from {source}) {label}",
                variable=choice_var,
                value=value,
            ).grid(row=idx, column=0, sticky="w")

        manual_row = len(field.options)
        ttk.Radiobutton(
            options_frame,
            text="Manual input:",
            variable=choice_var,
            value="manual",
        ).grid(row=manual_row, column=0, sticky="w", pady=(8, 0))
        manual_entry = ttk.Entry(options_frame, textvariable=manual_var, width=56)
        manual_entry.grid(row=manual_row + 1, column=0, sticky="ew", pady=(4, 0))

        button_frame = ttk.Frame(container)
        button_frame.grid(row=5, column=0, sticky="e", pady=(12, 0))
        outcome: dict[str, object] = {}

        def on_apply() -> None:
            choice = choice_var.get().strip()
            if choice.startswith("option:"):
                try:
                    idx = int(choice.split(":", maxsplit=1)[1])
                except ValueError:
                    self.messagebox.showerror("Invalid Selection", "Please select a valid option.")
                    return
                if 0 <= idx < len(field.options):
                    outcome["result"] = field.options[idx].value
                    dialog.destroy()
                    return
            if choice == "manual":
                manual_text = manual_var.get().strip()
                if manual_text:
                    outcome["result"] = manual_text
                    dialog.destroy()
                    return
                self.messagebox.showerror(
                    "Missing Value",
                    f"Please enter a value for {field.display_name}.",
                )
                return
            self.messagebox.showerror("Missing Selection", "Please choose an option.")

        def on_skip() -> None:
            outcome["result"] = ReviewDecision(action="skip_receipt")
            dialog.destroy()

        def on_cancel() -> None:
            outcome["result"] = ReviewDecision(action="cancel_run")
            dialog.destroy()

        ttk.Button(button_frame, text="Apply Choice", command=on_apply).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(button_frame, text="Skip Receipt", command=on_skip).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(button_frame, text="Cancel Run", command=on_cancel).pack(side="left")

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        manual_entry.focus_set()
        self.root.wait_window(dialog)
        result = outcome.get("result")
        if isinstance(result, ReviewDecision):
            return result
        return str(result or "")

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
                review_handler=self._create_gui_review_handler(),
                warning_handler=self._handle_pipeline_warning,
            )
            self.root.after(0, self._on_run_success, output_file)
        except RunCancelledError:
            self.root.after(0, self._on_run_cancelled)
        except Exception as exc:  # pragma: no cover - GUI error handling
            self.root.after(0, self._on_run_error, str(exc))

    def _on_run_success(self, output_file: Path) -> None:
        self._log_status(f"Completed successfully: {output_file}")
        self.run_button.configure(state="normal")

    def _on_run_error(self, error: str) -> None:
        self._log_status(f"Failed: {error}")
        self.messagebox.showerror("Run Failed", error)
        self.run_button.configure(state="normal")

    def _on_run_cancelled(self) -> None:
        self._log_status("Run cancelled by user.")
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
