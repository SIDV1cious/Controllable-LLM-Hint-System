import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { useEffect, useMemo, useRef, useState } from "react";
import "mathlive";
import "mathlive/static.css";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "math-field": any;
    }
  }
}

type TextBlock = {
  id: string;
  type: "text";
  text: string;
};

type FormulaBlock = {
  id: string;
  type: "formula";
  latex: string;
};

type ComposerBlock = TextBlock | FormulaBlock;

const FRAME_HEIGHT = 500;
const MAX_MATRIX_SIZE = 10;

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

const blockToValue = (block: ComposerBlock) => {
  if (block.type === "text") return block.text;
  const latex = block.latex.trim();
  return latex ? `$${latex}$` : "";
};

const serializeBlocks = (blocks: ComposerBlock[]) =>
  blocks.map(blockToValue).join("");

const mergeAdjacentTextBlocks = (blocks: ComposerBlock[]) => {
  const merged: ComposerBlock[] = [];

  blocks.forEach((block) => {
    const last = merged[merged.length - 1];
    if (last?.type === "text" && block.type === "text") {
      merged[merged.length - 1] = {
        ...last,
        text: `${last.text}${block.text}`,
      };
    } else {
      merged.push(block);
    }
  });

  return merged;
};

const parseInitialBlocks = (value: string, createId: () => string): ComposerBlock[] => {
  if (!value) return [{ id: createId(), type: "text", text: "" }];

  const blocks: ComposerBlock[] = [];
  const formulaPattern = /\$([^$]+)\$/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = formulaPattern.exec(value)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({
        id: createId(),
        type: "text",
        text: value.slice(lastIndex, match.index),
      });
    }

    blocks.push({
      id: createId(),
      type: "formula",
      latex: match[1],
    });

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < value.length) {
    blocks.push({
      id: createId(),
      type: "text",
      text: value.slice(lastIndex),
    });
  }

  return blocks.length ? blocks : [{ id: createId(), type: "text", text: value }];
};

const MyComponent = ({ args }: ComponentProps) => {
  const idCounterRef = useRef(0);
  const formulaRefs = useRef<Record<string, any>>({});
  const textRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  const textSelectionsRef = useRef<Record<string, { start: number; end: number }>>({});
  const activeBlockIdRef = useRef<string | null>(null);
  const pendingFormulaInsertRef = useRef<{ id: string; latex: string } | null>(null);
  const lastSerializedRef = useRef(args.default_value || "");

  const createId = () => `block_${Date.now()}_${idCounterRef.current++}`;

  const [blocks, setBlocks] = useState<ComposerBlock[]>(() =>
    parseInitialBlocks(args.default_value || "", createId)
  );
  const [activeBlockId, setActiveBlockId] = useState<string | null>(null);
  const [matrixRows, setMatrixRows] = useState(2);
  const [matrixCols, setMatrixCols] = useState(2);

  const activeFormulaId = useMemo(() => {
    const active = blocks.find((block) => block.id === activeBlockId);
    return active?.type === "formula" ? active.id : null;
  }, [activeBlockId, blocks]);

  const refreshFrameHeight = () => {
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 0);
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 80);
  };

  const setActiveBlock = (id: string) => {
    activeBlockIdRef.current = id;
    setActiveBlockId(id);
  };

  const syncBlocks = (nextBlocks: ComposerBlock[]) => {
    const safeBlocks = nextBlocks.length
      ? nextBlocks
      : [{ id: createId(), type: "text" as const, text: "" }];
    const serialized = serializeBlocks(safeBlocks);
    lastSerializedRef.current = serialized;
    setBlocks(safeBlocks);
    Streamlit.setComponentValue(serialized);
  };

  const updateTextSelection = (id: string) => {
    const textarea = textRefs.current[id];
    if (!textarea) return;

    textSelectionsRef.current[id] = {
      start: textarea.selectionStart ?? textarea.value.length,
      end: textarea.selectionEnd ?? textarea.value.length,
    };
  };

  const updateTextBlock = (id: string, text: string) => {
    const nextBlocks = blocks.map((block) =>
      block.id === id && block.type === "text" ? { ...block, text } : block
    );
    syncBlocks(nextBlocks);
  };

  const updateFormulaBlock = (id: string, latex: string) => {
    const nextBlocks = blocks.map((block) =>
      block.id === id && block.type === "formula" ? { ...block, latex } : block
    );
    syncBlocks(nextBlocks);
  };

  const insertFormulaBox = (initialLatex = "") => {
    const newFormula: FormulaBlock = { id: createId(), type: "formula", latex: "" };
    const newText: TextBlock = { id: createId(), type: "text", text: "" };
    const activeId = activeBlockIdRef.current;
    const activeIndex = blocks.findIndex((block) => block.id === activeId);
    let nextBlocks: ComposerBlock[];

    if (activeIndex >= 0 && blocks[activeIndex].type === "text") {
      const activeText = blocks[activeIndex] as TextBlock;
      const selection = textSelectionsRef.current[activeText.id] ?? {
        start: activeText.text.length,
        end: activeText.text.length,
      };
      const beforeText = activeText.text.slice(0, selection.start);
      const afterText = activeText.text.slice(selection.end);
      const replacements: ComposerBlock[] = [];

      if (beforeText) {
        replacements.push({ ...activeText, text: beforeText });
      }

      replacements.push(newFormula);
      replacements.push({ ...newText, text: afterText });

      nextBlocks = [
        ...blocks.slice(0, activeIndex),
        ...replacements,
        ...blocks.slice(activeIndex + 1),
      ];
    } else if (activeIndex >= 0) {
      nextBlocks = [
        ...blocks.slice(0, activeIndex + 1),
        newFormula,
        newText,
        ...blocks.slice(activeIndex + 1),
      ];
    } else {
      nextBlocks = [...blocks, newFormula, newText];
    }

    pendingFormulaInsertRef.current = initialLatex
      ? { id: newFormula.id, latex: initialLatex }
      : null;
    setActiveBlock(newFormula.id);
    syncBlocks(nextBlocks);

    window.setTimeout(() => {
      const mathField = formulaRefs.current[newFormula.id];
      mathField?.focus();
    }, 0);
  };

  const insertLatexIntoFormula = (latex: string) => {
    const targetId = activeFormulaId;

    if (!targetId) {
      insertFormulaBox(latex);
      return;
    }

    const mathField = formulaRefs.current[targetId];
    if (!mathField) {
      pendingFormulaInsertRef.current = { id: targetId, latex };
      return;
    }

    mathField.focus();
    mathField.insert(latex, {
      mode: "math",
      format: "latex",
      selectionMode: "placeholder",
      focus: true,
    });
    updateFormulaBlock(targetId, mathField.value || "");
  };

  const insertMatrix = () => {
    const rows = Math.min(Math.max(matrixRows, 1), MAX_MATRIX_SIZE);
    const cols = Math.min(Math.max(matrixCols, 1), MAX_MATRIX_SIZE);
    const body = Array.from({ length: rows }, () =>
      Array.from({ length: cols }, () => "#?").join(" & ")
    ).join(" \\\\ ");

    insertLatexIntoFormula(`\\begin{pmatrix}${body}\\end{pmatrix}`);
  };

  const removeFormulaBlock = (id: string) => {
    const index = blocks.findIndex((block) => block.id === id);
    if (index < 0) return;

    const nextBlocks = mergeAdjacentTextBlocks(
      blocks.filter((block) => block.id !== id)
    );
    if (!nextBlocks.some((block) => block.type === "text")) {
      nextBlocks.push({ id: createId(), type: "text", text: "" });
    }

    const nextTextBlock = (nextBlocks
      .slice(Math.max(index - 1, 0))
      .find((block) => block.type === "text") ?? nextBlocks.find(
      (block) => block.type === "text"
    )) as TextBlock | undefined;

    syncBlocks(nextBlocks);

    if (nextTextBlock) {
      setActiveBlock(nextTextBlock.id);
      window.setTimeout(() => textRefs.current[nextTextBlock.id]?.focus(), 0);
    }
  };

  useEffect(() => {
    const nextValue = args.default_value || "";
    if (nextValue !== lastSerializedRef.current) {
      lastSerializedRef.current = nextValue;
      setBlocks(parseInitialBlocks(nextValue, createId));
    }
  }, [args.default_value]);

  useEffect(() => {
    const pending = pendingFormulaInsertRef.current;
    if (!pending) return;

    const mathField = formulaRefs.current[pending.id];
    if (!mathField) return;

    pendingFormulaInsertRef.current = null;
    mathField.focus();
    mathField.insert(pending.latex, {
      mode: "math",
      format: "latex",
      selectionMode: "placeholder",
      focus: true,
    });
    updateFormulaBlock(pending.id, mathField.value || "");
  }, [blocks]);

  useEffect(() => {
    const style = document.createElement("style");
    style.innerHTML = `
      html, body {
        margin: 0;
        padding: 0;
        overflow: hidden !important;
        background: white;
      }

      math-field::part(menu-toggle),
      math-field::part(virtual-keyboard-toggle) {
        display: none;
      }
    `;
    document.head.appendChild(style);
    refreshFrameHeight();

    return () => {
      document.head.removeChild(style);
    };
  }, []);

  useEffect(() => {
    refreshFrameHeight();
  }, [blocks.length]);

  return (
    <div style={containerStyle}>
      <div style={toolbarHeaderStyle}>
        <button
          type="button"
          onClick={() => insertFormulaBox()}
          style={primaryButtonStyle}
        >
          插入公式框
        </button>

        <div style={matrixPanelStyle}>
          <span style={{ fontSize: "12px", color: "#536075" }}>矩阵</span>
          <select
            value={matrixRows}
            onChange={(e) => setMatrixRows(Number(e.target.value))}
            style={selectStyle}
          >
            {Array.from({ length: MAX_MATRIX_SIZE }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}行
              </option>
            ))}
          </select>
          <select
            value={matrixCols}
            onChange={(e) => setMatrixCols(Number(e.target.value))}
            style={selectStyle}
          >
            {Array.from({ length: MAX_MATRIX_SIZE }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}列
              </option>
            ))}
          </select>
          <button type="button" onClick={insertMatrix} style={toolButtonStyle}>
            插入矩阵
          </button>
        </div>
      </div>

      <div style={toolbarStyle}>
        {INSERT_TEMPLATES.map((item) => (
          <button
            key={item.label}
            type="button"
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
            onClick={() => insertLatexIntoFormula(item.latex)}
            style={toolButtonStyle}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div style={editorSurfaceStyle}>
        {blocks.map((block) =>
          block.type === "text" ? (
            <textarea
              key={block.id}
              ref={(node) => {
                textRefs.current[block.id] = node;
              }}
              value={block.text}
              onFocus={() => setActiveBlock(block.id)}
              onClick={() => updateTextSelection(block.id)}
              onKeyUp={() => updateTextSelection(block.id)}
              onSelect={() => updateTextSelection(block.id)}
              onChange={(e) => updateTextBlock(block.id, e.target.value)}
              placeholder="在这里输入文字。需要公式时，点击上方“插入公式框”。"
              style={textBlockStyle}
            />
          ) : (
            <FormulaBox
              key={block.id}
              id={block.id}
              latex={block.latex}
              active={block.id === activeFormulaId}
              registerRef={(id, ref) => {
                if (ref) formulaRefs.current[id] = ref;
                else delete formulaRefs.current[id];
              }}
              onFocus={() => setActiveBlock(block.id)}
              onChange={(latex) => updateFormulaBlock(block.id, latex)}
              onRemove={() => removeFormulaBlock(block.id)}
            />
          )
        )}
      </div>
    </div>
  );
};

const FormulaBox = ({
  id,
  latex,
  active,
  registerRef,
  onFocus,
  onChange,
  onRemove,
}: {
  id: string;
  latex: string;
  active: boolean;
  registerRef: (id: string, ref: any | null) => void;
  onFocus: () => void;
  onChange: (latex: string) => void;
  onRemove: () => void;
}) => {
  const mathFieldRef = useRef<any>(null);
  const onChangeRef = useRef(onChange);
  const onFocusRef = useRef(onFocus);

  useEffect(() => {
    onChangeRef.current = onChange;
    onFocusRef.current = onFocus;
  }, [onChange, onFocus]);

  useEffect(() => {
    const mathField = mathFieldRef.current;
    if (!mathField) return;

    registerRef(id, mathField);
    mathField.menuItems = [];
    mathField.defaultMode = "math";
    mathField.mathVirtualKeyboardPolicy = "manual";
    mathField.smartFence = true;
    mathField.maxMatrixCols = MAX_MATRIX_SIZE;

    const handleInput = () => onChangeRef.current(mathField.value || "");
    const handleFocus = () => onFocusRef.current();

    mathField.addEventListener("input", handleInput);
    mathField.addEventListener("focus", handleFocus);

    return () => {
      mathField.removeEventListener("input", handleInput);
      mathField.removeEventListener("focus", handleFocus);
      registerRef(id, null);
    };
  }, [id]);

  useEffect(() => {
    const mathField = mathFieldRef.current;
    if (mathField && document.activeElement !== mathField && mathField.value !== latex) {
      mathField.value = latex;
    }
  }, [latex]);

  return (
    <div
      style={{
        ...formulaBlockStyle,
        borderColor: active ? "#2563eb" : "#c7d2fe",
        boxShadow: active ? "0 0 0 2px rgba(37, 99, 235, 0.12)" : "none",
      }}
    >
      <div style={formulaLabelStyle}>公式框</div>
      <math-field ref={mathFieldRef} style={mathFieldStyle}></math-field>
      <button type="button" onClick={onRemove} style={removeButtonStyle}>
        删除
      </button>
    </div>
  );
};

const containerStyle: React.CSSProperties = {
  background: "white",
  border: "1px solid #d9dee8",
  borderRadius: "8px",
  padding: "10px",
  height: "455px",
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

const toolbarStyle: React.CSSProperties = {
  display: "flex",
  gap: "6px",
  flexWrap: "wrap",
  marginBottom: "8px",
};

const editorSurfaceStyle: React.CSSProperties = {
  height: "300px",
  boxSizing: "border-box",
  border: "1px solid #d9dee8",
  borderRadius: "8px",
  padding: "8px",
  background: "#ffffff",
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

const removeButtonStyle: React.CSSProperties = {
  border: "1px solid #fecaca",
  background: "#fff7f7",
  color: "#b91c1c",
  borderRadius: "6px",
  padding: "4px 8px",
  fontSize: "12px",
  cursor: "pointer",
  whiteSpace: "nowrap",
};

const selectStyle: React.CSSProperties = {
  border: "1px solid #cfd6e3",
  borderRadius: "6px",
  background: "white",
  color: "#263244",
  fontSize: "12px",
  height: "30px",
};

const textBlockStyle: React.CSSProperties = {
  width: "100%",
  minHeight: "70px",
  boxSizing: "border-box",
  resize: "vertical",
  border: "none",
  borderRadius: "6px",
  padding: "10px",
  outline: "none",
  background: "transparent",
  color: "#111827",
  fontSize: "18px",
  lineHeight: 1.65,
  fontFamily:
    "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

const formulaBlockStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "64px minmax(0, 1fr) auto",
  alignItems: "center",
  gap: "8px",
  margin: "6px 0",
  padding: "8px",
  border: "1px solid #c7d2fe",
  borderRadius: "8px",
  background: "#f8fbff",
};

const formulaLabelStyle: React.CSSProperties = {
  color: "#2563eb",
  fontSize: "12px",
  fontWeight: 700,
  whiteSpace: "nowrap",
};

const mathFieldStyle: React.CSSProperties = {
  width: "100%",
  minHeight: "42px",
  display: "block",
  boxSizing: "border-box",
  fontSize: "20px",
  border: "1px solid #cfd6e3",
  borderRadius: "6px",
  padding: "8px",
  outline: "none",
  background: "white",
  color: "#111827",
};

export default withStreamlitConnection(MyComponent);
