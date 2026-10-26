# StudioKit SDK Conversion Plan

## Overview
Convert studiokit from OpenRouter (OpenAI SDK) back to native Anthropic Claude SDK to achieve uniformity with renderkit and resolvekit.

## Current State
- **LLM bridge:** `core/llm.py` uses `from openai import OpenAI` pointing to OpenRouter (76 LoC)
- **Schema format:** Already using Anthropic input_schema pattern (comments at `core/llm.py:3-6` note original Anthropic origin)
- **Tools:** 23 tools in `core/tools.py:489`, with JSON schema in Anthropic format
- **Architecture:** Companion app, MCP server, FL device script, agent loop

## Phase 1: SDK Swap
1. Replace `core/llm.py` to use native `anthropic.Anthropic()`
   - Drop OpenAI SDK dependency
   - `model = "claude-opus-4-8"` (or cursor tier matching renderkit/resolvekit)
   - Keep tool-use loop intact (invoke → tool dispatch → resume)
2. Update `requirements.txt`: remove `openai`, add `anthropic`
3. Update `agent.py` call sites if needed (verify import path)

## Phase 2: Verification
- [ ] Run `agent.py` in standalone mode with test MIDI scenario
- [ ] Verify tool dispatch through `core/tools.py:dispatch()` on a sample query
- [ ] Test companion app bridging via UDP (FL→9500, us→9501)
- [ ] Spot-check MIDI generation pipeline (mido/loopMIDI)

## Phase 3: Cleanup
- [ ] Remove any stale OpenAI references
- [ ] Update `.env.example` to only require `ANTHROPIC_API_KEY`
- [ ] Verify StudioKit.exe rebuild (if applicable) or note deprecation

## Success Criteria
- studiokit uses `import anthropic` + `anthropic.Anthropic()` ✓
- All 23 tools invoke via Anthropic tool-use protocol ✓
- Companion + FL script still communicate correctly ✓
