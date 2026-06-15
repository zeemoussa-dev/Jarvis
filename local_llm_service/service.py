"""
Local LLM service — Llama 3.1 8B Instruct (4-bit, GPU)
Start:  venv\Scripts\python service.py
Port:   http://localhost:8001
"""

import os, torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import uvicorn

MODEL_ID = "meta-llama/Meta-Llama-3.1-8B-Instruct"
HF_TOKEN = os.getenv("HF_TOKEN")
DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"

SYSTEM_PROMPT = (
    "You are JARVIS, a sophisticated AI assistant. "
    "Be concise. Speak in plain sentences — no markdown, no asterisks, no bullet points. "
    "Address the user as sir."
)

app = FastAPI(title="Jarvis Local LLM")
tokenizer = None
model     = None


@app.on_event("startup")
def load_model():
    global tokenizer, model
    print(f"[LocalLLM] Loading {MODEL_ID} in 4-bit on {DEVICE}...")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, token=HF_TOKEN)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        token=HF_TOKEN,
        quantization_config=bnb,
        device_map="auto",
    )
    model.eval()
    print("[LocalLLM] Model ready.")


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    max_new_tokens: int = 256


@app.post("/chat")
def chat(req: ChatRequest):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend([m for m in req.history[-6:] if isinstance(m.get("content"), str)])
    messages.append({"role": "user", "content": req.message})

    input_ids = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)

    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=req.max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

    new_tokens = out[0][input_ids.shape[-1]:]
    response   = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    return {"response": response}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "device": DEVICE}


if __name__ == "__main__":
    uvicorn.run("service:app", host="0.0.0.0", port=8001, reload=False)
