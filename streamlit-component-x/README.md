# streamlit-component-x

Streamlit component that allows you to do X

## Installation instructions

```sh
pip install streamlit-component-x
```

## Usage instructions

```python
import streamlit as st

from streamlit_component_x import streamlit_component_x

value = streamlit_component_x()

st.write(value)
```

## Local development

1. Start Streamlit from the project root:

   ```sh
   streamlit run streamlit_component_x/example.py
   ```

2. In another terminal, run the Vite dev server from `streamlit_component_x/frontend`:

   ```sh
   npm install
   npm run start
   ```

### Important dev server notes

- The browser connects to the Vite dev server directly. Streamlit does **not** proxy this port, so the Vite port must be reachable from the client just like the Streamlit port.
- Vite listens on the value of `VITE_PORT` (default `3001`). This variable lives in `streamlit_component_x/frontend/.env`. Update that file whenever you need to change the port, and remember that Windows/WSL/Hyper-V or dev containers may silently remap addresses like `3001`.
- If a port is unavailable or blocked by a firewall/mobile connection, set `VITE_PORT=5173` (Vite's default) or any other open port inside the `.env` file before running `npm run start`, and ensure that port is reachable from your browser.
