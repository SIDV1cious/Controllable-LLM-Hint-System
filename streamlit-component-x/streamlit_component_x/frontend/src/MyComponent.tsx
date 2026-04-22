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

const MyComponent = ({ args }: ComponentProps) => {
  const mfRef = useRef<any>(null);
  const [latex, setLatex] = useState(args.default_value || "");

  useEffect(() => {
    const mf = mfRef.current;
    if (mf) {
      mf.value = args.default_value || "";
      mf.mathVirtualKeyboardPolicy = "manual";
      mf.virtualKeyboardMode = "manual";

      const handleInput = (e: any) => {
        const newValue = e.target.value;
        setLatex(newValue);
        Streamlit.setComponentValue(newValue);
      };

      mf.addEventListener("input", handleInput);

      return () => {
        mf.removeEventListener("input", handleInput);
      };
    }
  }, [args.default_value]);

  useEffect(() => {
    const interval = setInterval(() => {
      Streamlit.setFrameHeight();
    }, 200);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const style = document.createElement("style");
    style.innerHTML = `
      math-virtual-keyboard {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100vw !important;
        z-index: 999999 !important;
      }
    `;
    document.head.appendChild(style);

    return () => {
      document.head.removeChild(style);
    };
  }, []);

  const toggleKeyboard = () => {
    const vk = (window as any).mathVirtualKeyboard;
    if (vk) {
      vk.visible = !vk.visible;
    }
  };

  return (
    <div
      style={{
        background: "white",
        padding: "15px",
        borderRadius: "8px",
        border: "1px solid #ccc",
        minHeight: "450px",
        position: "relative",
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
        onClick={toggleKeyboard}
        style={{
          position: "absolute",
          top: "12px",
          right: "12px",
          zIndex: 9999,
          padding: "6px 12px",
          border: "none",
          borderRadius: "6px",
          background: "#4a90e2",
          color: "white",
          cursor: "pointer",
        }}
      >
        ⌨️
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
        <code style={{ marginLeft: "8px", color: "#4a90e2" }}>{latex}</code>
      </div>
    </div>
  );
};

export default withStreamlitConnection(MyComponent);