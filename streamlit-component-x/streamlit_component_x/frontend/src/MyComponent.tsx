import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { useEffect, useRef, useState } from "react";
import "mathlive";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "math-field": any;
    }
  }

  interface Window {
    mathVirtualKeyboard?: {
      show: () => void;
      hide: () => void;
    };
  }
}

const MyComponent = ({ args }: ComponentProps) => {
  const mfRef = useRef<any>(null);
  const [latex, setLatex] = useState(args.default_value || "");

  useEffect(() => {
    const mf = mfRef.current;

    if (mf) {
      mf.value = args.default_value || "";
      mf.mathVirtualKeyboardPolicy = "manual";

      const handleInput = (e: any) => {
        const newValue = e.target.value;
        setLatex(newValue);
        Streamlit.setComponentValue(newValue);
      };

      const handleFocus = () => {
        window.mathVirtualKeyboard?.show();
      };

      mf.addEventListener("input", handleInput);
      mf.addEventListener("focusin", handleFocus);

      return () => {
        mf.removeEventListener("input", handleInput);
        mf.removeEventListener("focusin", handleFocus);
      };
    }
  }, [args.default_value]);

  useEffect(() => {
    const interval = setInterval(() => {
      Streamlit.setFrameHeight();
    }, 100);

    return () => clearInterval(interval);
  }, []);

  return (
    <div
      style={{
        background: "white",
        padding: "15px",
        borderRadius: "8px",
        border: "1px solid #ccc",
        minHeight: "450px",
      }}
    >
      <div
        style={{
          fontSize: "14px",
          color: "#666",
          marginBottom: "10px",
          fontWeight: "bold",
        }}
      >
        📐 MathLive 面板
      </div>

      <button
        onClick={() => window.mathVirtualKeyboard?.show()}
        style={{
          marginBottom: "10px",
          padding: "8px 12px",
          cursor: "pointer",
          border: "1px solid #ccc",
          borderRadius: "4px",
          background: "#f5f5f5",
        }}
      >
        打开公式键盘
      </button>

      <math-field
        ref={mfRef}
        style={{
          fontSize: "24px",
          width: "100%",
          minHeight: "150px",
          outline: "none",
          border: "1px solid #ddd",
          borderRadius: "4px",
          padding: "10px",
          display: "block",
        }}
      ></math-field>

      <div
        style={{
          marginTop: "15px",
          fontSize: "12px",
          color: "#333",
          wordBreak: "break-all",
        }}
      >
        <strong>✨ 对应的 LaTeX代码:</strong>
        <code
          style={{
            marginLeft: "8px",
            color: "#4a90e2",
          }}
        >
          {latex}
        </code>
      </div>
    </div>
  );
};

export default withStreamlitConnection(MyComponent);