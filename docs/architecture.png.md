# Cómo generar architecture.png

El diagrama Mermaid está en `orchestration/architecture.md`.

## Pasos para exportar el PNG

1. Abre https://mermaid.live
2. Copia el bloque de código Mermaid del archivo `orchestration/architecture.md` (el primero, "Full Pipeline Architecture")
3. Click en **Export → PNG**
4. Guarda el archivo como:
   - `docs/architecture.png` (requerido por la estructura del repo)
   - `orchestration/architecture.png` (requerido por el rubric del Role 4)

## Alternativa con CLI (si tienes Node.js)

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i orchestration/architecture.md -o docs/architecture.png --theme dark
cp docs/architecture.png orchestration/architecture.png
```
