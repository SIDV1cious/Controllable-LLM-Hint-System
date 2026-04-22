import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib"
import React, { useEffect, useRef, useState } from "react"
import { MathfieldElement } from "mathlive"

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "math-field": any;
    }
  }
}

const MyComponent = ({ args }: ComponentProps) => {
  const mfRef = useRef<any>(null)
  const [latex, setLatex] = useState(args.default_value || "")

  useEffect(() => {
    const mf = mfRef.current
    if (mf) {
      mf.value = args.default_value || ""
      
      // 罪魁祸首已修正：直接赋值，彻底抛弃 setOptions
      mf.mathVirtualKeyboardPolicy = "manual"

      const handleInput = (e: any) => {
        const newValue = e.target.value
        setLatex(newValue)
        Streamlit.setComponentValue(newValue)
      }

      mf.addEventListener("input", handleInput)
      return () => mf.removeEventListener("input", handleInput)
    }
  }, [args.default_value])

  useEffect(() => {
    Streamlit.setFrameHeight()
  })

  return (
    <div style={{ background: "white", padding: "15px", borderRadius: "8px", border: "1px solid #ccc", minHeight: "400px" }}>
      <div style={{ fontSize: "14px", color: "#666", marginBottom: "10px", fontWeight: "bold" }}>
        📐 MathLive 面板
      </div>
      <math-field 
        ref={mfRef} 
        style={{ fontSize: "24px", width: "100%", minHeight: "150px", outline: "none", border: "1px solid #ddd", borderRadius: "4px", padding: "10px" }}
      ></math-field>
      <div style={{ marginTop: "15px", fontSize: "12px", color: "#333" }}>
        <strong>✨ 对应的 LaTeX代码:</strong>
        <code style={{ marginLeft: "8px", color: "#4a90e2", wordBreak: "break-all" }}>{latex}</code>
      </div>
    </div>
  )
}

export default withStreamlitConnection(MyComponent)