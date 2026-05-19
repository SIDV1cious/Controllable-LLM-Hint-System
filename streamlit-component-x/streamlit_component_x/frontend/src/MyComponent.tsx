import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { useEffect, useRef, useState } from "react";
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
  kind?: "cases" | "multi-integral";
};

type FormulaGroup = {
  title: string;
  items: FormulaItem[];
};

type MathRuntimeStatus = "loading" | "ready" | "failed";

const COMPACT_FRAME_HEIGHT = 420;
const EXPANDED_FRAME_HEIGHT = 520;
const COMPACT_CONTAINER_HEIGHT = "385px";
const EXPANDED_CONTAINER_HEIGHT = "485px";
const MAX_MATRIX_SIZE = 10;
const VALUE_SYNC_DEBOUNCE_MS = 2500;
const ZERO_WIDTH_SPACE = "\u200B";
const COMMON_SYMBOLS_TITLE = "符号";
const MATHFIELD_PLACEHOLDER_STYLE_ID = "hint-placeholder-style";
const CASES_SEGMENT_COUNTS = [2, 3, 4, 5];
const MULTI_INTEGRAL_COUNTS = [
  { count: 2, label: "二重" },
  { count: 3, label: "三重" },
  { count: 4, label: "四重" },
  { count: 5, label: "五重" },
];

let mathRuntimePromise: Promise<void> | null = null;

const loadMathRuntime = () => {
  mathRuntimePromise ??= import("mathlive").then(() => undefined);
  return mathRuntimePromise;
};

const FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "分式/上下标",
    items: [
      { label: "分式", latex: "\\frac{#?}{#?}" },
      { label: "斜分式", latex: "#?/#?" },
      { label: "倒数", latex: "\\frac{1}{#?}" },
      { label: "二项式", latex: "\\binom{#?}{#?}" },
      { label: "上标", latex: "#?^{#?}" },
      { label: "下标", latex: "#?_{#?}" },
      { label: "上下标", latex: "#?_{#?}^{#?}" },
      { label: "平方", latex: "#?^2" },
      { label: "立方", latex: "#?^3" },
      { label: "n次方", latex: "#?^{#?}" },
    ],
  },
  {
    title: "根式",
    items: [
      { label: "平方根", latex: "\\sqrt{#?}" },
      { label: "n次根", latex: "\\sqrt[#?]{#?}" },
      { label: "三次根", latex: "\\sqrt[3]{#?}" },
      { label: "四次根", latex: "\\sqrt[4]{#?}" },
    ],
  },
  {
    title: "积分",
    items: [
      { label: "不定积分", latex: "\\int #?\\,\\mathrm{d}#?" },
      { label: "定积分", latex: "\\int_{#?}^{#?}#?\\,\\mathrm{d}#?" },
      { label: "无穷积分", latex: "\\int_{-\\infty}^{+\\infty}#?\\,\\mathrm{d}#?" },
      {
        label: "多重积分",
        kind: "multi-integral",
      },
      {
        label: "区域多重积分",
        latex: "\\int\\cdots\\int_{#?}#?\\,\\mathrm{d}#?_{1}\\cdots\\mathrm{d}#?_{#?}",
      },
      { label: "曲线积分", latex: "\\int_{#?}#?\\,\\mathrm{d}s" },
      { label: "闭曲线积分", latex: "\\oint_{#?}#?\\,\\mathrm{d}s" },
      { label: "曲面积分", latex: "\\iint_{#?}#?\\,\\mathrm{d}S" },
    ],
  },
  {
    title: "运算",
    items: [
      { label: "求和", latex: "\\sum_{#?}^{#?}#?" },
      { label: "乘积", latex: "\\prod_{#?}^{#?}#?" },
      { label: "余积", latex: "\\coprod_{#?}^{#?}#?" },
      { label: "并集", latex: "\\bigcup_{#?}^{#?}#?" },
      { label: "交集", latex: "\\bigcap_{#?}^{#?}#?" },
      { label: "最大值", latex: "\\max_{#?}#?" },
      { label: "最小值", latex: "\\min_{#?}#?" },
      { label: "上确界", latex: "\\sup_{#?}#?" },
      { label: "下确界", latex: "\\inf_{#?}#?" },
      { label: "limsup", latex: "\\limsup_{#?\\to#?}#?" },
      { label: "liminf", latex: "\\liminf_{#?\\to#?}#?" },
      { label: "argmax", latex: "\\operatorname*{arg\\,max}_{#?}#?" },
      { label: "argmin", latex: "\\operatorname*{arg\\,min}_{#?}#?" },
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
      { label: "尖括号", latex: "\\left\\langle #?\\right\\rangle" },
      { label: "向下取整", latex: "\\left\\lfloor #?\\right\\rfloor" },
      { label: "向上取整", latex: "\\left\\lceil #?\\right\\rceil" },
      { label: "开区间", latex: "\\left(#?,#?\\right)" },
      { label: "闭区间", latex: "\\left[#?,#?\\right]" },
      { label: "左闭右开", latex: "\\left[#?,#?\\right)" },
      { label: "左开右闭", latex: "\\left(#?,#?\\right]" },
    ],
  },
  {
    title: "函数",
    items: [
      { label: "sin", latex: "\\sin(#?)" },
      { label: "cos", latex: "\\cos(#?)" },
      { label: "tan", latex: "\\tan(#?)" },
      { label: "cot", latex: "\\cot(#?)" },
      { label: "sec", latex: "\\sec(#?)" },
      { label: "csc", latex: "\\csc(#?)" },
      { label: "arcsin", latex: "\\arcsin(#?)" },
      { label: "arccos", latex: "\\arccos(#?)" },
      { label: "arctan", latex: "\\arctan(#?)" },
      { label: "sinh", latex: "\\sinh(#?)" },
      { label: "cosh", latex: "\\cosh(#?)" },
      { label: "tanh", latex: "\\tanh(#?)" },
      { label: "ln", latex: "\\ln(#?)" },
      { label: "log", latex: "\\log_{#?}{#?}" },
      { label: "exp", latex: "\\exp(#?)" },
      { label: "e指数", latex: "e^{#?}" },
      { label: "函数值", latex: "#?(#?)" },
      { label: "复合函数", latex: "#?\\left(#?(#?)\\right)" },
      { label: "极限", latex: "\\lim_{#?\\to#?}#?" },
      { label: "左极限", latex: "\\lim_{#?\\to#?^-}#?" },
      { label: "右极限", latex: "\\lim_{#?\\to#?^+}#?" },
      { label: "无穷极限", latex: "\\lim_{#?\\to\\infty}#?" },
      { label: "分段函数", kind: "cases" },
    ],
  },
  {
    title: "导数",
    items: [
      { label: "导数", latex: "\\frac{\\mathrm{d}}{\\mathrm{d}#?}#?" },
      { label: "一阶导", latex: "\\frac{\\mathrm{d}#?}{\\mathrm{d}#?}" },
      { label: "二阶导", latex: "\\frac{\\mathrm{d}^2#?}{\\mathrm{d}#?^2}" },
      { label: "n阶导", latex: "\\frac{\\mathrm{d}^{#?}}{\\mathrm{d}#?^{#?}}#?" },
      { label: "偏导", latex: "\\frac{\\partial}{\\partial #?}#?" },
      { label: "偏导数", latex: "\\frac{\\partial #?}{\\partial #?}" },
      { label: "二阶偏导", latex: "\\frac{\\partial^2 #?}{\\partial #?^2}" },
      { label: "n阶偏导", latex: "\\frac{\\partial^{#?}}{\\partial #?^{#?}}#?" },
      { label: "撇号导数", latex: "#?'" },
      { label: "二阶撇号", latex: "#?''" },
      { label: "微分", latex: "\\mathrm{d}#?" },
      { label: "梯度", latex: "\\nabla #?" },
      { label: "散度", latex: "\\nabla\\cdot #?" },
      { label: "旋度", latex: "\\nabla\\times #?" },
      { label: "拉普拉斯", latex: "\\Delta #?" },
    ],
  },
  {
    title: "标注",
    items: [
      { label: "向量", latex: "\\vec{#?}" },
      { label: "帽子", latex: "\\hat{#?}" },
      { label: "宽帽", latex: "\\widehat{#?}" },
      { label: "波浪", latex: "\\tilde{#?}" },
      { label: "宽波浪", latex: "\\widetilde{#?}" },
      { label: "上划线", latex: "\\overline{#?}" },
      { label: "下划线", latex: "\\underline{#?}" },
      { label: "点", latex: "\\dot{#?}" },
      { label: "二重点", latex: "\\ddot{#?}" },
      { label: "共轭", latex: "\\overline{#?}" },
      { label: "实部", latex: "\\Re(#?)" },
      { label: "虚部", latex: "\\Im(#?)" },
      { label: "右箭头", latex: "\\overrightarrow{#?}" },
      { label: "左箭头", latex: "\\overleftarrow{#?}" },
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
  { label: "≡", latex: "\\equiv" },
  { label: "∼", latex: "\\sim" },
  { label: "≃", latex: "\\simeq" },
  { label: "≪", latex: "\\ll" },
  { label: "≫", latex: "\\gg" },
  { label: "×", latex: "\\times" },
  { label: "÷", latex: "\\div" },
  { label: "·", latex: "\\cdot" },
  { label: "∗", latex: "\\ast" },
  { label: "≤", latex: "\\le" },
  { label: "≥", latex: "\\ge" },
  { label: "<", latex: "<" },
  { label: ">", latex: ">" },
  { label: "∈", latex: "\\in" },
  { label: "∉", latex: "\\notin" },
  { label: "⊂", latex: "\\subset" },
  { label: "⊆", latex: "\\subseteq" },
  { label: "⊃", latex: "\\supset" },
  { label: "⊇", latex: "\\supseteq" },
  { label: "∪", latex: "\\cup" },
  { label: "∩", latex: "\\cap" },
  { label: "∖", latex: "\\setminus" },
  { label: "∅", latex: "\\varnothing" },
  { label: "N", latex: "\\mathbb{N}" },
  { label: "Z", latex: "\\mathbb{Z}" },
  { label: "Q", latex: "\\mathbb{Q}" },
  { label: "R", latex: "\\mathbb{R}" },
  { label: "C", latex: "\\mathbb{C}" },
  { label: "∀", latex: "\\forall" },
  { label: "∃", latex: "\\exists" },
  { label: "∄", latex: "\\nexists" },
  { label: "∧", latex: "\\land" },
  { label: "∨", latex: "\\lor" },
  { label: "¬", latex: "\\neg" },
  { label: "∴", latex: "\\therefore" },
  { label: "∵", latex: "\\because" },
  { label: "←", latex: "\\leftarrow" },
  { label: "→", latex: "\\rightarrow" },
  { label: "↔", latex: "\\leftrightarrow" },
  { label: "⇒", latex: "\\Rightarrow" },
  { label: "⇔", latex: "\\Leftrightarrow" },
  { label: "↦", latex: "\\mapsto" },
  { label: "∂", latex: "\\partial" },
  { label: "∇", latex: "\\nabla" },
  { label: "⊥", latex: "\\perp" },
  { label: "∥", latex: "\\parallel" },
  { label: "°", latex: "^\\circ" },
  { label: "α", latex: "\\alpha" },
  { label: "β", latex: "\\beta" },
  { label: "γ", latex: "\\gamma" },
  { label: "δ", latex: "\\delta" },
  { label: "ε", latex: "\\varepsilon" },
  { label: "ζ", latex: "\\zeta" },
  { label: "η", latex: "\\eta" },
  { label: "θ", latex: "\\theta" },
  { label: "κ", latex: "\\kappa" },
  { label: "λ", latex: "\\lambda" },
  { label: "μ", latex: "\\mu" },
  { label: "ν", latex: "\\nu" },
  { label: "ξ", latex: "\\xi" },
  { label: "π", latex: "\\pi" },
  { label: "ρ", latex: "\\rho" },
  { label: "σ", latex: "\\sigma" },
  { label: "τ", latex: "\\tau" },
  { label: "φ", latex: "\\varphi" },
  { label: "χ", latex: "\\chi" },
  { label: "ψ", latex: "\\psi" },
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

const createMultiIntegralLatex = (integralCount: number) => {
  const integrals = Array.from(
    { length: integralCount },
    () => "\\int_{#?}^{#?}"
  ).join("");
  const differentials = Array.from(
    { length: integralCount },
    () => "\\mathrm{d}#?"
  ).join("\\,");
  return `${integrals}#?\\,${differentials}`;
};

const MyComponent = ({ args }: ComponentProps) => {
  const storageKey =
    typeof args.storage_key === "string" && args.storage_key
      ? `controlled_hint_composer:${args.storage_key}`
      : null;
  const readInitialValue = () => {
    const defaultValue = String(args.default_value || "");
    if (defaultValue) return defaultValue;
    if (!storageKey) return "";
    try {
      return window.localStorage.getItem(storageKey) || "";
    } catch (_error) {
      return "";
    }
  };
  const initialValue = readInitialValue();
  const editorRef = useRef<HTMLDivElement>(null);
  const savedRangeRef = useRef<Range | null>(null);
  const formulaRefs = useRef<Record<string, any>>({});
  const activeFormulaIdRef = useRef<string | null>(null);
  const lastValueRef = useRef(initialValue);
  const pendingValueRef = useRef(initialValue);
  const committedValueRef = useRef(initialValue);
  const initialValueRef = useRef(initialValue);
  const syncTimerRef = useRef<number | null>(null);
  const isComposingRef = useRef(false);
  const recentNativeTextInputRef = useRef<{ text: string; timestamp: number } | null>(
    null
  );
  const idCounterRef = useRef(0);

  const [matrixRows, setMatrixRows] = useState(1);
  const [matrixCols, setMatrixCols] = useState(1);
  const [openToolbarGroup, setOpenToolbarGroup] = useState<string | null>(null);
  const [mathRuntimeStatus, setMathRuntimeStatus] =
    useState<MathRuntimeStatus>("loading");

  const mathRuntimeReady = mathRuntimeStatus === "ready";

  const createId = () => `formula_${Date.now()}_${idCounterRef.current++}`;
  const refreshFrameHeight = () => {
    const frameHeight = openToolbarGroup ? EXPANDED_FRAME_HEIGHT : COMPACT_FRAME_HEIGHT;
    window.setTimeout(() => Streamlit.setFrameHeight(frameHeight), 0);
    window.setTimeout(() => Streamlit.setFrameHeight(frameHeight), 80);
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

  const rangesShareBoundaries = (left: Range, right: Range) =>
    left.startContainer === right.startContainer &&
    left.startOffset === right.startOffset &&
    left.endContainer === right.endContainer &&
    left.endOffset === right.endOffset;

  const restoreSavedSelection = (expectedRange?: Range | null) => {
    const editor = editorRef.current;
    const savedRange = savedRangeRef.current;
    const selection = window.getSelection();
    if (!editor || !savedRange || !selection) return false;
    if (!isInsideEditor(savedRange.commonAncestorContainer)) return false;
    if (closestFormulaChipFromNode(savedRange.commonAncestorContainer)) return false;

    if (expectedRange && selection.rangeCount > 0) {
      const currentRange = selection.getRangeAt(0);
      if (
        isInsideEditor(currentRange.commonAncestorContainer) &&
        !rangesShareBoundaries(currentRange, expectedRange)
      ) {
        return false;
      }
    }

    editor.focus({ preventScroll: true });
    selection.removeAllRanges();
    selection.addRange(savedRange.cloneRange());
    return true;
  };

  const focusEditorAtEnd = () => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection) return false;

    editor.focus({ preventScroll: true });
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
    savedRangeRef.current = range.cloneRange();
    return true;
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

  const rememberNativeTextInput = (event: InputEvent) => {
    if (event.isComposing || !event.data) return;
    if (!["insertText", "insertCompositionText"].includes(event.inputType)) return;

    recentNativeTextInputRef.current = {
      text: event.data,
      timestamp: Date.now(),
    };
  };

  const collapseRecentNativeInputSelection = (range: Range) => {
    if (range.collapsed) return range;

    const recentInput = recentNativeTextInputRef.current;
    if (!recentInput || Date.now() - recentInput.timestamp > 700) return range;

    const selectedText = range.toString().replaceAll(ZERO_WIDTH_SPACE, "");
    if (selectedText !== recentInput.text) return range;

    const collapsedRange = range.cloneRange();
    collapsedRange.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(collapsedRange);
    savedRangeRef.current = collapsedRange.cloneRange();
    return collapsedRange;
  };

  const setCaretAfter = (node: Node) => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!selection) return;

    editor?.focus({ preventScroll: true });
    const range = document.createRange();
    range.setStartAfter(node);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    savedRangeRef.current = range.cloneRange();
  };

  const setCaretFromPoint = (clientX: number, clientY: number) => {
    if (!clientX && !clientY) return false;

    const documentWithCaretRange = document as Document & {
      caretRangeFromPoint?: (x: number, y: number) => Range | null;
    };
    const documentWithCaretPosition = document as Document & {
      caretPositionFromPoint?: (
        x: number,
        y: number
      ) => { offsetNode: Node; offset: number } | null;
    };

    let range = documentWithCaretRange.caretRangeFromPoint?.(clientX, clientY) ?? null;
    if (!range) {
      const position = documentWithCaretPosition.caretPositionFromPoint?.(clientX, clientY);
      if (position) {
        range = document.createRange();
        range.setStart(position.offsetNode, position.offset);
        range.collapse(true);
      }
    }

    if (!range || !isInsideEditor(range.commonAncestorContainer)) return false;

    const formulaChip = closestFormulaChipFromNode(range.commonAncestorContainer);
    if (formulaChip) {
      range = document.createRange();
      range.setStartAfter(formulaChip);
      range.collapse(true);
    }

    const selection = window.getSelection();
    if (!selection) return false;
    selection.removeAllRanges();
    selection.addRange(range);
    savedRangeRef.current = range.cloneRange();
    return true;
  };

  const clearSyncTimer = () => {
    if (syncTimerRef.current) {
      window.clearTimeout(syncTimerRef.current);
      syncTimerRef.current = null;
    }
  };

  const flushValueToStreamlit = () => {
    clearSyncTimer();
    const editor = editorRef.current;
    const activeElement = document.activeElement;
    const activeNode = activeElement instanceof Node ? activeElement : null;
    const shouldRestoreSelection =
      !!editor &&
      !!activeElement &&
      (activeElement === editor || editor.contains(activeElement)) &&
      !closestFormulaChipFromNode(activeNode);
    if (shouldRestoreSelection) {
      saveSelection();
    }
    if (editor) {
      const currentValue = serializeEditor(editor);
      lastValueRef.current = currentValue;
      pendingValueRef.current = currentValue;
      persistDraftValue(currentValue);
    }

    if (pendingValueRef.current === committedValueRef.current) return;
    committedValueRef.current = pendingValueRef.current;
    const selectionSnapshot = shouldRestoreSelection
      ? savedRangeRef.current?.cloneRange() ?? null
      : null;
    Streamlit.setComponentValue(pendingValueRef.current);
    if (shouldRestoreSelection) {
      window.setTimeout(() => {
        if (!restoreSavedSelection(selectionSnapshot)) focusEditorAtEnd();
      }, 0);
      window.setTimeout(() => {
        if (!restoreSavedSelection(selectionSnapshot)) focusEditorAtEnd();
      }, 80);
    }
  };

  const persistDraftValue = (value: string) => {
    if (!storageKey) return;
    try {
      if (value) {
        window.localStorage.setItem(storageKey, value);
      } else {
        window.localStorage.removeItem(storageKey);
      }
    } catch (_error) {
      // Local storage can be unavailable in strict privacy modes; Streamlit sync
      // remains the source of truth in that case.
    }
  };

  const syncValue = (immediate = false) => {
    saveSelection();
    const editor = editorRef.current;
    if (!editor) return;

    const value = serializeEditor(editor);
    lastValueRef.current = value;
    pendingValueRef.current = value;
    persistDraftValue(value);

    if (immediate) {
      flushValueToStreamlit();
      return;
    }

    clearSyncTimer();
    syncTimerRef.current = window.setTimeout(flushValueToStreamlit, VALUE_SYNC_DEBOUNCE_MS);
  };

  const flushCurrentComposerValue = () => {
    Object.values(formulaRefs.current).forEach((mathField: any) => {
      const chip = mathField?.closest?.(".inline-formula-chip") as HTMLElement | null;
      if (chip) {
        chip.dataset.latex = getMathFieldLatex(
          mathField,
          "latex",
          chip.dataset.latex || ""
        );
      }
    });
    syncValue(true);
  };

  const handleContainerBlur = (event: React.FocusEvent<HTMLDivElement>) => {
    const nextTarget = event.relatedTarget as Node | null;
    if (nextTarget && event.currentTarget.contains(nextTarget)) return;
    window.setTimeout(flushCurrentComposerValue, 0);
  };

  const removeFormula = (chip: HTMLElement) => {
    const editor = editorRef.current;
    const next = chip.nextSibling;
    const previous = chip.previousSibling;
    const caretBefore = isZeroWidthText(previous)
      ? previous.previousSibling
      : previous;
    const caretAfter = isZeroWidthText(next) ? next.nextSibling : next;

    if (isZeroWidthText(next)) next.remove();
    if (isZeroWidthText(previous)) previous.remove();

    chip.remove();

    if (!editor) return;

    editor.focus();
    const range = document.createRange();
    if (caretBefore?.parentNode === editor) {
      if (caretBefore.nodeType === Node.TEXT_NODE) {
        range.setStart(caretBefore, caretBefore.textContent?.length || 0);
      } else {
        range.setStartAfter(caretBefore);
      }
    } else if (caretAfter?.parentNode === editor) {
      range.setStartBefore(caretAfter);
    } else {
      range.selectNodeContents(editor);
      range.collapse(false);
    }
    range.collapse(true);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    savedRangeRef.current = range.cloneRange();
    // Keep this debounced so immediate typing after deleting a formula does not
    // race a Streamlit rerender and lose the restored caret position.
    syncValue();
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

    mathField.addEventListener("blur", (event: FocusEvent) => {
      normalizeFilledPrompts(mathField);
      chip.dataset.latex = getMathFieldLatex(mathField, "latex");
      const nextTarget = event.relatedTarget as Node | null;
      const editor = editorRef.current;
      const focusStaysInEditor = !!editor && !!nextTarget && editor.contains(nextTarget);

      if (focusStaysInEditor) {
        syncValue();
        return;
      }

      window.setTimeout(() => {
        const activeElement = document.activeElement;
        const focusReturnedToEditor =
          !!editorRef.current &&
          !!activeElement &&
          editorRef.current.contains(activeElement);
        syncValue(!focusReturnedToEditor);
      }, 60);
    });

    mathField.addEventListener("keydown", (event: KeyboardEvent) => {
      event.stopPropagation();
      const isSelectAll =
        (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a";

      if (isSelectAll) {
        event.preventDefault();
        configureMathField(mathField);
        mathField.focus();
        const selected =
          mathField.executeCommand?.("selectAll") ||
          mathField.executeCommand?.("select-all");
        if (!selected && mathField.model?.lastOffset !== undefined) {
          mathField.selection = {
            ranges: [[0, mathField.model.lastOffset]],
            direction: "forward",
          };
        }
      }
    });

    mathField.addEventListener("input", (event: Event) => {
      event.stopPropagation();
      chip.dataset.latex = getMathFieldLatex(mathField, "latex");
      syncValue();
    });

    const handleRemoveButton = (event: Event) => {
      event.preventDefault();
      event.stopPropagation();
      if (!chip.isConnected) return;
      delete formulaRefs.current[id];
      removeFormula(chip);
    };

    removeButton.addEventListener("mousedown", handleRemoveButton);
    removeButton.addEventListener("click", handleRemoveButton);

    window.setTimeout(() => configureMathField(mathField), 0);

    return { id, chip, mathField };
  };

  const insertPlainText = (text: string, immediateSync = false) => {
    const range = getEditorRange();
    if (!range) return;

    if (text) {
      recentNativeTextInputRef.current = {
        text,
        timestamp: Date.now(),
      };
    }

    range.deleteContents();
    const textNode = document.createTextNode(text);
    range.insertNode(textNode);
    setCaretAfter(textNode);
    syncValue(immediateSync);
  };

  const insertLineBreak = () => {
    const editor = editorRef.current;
    const range = getEditorRange();
    if (!range) return;

    editor?.focus({ preventScroll: true });
    range.deleteContents();
    const lineBreak = document.createElement("br");
    const spacer = document.createTextNode(ZERO_WIDTH_SPACE);
    range.insertNode(lineBreak);
    lineBreak.after(spacer);
    setCaretAfter(spacer);
    editor?.focus({ preventScroll: true });
    // Keep Enter debounced so rapid newline + typing is not interrupted by a
    // Streamlit rerender stealing the caret between keystrokes.
    syncValue();
  };

  const insertFormulaBox = (initialLatex = "") => {
    if (!mathRuntimeReady) return;

    saveSelection();
    const editor = editorRef.current;
    const range = getEditorRange();
    if (!editor || !range) return;

    const insertionRange = collapseRecentNativeInputSelection(range);
    if (!initialLatex && !insertionRange.collapsed) {
      insertionRange.collapse(false);
    }
    const { id, chip, mathField } = createFormulaElement(initialLatex);
    const spacer = document.createTextNode(ZERO_WIDTH_SPACE);

    insertionRange.deleteContents();
    insertionRange.insertNode(spacer);
    insertionRange.insertNode(chip);
    setCaretAfter(spacer);
    setActiveFormula(id);
    configureMathField(mathField);
    mathField.focus();

    if (initialLatex) {
      setMathFieldLatex(mathField, initialLatex);
      chip.dataset.latex = getMathFieldLatex(
        mathField,
        "latex",
        initialLatex
      );
      syncValue(true);
      return;
    }

    syncValue();

    window.setTimeout(() => {
      mathField.focus();
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
    if (!mathRuntimeReady) return;

    const mathField = getActiveMathField();

    if (!mathField) {
      insertFormulaBox(latex);
      return;
    }

    insertIntoMathField(mathField, latex);

    const chip = mathField.closest(".inline-formula-chip") as HTMLElement | null;
    const syncActiveMathField = (immediate = false) => {
      if (chip) chip.dataset.latex = getMathFieldLatex(mathField, "latex");
      syncValue(immediate);
    };

    syncActiveMathField(true);
    window.setTimeout(() => syncActiveMathField(), 50);
    window.setTimeout(() => syncActiveMathField(true), 140);
  };

  const insertMatrix = () => {
    if (!mathRuntimeReady) return;

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

  const deleteSelectedEditorRange = () => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection || selection.rangeCount === 0) return false;

    const range = selection.getRangeAt(0);
    if (range.collapsed || !isInsideEditor(range.commonAncestorContainer)) {
      return false;
    }

    const knownChips = Array.from(
      editor.querySelectorAll<HTMLElement>(".inline-formula-chip")
    );
    editor.focus({ preventScroll: true });
    range.deleteContents();
    knownChips.forEach((chip) => {
      if (!chip.isConnected) {
        delete formulaRefs.current[chip.dataset.formulaId || ""];
      }
    });

    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    savedRangeRef.current = range.cloneRange();
    syncValue();
    return true;
  };

  const selectAllEditorContents = () => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection) return false;

    editor.focus({ preventScroll: true });
    const range = document.createRange();
    range.selectNodeContents(editor);
    selection.removeAllRanges();
    selection.addRange(range);
    savedRangeRef.current = range.cloneRange();
    return true;
  };

  const removeLineBreakBeforeCaret = () => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection || selection.rangeCount === 0) return false;

    const range = selection.getRangeAt(0);
    if (!range.collapsed || !isInsideEditor(range.commonAncestorContainer)) {
      return false;
    }
    if (range.startContainer.nodeType !== Node.TEXT_NODE) return false;

    const textNode = range.startContainer;
    const text = textNode.textContent || "";
    const beforeCaret = text.slice(0, range.startOffset);
    if (beforeCaret.replaceAll(ZERO_WIDTH_SPACE, "") !== "") return false;

    let previous = textNode.previousSibling;
    if (isZeroWidthText(previous)) previous = previous.previousSibling;
    if (!(previous instanceof HTMLBRElement)) return false;

    editor.focus({ preventScroll: true });
    previous.remove();
    textNode.textContent = text.replaceAll(ZERO_WIDTH_SPACE, "");

    const nextRange = document.createRange();
    nextRange.setStart(textNode, 0);
    nextRange.collapse(true);
    selection.removeAllRanges();
    selection.addRange(nextRange);
    editor.focus({ preventScroll: true });
    savedRangeRef.current = nextRange.cloneRange();
    // Backspace can be followed by another keystroke immediately. Debouncing the
    // Streamlit sync here avoids a rerender racing with that next native input.
    syncValue();
    return true;
  };

  const removeLineBreakAfterCaret = () => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection || selection.rangeCount === 0) return false;

    const range = selection.getRangeAt(0);
    if (!range.collapsed || !isInsideEditor(range.commonAncestorContainer)) {
      return false;
    }
    if (range.startContainer.nodeType !== Node.TEXT_NODE) return false;

    const textNode = range.startContainer;
    const text = textNode.textContent || "";
    const afterCaret = text.slice(range.startOffset);
    if (afterCaret.replaceAll(ZERO_WIDTH_SPACE, "") !== "") return false;

    let next = textNode.nextSibling;
    if (isZeroWidthText(next)) next = next.nextSibling;
    if (!(next instanceof HTMLBRElement)) return false;

    const following = next.nextSibling;
    if (isZeroWidthText(following)) {
      following.textContent = (following.textContent || "").replaceAll(
        ZERO_WIDTH_SPACE,
        ""
      );
    }

    editor.focus({ preventScroll: true });
    next.remove();
    textNode.textContent = text.replaceAll(ZERO_WIDTH_SPACE, "");

    const nextRange = document.createRange();
    nextRange.setStart(textNode, textNode.textContent?.length || 0);
    nextRange.collapse(true);
    selection.removeAllRanges();
    selection.addRange(nextRange);
    editor.focus({ preventScroll: true });
    savedRangeRef.current = nextRange.cloneRange();
    syncValue();
    return true;
  };

  const handleEditorKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (isComposingRef.current || event.nativeEvent.isComposing) {
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      insertLineBreak();
      return;
    }

    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
      if (selectAllEditorContents()) {
        event.preventDefault();
      }
      return;
    }

    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "x") {
      const selectedText = window.getSelection()?.toString() || "";
      if (selectedText && deleteSelectedEditorRange()) {
        event.preventDefault();
        void navigator.clipboard?.writeText(selectedText).catch(() => undefined);
      }
      return;
    }

    if (event.key === "Backspace" && removeLineBreakBeforeCaret()) {
      event.preventDefault();
      return;
    }

    if (event.key === "Delete" && removeLineBreakAfterCaret()) {
      event.preventDefault();
      return;
    }

    if (
      (event.key === "Backspace" || event.key === "Delete") &&
      deleteSelectedEditorRange()
    ) {
      event.preventDefault();
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

  const handleEditorBeforeInput = (event: React.FormEvent<HTMLDivElement>) => {
    const nativeInputEvent = event.nativeEvent as InputEvent;
    if (isComposingRef.current || nativeInputEvent.isComposing) {
      return;
    }

    rememberNativeTextInput(nativeInputEvent);

    if (nativeInputEvent.inputType === "insertText" && nativeInputEvent.data) {
      event.preventDefault();
      insertPlainText(nativeInputEvent.data);
      return;
    }

    if (nativeInputEvent.inputType === "insertParagraph") {
      event.preventDefault();
      insertLineBreak();
      return;
    }

    if (
      (nativeInputEvent.inputType === "deleteContentBackward" ||
        nativeInputEvent.inputType === "deleteContentForward") &&
      deleteSelectedEditorRange()
    ) {
      event.preventDefault();
      return;
    }

    if (
      nativeInputEvent.inputType === "deleteContentBackward" &&
      removeLineBreakBeforeCaret()
    ) {
      event.preventDefault();
      return;
    }

    if (
      nativeInputEvent.inputType === "deleteContentForward" &&
      removeLineBreakAfterCaret()
    ) {
      event.preventDefault();
      return;
    }

    if (
      nativeInputEvent.inputType === "deleteContentForward" &&
      removeAdjacentFormula("forward")
    ) {
      event.preventDefault();
    }
  };

  const handlePaste = (event: React.ClipboardEvent<HTMLDivElement>) => {
    const text =
      event.clipboardData.getData("text/plain") ||
      plainTextFromClipboardHtml(event.clipboardData.getData("text/html"));
    if (!text) return;

    event.preventDefault();
    insertPlainText(text, true);
  };

  const handleCut = (event: React.ClipboardEvent<HTMLDivElement>) => {
    const selection = window.getSelection();
    const selectedText = selection?.toString() || "";
    if (!selectedText) {
      syncAfterNativeEdit();
      return;
    }

    event.preventDefault();
    event.clipboardData.setData("text/plain", selectedText);
    deleteSelectedEditorRange();
  };

  const syncAfterNativeEdit = () => {
    window.setTimeout(() => {
      saveSelection();
      syncValue(true);
    }, 0);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    const text =
      event.dataTransfer.getData("text/plain") ||
      plainTextFromClipboardHtml(event.dataTransfer.getData("text/html"));
    if (!text) return;

    event.preventDefault();
    setCaretFromPoint(event.clientX, event.clientY);
    insertPlainText(text, true);
  };

  const renderValue = (value: string, allowFormulaRendering = true) => {
    const editor = editorRef.current;
    if (!editor) return;

    formulaRefs.current = {};
    editor.innerHTML = "";

    if (!allowFormulaRendering) {
      editor.append(document.createTextNode(value));
      setActiveFormula(null);
      refreshFrameHeight();
      return;
    }

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
    renderValue(initialValueRef.current, mathRuntimeReady);
    lastValueRef.current = initialValueRef.current;
    pendingValueRef.current = initialValueRef.current;
    committedValueRef.current = initialValueRef.current;
  }, []);

  useEffect(() => {
    let cancelled = false;

    loadMathRuntime()
      .then(() => {
        if (!cancelled) setMathRuntimeStatus("ready");
      })
      .catch((error) => {
        console.error("MathLive failed to load", error);
        if (!cancelled) setMathRuntimeStatus("failed");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (mathRuntimeReady) {
      const editor = editorRef.current;
      const activeElement = document.activeElement;
      const activeNode = activeElement instanceof Node ? activeElement : null;
      const shouldRestoreCaret =
        !!editor &&
        !!activeElement &&
        (activeElement === editor || editor.contains(activeElement)) &&
        !closestFormulaChipFromNode(activeNode);
      const currentValue = editor ? serializeEditor(editor) : lastValueRef.current;
      const valueToRender = currentValue || lastValueRef.current;

      lastValueRef.current = valueToRender;
      pendingValueRef.current = valueToRender;
      persistDraftValue(valueToRender);

      if (shouldRestoreCaret) saveSelection();
      const selectionSnapshot = shouldRestoreCaret
        ? savedRangeRef.current?.cloneRange() ?? null
        : null;

      renderValue(valueToRender, true);

      if (shouldRestoreCaret) {
        window.setTimeout(() => {
          if (!restoreSavedSelection(selectionSnapshot)) focusEditorAtEnd();
          syncValue();
        }, 0);
      }
    }
  }, [mathRuntimeReady]);

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;

    const handleCompositionStart = () => {
      isComposingRef.current = true;
    };
    const handleCompositionEnd = () => {
      isComposingRef.current = false;
      saveSelection();
      syncValue();
    };

    editor.addEventListener("compositionstart", handleCompositionStart);
    editor.addEventListener("compositionend", handleCompositionEnd);

    return () => {
      editor.removeEventListener("compositionstart", handleCompositionStart);
      editor.removeEventListener("compositionend", handleCompositionEnd);
    };
  }, []);

  useEffect(() => {
    refreshFrameHeight();
  }, [openToolbarGroup, mathRuntimeStatus]);

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
        max-width: calc(100% - 8px);
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
        flex: 1 1 auto;
        width: auto;
        min-width: 72px;
        max-width: none;
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

      #mathlive-suggestion-popover[aria-hidden="true"],
      #mathlive-suggestion-popover[aria-hidden="true"] * {
        pointer-events: none !important;
        visibility: hidden !important;
      }
    `;
    document.head.appendChild(style);
    refreshFrameHeight();

    return () => {
      clearSyncTimer();
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
    <div
      style={{
        ...containerStyle,
        height: openToolbarGroup ? EXPANDED_CONTAINER_HEIGHT : COMPACT_CONTAINER_HEIGHT,
      }}
      onBlurCapture={handleContainerBlur}
      onMouseLeave={flushCurrentComposerValue}
      onPointerLeave={flushCurrentComposerValue}
    >
      <div style={groupToolbarStyle}>
        <button
          type="button"
          disabled={!mathRuntimeReady}
          onMouseDown={(event) => {
            saveSelection();
            event.preventDefault();
          }}
          onClick={() => insertFormulaBox()}
          style={{
            ...primaryButtonStyle,
            ...(!mathRuntimeReady ? disabledButtonStyle : {}),
          }}
        >
          插入公式框
        </button>

        {FORMULA_GROUPS.map((group) => (
          <button
            key={group.title}
            className={`formula-toolbar-button${
              openToolbarGroup === group.title ? " is-active" : ""
            }`}
            type="button"
            disabled={!mathRuntimeReady}
            onMouseDown={(event) => {
              saveSelection();
              event.preventDefault();
            }}
            onClick={(event) => {
              event.currentTarget.blur();
              setOpenToolbarGroup((current) =>
                current === group.title ? null : group.title
              );
            }}
            style={{
              ...summaryStyle,
              ...(openToolbarGroup === group.title ? summaryActiveStyle : {}),
              ...(!mathRuntimeReady ? disabledButtonStyle : {}),
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
          disabled={!mathRuntimeReady}
          onMouseDown={(event) => {
            saveSelection();
            event.preventDefault();
          }}
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
            ...(!mathRuntimeReady ? disabledButtonStyle : {}),
          }}
        >
          {COMMON_SYMBOLS_TITLE}
        </button>

        <div style={matrixPanelStyle}>
          <span style={{ fontSize: "12px", color: "#536075" }}>矩阵</span>
          <select
            value={matrixRows}
            disabled={!mathRuntimeReady}
            onChange={(event) => setMatrixRows(Number(event.target.value))}
            onMouseDown={(event) => {
              saveSelection();
              event.stopPropagation();
            }}
            style={{
              ...selectStyle,
              ...(!mathRuntimeReady ? disabledButtonStyle : {}),
            }}
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
            disabled={!mathRuntimeReady}
            onChange={(event) => setMatrixCols(Number(event.target.value))}
            onMouseDown={(event) => {
              saveSelection();
              event.stopPropagation();
            }}
            style={{
              ...selectStyle,
              ...(!mathRuntimeReady ? disabledButtonStyle : {}),
            }}
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
            disabled={!mathRuntimeReady}
            onMouseDown={(event) => {
              saveSelection();
              event.preventDefault();
            }}
            onClick={insertMatrix}
            style={{
              ...toolButtonStyle,
              ...(!mathRuntimeReady ? disabledButtonStyle : {}),
            }}
          >
            插入矩阵
          </button>
        </div>
      </div>

      {mathRuntimeStatus !== "ready" && (
        <div style={runtimeStatusStyle}>
          {mathRuntimeStatus === "loading"
            ? "公式工具正在后台加载，文字输入可先使用。"
            : "公式工具暂未加载成功，可直接输入文字或 LaTeX 代码。"}
        </div>
      )}

      {mathRuntimeReady && openToolbarGroup && activeToolbarItems.length > 0 && (
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
                <option value="" disabled hidden>
                  {item.label}
                </option>
                {CASES_SEGMENT_COUNTS.map((count) => (
                  <option key={count} value={count}>
                    {count}段
                  </option>
                ))}
              </select>
            ) : item.kind === "multi-integral" ? (
              <select
                key={`${openToolbarGroup}-${item.label}-multi-integral`}
                defaultValue=""
                aria-label="插入多重积分"
                onMouseDown={(event) => event.stopPropagation()}
                onChange={(event) => {
                  const integralCount = Number(event.currentTarget.value);
                  if (integralCount) {
                    insertLatexIntoFormula(createMultiIntegralLatex(integralCount));
                  }
                  event.currentTarget.value = "";
                }}
                style={formulaSelectStyle}
              >
                <option value="" disabled hidden>
                  {item.label}
                </option>
                {MULTI_INTEGRAL_COUNTS.map(({ count, label }) => (
                  <option key={count} value={count}>
                    {label}
                  </option>
                ))}
              </select>
            ) : (
              <button
                key={`${openToolbarGroup}-${item.label}-${item.latex}`}
                type="button"
                onMouseDown={(event) => {
                  saveSelection();
                  event.preventDefault();
                }}
                onClick={() => item.latex && insertLatexIntoFormula(item.latex)}
                style={symbolButtonStyle}
              >
                {item.label}
              </button>
            )
          )}
        </div>
      )}

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
        onCompositionStart={() => {
          isComposingRef.current = true;
        }}
        onCompositionEnd={() => {
          isComposingRef.current = false;
          saveSelection();
          syncValue();
        }}
        onInput={(event) => {
          if (isComposingRef.current) return;
          rememberNativeTextInput(event.nativeEvent as InputEvent);
          saveSelection();
          syncValue();
        }}
        onBlur={() => syncValue(true)}
        onKeyDown={handleEditorKeyDown}
        onBeforeInput={handleEditorBeforeInput}
        onPaste={handlePaste}
        onCut={handleCut}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        style={editorStyle}
      />
    </div>
  );
};

const plainTextFromClipboardHtml = (html: string) => {
  if (!html) return "";

  const container = document.createElement("div");
  container.innerHTML = html;
  container.querySelectorAll("script, style").forEach((node) => node.remove());
  return (container.textContent || "").replaceAll("\u00a0", " ").trim();
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

const setMathFieldLatex = (mathField: any, latex: string) => {
  configureMathField(mathField);
  mathField.focus();

  const applyLatex = () => {
    try {
      mathField.value = latex;
      if (typeof mathField.setValue === "function") {
        mathField.setValue(latex);
      }
    } catch {
      mathField.value = latex;
    }
    mathField.dispatchEvent(new Event("input", { bubbles: true }));
  };

  applyLatex();

  if (!getMathFieldLatex(mathField, "latex").trim()) {
    mathField.value = latex;
    applyLatex();
  }

  [80, 220].forEach((delay) => {
    window.setTimeout(() => {
      if (!mathField.isConnected) return;
      if (getMathFieldLatex(mathField, "latex").trim()) return;
      applyLatex();
    }, delay);
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
    [part='placeholder'],
    .ML__placeholder {
      display: inline-block !important;
      min-width: 0.9em !important;
      min-height: 0.9em !important;
      opacity: 1 !important;
      color: #1d4ed8 !important;
      background: rgba(37, 99, 235, 0.22) !important;
      border: 1px solid #2563eb !important;
      border-radius: 3px !important;
      box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.16) !important;
      box-sizing: border-box !important;
      padding: 0 0.14em !important;
      text-align: center !important;
      cursor: text !important;
      pointer-events: auto !important;
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

const groupToolbarStyle: React.CSSProperties = {
  display: "flex",
  gap: "5px",
  flexWrap: "wrap",
  alignItems: "center",
  marginBottom: "8px",
};

const matrixPanelStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "5px",
  flex: "0 0 auto",
  flexWrap: "nowrap",
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

const disabledButtonStyle: React.CSSProperties = {
  opacity: 0.55,
  cursor: "not-allowed",
};

const runtimeStatusStyle: React.CSSProperties = {
  margin: "-2px 0 7px",
  color: "#64748b",
  fontSize: "12px",
  lineHeight: 1.5,
};

const formulaPanelStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(84px, 1fr))",
  alignContent: "start",
  gap: "6px",
  padding: "8px",
  border: "1px solid #d9dee8",
  borderRadius: "8px",
  background: "#fbfdff",
  marginBottom: "8px",
  maxHeight: "126px",
  overflowY: "auto",
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
