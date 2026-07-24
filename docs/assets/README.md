# docs/assets

This directory holds diagram source files and exported images.

## Diagrams

Mermaid source diagrams are embedded inline in the documentation files:
- Platform topology → `SYSTEM_ARCHITECTURE.md`
- Authentication flow → `SYSTEM_ARCHITECTURE.md`
- Delivery state machine → `BUSINESS_WORKFLOW.md`
- Order lifecycle sequence → `BUSINESS_WORKFLOW.md`

## Generating Images from Mermaid Source

If you have @mermaid-js/mermaid-cli installed:
```bash
# Install
npm install -g @mermaid-js/mermaid-cli

# Export a diagram block from a markdown file
mmdc -i SYSTEM_ARCHITECTURE.md -o assets/system-overview.svg --theme dark

# Export individual .mmd files
mmdc -i assets/state-machine.mmd -o assets/state-machine.svg --theme default
```

Mermaid diagrams render natively in:
- GitHub (markdown preview)
- VS Code (with Mermaid extension)
- Most AI assistant interfaces
