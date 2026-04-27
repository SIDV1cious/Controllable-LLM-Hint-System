import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { useEffect, useRef, useState } from "react";
import { initVirtualKeyboardInCurrentBrowsingContext } from "mathlive";
import "mathlive";
import "mathlive/static.css";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "math-field": any;
    }
  }
}

const FRAME_HEIGHT = 560;
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
  { label: "换行", latex: "\\\\" },
];

const MyComponent = ({ args }: ComponentProps) => {
  const mfRef = useRef<any>(null);
  const vkRef = useRef<any>(null);
  const syncTimerRef = useRef<number | null>(null);
  const isComposingRef = useRef(false);
  const [matrixRows, setMatrixRows] = useState(2);
  const [matrixCols, setMatrixCols] = useState(2);

  const refreshFrameHeight = () => {
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 0);
    window.setTimeout(() => Streamlit.setFrameHeight(FRAME_HEIGHT), 80);
  };

  const syncValue = () => {
    const mf = mfRef.current;
    if (mf) {
      Streamlit.setComponentValue(mf.value || "");
    }
  };

  const scheduleSyncValue = () => {
    if (isComposingRef.current) return;
    if (syncTimerRef.current !== null) {
      window.clearTimeout(syncTimerRef.current);
    }
    syncTimerRef.current = window.setTimeout(() => {
      syncTimerRef.current = null;
      syncValue();
    }, 120);
  };

  const focusMathField = () => {
    window.setTimeout(() => mfRef.current?.focus(), 0);
  };

  const insertLatex = (latex: string) => {
    const mf = mfRef.current;
    if (!mf) return;
    mf.insert(latex, {
      mode: "math",
      format: "latex",
      selectionMode: "placeholder",
      focus: true,
    });
    syncValue();
    focusMathField();
  };

  const insertMatrix = () => {
    const rows = Math.min(Math.max(matrixRows, 1), MAX_MATRIX_SIZE);
    const cols = Math.min(Math.max(matrixCols, 1), MAX_MATRIX_SIZE);
    const body = Array.from({ length: rows }, () =>
      Array.from({ length: cols }, () => "").join(" & ")
    ).join(" \\\\ ");
    insertLatex(`\\begin{pmatrix}${body}\\end{pmatrix}`);
  };

  useEffect(() => {
    vkRef.current = initVirtualKeyboardInCurrentBrowsingContext();
    refreshFrameHeight();
  }, []);

  useEffect(() => {
    const mf = mfRef.current;
    const vk = vkRef.current;

    if (!mf) return;

    const nextValue = args.default_value || "";
    if (document.activeElement !== mf && nextValue !== mf.value) {
      mf.value = nextValue;
      Streamlit.setComponentValue(nextValue);
    }

    mf.mathVirtualKeyboardPolicy = "sandboxed";
    mf.defaultMode = "text";
    mf.menuItems = [];
    mf.maxMatrixCols = MAX_MATRIX_SIZE;
    mf.mathModeSpace = "\\;";
    mf.smartFence = true;
    mf.smartMode = false;
    mf.popoverPolicy = "off";
    mf.environmentPopoverPolicy = "off";

    const handleInput = (e: any) => {
      scheduleSyncValue();
    };

    const handleCompositionStart = () => {
      isComposingRef.current = true;
    };

    const handleCompositionEnd = () => {
      isComposingRef.current = false;
      syncValue();
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        mf.insert("\\\\", { mode: "math", format: "latex", selectionMode: "after" });
        syncValue();
      }
    };

    const handleGeometryChange = () => {
      refreshFrameHeight();
    };

    mf.addEventListener("input", handleInput);
    mf.addEventListener("compositionstart", handleCompositionStart);
    mf.addEventListener("compositionend", handleCompositionEnd);
    mf.addEventListener("keydown", handleKeyDown);
    mf.addEventListener("blur", syncValue);

    if (vk) {
      vk.addEventListener("geometrychange", handleGeometryChange);
    }

    refreshFrameHeight();

    return () => {
      if (syncTimerRef.current !== null) {
        window.clearTimeout(syncTimerRef.current);
        syncTimerRef.current = null;
      }
      mf.removeEventListener("input", handleInput);
      mf.removeEventListener("compositionstart", handleCompositionStart);
      mf.removeEventListener("compositionend", handleCompositionEnd);
      mf.removeEventListener("keydown", handleKeyDown);
      mf.removeEventListener("blur", syncValue);
      if (vk) {
        vk.removeEventListener("geometrychange", handleGeometryChange);
      }
    };
  }, [args.default_value]);

  useEffect(() => {
    const style = document.createElement("style");
    style.innerHTML = `
      html, body {
        margin: 0;
        padding: 0;
        overflow: hidden !important;
        background: white;
      }

      #root {
        height: 100%;
      }

      math-virtual-keyboard {
        position: fixed !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        width: 100% !important;
        z-index: 2147483647 !important;
      }

      math-field::part(menu-toggle) {
        display: none;
      }

      math-field {
        --selection-color: #111827;
        --selection-background-color: rgba(17, 24, 39, 0.10);
        color: #111827;
      }
    `;
    document.head.appendChild(style);

    return () => {
      document.head.removeChild(style);
    };
  }, []);

  return (
    <div
      style={{
        background: "white",
        border: "1px solid #d9dee8",
        borderRadius: "6px",
        padding: "10px",
        height: "500px",
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px",
          marginBottom: "8px",
          flexWrap: "wrap",
        }}
      >
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
            onClick={() => insertLatex(item.latex)}
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
            onClick={() => insertLatex(item.latex)}
            style={toolButtonStyle}
          >
            {item.label}
          </button>
        ))}
      </div>

      <math-field
        ref={mfRef}
        style={{
          width: "100%",
          height: "220px",
          minHeight: "220px",
          display: "block",
          boxSizing: "border-box",
          fontSize: "24px",
          border: "1px solid #d9dee8",
          borderRadius: "6px",
          padding: "12px",
          outline: "none",
          overflow: "auto",
          background: "white",
          color: "#111827",
        }}
      ></math-field>
    </div>
  );
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

export default withStreamlitConnection(MyComponent);
