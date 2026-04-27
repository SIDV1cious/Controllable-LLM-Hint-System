import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { useEffect, useRef, useState } from "react";

const FRAME_HEIGHT = 430;
const MAX_MATRIX_SIZE = 10;

const INSERT_TEMPLATES = [
  { label: "绝对值", latex: "|#?|" },
  { label: "n次根", latex: "\\sqrt[#?]{#?}" },
  { label: "对数", latex: "\\log_{#?}{#?}" },
  { label: "导数", latex: "\\dfrac{\\mathrm{d}}{\\mathrm{d}x}#?\\bigm|_{x=#?}" },
  { label: "n阶导", latex: "\\dfrac{\\mathrm{d}^#?}{\\mathrm{d}x^#?}#?\\bigm|_{x=#?}" },
  { label: "积分", latex: "\\int_#?^#?#?\\,\\mathrm{d}#?" },
  { label: "求和", latex: "\\sum_#?^#?#?" },
  { label: "乘积", latex: "\\prod_#?^#?#?" },
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
  { label: "空格", latex: "\\;" },
  { label: "换行", latex: "\n" },
];

const MyComponent = ({ args }: ComponentProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState(args.default_value || "");
  const [matrixRows, setMatrixRows] = useState(2);
  const [matrixCols, setMatrixCols] = useState(2);

  const refreshFrameHeight = () => {
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 0);
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 80);
  };

  const updateValue = (nextValue: string) => {
    setValue(nextValue);
    Streamlit.setComponentValue(nextValue);
  };

  const insertText = (snippet: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart ?? value.length;
    const end = textarea.selectionEnd ?? value.length;
    const nextValue = value.slice(0, start) + snippet + value.slice(end);
    updateValue(nextValue);

    const cursor = start + snippet.length;
    window.setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(cursor, cursor);
    }, 0);
  };

  const insertMatrix = () => {
    const rows = Math.min(Math.max(matrixRows, 1), MAX_MATRIX_SIZE);
    const cols = Math.min(Math.max(matrixCols, 1), MAX_MATRIX_SIZE);
    const body = Array.from({ length: rows }, () =>
      Array.from({ length: cols }, () => "#?").join(" & ")
    ).join(" \\\\\n");
    insertText(`\\begin{pmatrix}\n${body}\n\\end{pmatrix}`);
  };

  useEffect(() => {
    const nextValue = args.default_value || "";
    if (document.activeElement !== textareaRef.current && nextValue !== value) {
      setValue(nextValue);
    }
  }, [args.default_value]);

  useEffect(() => {
    refreshFrameHeight();
  }, []);

  return (
    <div style={containerStyle}>
      <div style={topRowStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
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
            插入
          </button>
        </div>
      </div>

      <div style={toolbarStyle}>
        {INSERT_TEMPLATES.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => insertText(item.latex)}
            style={toolButtonStyle}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div style={toolbarStyle}>
        {QUICK_SYMBOLS.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => insertText(item.latex)}
            style={toolButtonStyle}
          >
            {item.label}
          </button>
        ))}
      </div>

      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => updateValue(e.target.value)}
        placeholder="请输入智能辅导问题，可直接输入文字，也可使用上方按钮插入 LaTeX 片段。"
        style={textareaStyle}
      />
    </div>
  );
};

const containerStyle: React.CSSProperties = {
  background: "white",
  border: "1px solid #d9dee8",
  borderRadius: "6px",
  padding: "10px",
  height: "380px",
  boxSizing: "border-box",
  overflow: "hidden",
};

const topRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  gap: "8px",
  marginBottom: "8px",
  flexWrap: "wrap",
};

const toolbarStyle: React.CSSProperties = {
  display: "flex",
  gap: "6px",
  flexWrap: "wrap",
  marginBottom: "8px",
};

const toolButtonStyle: React.CSSProperties = {
  border: "1px solid #cfd6e3",
  background: "#f8fafc",
  color: "#263244",
  borderRadius: "6px",
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
  height: "28px",
};

const textareaStyle: React.CSSProperties = {
  width: "100%",
  height: "205px",
  boxSizing: "border-box",
  resize: "none",
  border: "1px solid #d9dee8",
  borderRadius: "6px",
  padding: "12px",
  outline: "none",
  background: "white",
  color: "#111827",
  fontSize: "18px",
  lineHeight: 1.6,
  fontFamily:
    "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

export default withStreamlitConnection(MyComponent);
