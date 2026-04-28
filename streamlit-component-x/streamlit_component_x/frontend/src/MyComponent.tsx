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

type FormulaItem = {
  label: string;
  latex?: string;
  kind?: "cases";
};

type FormulaGroup = {
  title: string;
  items: FormulaItem[];
};

const FRAME_HEIGHT = 520;
const MAX_MATRIX_SIZE = 10;
const ZERO_WIDTH_SPACE = "\u200B";
const COMMON_SYMBOLS_TITLE = "常用符号";
const MATHFIELD_PLACEHOLDER_STYLE_ID = "hint-placeholder-style";
const ACCENT_TEMPLATE_PATTERN = /^\\(vec|hat|dot|ddot|overline)\{#\?\}$/;
const CASES_SEGMENT_COUNTS = [2, 3, 4, 5];

const FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "分式/上下标",
    items: [
      { label: "分式", latex: "\\frac{#?}{#?}" },
      { label: "斜分式", latex: "#?/#?" },
      { label: "上标", latex: "#?^{#?}" },
      { label: "下标", latex: "#?_{#?}" },
      { label: "上下标", latex: "#?_{#?}^{#?}" },
    ],
  },
  {
    title: "根式",
    items: [
      { label: "平方根", latex: "\\sqrt{#?}" },
      { label: "n次根", latex: "\\sqrt[#?]{#?}" },
    ],
  },
  {
    title: "积分",
    items: [
      { label: "积分", latex: "\\int_{#?}^{#?}#?\\,\\mathrm{d}#?" },
      { label: "二重积分", latex: "\\iint_{#?}#?\\,\\mathrm{d}#?" },
      { label: "三重积分", latex: "\\iiint_{#?}#?\\,\\mathrm{d}#?" },
      { label: "闭合积分", latex: "\\oint_{#?}#?\\,\\mathrm{d}#?" },
    ],
  },
  {
    title: "运算",
    items: [
      { label: "求和", latex: "\\sum_{#?}^{#?}#?" },
      { label: "乘积", latex: "\\prod_{#?}^{#?}#?" },
      { label: "并集", latex: "\\bigcup_{#?}^{#?}#?" },
      { label: "交集", latex: "\\bigcap_{#?}^{#?}#?" },
    ],
  },
  {
    title: "括号",
    items: [
      { label: "圆括号", latex: "\\left(#?\\right)" },
      { label: "方括号", latex: "\\left[#?\\right]" },
      { label: "大括号", latex: "\\left\\{#?\\right\\}" },
      { label: "绝对值", latex: "\\left|#?\\right|" },
      { label: "范数", latex: "\\left\\|#?\\right\\|" },
    ],
  },
  {
    title: "函数",
    items: [
      { label: "sin", latex: "\\sin(#?)" },
      { label: "cos", latex: "\\cos(#?)" },
      { label: "tan", latex: "\\tan(#?)" },
      { label: "ln", latex: "\\ln(#?)" },
      { label: "log", latex: "\\log_{#?}{#?}" },
      { label: "exp", latex: "\\exp(#?)" },
      { label: "lim", latex: "\\lim_{#?\\to#?}#?" },
      { label: "分段函数", kind: "cases" },
    ],
  },
  {
    title: "导数",
    items: [
      { label: "导数", latex: "\\frac{\\mathrm{d}}{\\mathrm{d}#?}#?" },
      { label: "n阶导", latex: "\\frac{\\mathrm{d}^{#?}}{\\mathrm{d}#?^{#?}}#?" },
      { label: "偏导", latex: "\\frac{\\partial}{\\partial #?}#?" },
      { label: "n阶偏导", latex: "\\frac{\\partial^{#?}}{\\partial #?^{#?}}#?" },
    ],
  },
  {
    title: "标注",
    items: [
      { label: "向量", latex: "\\vec{#?}" },
      { label: "帽子", latex: "\\hat{#?}" },
      { label: "上划线", latex: "\\overline{#?}" },
      { label: "点", latex: "\\dot{#?}" },
      { label: "二重点", latex: "\\ddot{#?}" },
      { label: "共轭", latex: "\\overline{#?}" },
      { label: "实部", latex: "\\Re(#?)" },
      { label: "虚部", latex: "\\Im(#?)" },
    ],
  },
];

const COMMON_SYMBOLS: FormulaItem[] = [
  { label: "±", latex: "\\pm" },
  { label: "∓", latex: "\\mp" },
  { label: "∞", latex: "\\infty" },
  { label: "=", latex: "=" },
  { label: "≠", latex: "\\ne" },
  { label: "≈", latex: "\\approx" },
  { label: "≅", latex: "\\cong" },
  { label: "∝", latex: "\\propto" },
  { label: "×", latex: "\\times" },
  { label: "÷", latex: "\\div" },
  { label: "≤", latex: "\\le" },
  { label: "≥", latex: "\\ge" },
  { label: "∈", latex: "\\in" },
  { label: "∉", latex: "\\notin" },
  { label: "⊂", latex: "\\subset" },
  { label: "⊆", latex: "\\subseteq" },
  { label: "∪", latex: "\\cup" },
  { label: "∩", latex: "\\cap" },
  { label: "∅", latex: "\\varnothing" },
  { label: "∀", latex: "\\forall" },
  { label: "∃", latex: "\\exists" },
  { label: "∄", latex: "\\nexists" },
  { label: "∴", latex: "\\therefore" },
  { label: "∵", latex: "\\because" },
  { label: "←", latex: "\\leftarrow" },
  { label: "→", latex: "\\rightarrow" },
  { label: "↔", latex: "\\leftrightarrow" },
  { label: "⇒", latex: "\\Rightarrow" },
  { label: "⇔", latex: "\\Leftrightarrow" },
  { label: "α", latex: "\\alpha" },
  { label: "β", latex: "\\beta" },
  { label: "γ", latex: "\\gamma" },
  { label: "δ", latex: "\\delta" },
  { label: "ε", latex: "\\varepsilon" },
  { label: "θ", latex: "\\theta" },
  { label: "λ", latex: "\\lambda" },
  { label: "μ", latex: "\\mu" },
  { label: "π", latex: "\\pi" },
  { label: "ρ", latex: "\\rho" },
  { label: "σ", latex: "\\sigma" },
  { label: "φ", latex: "\\varphi" },
  { label: "ω", latex: "\\omega" },
  { label: "Γ", latex: "\\Gamma" },
  { label: "Δ", latex: "\\Delta" },
  { label: "Θ", latex: "\\Theta" },
  { label: "Λ", latex: "\\Lambda" },
  { label: "Π", latex: "\\Pi" },
  { label: "Σ", latex: "\\Sigma" },
  { label: "Φ", latex: "\\Phi" },
  { label: "Ω", latex: "\\Omega" },
];

const createCasesLatex = (segmentCount: number) => {
  const rows = Array.from({ length: segmentCount }, () => "#?, & #?").join(
    " \\\\ "
  );
  return `\\begin{cases}${rows}\\end{cases}`;
};

const MyComponent = ({ args }: ComponentProps) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const savedRangeRef = useRef<Range | null>(null);
  const formulaRefs = useRef<Record<string, any>>({});
  const activeFormulaIdRef = useRef<string | null>(null);
  const lastValueRef = useRef(args.default_value || "");
  const idCounterRef = useRef(0);

  const [matrixRows, setMatrixRows] = useState(1);
  const [matrixCols, setMatrixCols] = useState(1);
  const [openToolbarGroup, setOpenToolbarGroup] = useState<string | null>(null);

  const createId = () => `formula_${Date.now()}_${idCounterRef.current++}`;
  const createPromptId = () => `hintPrompt${Date.now()}${idCounterRef.current++}`;

  const prepareLatexTemplate = (latex: string) =>
    latex.replace(ACCENT_TEMPLATE_PATTERN, (_match, command) => {
      return `\\${command}{\\placeholder[${createPromptId()}]{}}`;
    });

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
      window.setTimeout(() => selectFirstPrompt(mathField), 0);
    });

    mathField.addEventListener("focus", () => {
      setActiveFormula(id);
    });

    mathField.addEventListener("blur", () => {
      normalizeFilledPrompts(mathField);
      chip.dataset.latex = getMathFieldLatex(mathField, "latex");
      syncValue();
    });

    mathField.addEventListener("keydown", (event: KeyboardEvent) => {
      event.stopPropagation();
    });

    mathField.addEventListener("input", (event: Event) => {
      event.stopPropagation();
      chip.dataset.latex = getMathFieldLatex(mathField, "latex");
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
        chip.dataset.latex = getMathFieldLatex(mathField, "latex");
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
    const preparedLatex = prepareLatexTemplate(latex);

    if (!mathField) {
      insertFormulaBox(preparedLatex);
      return;
    }

    insertIntoMathField(mathField, preparedLatex);

    const chip = mathField.closest(".inline-formula-chip") as HTMLElement | null;
    if (chip) chip.dataset.latex = getMathFieldLatex(mathField, "latex");
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

      button:focus,
      button:focus-visible {
        outline: none !important;
        box-shadow: none !important;
      }

      .formula-toolbar-button,
      .formula-toolbar-button:hover,
      .formula-toolbar-button:active,
      .formula-toolbar-button:focus,
      .formula-toolbar-button:focus-visible {
        border: 1px solid #cfd6e3 !important;
        outline: none !important;
        box-shadow: none !important;
      }

      .formula-toolbar-button.is-active,
      .formula-toolbar-button.is-active:hover,
      .formula-toolbar-button.is-active:active,
      .formula-toolbar-button.is-active:focus,
      .formula-toolbar-button.is-active:focus-visible {
        border: 1px solid #2563eb !important;
        color: #1d4ed8 !important;
        background-color: #eff6ff !important;
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

      .inline-formula-field::part(placeholder) {
        display: inline-block;
        min-width: 0.9em;
        min-height: 0.9em;
        padding: 0 0.14em;
        color: #1d4ed8 !important;
        background: rgba(37, 99, 235, 0.22) !important;
        border: 1px solid #2563eb;
        border-radius: 3px;
        box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.16);
        text-align: center;
      }

      .inline-formula-field::part(prompt) {
        background: transparent;
        border: 0;
        box-shadow: none;
        cursor: text;
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

  const activeFormulaGroup = FORMULA_GROUPS.find(
    (group) => group.title === openToolbarGroup
  );
  const activeToolbarItems =
    openToolbarGroup === COMMON_SYMBOLS_TITLE
      ? COMMON_SYMBOLS
      : activeFormulaGroup?.items ?? [];

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
      </div>

      <div style={groupToolbarStyle}>
        {FORMULA_GROUPS.map((group) => (
          <button
            key={group.title}
            className={`formula-toolbar-button${
              openToolbarGroup === group.title ? " is-active" : ""
            }`}
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onClick={(event) => {
              event.currentTarget.blur();
              setOpenToolbarGroup((current) =>
                current === group.title ? null : group.title
              );
            }}
            style={{
              ...summaryStyle,
              ...(openToolbarGroup === group.title ? summaryActiveStyle : {}),
            }}
          >
            {group.title}
          </button>
        ))}

        <button
          className={`formula-toolbar-button${
            openToolbarGroup === COMMON_SYMBOLS_TITLE ? " is-active" : ""
          }`}
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={(event) => {
            event.currentTarget.blur();
            setOpenToolbarGroup((current) =>
              current === COMMON_SYMBOLS_TITLE ? null : COMMON_SYMBOLS_TITLE
            );
          }}
          style={{
            ...summaryStyle,
            ...(openToolbarGroup === COMMON_SYMBOLS_TITLE
              ? summaryActiveStyle
              : {}),
          }}
        >
          {COMMON_SYMBOLS_TITLE}
        </button>
      </div>

      {openToolbarGroup && activeToolbarItems.length > 0 && (
        <div
          style={
            openToolbarGroup === COMMON_SYMBOLS_TITLE
              ? commonSymbolsPanelStyle
              : formulaPanelStyle
          }
        >
          {activeToolbarItems.map((item) =>
            item.kind === "cases" ? (
              <select
                key={`${openToolbarGroup}-${item.label}-cases`}
                defaultValue=""
                aria-label="插入分段函数"
                onMouseDown={(event) => event.stopPropagation()}
                onChange={(event) => {
                  const segmentCount = Number(event.currentTarget.value);
                  if (segmentCount) {
                    insertLatexIntoFormula(createCasesLatex(segmentCount));
                  }
                  event.currentTarget.value = "";
                }}
                style={formulaSelectStyle}
              >
                <option value="" disabled>
                  {item.label}
                </option>
                {CASES_SEGMENT_COUNTS.map((count) => (
                  <option key={count} value={count}>
                    {count}段
                  </option>
                ))}
              </select>
            ) : (
              <button
                key={`${openToolbarGroup}-${item.label}-${item.latex}`}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => item.latex && insertLatexIntoFormula(item.latex)}
                style={symbolButtonStyle}
              >
                {item.label}
              </button>
            )
          )}
        </div>
      )}

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
      const latex = getMathFieldLatex(
        mathField,
        "latex-without-placeholders",
        node.dataset.latex || ""
      ).trim();
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

const getMathFieldLatex = (
  mathField: any,
  format: "latex" | "latex-without-placeholders" = "latex",
  fallback = ""
) => {
  if (!mathField) return fallback;

  try {
    const value = mathField.getValue?.(format);
    if (typeof value === "string") return value;
  } catch {
    // Fall back to the raw value for older MathLive versions.
  }

  return typeof mathField.value === "string" ? mathField.value : fallback;
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

  if (latex.includes("\\placeholder[")) {
    window.setTimeout(() => selectFirstPrompt(mathField), 0);
  }
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
  injectMathFieldPlaceholderStyles(mathField);
};

const trySetMathFieldOption = (setter: () => void) => {
  try {
    setter();
  } catch {
    // Some MathLive properties are not writable until its internal model mounts.
  }
};

const injectMathFieldPlaceholderStyles = (mathField: any, attempt = 0) => {
  trySetMathFieldOption(() => {
    mathField.style.setProperty("--placeholder-color", "#1d4ed8");
    mathField.style.setProperty("--placeholder-opacity", "1");
  });

  const root = mathField.shadowRoot as ShadowRoot | null;
  if (!root) {
    if (attempt < 10) {
      window.setTimeout(
        () => injectMathFieldPlaceholderStyles(mathField, attempt + 1),
        30
      );
    }
    return;
  }
  if (root.getElementById(MATHFIELD_PLACEHOLDER_STYLE_ID)) return;

  const style = document.createElement("style");
  style.id = MATHFIELD_PLACEHOLDER_STYLE_ID;
  style.textContent = `
    [part='prompt'],
    .ML__prompt {
      background: transparent !important;
      border: 0 !important;
      box-shadow: none !important;
      cursor: text !important;
      pointer-events: auto !important;
    }

    .ML__focusedPromptBox,
    .ML__prompt-atom:has(.ML__focusedPromptBox) {
      background: transparent !important;
      box-shadow: none !important;
    }

    [part='placeholder'],
    .ML__placeholder {
      display: inline-block !important;
      min-width: 0.9em !important;
      min-height: 0.9em !important;
      opacity: 1 !important;
      color: #1d4ed8 !important;
      background: rgba(37, 99, 235, 0.22) !important;
      border: 1px solid #2563eb;
      border-radius: 3px;
      box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.16);
      padding: 0 0.14em !important;
      text-align: center;
    }

    [part='placeholder'].ML__placeholder-selected,
    .ML__placeholder-selected,
    .ML__selected .ML__placeholder {
      background: rgba(37, 99, 235, 0.34) !important;
      box-shadow: 0 0 0 1px #2563eb inset;
    }
  `;
  root.appendChild(style);
};

const selectFirstPrompt = (mathField: any) => {
  trySetMathFieldOption(() => {
    const promptIds = mathField.getPrompts?.({ locked: false });
    const firstPromptId = Array.isArray(promptIds) ? promptIds[0] : null;
    const range = firstPromptId ? mathField.getPromptRange?.(firstPromptId) : null;
    if (range) {
      mathField.focus();
      mathField.selection = range;
    }
  });
};

const normalizeFilledPrompts = (mathField: any) => {
  trySetMathFieldOption(() => {
    const promptIds = mathField.getPrompts?.({ locked: false });
    if (!Array.isArray(promptIds) || promptIds.length === 0) return;

    const hasEmptyPrompt = promptIds.some((id) => {
      const value = mathField.getPromptValue?.(
        id,
        "latex-without-placeholders"
      );
      return !String(value || "").trim();
    });
    if (hasEmptyPrompt) return;

    const plainLatex = getMathFieldLatex(
      mathField,
      "latex-without-placeholders"
    ).trim();
    if (!plainLatex) return;

    mathField.setValue?.(plainLatex, {
      selectionMode: "after",
      silenceNotifications: true,
    });
  });
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
  height: "485px",
  boxSizing: "border-box",
  overflow: "hidden",
};

const toolbarHeaderStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-start",
  gap: "8px",
  marginBottom: "8px",
  flexWrap: "wrap",
};

const groupToolbarStyle: React.CSSProperties = {
  display: "flex",
  gap: "4px",
  flexWrap: "nowrap",
  alignItems: "flex-start",
  marginBottom: "8px",
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

const summaryStyle: React.CSSProperties = {
  border: "1px solid #cfd6e3",
  backgroundColor: "#f8fafc",
  backgroundImage:
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%23536075' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E\")",
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 7px center",
  backgroundSize: "10px 6px",
  color: "#263244",
  borderRadius: "7px",
  padding: "6px 21px 6px 8px",
  display: "flex",
  alignItems: "center",
  fontSize: "12px",
  cursor: "pointer",
  flex: "0 0 auto",
  minHeight: "30px",
  outline: "none",
  listStyle: "none",
};

const summaryActiveStyle: React.CSSProperties = {
  borderColor: "#2563eb",
  color: "#1d4ed8",
  backgroundColor: "#eff6ff",
};

const formulaPanelStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(84px, 1fr))",
  gap: "6px",
  padding: "8px",
  border: "1px solid #d9dee8",
  borderRadius: "8px",
  background: "#fbfdff",
  marginBottom: "8px",
};

const commonSymbolsPanelStyle: React.CSSProperties = {
  ...formulaPanelStyle,
  gridTemplateColumns: "repeat(auto-fill, minmax(34px, 1fr))",
  maxHeight: "118px",
  overflowY: "auto",
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
  outline: "none",
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
  outline: "none",
};

const symbolButtonStyle: React.CSSProperties = {
  ...toolButtonStyle,
  minHeight: "30px",
  padding: "4px 7px",
};

const selectStyle: React.CSSProperties = {
  border: "1px solid #cfd6e3",
  borderRadius: "6px",
  background: "white",
  color: "#263244",
  fontSize: "12px",
  height: "30px",
  outline: "none",
};

const formulaSelectStyle: React.CSSProperties = {
  ...selectStyle,
  width: "100%",
  minHeight: "30px",
  padding: "0 7px",
};

const editorStyle: React.CSSProperties = {
  width: "100%",
  height: "215px",
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
