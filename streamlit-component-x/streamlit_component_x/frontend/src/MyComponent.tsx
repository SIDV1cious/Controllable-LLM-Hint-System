import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { useEffect, useRef, useState } from "react";
import "mathlive";
import "mathlive/static.css";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "math-field": any;
    }
  }
}

const FRAME_HEIGHT = 455;
const MAX_MATRIX_SIZE = 10;
const ZERO_WIDTH_SPACE = "\u200B";

const INSERT_TEMPLATES = [
  { label: "绝对值", latex: "\\lvert#?\\rvert" },
  { label: "n次根", latex: "\\sqrt[#?]{#?}" },
  { label: "对数", latex: "\\log_{#?}{#?}" },
  { label: "导数", latex: "\\dfrac{\\mathrm{d}}{\\mathrm{d}x}#?\\bigm|_{x=#?}" },
  { label: "n阶导", latex: "\\dfrac{\\mathrm{d}^{#?}}{\\mathrm{d}x^{#?}}#?\\bigm|_{x=#?}" },
  { label: "积分", latex: "\\int_{#?}^{#?}#?\\,\\mathrm{d}#?" },
  { label: "求和", latex: "\\sum_{#?}^{#?}#?" },
  { label: "乘积", latex: "\\prod_{#?}^{#?}#?" },
  { label: "模长", latex: "\\lvert#?\\rvert" },
  { label: "辐角", latex: "\\arg(#?)" },
  { label: "实部", latex: "\\Re(#?)" },
  { label: "虚部", latex: "\\Im(#?)" },
  { label: "共轭", latex: "\\overline{#?}" },
];

const QUICK_SYMBOLS = [
  { label: "≤", latex: "\\le" },
  { label: "≥", latex: "\\ge" },
  { label: "≠", latex: "\\ne" },
  { label: "∞", latex: "\\infty" },
  { label: "α", latex: "\\alpha" },
  { label: "β", latex: "\\beta" },
  { label: "θ", latex: "\\theta" },
  { label: "π", latex: "\\pi" },
];

const MyComponent = ({ args }: ComponentProps) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const savedRangeRef = useRef<Range | null>(null);
  const formulaRefs = useRef<Record<string, any>>({});
  const activeFormulaIdRef = useRef<string | null>(null);
  const lastValueRef = useRef(args.default_value || "");
  const idCounterRef = useRef(0);

  const [matrixRows, setMatrixRows] = useState(1);
  const [matrixCols, setMatrixCols] = useState(1);

  const createId = () => `formula_${Date.now()}_${idCounterRef.current++}`;

  const refreshFrameHeight = () => {
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 0);
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 80);
  };

  const isInsideEditor = (node: Node | null) => {
    const editor = editorRef.current;
    return !!editor && !!node && editor.contains(node);
  };

  const saveSelection = () => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const range = selection.getRangeAt(0);
    if (!isInsideEditor(range.commonAncestorContainer)) return;
    if (closestFormulaChipFromNode(range.commonAncestorContainer)) return;

    savedRangeRef.current = range.cloneRange();
  };

  const setActiveFormula = (id: string | null) => {
    activeFormulaIdRef.current = id;
    const editor = editorRef.current;
    if (!editor) return;

    editor.querySelectorAll<HTMLElement>(".inline-formula-chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.formulaId === id);
    });
  };

  const getEditorRange = () => {
    const editor = editorRef.current;
    if (!editor) return null;

    const selection = window.getSelection();
    if (
      selection &&
      selection.rangeCount > 0 &&
      isInsideEditor(selection.getRangeAt(0).commonAncestorContainer)
    ) {
      const range = selection.getRangeAt(0);
      const formulaChip = closestFormulaChipFromNode(range.commonAncestorContainer);
      if (!formulaChip) return range;

      const afterFormula = document.createRange();
      afterFormula.setStartAfter(formulaChip);
      afterFormula.collapse(true);
      return afterFormula;
    }

    if (
      savedRangeRef.current &&
      isInsideEditor(savedRangeRef.current.commonAncestorContainer) &&
      !closestFormulaChipFromNode(savedRangeRef.current.commonAncestorContainer)
    ) {
      return savedRangeRef.current.cloneRange();
    }

    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    return range;
  };

  const setCaretAfter = (node: Node) => {
    const selection = window.getSelection();
    if (!selection) return;

    const range = document.createRange();
    range.setStartAfter(node);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    savedRangeRef.current = range.cloneRange();
  };

  const syncValue = () => {
    const editor = editorRef.current;
    if (!editor) return;

    const value = serializeEditor(editor);
    lastValueRef.current = value;
    Streamlit.setComponentValue(value);
    refreshFrameHeight();
  };

  const removeFormula = (chip: HTMLElement) => {
    const next = chip.nextSibling;
    const previous = chip.previousSibling;

    if (isZeroWidthText(next)) next.remove();
    if (isZeroWidthText(previous)) previous.remove();

    chip.remove();
    syncValue();

    const editor = editorRef.current;
    if (!editor) return;

    editor.focus();
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    savedRangeRef.current = range.cloneRange();
  };

  const createFormulaElement = (latex = "") => {
    const id = createId();
    const chip = document.createElement("span");
    chip.className = "inline-formula-chip";
    chip.dataset.formulaId = id;
    chip.dataset.latex = latex;
    chip.contentEditable = "false";

    const mathField = document.createElement("math-field") as any;
    mathField.className = "inline-formula-field";
    mathField.value = latex;
    mathField.setAttribute("math-virtual-keyboard-policy", "manual");
    mathField.setAttribute("max-matrix-cols", String(MAX_MATRIX_SIZE));

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "inline-formula-remove";
    removeButton.textContent = "x";
    removeButton.title = "删除公式框";

    chip.append(mathField, removeButton);
    formulaRefs.current[id] = mathField;

    chip.addEventListener("mousedown", (event) => {
      event.stopPropagation();
      setActiveFormula(id);
    });

    chip.addEventListener("click", () => {
      setActiveFormula(id);
      mathField.focus();
    });

    mathField.addEventListener("focus", () => {
      setActiveFormula(id);
    });

    mathField.addEventListener("keydown", (event: KeyboardEvent) => {
      event.stopPropagation();
    });

    mathField.addEventListener("input", (event: Event) => {
      event.stopPropagation();
      chip.dataset.latex = mathField.value || "";
      syncValue();
    });

    removeButton.addEventListener("mousedown", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });

    removeButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      delete formulaRefs.current[id];
      removeFormula(chip);
    });

    window.setTimeout(() => configureMathField(mathField), 0);

    return { id, chip, mathField };
  };

  const insertPlainText = (text: string) => {
    const range = getEditorRange();
    if (!range) return;

    range.deleteContents();
    const textNode = document.createTextNode(text);
    range.insertNode(textNode);
    setCaretAfter(textNode);
    syncValue();
  };

  const insertFormulaBox = (initialLatex = "") => {
    const editor = editorRef.current;
    const range = getEditorRange();
    if (!editor || !range) return;

    const { id, chip, mathField } = createFormulaElement("");
    const spacer = document.createTextNode(ZERO_WIDTH_SPACE);

    range.deleteContents();
    range.insertNode(spacer);
    range.insertNode(chip);
    setCaretAfter(spacer);
    setActiveFormula(id);
    syncValue();

    window.setTimeout(() => {
      mathField.focus();
      if (initialLatex) {
        insertIntoMathField(mathField, initialLatex);
        chip.dataset.latex = mathField.value || "";
        syncValue();
      }
    }, 0);
  };

  const getActiveMathField = () => {
    const activeId = activeFormulaIdRef.current;
    const activeField = activeId ? formulaRefs.current[activeId] : null;
    if (activeField?.isConnected) return activeField;

    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0) {
      const selectionChip = closestFormulaChipFromNode(
        selection.getRangeAt(0).commonAncestorContainer
      );
      const selectionId = selectionChip?.dataset.formulaId || null;
      const selectionField = selectionId ? formulaRefs.current[selectionId] : null;
      if (selectionField?.isConnected) {
        setActiveFormula(selectionId);
        return selectionField;
      }
    }

    const focusedChip = closestFormulaChipFromNode(document.activeElement);
    const focusedId = focusedChip?.dataset.formulaId || null;
    const focusedField = focusedId ? formulaRefs.current[focusedId] : null;
    if (focusedField?.isConnected) {
      setActiveFormula(focusedId);
      return focusedField;
    }

    const selectedChip = editorRef.current?.querySelector<HTMLElement>(
      ".inline-formula-chip.active"
    );
    const selectedId = selectedChip?.dataset.formulaId || null;
    const selectedField = selectedId ? formulaRefs.current[selectedId] : null;
    if (selectedField?.isConnected) {
      setActiveFormula(selectedId);
      return selectedField;
    }

    return null;
  };

  const insertLatexIntoFormula = (latex: string) => {
    const mathField = getActiveMathField();

    if (!mathField) {
      insertFormulaBox(latex);
      return;
    }

    insertIntoMathField(mathField, latex);

    const chip = mathField.closest(".inline-formula-chip") as HTMLElement | null;
    if (chip) chip.dataset.latex = mathField.value || "";
    syncValue();
  };

  const insertMatrix = () => {
    const rows = Math.min(Math.max(matrixRows, 1), MAX_MATRIX_SIZE);
    const cols = Math.min(Math.max(matrixCols, 1), MAX_MATRIX_SIZE);
    const body = Array.from({ length: rows }, () =>
      Array.from({ length: cols }, () => "#?").join(" & ")
    ).join(" \\\\ ");

    insertLatexIntoFormula(`\\begin{pmatrix}${body}\\end{pmatrix}`);
  };

  const openVirtualKeyboard = () => {
    const mathField = getActiveMathField();

    if (!mathField) {
      insertFormulaBox();
      window.setTimeout(() => {
        const nextField = getActiveMathField();
        if (nextField) showVirtualKeyboard(nextField);
      }, 80);
      return;
    }

    showVirtualKeyboard(mathField);
  };

  const removeAdjacentFormula = (direction: "backward" | "forward") => {
    const range = getEditorRange();
    if (!range || !range.collapsed) return false;

    const candidate =
      direction === "backward"
        ? getNodeBeforeRange(range)
        : getNodeAfterRange(range);
    const formula = findFormulaChip(candidate);
    if (!formula) return false;

    delete formulaRefs.current[formula.dataset.formulaId || ""];
    removeFormula(formula);
    return true;
  };

  const handleEditorKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      insertPlainText("\n");
      return;
    }

    if (event.key === "Backspace" && removeAdjacentFormula("backward")) {
      event.preventDefault();
      return;
    }

    if (event.key === "Delete" && removeAdjacentFormula("forward")) {
      event.preventDefault();
    }
  };

  const handlePaste = (event: React.ClipboardEvent<HTMLDivElement>) => {
    const text = event.clipboardData.getData("text/plain");
    if (!text) return;

    event.preventDefault();
    insertPlainText(text);
  };

  const renderValue = (value: string) => {
    const editor = editorRef.current;
    if (!editor) return;

    formulaRefs.current = {};
    editor.innerHTML = "";

    const pattern = /\$([^$]*)\$/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(value)) !== null) {
      if (match.index > lastIndex) {
        editor.append(document.createTextNode(value.slice(lastIndex, match.index)));
      }

      const { chip } = createFormulaElement(match[1]);
      editor.append(chip, document.createTextNode(ZERO_WIDTH_SPACE));
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < value.length) {
      editor.append(document.createTextNode(value.slice(lastIndex)));
    }

    setActiveFormula(null);
    refreshFrameHeight();
  };

  useEffect(() => {
    renderValue(args.default_value || "");
    lastValueRef.current = args.default_value || "";
  }, []);

  useEffect(() => {
    const style = document.createElement("style");
    style.innerHTML = `
      html, body {
        margin: 0;
        padding: 0;
        overflow: hidden !important;
        background: white;
      }

      .mixed-editor {
        caret-color: #111827;
      }

      .mixed-editor:focus {
        border-color: #2563eb;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.10);
      }

      .inline-formula-chip {
        display: inline-flex;
        align-items: center;
        vertical-align: baseline;
        max-width: min(340px, 80vw);
        min-width: 92px;
        min-height: 34px;
        margin: 0 3px;
        padding: 2px 5px;
        border: 1px solid #a3a3a3;
        border-radius: 2px;
        background: #eeeeee;
        box-sizing: border-box;
        white-space: nowrap;
      }

      .inline-formula-chip.active {
        border-color: #2563eb;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
        background: #f8fbff;
      }

      .inline-formula-field {
        display: inline-block;
        width: 100%;
        min-width: 72px;
        max-width: 300px;
        min-height: 28px;
        border: 0;
        padding: 2px 4px;
        background: transparent;
        font-size: 18px;
        outline: none;
        overflow-x: auto;
      }

      .inline-formula-field::part(menu-toggle),
      .inline-formula-field::part(virtual-keyboard-toggle) {
        display: none;
      }

      .inline-formula-remove {
        flex: 0 0 auto;
        width: 18px;
        height: 22px;
        margin-left: 2px;
        border: 0;
        border-left: 1px solid #c7c7c7;
        background: transparent;
        color: #6b7280;
        cursor: pointer;
        font-size: 14px;
        line-height: 1;
      }

      .inline-formula-remove:hover {
        color: #b91c1c;
      }
    `;
    document.head.appendChild(style);
    refreshFrameHeight();

    return () => {
      document.head.removeChild(style);
    };
  }, []);

  return (
    <div style={containerStyle}>
      <div style={toolbarHeaderStyle}>
        <button
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => insertFormulaBox()}
          style={primaryButtonStyle}
        >
          插入公式框
        </button>

        <button
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={openVirtualKeyboard}
          style={toolButtonStyle}
        >
          虚拟键盘
        </button>
      </div>

      <div style={toolbarStyle}>
        {INSERT_TEMPLATES.map((item) => (
          <button
            key={item.label}
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => insertLatexIntoFormula(item.latex)}
            style={toolButtonStyle}
          >
            {item.label}
          </button>
        ))}
        {QUICK_SYMBOLS.map((item) => (
          <button
            key={item.label}
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => insertLatexIntoFormula(item.latex)}
            style={toolButtonStyle}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div style={matrixRowStyle}>
        <div style={matrixPanelStyle}>
          <span style={{ fontSize: "12px", color: "#536075" }}>矩阵</span>
          <select
            value={matrixRows}
            onChange={(event) => setMatrixRows(Number(event.target.value))}
            onMouseDown={(event) => event.stopPropagation()}
            style={selectStyle}
          >
            {Array.from({ length: MAX_MATRIX_SIZE }, (_, index) => index + 1).map(
              (n) => (
                <option key={n} value={n}>
                  {n}行
                </option>
              )
            )}
          </select>
          <select
            value={matrixCols}
            onChange={(event) => setMatrixCols(Number(event.target.value))}
            onMouseDown={(event) => event.stopPropagation()}
            style={selectStyle}
          >
            {Array.from({ length: MAX_MATRIX_SIZE }, (_, index) => index + 1).map(
              (n) => (
                <option key={n} value={n}>
                  {n}列
                </option>
              )
            )}
          </select>
          <button
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onClick={insertMatrix}
            style={toolButtonStyle}
          >
            插入矩阵
          </button>
        </div>
      </div>

      <div
        ref={editorRef}
        className="mixed-editor"
        contentEditable
        suppressContentEditableWarning
        onFocus={() => {
          setActiveFormula(null);
          saveSelection();
        }}
        onMouseUp={saveSelection}
        onKeyUp={saveSelection}
        onInput={() => {
          saveSelection();
          syncValue();
        }}
        onKeyDown={handleEditorKeyDown}
        onPaste={handlePaste}
        style={editorStyle}
      />
    </div>
  );
};

const serializeEditor = (root: HTMLElement) => {
  let value = "";

  const visit = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      value += (node.textContent || "").replaceAll(ZERO_WIDTH_SPACE, "");
      return;
    }

    if (!(node instanceof HTMLElement)) return;

    if (node.classList.contains("inline-formula-chip")) {
      const mathField = node.querySelector("math-field") as any;
      const latex = (mathField?.value || node.dataset.latex || "").trim();
      if (latex) value += `$${latex}$`;
      return;
    }

    if (node.tagName === "BR") {
      value += "\n";
      return;
    }

    node.childNodes.forEach(visit);
  };

  root.childNodes.forEach(visit);
  return value;
};

const insertIntoMathField = (mathField: any, latex: string) => {
  configureMathField(mathField);
  mathField.focus();
  mathField.insert(latex, {
    mode: "math",
    format: "latex",
    selectionMode: "placeholder",
    focus: true,
  });
};

const showVirtualKeyboard = (mathField: any) => {
  configureMathField(mathField);
  mathField.focus();

  trySetMathFieldOption(() => {
    mathField.executeCommand?.("showVirtualKeyboard");
  });

  trySetMathFieldOption(() => {
    (window as any).mathVirtualKeyboard?.show?.();
  });
};

const configureMathField = (mathField: any, attempt = 0) => {
  if (!mathField.isConnected) {
    if (attempt < 10) {
      window.setTimeout(() => configureMathField(mathField, attempt + 1), 30);
    }
    return;
  }

  trySetMathFieldOption(() => {
    mathField.defaultMode = "math";
  });
  trySetMathFieldOption(() => {
    mathField.mathVirtualKeyboardPolicy = "manual";
  });
  trySetMathFieldOption(() => {
    mathField.smartFence = true;
  });
  trySetMathFieldOption(() => {
    mathField.maxMatrixCols = MAX_MATRIX_SIZE;
  });
  trySetMathFieldOption(() => {
    mathField.menuItems = [];
  });
};

const trySetMathFieldOption = (setter: () => void) => {
  try {
    setter();
  } catch {
    // Some MathLive properties are not writable until its internal model mounts.
  }
};

const isZeroWidthText = (node: Node | null): node is Text =>
  node?.nodeType === Node.TEXT_NODE &&
  (node.textContent || "").replaceAll(ZERO_WIDTH_SPACE, "") === "";

const isFormulaChip = (node: Node | null): node is HTMLElement =>
  node instanceof HTMLElement && node.classList.contains("inline-formula-chip");

const closestFormulaChipFromNode = (node: Node | null) => {
  if (!node) return null;
  if (isFormulaChip(node)) return node;

  const element =
    node instanceof HTMLElement ? node : node.parentElement || null;
  return element?.closest<HTMLElement>(".inline-formula-chip") || null;
};

const findFormulaChip = (node: Node | null) => {
  if (isFormulaChip(node)) return node;
  if (isZeroWidthText(node)) {
    if (isFormulaChip(node.previousSibling)) return node.previousSibling;
    if (isFormulaChip(node.nextSibling)) return node.nextSibling;
  }
  return null;
};

const getNodeBeforeRange = (range: Range) => {
  const { startContainer, startOffset } = range;

  if (startContainer.nodeType === Node.TEXT_NODE) {
    const textBefore = (startContainer.textContent || "").slice(0, startOffset);
    if (textBefore.replaceAll(ZERO_WIDTH_SPACE, "") === "") {
      return startContainer.previousSibling;
    }
    return null;
  }

  return startContainer.childNodes[startOffset - 1] || null;
};

const getNodeAfterRange = (range: Range) => {
  const { startContainer, startOffset } = range;

  if (startContainer.nodeType === Node.TEXT_NODE) {
    const textAfter = (startContainer.textContent || "").slice(startOffset);
    if (textAfter.replaceAll(ZERO_WIDTH_SPACE, "") === "") {
      return startContainer.nextSibling;
    }
    return null;
  }

  return startContainer.childNodes[startOffset] || null;
};

const containerStyle: React.CSSProperties = {
  background: "white",
  border: "1px solid #d9dee8",
  borderRadius: "8px",
  padding: "10px",
  height: "420px",
  boxSizing: "border-box",
  overflow: "hidden",
};

const toolbarHeaderStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "8px",
  marginBottom: "8px",
  flexWrap: "wrap",
};

const matrixPanelStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "6px",
  flexWrap: "wrap",
};

const matrixRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  gap: "8px",
  marginBottom: "8px",
};

const toolbarStyle: React.CSSProperties = {
  display: "flex",
  gap: "6px",
  flexWrap: "wrap",
  marginBottom: "8px",
};

const primaryButtonStyle: React.CSSProperties = {
  border: "1px solid #2563eb",
  background: "#2563eb",
  color: "white",
  borderRadius: "7px",
  padding: "6px 12px",
  fontSize: "13px",
  fontWeight: 700,
  cursor: "pointer",
  minHeight: "32px",
};

const toolButtonStyle: React.CSSProperties = {
  border: "1px solid #cfd6e3",
  background: "#f8fafc",
  color: "#263244",
  borderRadius: "7px",
  padding: "5px 9px",
  fontSize: "12px",
  cursor: "pointer",
  minHeight: "28px",
};

const selectStyle: React.CSSProperties = {
  border: "1px solid #cfd6e3",
  borderRadius: "6px",
  background: "white",
  color: "#263244",
  fontSize: "12px",
  height: "30px",
};

const editorStyle: React.CSSProperties = {
  width: "100%",
  height: "210px",
  boxSizing: "border-box",
  overflowY: "auto",
  border: "1px solid #d9dee8",
  borderRadius: "8px",
  padding: "13px",
  outline: "none",
  background: "white",
  color: "#111827",
  fontSize: "18px",
  lineHeight: 1.75,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  fontFamily:
    "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

export default withStreamlitConnection(MyComponent);
